#!/usr/bin/env python3
# Phase 2c of ADR-045: package-level data inventory (pre-Phase 3).
# Strictly mechanical extraction from Globals/*.zwr filenames.
# Companion to build_routine_inventory.py; together they give the
# code+data shipping manifest per package.
# Spec: docs/vista-meta-spec-v0.4.md § 11

"""Inventory ZWR data exports shipped under each package's Globals/ dir.

VistA FOIA packages ship their DD definitions and seed records as
ZWRITE-format exports under Packages/<pkg>/Globals/. Three filename shapes:
  - `<FILE_NUMBER>+<FILE_NAME>.zwr`             — whole FileMan file export
  - `<FILE_NUMBER>-<CHUNK>+<FILE_NAME>.zwr`     — sharded file (big tables
    like ICD DIAGNOSIS, RXNORM CONCEPTS are chunked across multiple ZWRs)
  - `<GLOBAL_NAME>.zwr`                         — non-FileMan global export

All three are strictly identifiable from the filename. No ZWR parsing —
the inventory records the filename and byte size only.
"""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
HOST_SNAPSHOT = PROJECT_ROOT / "vista/vista-m-host"
PACKAGES_DIR = HOST_SNAPSHOT / "Packages"
OUT_DIR = PROJECT_ROOT / "vista/export/normalized"
OUT_TSV = OUT_DIR / "package-data.tsv"

CONTAINER_PREFIX = str(HOST_SNAPSHOT) + "/"
CONTAINER_ROOT = "/opt/VistA-M/"

FIELDS = [
    "package",
    "kind",
    "file_number",
    "chunk",
    "entity_name",
    "source_path",
    "byte_size",
]

# FileMan file export: `702+CP TRANSACTION.zwr` (whole) or
# `80-3+ICD DIAGNOSIS.zwr` (sharded — chunk 3 of a multi-part export).
FILE_RE = re.compile(r"^(\d+(?:\.\d+)?)(?:-(\d+))?\+(.+)\.zwr$")
# Anything else ending in .zwr with no `+` separator is a non-FileMan
# global export (e.g. `LA.zwr`, `PRC.zwr`, `PXRMINDX.zwr`).
GLOBAL_RE = re.compile(r"^([^+]+)\.zwr$")


def to_container_path(host_path: Path) -> str:
    rel = str(host_path).removeprefix(CONTAINER_PREFIX)
    return CONTAINER_ROOT + rel


def classify(filename: str) -> tuple[str, str, str, str]:
    m = FILE_RE.match(filename)
    if m:
        file_number, chunk, entity_name = m.group(1), m.group(2) or "", m.group(3)
        return "file", file_number, chunk, entity_name
    m = GLOBAL_RE.match(filename)
    if m:
        return "global", "", "", m.group(1)
    raise ValueError(f"Unrecognized ZWR filename shape: {filename}")


def main() -> int:
    if not PACKAGES_DIR.exists():
        print(
            f"ERROR: {PACKAGES_DIR} not found. Run `make sync-routines` first.",
            file=sys.stderr,
        )
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    rows: list[dict] = []
    for zwr in sorted(PACKAGES_DIR.glob("*/Globals/*.zwr")):
        package = zwr.parent.parent.name
        kind, file_number, chunk, entity_name = classify(zwr.name)
        rows.append({
            "package": package,
            "kind": kind,
            "file_number": file_number,
            "chunk": chunk,
            "entity_name": entity_name,
            "source_path": to_container_path(zwr),
            "byte_size": zwr.stat().st_size,
        })

    rows.sort(key=lambda r: (
        r["package"], r["kind"], r["file_number"], r["entity_name"],
        int(r["chunk"]) if r["chunk"] else 0,
    ))

    with OUT_TSV.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, delimiter="\t")
        w.writeheader()
        w.writerows(rows)

    file_rows = sum(1 for r in rows if r["kind"] == "file")
    sharded_rows = sum(1 for r in rows if r["kind"] == "file" and r["chunk"])
    global_rows = sum(1 for r in rows if r["kind"] == "global")
    distinct_files = len({r["file_number"] for r in rows if r["kind"] == "file"})
    total_bytes = sum(r["byte_size"] for r in rows)
    pkgs_with_data = len({r["package"] for r in rows})

    print(f"package-data.tsv:   {len(rows):,} rows")
    print(f"  kind=file:        {file_rows:,} FileMan exports "
          f"({sharded_rows:,} of them are sharded chunks)")
    print(f"  kind=global:      {global_rows:,} non-FileMan global exports")
    print(f"distinct files:     {distinct_files}")
    print(f"packages w/ data:   {pkgs_with_data}")
    print(f"total zwr bytes:    {total_bytes:,}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
