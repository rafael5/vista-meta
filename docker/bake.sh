#!/usr/bin/env bash
# bake.sh — first-run + manual analytics pipeline (STUB).
# Spec: docs/vista-meta-spec-v0.4.md § 6
#
# RUNS IN: container, as vehu user
# INVOKED BY: entrypoint.sh (first run) or `make bake*` (manual)
#
# This is a placeholder. Full implementation pending.
# For now, it creates the sentinel file so the entrypoint doesn't
# re-invoke it on every container start.

set -euo pipefail

SENTINEL="/home/vehu/export/.vista-meta-initialized"

echo "[bake] stub — full pipeline not yet implemented"
echo "[bake] creating sentinel to prevent re-invocation"

cat > "$SENTINEL" <<SENTINEL_EOF
{
  "initialized_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "image_tag": "vista-meta:stub",
  "ydb_version": "$(mumps -run %XCMD 'W $P($ZV," ",2)' 2>/dev/null || echo unknown)",
  "vehu_m_source": "stub",
  "phases": {
    "xindex":      { "status": "pending", "items_ok": 0, "items_failed": 0, "duration_sec": 0, "log": "" },
    "dd-text":     { "status": "pending", "items_ok": 0, "items_failed": 0, "duration_sec": 0, "log": "" },
    "dd-fmql":     { "status": "pending", "items_ok": 0, "items_failed": 0, "duration_sec": 0, "log": "" },
    "dd-template": { "status": "pending", "items_ok": 0, "items_failed": 0, "duration_sec": 0, "log": "" }
  }
}
SENTINEL_EOF

echo "[bake] sentinel written to $SENTINEL"
