#!/usr/bin/env bash
# HEALTHCHECK — validates core services are listening.
# Spec: docs/vista-meta-spec-v0.4.md § 5 (HEALTHCHECK)
# ADR-024: bake status is NOT a health criterion.
#
# RUNS IN: container, called by Docker HEALTHCHECK directive every 30s.
# Exit 0 = healthy, exit 1 = unhealthy.
set -euo pipefail

fail() { echo "UNHEALTHY: $1" >&2; exit 1; }

# sshd :22, RPC Broker :9430, VistALink :8001, rocto :1338, YDB GUI :8089
for port in 22 9430 8001 1338 8089; do
    timeout 2 bash -c "echo >/dev/tcp/127.0.0.1/$port" 2>/dev/null \
        || fail "port $port not listening"
done

exit 0
