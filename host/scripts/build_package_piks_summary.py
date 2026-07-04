#!/usr/bin/env python3
# Phase 2d of ADR-045: join package-data.tsv × files.tsv on file_number.
# Produces per-package PIKS distribution of the data each package ships.
# Spec: docs/reference/model-extraction-contract.md § 11

"""Aggregate per-package PIKS distribution of shipped FileMan files.

Reads:
  - vista/export/code-model/package-data.tsv  (Phase 2c inventory)
  - vista/export/data-model/piks.tsv          (automated PIKS from heuristics)
  - vista/export/data-model/piks-triage.tsv   (manual triage — takes precedence)

Writes:
  - vista/export/code-model/package-piks-summary.tsv

One row per package. Counts distinct file_numbers that the package
ships (sharded chunks collapse to a single file), bucketed by PIKS.
Manual triage overrides automated where both apply (RF-009 convention).

Two "no-PIKS" buckets are kept explicit rather than lumped together:
  - unclassified      : file_number is not in piks.tsv or piks-triage.tsv
  - not_in_piks_work  : intentionally same bucket as above (files.tsv is
                        structural only; piks.tsv is the authority)
Kept as one bucket `unclassified` for simplicity.
"""

from __future__ import annotations

import csv
import sys
from collections import defaultdict
from pathlib import Path

import schema_v1
import tsvio

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CODE_MODEL = PROJECT_ROOT / "vista/export/code-model"
DATA_MODEL = PROJECT_ROOT / "vista/export/data-model"
PACKAGE_DATA = CODE_MODEL / "package-data.tsv"
PIKS_TSV = DATA_MODEL / "piks.tsv"
OUT_TSV = CODE_MODEL / "package-piks-summary.tsv"

SPEC = schema_v1.spec_for("package-piks-summary.tsv")
FIELDS = list(SPEC.columns)


def load_piks() -> dict[str, str]:
    """file_number → PIKS from the materialized piks.tsv (V2/B1:
    triage/auto/inheritance precedence is the producer's job — this
    consumer never re-merges)."""
    with PIKS_TSV.open(newline="", encoding="utf-8") as fh:
        return {row["file_number"]: row["piks"].strip()
                for row in csv.DictReader(fh, delimiter="\t")
                if row.get("piks", "").strip()}


def main() -> int:
    for src in (PACKAGE_DATA, PIKS_TSV):
        if not src.exists():
            print(f"ERROR: {src} missing.", file=sys.stderr)
            return 1

    piks_of = load_piks()

    pkg_files: dict[str, set[str]] = defaultdict(set)
    with PACKAGE_DATA.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            if row["kind"] != "file":
                continue
            pkg_files[row["package"]].add(row["file_number"])

    bucket = {"P": "p_files", "I": "i_files", "K": "k_files", "S": "s_files"}

    out_rows: list[dict] = []
    for package, file_numbers in sorted(pkg_files.items()):
        counts = {k: 0 for k in ("p_files", "i_files", "k_files", "s_files",
                                 "unclassified")}
        for fn in file_numbers:
            p = piks_of.get(fn, "")
            counts[bucket.get(p, "unclassified")] += 1
        out_rows.append({
            "package": package,
            **counts,
            "total_distinct_files": len(file_numbers),
        })

    tsvio.write_spec(OUT_TSV, SPEC, out_rows)

    totals = {k: sum(r[k] for r in out_rows) for k in FIELDS if k != "package"}
    print(f"package-piks-summary.tsv: {len(out_rows)} packages")
    print(f"  P={totals['p_files']}  I={totals['i_files']}  "
          f"K={totals['k_files']}  S={totals['s_files']}")
    print(f"  unclassified={totals['unclassified']}")
    print(f"  total distinct files shipped: {totals['total_distinct_files']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
