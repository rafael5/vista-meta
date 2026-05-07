#!/usr/bin/env bash
# HEALTHCHECK — validates services the entrypoint is actually expected to
# start, and that the YDB engine itself responds. Spec: docs/vista-meta-spec-v0.4.md § 5
# ADR-024: bake status is NOT a health criterion.
#
# RUNS IN: container, called by Docker HEALTHCHECK directive every 30s.
# Exit 0 = healthy, exit 1 = unhealthy.
#
# Required = ports without which the developer workflow is broken (sshd for
# `make shell` and sibling-project SSH-based tests; xinetd for the RPC Broker
# and VistALink endpoints clients connect to). Optional = services whose
# absence is informational only (rocto and YDB GUI fail in the stub image
# because $ZRO is not configured for the rocto plugin; healthcheck must not
# permanently flag the container unhealthy for that). Override via env:
#   VISTA_META_HC_REQUIRED  (default: "22 9430 8001")
#   VISTA_META_HC_OPTIONAL  (default: "1338 8089")
#   VISTA_META_HC_SKIP_YDB  (default: unset; set to 1 to skip engine probe)
set -euo pipefail

REQUIRED="${VISTA_META_HC_REQUIRED:-22 9430 8001}"
OPTIONAL="${VISTA_META_HC_OPTIONAL:-1338 8089}"

fail() { echo "UNHEALTHY: $1" >&2; exit 1; }

probe() {
    timeout 2 bash -c "echo >/dev/tcp/127.0.0.1/$1" 2>/dev/null
}

for port in $REQUIRED; do
    probe "$port" || fail "required port $port not listening"
done

# YDB engine round-trip: proves mumps -direct can attach to the database.
# Catches REQRUNDOWN states that survived rundown, full-disk, or globals
# corruption that ports-listening would not catch.
if [ "${VISTA_META_HC_SKIP_YDB:-}" != "1" ]; then
    out=$(timeout 5 su -s /bin/bash vehu -c '
        source /etc/profile.d/ydb_env.sh 2>/dev/null
        printf "set ^HCK($J)=\"ok\"\nwrite ^HCK($J)\nkill ^HCK($J)\nhalt\n" \
            | $ydb_dist/mumps -direct 2>&1
    ' 2>/dev/null) || fail "YDB engine probe failed (timeout or error)"
    [[ "$out" == *ok* ]] || fail "YDB engine probe did not round-trip"
fi

# Optional services: log only, do not fail. Healthcheck output is visible via
# `docker inspect --format '{{json .State.Health}}'`.
missing_opt=""
for port in $OPTIONAL; do
    probe "$port" || missing_opt="$missing_opt $port"
done
if [ -n "$missing_opt" ]; then
    echo "OK (optional ports down:$missing_opt)" >&2
fi

exit 0
