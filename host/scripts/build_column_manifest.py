#!/usr/bin/env python3
# V3/R1 of the producer-contracts plan: the typed column manifest.
# Spec: docs/reference/schema-v1-normalization-spec.md § 6 R1

"""Emit the machine-checkable typed column manifest as data.

Generated entirely from schema_v1 (the single source of truth), so a
schema change is made once and the manifest follows. For every file:
each column's name, type (str/int/float/enum/bool), nullable, and
key_role (pk / fk with target / none). fk targets may name the four
cross-producer vocabularies (routine_name, file_number, option name,
rpc name) — the thin, non-deferred slice of the entity-identity
contract; those columns are additionally marked shared_vocabulary on
their authoritative side.

This is a typed column list, deliberately NOT a full JSON-schema.

Writes:  vista/export/meta/column-manifest.json
Gate:    --check verifies manifest ≡ actual emitted headers (every
         file present, every column, emit order) — the V3 gate, and
         a V6 validate input.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import schema_v1
import tsvio

PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXPORT_DIR = PROJECT_ROOT / "vista/export"
OUT_JSON = EXPORT_DIR / "meta/column-manifest.json"

_VOCAB = set(schema_v1.SHARED_VOCABULARIES)


def _column_entry(spec: schema_v1.FileSpec, col: str) -> dict:
    entry = {
        "name": col,
        "type": spec.effective_type(col),
        "nullable": col in spec.nullable,
        "key_role": spec.key_role(col),
    }
    if col in spec.fks:
        entry["fk_target"] = spec.fks[col]
    if (spec.name, col) in _VOCAB:
        entry["shared_vocabulary"] = True
    return entry


def build_manifest() -> dict:
    return {
        "schema_version": 1,
        "generated_from": "host/scripts/schema_v1.py",
        "shared_vocabularies": [
            {"file": f, "column": c}
            for f, c in schema_v1.SHARED_VOCABULARIES],
        "files": {
            f"{spec.model}/{name}": {
                "pk": list(spec.pk),
                "columns": [_column_entry(spec, c) for c in spec.columns],
            }
            for name, spec in sorted(schema_v1.FILES.items())
        },
    }


def render() -> str:
    return json.dumps(build_manifest(), indent=2, sort_keys=True) + "\n"


def check_headers(export_dir: Path) -> list[str]:
    """The mechanical gate: manifest ≡ actual headers, all 24 files."""
    errors = []
    for name, spec in sorted(schema_v1.FILES.items()):
        p = export_dir / spec.model / name
        if not p.exists():
            errors.append(f"{spec.model}/{name}: missing from tree")
            continue
        cols, _ = tsvio.read_tsv(p)
        if cols != list(spec.columns):
            errors.append(
                f"{spec.model}/{name}: header != manifest "
                f"(+{set(cols) - set(spec.columns) or '{}'} "
                f"-{set(spec.columns) - set(cols) or '{}'})")
    return errors


def main(argv: list[str]) -> int:
    if argv == ["--check"]:
        errors = check_headers(EXPORT_DIR)
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        print("column-manifest check: "
              + ("FAIL" if errors else "PASS (24 files ≡ manifest)"))
        return 1 if errors else 0
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(render(), encoding="utf-8")
    n_cols = sum(len(s.columns) for s in schema_v1.FILES.values())
    print(f"column-manifest.json: 24 files, {n_cols} columns")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
