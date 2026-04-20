#!/usr/bin/env python3
# Phase 6b of ADR-045: per-routine comprehensive view.
# Spec: docs/vista-meta-spec-v0.4.md § 11

"""Build routines-comprehensive.tsv — one row per routine, all signals joined.

Reads (all from vista/export/code-model/):
  - routines.tsv           (base inventory + static features)
  - vista-file-9-8.tsv     (VistA Kernel's view of the routine)
  - rpcs.tsv               (is-RPC signal from File 8994)
  - options.tsv            (is-option-entry signal from File 19, TYPE=R)
  - routine-calls.tsv      (out/in degree, call volumes)
  - routine-globals.tsv    (data access breadth)
  - protocol-calls.tsv     (invocations from File 101 ENTRY/EXIT ACTION)

Writes:
  - vista/export/code-model/routines-comprehensive.tsv  (39,330 rows × 20 cols)

protocol_invoked_count column captures the Phase 5b result: how many
distinct protocols invoke this routine via ENTRY or EXIT ACTION.
"""

from __future__ import annotations

import csv
import sys
from collections import defaultdict
from pathlib import Path

NORM = Path(__file__).resolve().parents[2] / "vista/export/code-model"
OUT_TSV = NORM / "routines-comprehensive.tsv"

FIELDS = [
    "routine_name", "package", "source_path",
    "line_count", "byte_size", "tag_count", "comment_line_count",
    "version_line", "is_percent_routine",
    "in_file_9_8", "file_9_8_type", "rpc_count", "option_count",
    "protocol_invoked_count",
    "out_degree", "in_degree", "out_calls_total", "in_calls_total",
    "distinct_globals_touched", "global_ref_total",
]


def load_tsv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def main() -> int:
    required = ("routines.tsv", "vista-file-9-8.tsv", "rpcs.tsv",
                "options.tsv", "routine-calls.tsv", "routine-globals.tsv",
                "protocol-calls.tsv")
    for f in required:
        if not (NORM / f).exists():
            print(f"ERROR: {NORM/f} missing.", file=sys.stderr)
            return 1

    # File 9.8 knowledge — routine → type (may be empty)
    f98: dict[str, str] = {}
    for r in load_tsv(NORM / "vista-file-9-8.tsv"):
        if r["name"]:
            f98[r["name"]] = r.get("type", "")

    # RPC counts per routine
    rpc_count: dict[str, int] = defaultdict(int)
    for r in load_tsv(NORM / "rpcs.tsv"):
        if r["routine"]:
            rpc_count[r["routine"]] += 1

    # Option TYPE=R counts per routine
    opt_count: dict[str, int] = defaultdict(int)
    for r in load_tsv(NORM / "options.tsv"):
        if r["type"] == "R" and r["routine"]:
            opt_count[r["routine"]] += 1

    # Call graph aggregates. Each row in routine-calls.tsv is already a
    # unique (caller, callee_tag, callee_routine, kind) tuple — count
    # rows for degrees, sum ref_count for call-volume totals.
    out_degree: dict[str, set[str]] = defaultdict(set)
    in_degree: dict[str, set[str]] = defaultdict(set)
    out_total: dict[str, int] = defaultdict(int)
    in_total: dict[str, int] = defaultdict(int)
    for r in load_tsv(NORM / "routine-calls.tsv"):
        caller, callee, cnt = r["caller_name"], r["callee_routine"], int(r["ref_count"])
        out_degree[caller].add(callee)
        in_degree[callee].add(caller)
        out_total[caller] += cnt
        in_total[callee] += cnt

    # Global reference aggregates
    glob_degree: dict[str, set[str]] = defaultdict(set)
    glob_total: dict[str, int] = defaultdict(int)
    for r in load_tsv(NORM / "routine-globals.tsv"):
        rou, glob, cnt = r["routine_name"], r["global_name"], int(r["ref_count"])
        glob_degree[rou].add(glob)
        glob_total[rou] += cnt

    # Protocol invocations — distinct protocols that call each routine
    # (Phase 5b: routines invoked from File 101 ENTRY/EXIT ACTION).
    proto_invokers: dict[str, set[str]] = defaultdict(set)
    for r in load_tsv(NORM / "protocol-calls.tsv"):
        proto_invokers[r["callee_routine"]].add(r["protocol_name"])

    out_rows: list[dict] = []
    for r in load_tsv(NORM / "routines.tsv"):
        name = r["routine_name"]
        out_rows.append({
            "routine_name": name,
            "package": r["package"],
            "source_path": r["source_path"],
            "line_count": r["line_count"],
            "byte_size": r["byte_size"],
            "tag_count": r["tag_count"],
            "comment_line_count": r["comment_line_count"],
            "version_line": r["version_line"],
            "is_percent_routine": r["is_percent_routine"],
            "in_file_9_8": "Y" if name in f98 else "N",
            "file_9_8_type": f98.get(name, ""),
            "rpc_count": rpc_count.get(name, 0),
            "option_count": opt_count.get(name, 0),
            "protocol_invoked_count": len(proto_invokers.get(name, ())),
            "out_degree": len(out_degree.get(name, ())),
            "in_degree": len(in_degree.get(name, ())),
            "out_calls_total": out_total.get(name, 0),
            "in_calls_total": in_total.get(name, 0),
            "distinct_globals_touched": len(glob_degree.get(name, ())),
            "global_ref_total": glob_total.get(name, 0),
        })

    out_rows.sort(key=lambda r: r["routine_name"])
    with OUT_TSV.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, delimiter="\t")
        w.writeheader()
        w.writerows(out_rows)

    total_rpc = sum(1 for r in out_rows if r["rpc_count"] > 0)
    total_opt = sum(1 for r in out_rows if r["option_count"] > 0)
    total_proto = sum(1 for r in out_rows if r["protocol_invoked_count"] > 0)
    total_any = sum(1 for r in out_rows if r["rpc_count"] > 0 or r["option_count"] > 0 or r["protocol_invoked_count"] > 0)
    total_in_f98 = sum(1 for r in out_rows if r["in_file_9_8"] == "Y")
    total_leaves = sum(1 for r in out_rows if r["out_degree"] == 0)
    total_sinks = sum(1 for r in out_rows if r["in_degree"] == 0)
    total_orphan_no_role = sum(
        1 for r in out_rows
        if r["in_degree"] == 0 and r["rpc_count"] == 0
        and r["option_count"] == 0 and r["protocol_invoked_count"] == 0
    )
    print(f"routines-comprehensive.tsv: {len(out_rows):,} rows")
    print(f"  backs >=1 RPC:               {total_rpc:,}")
    print(f"  backs >=1 option (TYPE=R):   {total_opt:,}")
    print(f"  invoked from >=1 protocol:   {total_proto:,}")
    print(f"  backs >=1 of any role:       {total_any:,}")
    print(f"  in File 9.8:                 {total_in_f98:,}")
    print(f"  out_degree == 0 (leaves):    {total_leaves:,}")
    print(f"  in_degree == 0 (sinks):      {total_sinks:,}")
    print(f"  truly unreferenced:          {total_orphan_no_role:,}")
    print(f"    (in_deg=0 AND no RPC, option, or protocol invocation)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
