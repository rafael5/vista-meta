#!/usr/bin/env python3
# Phase 6c of ADR-045: package-to-package call edge matrix.
# Spec: docs/vista-meta-spec-v0.4.md § 11

"""Build package-edge-matrix.tsv — sparse (src_pkg → dst_pkg) matrix.

Aggregates routine-calls.tsv up to the package level. Each row is a
(source_package, dest_package) pair with counts of:
  - call_edges               : unique (caller, callee_tag, callee_routine, kind)
                               tuples crossing this package boundary
  - distinct_caller_routines : distinct source-package routines making calls
  - distinct_callee_routines : distinct destination-package routines called

Rows include intra-package edges (source == dest). Pairs with zero
edges are omitted (sparse). Callees not in MANIFEST (T-002 cohort) are
skipped — they have no canonical package assignment.

Reads:
  - vista/export/normalized/routines.tsv       (routine → package)
  - vista/export/normalized/routine-calls.tsv  (edges)

Writes:
  - vista/export/normalized/package-edge-matrix.tsv
"""

from __future__ import annotations

import csv
import sys
from collections import defaultdict
from pathlib import Path

NORM = Path(__file__).resolve().parents[2] / "vista/export/normalized"
OUT_TSV = NORM / "package-edge-matrix.tsv"

FIELDS = [
    "source_package",
    "dest_package",
    "call_edges",
    "distinct_caller_routines",
    "distinct_callee_routines",
]


def load_tsv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def main() -> int:
    for f in ("routines.tsv", "routine-calls.tsv"):
        if not (NORM / f).exists():
            print(f"ERROR: {NORM/f} missing.", file=sys.stderr)
            return 1

    rou_pkg: dict[str, str] = {}
    for r in load_tsv(NORM / "routines.tsv"):
        rou_pkg[r["routine_name"]] = r["package"]

    # (src_pkg, dst_pkg) → { edges, callers, callees }
    edges: dict[tuple[str, str], int] = defaultdict(int)
    callers: dict[tuple[str, str], set[str]] = defaultdict(set)
    callees: dict[tuple[str, str], set[str]] = defaultdict(set)

    skipped_no_pkg = 0
    for r in load_tsv(NORM / "routine-calls.tsv"):
        src_pkg = r["caller_package"]
        callee = r["callee_routine"]
        dst_pkg = rou_pkg.get(callee)
        if not dst_pkg:
            skipped_no_pkg += 1
            continue
        key = (src_pkg, dst_pkg)
        edges[key] += 1
        callers[key].add(r["caller_name"])
        callees[key].add(callee)

    rows = []
    for (src, dst), n in edges.items():
        rows.append({
            "source_package": src,
            "dest_package": dst,
            "call_edges": n,
            "distinct_caller_routines": len(callers[(src, dst)]),
            "distinct_callee_routines": len(callees[(src, dst)]),
        })
    rows.sort(key=lambda r: (-r["call_edges"], r["source_package"], r["dest_package"]))

    with OUT_TSV.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, delimiter="\t")
        w.writeheader()
        w.writerows(rows)

    intra = sum(r["call_edges"] for r in rows if r["source_package"] == r["dest_package"])
    inter = sum(r["call_edges"] for r in rows if r["source_package"] != r["dest_package"])
    distinct_pairs = len(rows)
    cross_pairs = sum(1 for r in rows if r["source_package"] != r["dest_package"])
    source_packages = len({r["source_package"] for r in rows})
    dest_packages = len({r["dest_package"] for r in rows})

    print(f"package-edge-matrix.tsv: {distinct_pairs:,} non-zero pairs")
    print(f"  distinct source packages: {source_packages}")
    print(f"  distinct dest packages:   {dest_packages}")
    print(f"  cross-package pairs:      {cross_pairs:,}")
    print(f"  intra-package edges:      {intra:,}")
    print(f"  cross-package edges:      {inter:,} "
          f"({100*inter/(intra+inter):.1f}%)")
    print(f"  skipped (callee not in MANIFEST / T-002): {skipped_no_pkg:,}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
