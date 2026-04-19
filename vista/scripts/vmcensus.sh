#!/usr/bin/env bash
# vmcensus.sh — Phase 1 global recon
# Spec: docs/vista-meta-spec-v0.4.md § 11.4.4
# RUNS IN: container, as vehu
set -euo pipefail
source /etc/profile.d/ydb_env.sh

echo "[vmcensus] Enumerating globals via mupip size..."

# Get global names
GLIST=$($ydb_dist/mupip size -reg DEFAULT -select="*" 2>&1 | grep "^Global:" | sed 's/Global: //;s/ .*//')
GCOUNT=$(echo "$GLIST" | wc -l)
echo "[vmcensus] Found $GCOUNT globals."

# Build M SET commands to populate ^TMP
MCMD=""
while IFS= read -r g; do
    [ -z "$g" ] && continue
    MCMD="${MCMD}S ^TMP(\"VMCENSUS\",\$J,\"$g\")=\"\" "
done <<< "$GLIST"

# Run recon
echo "[vmcensus] Running recon..."
$ydb_dist/mumps -run %XCMD "${MCMD}D RECON^VMCENSUS K ^TMP(\"VMCENSUS\",\$J)"

echo "[vmcensus] Done."
