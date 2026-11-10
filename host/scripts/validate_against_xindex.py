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

Checks each xindex-xrefs location against the caller's source text
in vista/vista-m-host/ (exit 1 past CALL_SITE_TOLERANCE).

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
from typing import Callable

import schema_v1
import tsvio
from mcp_cards import host_relative, parse_labels

NORM = Path(__file__).resolve().parents[2] / "vista/export/code-model"
SOURCE_ROOT = Path(__file__).resolve().parents[2] / "vista/vista-m-host"
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
    source_paths: dict[str, str] = {}
    for r in load_tsv(NORM / "routines.tsv"):
        source_paths[r["routine_name"]] = r["source_path"]
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
    xrefs = load_tsv(NORM / "xindex-xrefs.tsv")
    for r in xrefs:
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
    print()

    def lines_of(routine: str) -> list[str] | None:
        rel = host_relative(source_paths.get(routine))
        if rel is None or not (SOURCE_ROOT / rel).is_file():
            return None
        return (SOURCE_ROOT / rel).read_text(
            encoding="utf-8", errors="replace").splitlines()

    report, ok = call_site_report(*call_site_misses(xrefs, lines_of))
    for line in report:
        print(line)
    return 0 if ok else 1


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


INDIRECT_REF = "@("        # XINDEX's key for `D @X`, `D ^@X`: no name
LOCATION_FLAGS = "*!~"     # XINDX5 CR2 appends these to a location
CALL_SITE_TOLERANCE = 0.001


def call_site_misses(xrefs: list[dict],
                     lines_of: Callable[[str], list[str] | None]
                     ) -> tuple[int, int, list[str]]:
    """Check each XINDEX location against the caller's source text.

    A location is `TAG+n` (a bare `TAG` is the label line itself); the
    line it points at must name the called routine. data-v1 shipped
    XINDEX chunk numbers here instead ("0" on 213,713 rows) and every
    shape check passed — only the source shows the values are wrong.
    Returns (locations checked, indirect refs skipped, misses).
    """
    checked = indirect = 0
    misses: list[str] = []
    current, lines, labels = None, None, {}
    for row in xrefs:
        if row["ref"] == INDIRECT_REF:
            indirect += 1
            continue
        if row["routine_name"] != current:
            current = row["routine_name"]
            lines = lines_of(current)
            labels = {lb["tag"]: lb["line"]
                      for lb in parse_labels(lines or [])}
        callee = row["ref"].split(" ")[0]
        for loc in filter(None, row["location_list"].split(",")):
            checked += 1
            text = _line_at(lines or [], labels, loc.rstrip(LOCATION_FLAGS))
            if text is None or callee not in text:
                misses.append(f"{current} {loc} -> {row['ref']}")
    return checked, indirect, misses


def _line_at(lines: list[str], labels: dict[str, int],
             loc: str) -> str | None:
    tag, _, offset = loc.partition("+")
    offset = offset or "0"
    if tag not in labels or not offset.isdigit():
        return None
    i = labels[tag] + int(offset) - 1
    return lines[i] if i < len(lines) else None


def call_site_report(checked: int, indirect: int,
                     misses: list[str]) -> tuple[list[str], bool]:
    """The summary lines, and whether the misses are within tolerance."""
    limit = int(checked * CALL_SITE_TOLERANCE)
    ok = checked > 0 and len(misses) <= limit
    lines = ["=== Call sites (xindex-xrefs location_list vs the source) ===",
             f"  locations checked: {checked:,}",
             f"  not naming the callee: {len(misses):,} (limit {limit:,})"
             + ("" if ok else " — FAIL"),
             f"  indirect refs skipped (no routine name to find): "
             f"{indirect:,}"]
    if misses:
        shown = misses[:SHOW_NAMES]
        more = len(misses) - len(shown)
        lines.append("    " + "; ".join(shown)
                     + (f" (and {more:,} more)" if more else ""))
    return lines, ok


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
