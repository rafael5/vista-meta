#!/usr/bin/env python3
# Phase 7 (post-Phase-6 validation): compare our regex-based extractions
# against XINDEX's authoritative output. ADR-045 validation pass.
# Spec: docs/reference/xindex-reference.md

"""Validate our regex extractions against XINDEX ground truth.

Reads (all from vista/export/code-model/):
  - routines.tsv             (our Phase 1b/2a — line_count, tag_count)
  - routine-calls.tsv        (our Phase 5 — routine→routine edges)
  - xindex-routines.tsv      (XINDEX — line_count, tag_count, xref_count)
  - xindex-xrefs.tsv         (XINDEX — routine → external refs)

Writes:
  - vista/export/code-model/xindex-validation.tsv
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

import schema_v1
import tsvio

NORM = Path(__file__).resolve().parents[2] / "vista/export/code-model"
OUT_TSV = NORM / "xindex-validation.tsv"

SPEC = schema_v1.spec_for("xindex-validation.tsv")


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
        xindex_rou[r["routine_name"]] = {
            "lines": int(r["line_count"]),
            "tags": int(r["tag_count"]),
            "xref_count": int(r["xref_count"]),
        }

    # Our call graph: routine → set of callee routine names
    our_callees: dict[str, set[str]] = defaultdict(set)
    for r in load_tsv(NORM / "routine-calls.tsv"):
        our_callees[r["caller_routine"]].add(r["callee_routine"])

    # XINDEX xrefs: routine → set of callee routine names
    xindex_callees: dict[str, set[str]] = defaultdict(set)
    for r in load_tsv(NORM / "xindex-xrefs.tsv"):
        rou, _tag = parse_xref_ref(r["ref"])
        if rou:
            xindex_callees[r["routine_name"]].add(rou)

    names, no_package = validated_names(our_rou, set(xindex_rou))
    rows: list[dict] = []
    for name in names:
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
            "routine_name": name,
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

    tsvio.write_spec(OUT_TSV, SPEC, rows)

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
    for line in coverage_report(set(our_rou), set(xindex_rou)):
        print(line)
    print(f"  processed but left out of xindex-validation (no package): "
          f"{len(no_package):,}" + (f" — {', '.join(no_package)}"
                                    if no_package else ""))
    return 0


def validated_names(our_rou: dict[str, dict],
                    xindexed: set[str]) -> tuple[list[str], list[str]]:
    """The routines xindex-validation.tsv holds, and those it skips.

    One row per routine both in the census and processed by XINDEX —
    except a routine in no package (e.g. YottaDB's own %YDBOCTOVISTAM
    in r/): the table's package column is non-null, an FK to
    packages.tsv, so such a routine is skipped and named.
    """
    both = sorted(n for n in xindexed if n in our_rou)
    return ([n for n in both if our_rou[n]["package"]],
            [n for n in both if not our_rou[n]["package"]])


SHOW_NAMES = 10


def coverage_report(census: set[str], xindexed: set[str]) -> list[str]:
    """Counts and names on each side of the census/XINDEX difference.

    Names only what was measured: why a routine is missing is not in
    these two sets, so no cause is printed.
    """
    lines = ["=== Population coverage ==="]
    for label, names in (
            ("in the census but not processed by XINDEX",
             census - xindexed),
            ("processed by XINDEX but not in the census",
             xindexed - census)):
        lines.append(f"  {label}: {len(names):,}")
        if names:
            shown = sorted(names)[:SHOW_NAMES]
            more = len(names) - len(shown)
            lines.append("    " + ", ".join(shown)
                         + (f" (and {more:,} more)" if more else ""))
    return lines


if __name__ == "__main__":
    sys.exit(main())
