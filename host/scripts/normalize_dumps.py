#!/usr/bin/env python3
# V1.4 of the producer-contracts plan: host-side normalization of the
# M-dump-origin TSVs into their schema_version 1 final form.
# Spec: docs/proposals/schema-v1-normalization-spec.md § 2/§ 3/§ 5

"""Normalize raw M-dump TSVs into schema_version 1 finals.

The M routines (VMFILES/VMPIKS/VMFPIKS/VMDUMP*/VMXIDX) stay untouched
and emit their historical "raw" shape into vista/export/raw/; this
step owns every final-file concern the raw dumps lack:

  raw dump → augment (rpcs/options/protocols package columns, reusing
  augment_registries' pure functions) → rename per schema_v1 → drop
  per schema_v1 → tsvio.write_spec (LF, bytewise PK sort, _label
  derivation, boolean enforcement)

piks-triage.tsv is the one special case: it is hand-curated source,
not a dump, so it is canonicalized in place (data-model/) and never
deduplicated — V2's red-gate owns triage conflicts.

Bootstrap: raw inputs may also be current finals (already augmented /
renamed) — every step is a fixpoint, so re-normalizing is idempotent.

Reads:
  - vista/export/raw/<name> (or data-model/piks-triage.tsv)
  - vista/export/code-model/routines.tsv (routine → package lookup)
  - docs/Packages.csv (package name ↔ directory maps)

Writes:
  - vista/export/{data-model,code-model}/<name> per schema_v1
"""

from __future__ import annotations

import sys
from pathlib import Path

import materialize_piks
import schema_v1
import tsvio
from augment_registries import (
    augment_options,
    augment_protocols,
    augment_rpcs,
    build_dir_to_name,
    build_name_to_dir,
    build_routine_to_dir,
)
from build_package_namespace import parse_packages_csv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "vista/export/raw"
DATA_DIR = PROJECT_ROOT / "vista/export/data-model"
CODE_DIR = PROJECT_ROOT / "vista/export/code-model"
PACKAGES_CSV = PROJECT_ROOT / "docs/Packages.csv"

# Every M-dump-origin final, plus the curated triage file.
NORMALIZED_FILES = (
    "field-piks.tsv", "files.tsv", "piks.tsv", "piks-triage.tsv",
    "options.tsv", "protocols.tsv", "rpcs.tsv", "vista-file-9-8.tsv",
    "xindex-errors.tsv", "xindex-routines.tsv", "xindex-tags.tsv",
    "xindex-xrefs.tsv",
)


def _augment(name: str, fields: list[str], rows: list[dict],
             code_dir: Path, parsed: dict) -> list[dict]:
    """Package-column augmentation for the three registries (P1/P2)."""
    if name not in ("rpcs.tsv", "options.tsv", "protocols.tsv"):
        return rows
    # Bootstrap input may already be renamed; the augment functions
    # read the raw `routine` key, so un-rename first (the rename step
    # after augmentation restores the final name either way).
    for row in rows:
        if "routine" not in row and "routine_name" in row:
            row["routine"] = row.pop("routine_name")
    name_to_dir = build_name_to_dir(parsed)
    dir_to_name = build_dir_to_name(parsed)
    rcols, rrows = tsvio.read_tsv(code_dir / "routines.tsv")
    routine_to_dir = build_routine_to_dir(
        [dict(zip(rcols, r)) for r in rrows])
    if name == "rpcs.tsv":
        _, rows = augment_rpcs(fields, rows, routine_to_dir, dir_to_name)
    elif name == "options.tsv":
        _, rows = augment_options(fields, rows, name_to_dir, routine_to_dir)
    else:
        _, rows = augment_protocols(fields, rows, name_to_dir)
    return rows


def _read_dicts(path: Path) -> list[dict]:
    cols, rows = tsvio.read_tsv(path)
    return [dict(zip(cols, r)) for r in rows]


def normalize_file(name: str, raw_dir: Path, data_dir: Path,
                   code_dir: Path, parsed: dict) -> int:
    """Normalize one file; returns its row count."""
    spec = schema_v1.spec_for(name)
    out_dir = data_dir if spec.model == "data-model" else code_dir

    if name == "piks.tsv":
        # V2/B1: the final is the materialized merge, not the dump.
        # Inputs must come from ONE extraction: raw auto dump + raw
        # files.tsv (parent tree) + the curated triage file.
        rows = materialize_piks.merge(
            files_rows=_read_dicts(raw_dir / "files.tsv"),
            auto_rows=_read_dicts(raw_dir / "piks.tsv"),
            triage_rows=_read_dicts(data_dir / "piks-triage.tsv"))
        return tsvio.write_spec(out_dir / name, spec, rows)

    # piks-triage is curated source living at its final path.
    src = out_dir / name if name == "piks-triage.tsv" else raw_dir / name

    fields, raw_rows = tsvio.read_tsv(src)
    rows = [dict(zip(fields, r)) for r in raw_rows]

    rows = _augment(name, fields, rows, code_dir, parsed)

    for row in rows:
        # Rename (tolerant: bootstrap input may already be renamed).
        for old, new in spec.renames.items():
            if old in row:
                row[new] = row.pop(old)
        # Drop retired columns and anything outside the final set
        # (e.g. files.tsv's 10 empty classification columns).
        for k in list(row):
            if k not in spec.columns:
                row.pop(k)

    return tsvio.write_spec(out_dir / name, spec, rows)


def main(names: list[str] | None = None) -> int:
    todo = names or list(NORMALIZED_FILES)
    unknown = [n for n in todo if n not in NORMALIZED_FILES]
    if unknown:
        print(f"ERROR: not M-dump-normalized files: {unknown}",
              file=sys.stderr)
        return 1
    parsed = parse_packages_csv(PACKAGES_CSV)
    for name in todo:
        n = normalize_file(name, RAW_DIR, DATA_DIR, CODE_DIR, parsed)
        print(f"{name+':':22} {n:,} rows normalized")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or None))
