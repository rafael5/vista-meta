#!/usr/bin/env python3
# Phase 6a of ADR-045: the code↔data bridge in its full per-package form.
# Joins routines, packages, data-shipments, PIKS distribution, RPC roles,
# option roles, global touches, and call-graph fan-out into one TSV.
# Spec: docs/vista-meta-spec-v0.4.md § 11

"""Build packages-manifest.tsv — one row per package, all sources joined.

Canonical package name = filesystem directory (routines.tsv.package).
For rpcs/options/protocols whose own PACKAGE field uses File 9.4's
uppercase convention (RF-018), we join via the ROUTINE field through
routines.tsv to get the canonical package — sidestepping the
case-mismatch.

Reads (all from vista/export/code-model/):
  - packages.tsv            (routine counts, total lines)
  - routines.tsv            (routine → package mapping)
  - package-piks-summary.tsv (PIKS distribution of shipped files)
  - rpcs.tsv                (File 8994 routines)
  - options.tsv             (File 19 routines, filtered to TYPE=R)
  - routine-globals.tsv     (routine → global edges)
  - routine-calls.tsv       (routine → routine edges)

Writes:
  - vista/export/code-model/package-manifest.tsv  (~176 rows × 13 cols)
"""

from __future__ import annotations

import csv
import sys
from collections import defaultdict
from pathlib import Path

NORM = Path(__file__).resolve().parents[2] / "vista/export/code-model"
OUT_TSV = NORM / "package-manifest.tsv"

FIELDS = [
    "package",
    "routine_count",
    "total_lines",
    "files_shipped",
    "p_files",
    "i_files",
    "k_files",
    "s_files",
    "rpc_routines",
    "option_routines",
    "distinct_globals_touched",
    "outbound_edges",
    "outbound_cross_pkg",
]


def load_tsv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def main() -> int:
    for f in ("packages.tsv", "routines.tsv", "package-piks-summary.tsv",
              "rpcs.tsv", "options.tsv", "routine-globals.tsv",
              "routine-calls.tsv"):
        if not (NORM / f).exists():
            print(f"ERROR: {NORM/f} missing. Upstream phase incomplete.",
                  file=sys.stderr)
            return 1

    # Authoritative routine → package map (from MANIFEST-based inventory).
    rou_pkg: dict[str, str] = {}
    for r in load_tsv(NORM / "routines.tsv"):
        rou_pkg[r["routine_name"]] = r["package"]

    # Seed manifest from packages.tsv (174 routine-bearing packages).
    manifest: dict[str, dict] = {}
    for r in load_tsv(NORM / "packages.tsv"):
        manifest[r["package"]] = {
            "package": r["package"],
            "routine_count": int(r["routine_count"]),
            "total_lines": int(r["total_lines"]),
            "files_shipped": 0, "p_files": 0, "i_files": 0, "k_files": 0, "s_files": 0,
            "rpc_routines": 0, "option_routines": 0,
            "distinct_globals_touched": 0, "outbound_edges": 0, "outbound_cross_pkg": 0,
        }

    # PIKS distribution of files shipped. Some globals-only packages in
    # package-piks-summary aren't in packages.tsv (no routines) — add them.
    for r in load_tsv(NORM / "package-piks-summary.tsv"):
        pkg = r["package"]
        if pkg not in manifest:
            manifest[pkg] = {
                "package": pkg, "routine_count": 0, "total_lines": 0,
                "files_shipped": 0, "p_files": 0, "i_files": 0, "k_files": 0, "s_files": 0,
                "rpc_routines": 0, "option_routines": 0,
                "distinct_globals_touched": 0, "outbound_edges": 0, "outbound_cross_pkg": 0,
            }
        m = manifest[pkg]
        m["files_shipped"] = int(r["total_distinct_files"])
        m["p_files"] = int(r["p_files"])
        m["i_files"] = int(r["i_files"])
        m["k_files"] = int(r["k_files"])
        m["s_files"] = int(r["s_files"])

    # RPC-backing routines, counted per package via the canonical
    # routines.tsv lookup (skips routines not in MANIFEST — T-002 cohort).
    rpc_rous_per_pkg: dict[str, set[str]] = defaultdict(set)
    for r in load_tsv(NORM / "rpcs.tsv"):
        rou = r["routine"]
        if rou and rou in rou_pkg:
            rpc_rous_per_pkg[rou_pkg[rou]].add(rou)
    for pkg, rous in rpc_rous_per_pkg.items():
        if pkg in manifest:
            manifest[pkg]["rpc_routines"] = len(rous)

    # Option-backing routines (TYPE=R), same pattern.
    opt_rous_per_pkg: dict[str, set[str]] = defaultdict(set)
    for r in load_tsv(NORM / "options.tsv"):
        if r["type"] != "R":
            continue
        rou = r["routine"]
        if rou and rou in rou_pkg:
            opt_rous_per_pkg[rou_pkg[rou]].add(rou)
    for pkg, rous in opt_rous_per_pkg.items():
        if pkg in manifest:
            manifest[pkg]["option_routines"] = len(rous)

    # Distinct globals touched per package (routine-globals grouped by
    # caller's package).
    globals_per_pkg: dict[str, set[str]] = defaultdict(set)
    for r in load_tsv(NORM / "routine-globals.tsv"):
        globals_per_pkg[r["package"]].add(r["global_name"])
    for pkg, globs in globals_per_pkg.items():
        if pkg in manifest:
            manifest[pkg]["distinct_globals_touched"] = len(globs)

    # Outbound edges + cross-package subset. Edge counts are edge rows
    # (unique caller,callee,tag,kind tuples), not summed ref_counts —
    # gives a routine-level coupling signal instead of raw call volume.
    for r in load_tsv(NORM / "routine-calls.tsv"):
        src_pkg = r["caller_package"]
        callee = r["callee_routine"]
        if src_pkg not in manifest:
            continue
        manifest[src_pkg]["outbound_edges"] += 1
        dst_pkg = rou_pkg.get(callee, "")
        if dst_pkg and dst_pkg != src_pkg:
            manifest[src_pkg]["outbound_cross_pkg"] += 1

    rows = sorted(manifest.values(), key=lambda r: r["package"])
    with OUT_TSV.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, delimiter="\t")
        w.writeheader()
        w.writerows(rows)

    # Summary to stdout.
    total_rpc = sum(r["rpc_routines"] for r in rows)
    total_opt = sum(r["option_routines"] for r in rows)
    total_out = sum(r["outbound_edges"] for r in rows)
    total_xpk = sum(r["outbound_cross_pkg"] for r in rows)
    print(f"package-manifest.tsv: {len(rows)} packages")
    print(f"  rpc_routines sum:         {total_rpc:,}")
    print(f"  option_routines sum:      {total_opt:,}")
    print(f"  outbound_edges sum:       {total_out:,}")
    print(f"  outbound_cross_pkg sum:   {total_xpk:,} "
          f"({100*total_xpk/total_out:.1f}% cross-package)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
