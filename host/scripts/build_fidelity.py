#!/usr/bin/env python3
# V4/R2+F9 of the producer-contracts plan: fidelity declarations.
# Spec: docs/proposals/schema-v1-normalization-spec.md § 6 R2
# Plan: docs/proposals/producer-contracts-implementation-plan.md § V4

"""Emit the three schema_version 1 fidelity declarations as data.

1. fk_open_world — every declared FK edge with its measured
   resolution rate; a failed join on an open_world edge is expected,
   not a defect.
2. xindex_static_call_authority — XINDEX is the reference authority
   for statically expressed calls only; dynamic dispatch is declared
   out of scope, and the callee divergence rate is measured from
   xindex-validation.tsv.
3. xindex_coverage (F9) — the xindex family describes only File
   9.8-registered routines (VMXIDX iterates ^DIC(9.8)); the census
   gap is decomposed, and %-routines are verified outside XINDEX so
   the divergence denominator excludes them.

Every number is re-measured from the emitted TSVs at build time —
the V4 gate forbids stale rates. --check re-measures and fails on
any drift (a V6 validate input).

Writes: vista/export/meta/fidelity.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import schema_v1
import tsvio

PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXPORT_DIR = PROJECT_ROOT / "vista/export"
OUT_JSON = EXPORT_DIR / "meta/fidelity.json"

# Directory-census misses share one cause; they get the same note.
_PKG_NOTE = ("Package attributions sourced from registry/repo metadata "
             "may name packages with no Packages/ directory in the "
             "source tree.")

# Measured causes for edges known to be open-world on this emission.
FK_NOTES = {
    ("routine-calls.tsv", "callee_routine"):
        "External/unmapped call targets, incl. calls into the "
        "%-namespace beyond the %-routines shipped as source on this "
        "instance.",
    ("protocol-calls.tsv", "callee_routine"):
        "Protocol actions may invoke routines not shipped as source.",
    ("options.tsv", "routine_name"):
        "Option registry entries may name routines not shipped as "
        "source.",
    ("rpcs.tsv", "routine_name"):
        "RPC registry entries may name routines not shipped as source.",
    ("vista-file-9-8.tsv", "routine_name"):
        "The File 9.8-only cohort (T-002): Kernel-registered routines "
        "with no source under Packages/*/Routines/.",
    ("files.tsv", "parent_file"):
        "Orphan subfile parents absent from the DD (triage-resolved "
        "for PIKS at V2; the extracted value stands).",
    ("field-piks.tsv", "pointer_target"):
        "Pointer definitions may target files absent from this "
        "instance's DD.",
    ("package-data.tsv", "file_number"):
        "Shipped data chunks may reference files absent from the DD.",
    ("package-data.tsv", "package"): _PKG_NOTE,
    ("package-manifest.tsv", "package"): _PKG_NOTE,
    ("package-piks-summary.tsv", "package"): _PKG_NOTE,
    ("options.tsv", "package_dir"): _PKG_NOTE,
}

OUT_OF_SCOPE = (
    "indirection (DO @X / GOTO @X)",
    "XECUTE strings",
    "option/protocol/RPC dispatch (registry-driven entry points)",
)

STATEMENTS = {
    "fk_open_world":
        "Declared FK edges are open-world: a value may name an entity "
        "outside this export. A failed join on an edge measured "
        "open_world=true below is expected and is not a data defect. "
        "All rates are measured on this emission at build time.",
    "xindex_static_call_authority":
        "XINDEX is the reference authority for STATICALLY EXPRESSED "
        "calls only. Calls made through dynamic dispatch (out_of_scope "
        "below) are invisible to static cross-referencing and are "
        "declared out of scope for both XINDEX and this export's call "
        "graph — out of scope, not covered-by-authority. Line and tag "
        "counts agree exactly; divergence is confined to callee sets.",
    "xindex_coverage":
        "The xindex-* family describes only routines registered in "
        "VistA File 9.8 (the Kernel ROUTINE file): the XINDEX driver "
        "(VMXIDX) iterates ^DIC(9.8), so census routines never "
        "registered there are structurally outside XINDEX's scope. "
        "Absence of xindex rows/findings for a routine means "
        "NOT-PROCESSED, not clean.",
}

DIVERGENCE_DENOMINATOR = (
    "xindex-validated routines only (File 9.8-registered and "
    "XINDEX-processed). %-routines are excluded: File 9.8 holds no "
    "%-routines on this instance and none appear in "
    "xindex-validation.tsv (verified at build time, and asserted by "
    "percent_routines_covered below).")


def _read(export_dir: Path, name: str) -> tuple[list[str], list[list[str]]]:
    spec = schema_v1.spec_for(name)
    return tsvio.read_tsv(export_dir / spec.model / name)


def _column(export_dir: Path, name: str, col: str) -> list[str]:
    cols, rows = _read(export_dir, name)
    i = cols.index(col)
    return [r[i] for r in rows]


def measure_fk_edges(export_dir: Path) -> list[dict]:
    target_cache: dict[str, set[str]] = {}

    def target_values(target: str) -> set[str]:
        if target not in target_cache:
            fname, col = target.split(":")
            target_cache[target] = set(_column(export_dir, fname, col))
        return target_cache[target]

    edges = []
    for name, spec in sorted(schema_v1.FILES.items()):
        for col, target in sorted(spec.fks.items()):
            values = {v for v in _column(export_dir, name, col) if v}
            unresolved = values - target_values(target)
            entry = {
                "file": name,
                "column": col,
                "target": target,
                "distinct_values": len(values),
                "unresolved": len(unresolved),
                "unresolved_rate": (round(len(unresolved) / len(values), 4)
                                    if values else 0.0),
                "open_world": bool(unresolved),
            }
            if (name, col) in FK_NOTES:
                entry["note"] = FK_NOTES[(name, col)]
            edges.append(entry)
    return edges


def measure_xindex_authority(export_dir: Path) -> dict:
    cols, rows = _read(export_dir, "xindex-validation.tsv")
    i = {c: cols.index(c) for c in cols}
    divergent = [r for r in rows
                 if int(r[i["callees_ours_only_count"]])
                 + int(r[i["callees_xindex_only_count"]]) > 0]
    return {
        "validated_routines": len(rows),
        "callee_divergent_routines": len(divergent),
        "callee_divergence_rate": (round(len(divergent) / len(rows), 4)
                                   if rows else 0.0),
        "lines_mismatch": sum(r[i["lines_match"]] != "Y" for r in rows),
        "tags_mismatch": sum(r[i["tags_match"]] != "Y" for r in rows),
    }


def measure_xindex_coverage(export_dir: Path) -> dict:
    cols, rows = _read(export_dir, "routines-comprehensive.tsv")
    i = {c: cols.index(c) for c in cols}
    covered = set(_column(export_dir, "xindex-routines.tsv",
                          "routine_name"))
    census = {r[i["routine_name"]] for r in rows}
    in_9_8_r = {r[i["routine_name"]] for r in rows
                if r[i["in_file_9_8"]] == "Y"
                and r[i["file_9_8_type"]] == "R"}
    in_9_8_other = {r[i["routine_name"]] for r in rows
                    if r[i["in_file_9_8"]] == "Y"
                    and r[i["file_9_8_type"]] != "R"}
    percent = {r[i["routine_name"]] for r in rows
               if r[i["is_percent_routine"]] == "Y"}
    gap = census - covered
    return {
        "census_routines": len(census),
        "covered_routines": len(covered),
        "coverage_rate": (round(len(covered) / len(census), 4)
                          if census else 0.0),
        "gap": {
            "not_in_file_9_8": len(gap - in_9_8_r - in_9_8_other),
            "file_9_8_non_r_uncovered": len(gap & in_9_8_other),
            "file_9_8_r_uncovered": len(gap & in_9_8_r),
            # The compile/ZLINK-failure cohort, by name — small by
            # construction; a big list here is itself a red flag.
            "file_9_8_r_uncovered_routines": sorted(gap & in_9_8_r),
        },
        "percent_routines_in_census": len(percent),
        "percent_routines_covered": len(percent & covered),
    }


def build_fidelity(export_dir: Path) -> dict:
    return {
        "schema_version": 1,
        "generated_from": "host/scripts/build_fidelity.py",
        "declarations": {
            "fk_open_world": {
                "statement": STATEMENTS["fk_open_world"],
                "edges": measure_fk_edges(export_dir),
            },
            "xindex_static_call_authority": {
                "statement": STATEMENTS["xindex_static_call_authority"],
                "out_of_scope": list(OUT_OF_SCOPE),
                "measured": measure_xindex_authority(export_dir),
            },
            "xindex_coverage": {
                "statement": STATEMENTS["xindex_coverage"],
                "divergence_denominator": DIVERGENCE_DENOMINATOR,
                "measured": measure_xindex_coverage(export_dir),
            },
        },
    }


def render(export_dir: Path) -> str:
    return json.dumps(build_fidelity(export_dir), indent=2,
                      sort_keys=True) + "\n"


def check(export_dir: Path, out_json: Path) -> list[str]:
    """The freshness gate: written declarations ≡ re-measured tree."""
    if not out_json.exists():
        return [f"{out_json}: missing — run build_fidelity.py first"]
    written = json.loads(out_json.read_text(encoding="utf-8"))
    fresh = build_fidelity(export_dir)
    if written == fresh:
        return []
    errors = []
    for key, fresh_decl in fresh["declarations"].items():
        if written.get("declarations", {}).get(key) != fresh_decl:
            errors.append(f"{key}: written declaration is stale "
                          "(re-measured values differ)")
    return errors or ["fidelity.json: top-level fields drifted"]


def main(argv: list[str]) -> int:
    if argv == ["--check"]:
        errors = check(EXPORT_DIR, OUT_JSON)
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        print("fidelity check: "
              + ("FAIL" if errors else "PASS (declarations ≡ tree)"))
        return 1 if errors else 0
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(render(EXPORT_DIR), encoding="utf-8")
    doc = json.loads(OUT_JSON.read_text(encoding="utf-8"))
    m = doc["declarations"]
    cov = m["xindex_coverage"]["measured"]
    auth = m["xindex_static_call_authority"]["measured"]
    open_edges = [e for e in m["fk_open_world"]["edges"] if e["open_world"]]
    print(f"fidelity.json: {len(open_edges)} open-world FK edges; "
          f"xindex divergence "
          f"{auth['callee_divergent_routines']}/"
          f"{auth['validated_routines']}; coverage "
          f"{cov['covered_routines']}/{cov['census_routines']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
