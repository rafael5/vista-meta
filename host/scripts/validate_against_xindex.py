#!/usr/bin/env python3
# Phase 7 (post-Phase-6 validation): compare our regex-based extractions
# against XINDEX's authoritative output. ADR-045 validation pass.
# Spec: docs/xindex-reference.md

"""Validate our regex extractions against XINDEX ground truth.

Reads (all from vista/export/normalized/):
  - routines.tsv             (our Phase 1b/2a — line_count, tag_count)
  - routine-calls.tsv        (our Phase 5 — routine→routine edges)
  - xindex-routines.tsv      (XINDEX — line_count, tag_count, xref_count)
  - xindex-xrefs.tsv         (XINDEX — routine → external refs)

Writes:
  - vista/export/normalized/xindex-validation.tsv
    one row per routine (joined inner on the ones XINDEX processed)
    columns:
      routine, package,
      lines_ours, lines_xindex, lines_match,
      tags_ours, tags_xindex, tags_match,
      callees_ours_count, callees_xindex_count,
      callees_match_count, callees_ours_only_count, callees_xindex_only_count,
      callees_agreement_ratio

Summary statistics printed to stdout.
"""

from __future__ import annotations

import csv
import sys
from collections import defaultdict
from pathlib import Path

NORM = Path(__file__).resolve().parents[2] / "vista/export/normalized"
OUT_TSV = NORM / "xindex-validation.tsv"

FIELDS = [
    "routine", "package",
    "lines_ours", "lines_xindex", "lines_match",
    "tags_ours", "tags_xindex", "tags_match",
    "callees_ours_count", "callees_xindex_count",
    "callees_match_count",
    "callees_ours_only_count", "callees_xindex_only_count",
    "callees_agreement_ratio",
]


def load_tsv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def parse_xref_ref(ref: str) -> tuple[str, str]:
    """XINDEX xref ref column format: 'ROUTINE' or 'ROUTINE TAG'
    (space-separated with routine first, tag second, when both present).
    Returns (routine, tag) — tag="" if no tag."""
    parts = ref.split(" ", 1)
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], parts[1]


def main() -> int:
    required = ("routines.tsv", "routine-calls.tsv",
                "xindex-routines.tsv", "xindex-xrefs.tsv")
    for f in required:
        if not (NORM / f).exists():
            print(f"ERROR: {NORM/f} missing.", file=sys.stderr)
            return 1

    # Our regex per-routine data
    our_rou: dict[str, dict] = {}
    for r in load_tsv(NORM / "routines.tsv"):
        our_rou[r["routine_name"]] = {
            "package": r["package"],
            "lines": int(r["line_count"]),
            "tags": int(r["tag_count"]),
        }

    # XINDEX per-routine data (authoritative)
    xindex_rou: dict[str, dict] = {}
    for r in load_tsv(NORM / "xindex-routines.tsv"):
        xindex_rou[r["routine"]] = {
            "lines": int(r["line_count"]),
            "tags": int(r["tag_count"]),
            "xref_count": int(r["xref_count"]),
        }

    # Our call graph: routine → set of callee routine names
    our_callees: dict[str, set[str]] = defaultdict(set)
    for r in load_tsv(NORM / "routine-calls.tsv"):
        our_callees[r["caller_name"]].add(r["callee_routine"])

    # XINDEX xrefs: routine → set of callee routine names
    xindex_callees: dict[str, set[str]] = defaultdict(set)
    for r in load_tsv(NORM / "xindex-xrefs.tsv"):
        rou, _tag = parse_xref_ref(r["ref"])
        if rou:
            xindex_callees[r["routine"]].add(rou)

    # Build validation rows — one per XINDEX-processed routine that also
    # appears in our inventory. (Excludes T-002 cohort that XINDEX can't
    # process; excludes nothing from our side since ours is a superset.)
    rows: list[dict] = []
    for name in sorted(xindex_rou.keys()):
        if name not in our_rou:
            continue
        ours = our_rou[name]
        xi = xindex_rou[name]
        oc = our_callees.get(name, set())
        xc = xindex_callees.get(name, set())
        match = oc & xc
        ours_only = oc - xc
        xindex_only = xc - oc
        union = oc | xc
        ratio = len(match) / len(union) if union else 1.0
        rows.append({
            "routine": name,
            "package": ours["package"],
            "lines_ours": ours["lines"],
            "lines_xindex": xi["lines"],
            "lines_match": "Y" if ours["lines"] == xi["lines"] else "N",
            "tags_ours": ours["tags"],
            "tags_xindex": xi["tags"],
            "tags_match": "Y" if ours["tags"] == xi["tags"] else "N",
            "callees_ours_count": len(oc),
            "callees_xindex_count": len(xc),
            "callees_match_count": len(match),
            "callees_ours_only_count": len(ours_only),
            "callees_xindex_only_count": len(xindex_only),
            "callees_agreement_ratio": f"{ratio:.4f}",
        })

    with OUT_TSV.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, delimiter="\t")
        w.writeheader()
        w.writerows(rows)

    # ---- Summary statistics ----
    n = len(rows)
    lines_matched = sum(1 for r in rows if r["lines_match"] == "Y")
    tags_matched = sum(1 for r in rows if r["tags_match"] == "Y")
    total_match = sum(r["callees_match_count"] for r in rows)
    total_ours = sum(r["callees_ours_count"] for r in rows)
    total_xindex = sum(r["callees_xindex_count"] for r in rows)
    total_ours_only = sum(r["callees_ours_only_count"] for r in rows)
    total_xindex_only = sum(r["callees_xindex_only_count"] for r in rows)
    avg_ratio = sum(float(r["callees_agreement_ratio"]) for r in rows) / n if n else 0

    # In-MANIFEST-but-not-in-XINDEX (T-002 cohort)
    not_in_xindex = set(our_rou.keys()) - set(xindex_rou.keys())
    # In-XINDEX-but-not-in-MANIFEST (File 9.8-only with ZLINK success)
    not_in_ours = set(xindex_rou.keys()) - set(our_rou.keys())

    print(f"xindex-validation.tsv: {n:,} rows (routines in both our data and XINDEX)")
    print()
    print("=== Per-routine static features (our regex vs XINDEX parser) ===")
    print(f"  line_count match:  {lines_matched:,}/{n:,} "
          f"({100*lines_matched/n:.2f}%)")
    print(f"  tag_count match:   {tags_matched:,}/{n:,} "
          f"({100*tags_matched/n:.2f}%)")
    print()
    print("=== Call graph (our regex vs XINDEX) ===")
    print(f"  our callee edges (summed per-routine):     {total_ours:,}")
    print(f"  XINDEX callee edges (summed per-routine):  {total_xindex:,}")
    print(f"  matched (both agree):                      {total_match:,}")
    print(f"  our-only (XINDEX missed):                  {total_ours_only:,}")
    print(f"  XINDEX-only (we missed):                   {total_xindex_only:,}")
    print(f"  average per-routine agreement ratio:       {avg_ratio:.4f}")
    print()
    print("=== Population coverage ===")
    print(f"  in our MANIFEST but not in XINDEX: {len(not_in_xindex):,}")
    print(f"    (T-002 cohort — ABS*, A1A*, etc. — shipped but ZLINK fails)")
    print(f"  in XINDEX but not in our MANIFEST: {len(not_in_ours):,}")
    print(f"    (routines Kernel knows AND has registered; validate T-002 B-cohort)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
