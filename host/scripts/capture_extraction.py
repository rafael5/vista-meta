#!/usr/bin/env python3
# V1.6 of the producer-contracts plan: R3 engine identity/state capture.
# Spec: docs/proposals/schema-v1-normalization-spec.md § 6 R3

"""Capture the R3 sidecar at extraction time.

Without these fields, `source_commit` pins code that describes
unidentifiable data (the measured A1 finding: sandbox-vs-gold drift,
CPT #81 off by >10×). Captured DURING emit-all — R3 identity cannot
be reconstructed after the fact (risk F7).

Fields: engine, engine image name + id, container id, extraction
timestamp (UTC), DB-state fingerprint (sha256 over the bytewise-sorted
`file_number\trecord_count` lines of the raw files.tsv dump), and the
producing source_commit (V7 re-verifies clean-tree at release).

Writes: vista/export/raw/extraction.json (travels with the raw
intermediates; V7 folds it into manifest.json).
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import tsvio

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_FILES = PROJECT_ROOT / "vista/export/raw/files.tsv"
OUT_JSON = PROJECT_ROOT / "vista/export/raw/extraction.json"


def db_fingerprint(rows: list[dict]) -> str:
    """sha256 over LF-joined, bytewise-sorted file_number/record_count."""
    lines = sorted(
        f"{r['file_number']}\t{r.get('record_count', '')}".encode("utf-8")
        for r in rows)
    return hashlib.sha256(b"\n".join(lines)).hexdigest()


def build_sidecar(engine: str, image: str, image_id: str,
                  container_id: str, source_commit: str, db_fp: str,
                  timestamp: str) -> dict:
    return {
        "engine": engine,
        "engine_image": image,
        "engine_image_id": image_id,
        "container_id": container_id,
        "extraction_timestamp": timestamp,
        "db_state_fingerprint": db_fp,
        "source_commit": source_commit,
    }


def _docker_inspect(container: str, fmt: str) -> str:
    return subprocess.run(
        ["docker", "inspect", container, "--format", fmt],
        capture_output=True, text=True, check=True).stdout.strip()


def main(container: str) -> int:
    if not RAW_FILES.exists():
        print(f"ERROR: {RAW_FILES} missing — run 'make dump-files' first "
              "(the fingerprint pins the same extraction).",
              file=sys.stderr)
        return 1
    cols, rows = tsvio.read_tsv(RAW_FILES)
    dicts = [dict(zip(cols, r)) for r in rows]

    doc = build_sidecar(
        engine="ydb",
        image=_docker_inspect(container, "{{.Config.Image}}"),
        image_id=_docker_inspect(container, "{{.Image}}"),
        container_id=_docker_inspect(container, "{{.Id}}")[:12],
        source_commit=subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=PROJECT_ROOT,
            capture_output=True, text=True, check=True).stdout.strip(),
        db_fp=db_fingerprint(dicts),
        timestamp=datetime.now(timezone.utc).isoformat(
            timespec="seconds").replace("+00:00", "Z"),
    )
    OUT_JSON.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print(f"extraction.json: engine={doc['engine']} "
          f"image={doc['engine_image']} db_fp={doc['db_state_fingerprint'][:12]}…")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: capture_extraction.py <container-name>",
              file=sys.stderr)
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
