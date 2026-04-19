#!/usr/bin/env bash
# vista-meta entrypoint — container startup, invoked by tini as PID 1 child.
# Spec: docs/vista-meta-spec-v0.4.md § 5
# ADR-021: tini as PID 1, bash entrypoint
#
# RUNS IN: container, initially as root (tini -> this script)
# NOT directly invoked — called via ENTRYPOINT in Dockerfile.
#
# Phases:
#   1. Pre-flight     (root)  — validate env, generate SSH host keys
#   2. UID reconcile  (root)  — chown bind mounts for vehu
#   3. Service start  (mixed) — sshd, xinetd, rocto, YDB GUI
#   4. First-run bake (vehu)  — background, sentinel-gated
#   5. Supervise      (wait)  — SIGTERM trap for graceful shutdown
set -euo pipefail

SENTINEL="/home/vehu/export/.vista-meta-initialized"

log() { echo "[entrypoint] $(date '+%H:%M:%S') $*"; }

# ── Phase 1: Pre-flight ──────────────────────────────────────────────
log "phase 1: pre-flight"

source /etc/profile.d/ydb_env.sh

# SSH host keys — generate once, persist across restarts
ssh-keygen -A 2>/dev/null || true

mkdir -p /tmp/ydb /run/sshd "$ydb_log"

# ── Phase 2: UID reconciliation ──────────────────────────────────────
# ADR-009: chown bind mounts so vehu can write regardless of host UID
log "phase 2: UID reconciliation"
chown -R vehu:vehu /home/vehu/dev \
                   /home/vehu/scripts \
                   /home/vehu/export \
                   /home/vehu/g

# ── Phase 3: Service startup ─────────────────────────────────────────
# ADR-013: sshd → xinetd → rocto → YDB GUI
# All services listen on 0.0.0.0 inside the container.
# Tailscale IP binding enforced at Docker -p level (ADR-008).
log "phase 3: starting services"

# -D / -dontfork: keep services in foreground so they remain direct children
# of this script. Tini reaps zombies; we track PIDs for graceful shutdown.
log "  sshd"
/usr/sbin/sshd -D &
SSHD_PID=$!

log "  xinetd (RPC Broker :9430, VistALink :8001)"
/usr/sbin/xinetd -dontfork &
XINETD_PID=$!

# exec replaces the su/bash shell with the actual service process,
# so the PID we capture is the service itself, not a wrapper shell.
log "  rocto (Octo SQL :1338)"
su -s /bin/bash vehu -c "source /etc/profile.d/ydb_env.sh && exec \$ydb_dist/plugin/bin/rocto -p 1338" &
ROCTO_PID=$!

# YDBGUI uses a Node.js WebSocket server. Start only if node is available.
if command -v node >/dev/null 2>&1; then
    log "  YDB GUI (:8089)"
    su -s /bin/bash vehu -c "exec node \$ydb_dist/plugin/etc/ydbgui/node/startup.js --port=8089 --ydb_dist=\$ydb_dist" &
    YDBGUI_PID=$!
else
    log "  YDB GUI (:8089) — SKIPPED (node not installed)"
    YDBGUI_PID=""
fi

# ── Phase 4: First-run bake (background) ─────────────────────────────
# ADR-022: bake runs in background after services are up
# ADR-023: continue-on-error within bake phases
if [ ! -f "$SENTINEL" ]; then
    log "phase 4: first run — launching bake in background"
    su -s /bin/bash vehu -c \
        "source /etc/profile.d/ydb_env.sh && exec /usr/local/bin/bake.sh --all" &
# Check if any bake phase was left in "pending" state (interrupted mid-run)
elif command -v jq >/dev/null && jq -e \
        '.phases | to_entries[] | select(.value.status == "pending")' \
        "$SENTINEL" >/dev/null 2>&1; then
    log "phase 4: incomplete bake detected — resuming in background"
    su -s /bin/bash vehu -c \
        "source /etc/profile.d/ydb_env.sh && exec /usr/local/bin/bake.sh --all" &
else
    log "phase 4: bake already complete — skipping"
fi

# ── Phase 5: Supervise ───────────────────────────────────────────────
# ADR-021: tini reaps zombies; we trap SIGTERM for graceful shutdown.
cleanup() {
    log "SIGTERM received — shutting down"

    # Stop rocto
    su -s /bin/bash vehu -c \
        "source /etc/profile.d/ydb_env.sh && rocto -stop" 2>/dev/null || true

    # Stop xinetd
    kill "$XINETD_PID" 2>/dev/null || true

    # Stop YDB GUI
    [ -n "$YDBGUI_PID" ] && kill "$YDBGUI_PID" 2>/dev/null || true

    # Stop sshd
    kill "$SSHD_PID" 2>/dev/null || true

    # Brief grace period for processes to exit
    sleep 2

    log "shutdown complete"
    exit 0
}

trap cleanup SIGTERM SIGINT

log "all services started — waiting"
wait
