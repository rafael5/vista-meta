#!/usr/bin/env bash
# Post-build smoke tests — the one test artifact per ADR-027 (spec §13, as-built
# record docs/historical/vista-meta-spec-v0.4.md). Run via `make smoke` after
# `make build && make run`, after restoring a snapshot, or after a YDB/VEHU bump.
#
# Twelve checks, S-01…S-12: container up → engine responds → data plane intact
# → services listening → FileMan + VEHU data alive. Plain bash, no framework.
# Exit 0 = all pass (skips allowed), exit 1 = any failure; failures print the
# failing command's output for diagnosis.

set -u

CONTAINER="${CONTAINER:-vista-vehu}"

PASS=0 FAIL=0 WARN=0 SKIP=0

# report <id> <label> <status> [detail...]
report() {
    local id="$1" label="$2" status="$3"; shift 3
    local dots
    dots=$(printf '%.*s' $((40 - ${#label})) "............................................")
    echo "[smoke] $id $label $dots $status"
    if [ "$status" = FAIL ] && [ $# -gt 0 ]; then
        printf '        %s\n' "$@"
    fi
    case "$status" in PASS) PASS=$((PASS+1));; FAIL) FAIL=$((FAIL+1));; WARN) WARN=$((WARN+1));; SKIP) SKIP=$((SKIP+1));; esac
}

# check <id> <label> <cmd...>  — pass iff the command exits 0
check() {
    local id="$1" label="$2"; shift 2
    local out
    if out=$("$@" 2>&1); then
        report "$id" "$label" PASS
    else
        report "$id" "$label" FAIL "$out"
    fi
}

# warn_check — same, but a failure is non-gating (WARN): for baked services
# with no consumers (ADR-051 — rocto, ydbgui). Still probed so a revival or
# an intentional adoption shows up here first.
warn_check() {
    local id="$1" label="$2"; shift 2
    if "$@" >/dev/null 2>&1; then
        report "$id" "$label" PASS
    else
        report "$id" "$label" WARN
    fi
}

# in_m <M-code> — run one line of M under the vehu login env, print its output
in_m() {
    docker exec -u vehu "$CONTAINER" bash -lc \
        "\"\$ydb_dist\"/mumps -run %XCMD '$1'" 2>&1
}

# ── S-01 gates everything: no container, no point probing further ────
if [ "$(docker inspect -f '{{.State.Running}}' "$CONTAINER" 2>/dev/null)" = "true" ]; then
    report S-01 "container running" PASS
else
    report S-01 "container running" FAIL "container '$CONTAINER' not running — make run"
    echo "[smoke] 0/12 passed, 1 failed, 11 not run (container down)"
    exit 1
fi

# ── S-02 SSH connectivity (loopback — local-only stack, ADR-050) ─────
check S-02 "SSH connectivity" \
    ssh -p 2222 -o BatchMode=yes -o ConnectTimeout=5 \
        -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
        vehu@127.0.0.1 echo ok

# ── S-03 YottaDB responds ─────────────────────────────────────────────
# ($ZV reports the upstream GT.M compatibility string; $ZYRELEASE names YottaDB.)
out=$(in_m 'W $ZYRELEASE')
case "$out" in
    *YottaDB*) report S-03 "YottaDB responds" PASS ;;
    *)         report S-03 "YottaDB responds" FAIL "$out" ;;
esac

# ── S-04 global directory exists ──────────────────────────────────────
check S-04 "global directory exists" \
    docker exec "$CONTAINER" sh -c 'stat /home/vehu/g/*.dat >/dev/null'

# ── S-05 routine farm populated ───────────────────────────────────────
check S-05 "routine farm populated" \
    docker exec "$CONTAINER" test -s /opt/VistA-M/r/MANIFEST.tsv

# ── S-06 routine compilation ──────────────────────────────────────────
check S-06 "compiled objects present" \
    docker exec "$CONTAINER" sh -c 'ls /opt/VistA-M/o/*.o >/dev/null 2>&1'

# ── S-07..S-10 service ports (probed inside the container) ───────────
port_check() { # <id> <label> <port>
    check "$1" "$2" docker exec "$CONTAINER" \
        timeout 2 bash -c "echo >/dev/tcp/127.0.0.1/$3"
}
# S-07 is protocol-level, not just a port probe: xinetd accepts even when the
# spawned M handler crashes (BL-014 — the pre-fix broker died on every
# connection while the port probe passed). A real XWB TCPConnect frame must
# come back 'accept'.
out=$(docker exec "$CONTAINER" timeout 5 bash -c '
    exec 3<>/dev/tcp/127.0.0.1/9430 || exit 1
    printf "[XWB]10304\nTCPConnect50010127.0.0.1f00010f0009localhostf\x04" >&3
    IFS= read -r -t 4 -d $'"'"'\x04'"'"' reply <&3
    printf "%s" "$reply"' 2>&1)
case "$out" in
    *accept*) report S-07 "RPC Broker answers XWB connect" PASS ;;
    *)        report S-07 "RPC Broker answers XWB connect" FAIL "reply: '$out'" ;;
esac
# S-08 checks the xinetd layer only — the VistALink app handler closes idle
# connections immediately and has no consumer today (see BL-014).
port_check S-08 "VistALink port 8001 (xinetd layer)" 8001
# S-09/S-10: baked (ADR-013) but UNCONSUMED services — WARN, never FAIL (ADR-051).
warn_check S-09 "Rocto SQL port 1338 (no consumers)" docker exec "$CONTAINER" \
    timeout 2 bash -c "echo >/dev/tcp/127.0.0.1/1338"
warn_check S-10 "YDB GUI port 8089 (no consumers)" docker exec "$CONTAINER" \
    timeout 2 bash -c "echo >/dev/tcp/127.0.0.1/8089"

# ── S-11 FileMan responds ─────────────────────────────────────────────
out=$(in_m 'S DUZ=.5 D DT^DICRW W $$NOW^XLFDT' | tr -d '[:space:]')
case "$out" in
    3[0-9][0-9][0-9][0-9][0-9][0-9]*) report S-11 "FileMan responds" PASS ;;  # FM date: 3YYMMDD…
    *)                                report S-11 "FileMan responds" FAIL "$out" ;;
esac

# ── S-12 VEHU patient data ────────────────────────────────────────────
out=$(in_m 'W $D(^DPT(1))' | tr -d '[:space:]')
case "$out" in
    1|10|11) report S-12 "VEHU patient data present" PASS ;;
    *)       report S-12 "VEHU patient data present" FAIL "\$D(^DPT(1)) = '$out'" ;;
esac

# ── Summary ───────────────────────────────────────────────────────────
TOTAL=$((PASS + FAIL + WARN + SKIP))
echo "[smoke] $PASS/$TOTAL passed, $FAIL failed, $WARN warned, $SKIP skipped"
[ "$FAIL" -eq 0 ]
