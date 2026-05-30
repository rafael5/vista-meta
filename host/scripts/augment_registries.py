#!/usr/bin/env python3
# P1 + P2 of upstream-data-fixes: package association + canonical package_dir
# on the authoritative registries (rpcs / options / protocols).
# Companion to build_package_namespace.py (P3/P4).

"""Augment rpcs.tsv, options.tsv, protocols.tsv with package columns.

Backward-compatible / byte-parity safe: only *appends* columns; existing
columns (including the upper-case `package` on options/protocols) are left
untouched, so neither downstream tool's goldens move.

Added columns (uniform meaning across all three files):

  package_dir   canonical package **directory name** — byte-identical to
                packages.tsv's `package`, so consumers can finally join.
  package       (rpcs only — it had none) the upper-case PACKAGE-file (#9.4)
                NAME, mirroring options/protocols' existing `package`.

Resolution:
  * options/protocols already store the upper #9.4 NAME in `package`; map it
    to the directory via docs/Packages.csv (Package Name -> Directory Name).
    Options also fall back to their `routine`'s package where `package` is
    blank or unmapped.
  * rpcs carry only a `routine`; resolve routine -> directory via routines.tsv,
    then directory -> upper #9.4 NAME via docs/Packages.csv.

Reads (defaults overridable via VM_CODE_MODEL_DIR for staging):
  - docs/Packages.csv
  - vista/export/code-model/{routines,rpcs,options,protocols}.tsv

Rewrites in place:
  - vista/export/code-model/{rpcs,options,protocols}.tsv

This script is idempotent: re-running strips previously-added columns before
re-appending, so the output is stable.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from build_package_namespace import parse_packages_csv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PACKAGES_CSV = PROJECT_ROOT / "docs/Packages.csv"
CODE_MODEL_DIR = Path(
    os.environ.get(
        "VM_CODE_MODEL_DIR", str(PROJECT_ROOT / "vista/export/code-model")
    )
)


# ── map builders ──────────────────────────────────────────────────────
def build_name_to_dir(parsed: dict[str, dict]) -> dict[str, str]:
    """Upper-case #9.4 NAME -> directory name."""
    out: dict[str, str] = {}
    for d, e in parsed.items():
        name = e.get("package_name", "")
        if name:
            out[name] = d
    return out


def build_dir_to_name(parsed: dict[str, dict]) -> dict[str, str]:
    """Directory name -> upper-case #9.4 NAME."""
    return {d: e.get("package_name", "") for d, e in parsed.items()}


def build_routine_to_dir(routines_rows: list[dict]) -> dict[str, str]:
    return {r["routine_name"]: r["package"] for r in routines_rows}


# ── per-file augmentation (pure) ──────────────────────────────────────
def _without(fields: list[str], drop: list[str]) -> list[str]:
    return [f for f in fields if f not in drop]


def augment_options(
    fields: list[str], rows: list[dict],
    name_to_dir: dict[str, str], routine_to_dir: dict[str, str],
) -> tuple[list[str], list[dict]]:
    base = _without(fields, ["package_dir"])
    for r in rows:
        pkg_dir = name_to_dir.get(r.get("package", ""), "")
        if not pkg_dir:
            pkg_dir = routine_to_dir.get(r.get("routine", ""), "")
        r["package_dir"] = pkg_dir
    return base + ["package_dir"], rows


def augment_protocols(
    fields: list[str], rows: list[dict], name_to_dir: dict[str, str],
) -> tuple[list[str], list[dict]]:
    base = _without(fields, ["package_dir"])
    for r in rows:
        r["package_dir"] = name_to_dir.get(r.get("package", ""), "")
    return base + ["package_dir"], rows


def augment_rpcs(
    fields: list[str], rows: list[dict],
    routine_to_dir: dict[str, str], dir_to_name: dict[str, str],
) -> tuple[list[str], list[dict]]:
    base = _without(fields, ["package", "package_dir"])
    for r in rows:
        pkg_dir = routine_to_dir.get(r.get("routine", ""), "")
        r["package_dir"] = pkg_dir
        r["package"] = dir_to_name.get(pkg_dir, "") if pkg_dir else ""
    return base + ["package", "package_dir"], rows


# ── raw line-oriented IO ──────────────────────────────────────────────
# We *append* columns by concatenating a tab + value onto each original line,
# never re-serializing the existing fields. This guarantees the existing
# columns are byte-for-byte preserved (Python's csv writer would otherwise
# quote any field containing a `"`, silently breaking downstream byte-parity
# goldens). Safe because the M dumps strip tab/newline from every field, and
# the values we append (directory / #9.4 names) contain neither.

def split_table(text: str) -> tuple[list[str], list[str], bool]:
    parts = text.split("\n")
    trailing_nl = parts and parts[-1] == ""
    if trailing_nl:
        parts = parts[:-1]
    header = parts[0].split("\t") if parts else []
    data = parts[1:]
    return header, data, trailing_nl


def strip_tail_added(
    header: list[str], data: list[str], added_cols: list[str]
) -> tuple[list[str], list[str]]:
    """Drop any of `added_cols` already present as trailing columns (idempotency)."""
    n = 0
    h = list(header)
    while h and h[-1] in added_cols:
        h.pop()
        n += 1
    if n == 0:
        return header, data
    stripped = [ln.rsplit("\t", n)[0] for ln in data]
    return h, stripped


def parse_rows(header: list[str], data: list[str]) -> list[dict]:
    return [dict(zip(header, ln.split("\t"))) for ln in data]


def render_table(
    base_header: list[str], base_data: list[str],
    added_cols: list[str], rows: list[dict], trailing_nl: bool,
) -> str:
    lines = ["\t".join(base_header + added_cols)]
    for ln, row in zip(base_data, rows):
        lines.append(ln + "".join("\t" + row.get(c, "") for c in added_cols))
    text = "\n".join(lines)
    if trailing_nl:
        text += "\n"
    return text


def _coverage(rows: list[dict], col: str) -> int:
    return sum(1 for r in rows if r.get(col))


def main() -> int:
    for p in (PACKAGES_CSV, CODE_MODEL_DIR / "routines.tsv"):
        if not p.exists():
            print(f"ERROR: {p} not found.", file=sys.stderr)
            return 1

    parsed = parse_packages_csv(PACKAGES_CSV)
    name_to_dir = build_name_to_dir(parsed)
    dir_to_name = build_dir_to_name(parsed)
    routines_text = (CODE_MODEL_DIR / "routines.tsv").read_text(encoding="utf-8")
    rh, rd, _ = split_table(routines_text)
    routine_to_dir = build_routine_to_dir(parse_rows(rh, rd))

    def run(name: str, added: list[str], pure):
        path = CODE_MODEL_DIR / name
        header, data, nl = split_table(path.read_text(encoding="utf-8"))
        base_header, base_data = strip_tail_added(header, data, added)
        rows = parse_rows(base_header, base_data)
        full_fields, rows = pure(base_header, rows)
        assert full_fields == base_header + added, (full_fields, base_header, added)
        path.write_text(
            render_table(base_header, base_data, added, rows, nl), encoding="utf-8"
        )
        print(f"{name+':':14} {len(rows):,} rows, "
              f"{_coverage(rows, 'package_dir')} with package_dir")

    run("rpcs.tsv", ["package", "package_dir"],
        lambda f, r: augment_rpcs(f, r, routine_to_dir, dir_to_name))
    run("options.tsv", ["package_dir"],
        lambda f, r: augment_options(f, r, name_to_dir, routine_to_dir))
    run("protocols.tsv", ["package_dir"],
        lambda f, r: augment_protocols(f, r, name_to_dir))
    return 0


if __name__ == "__main__":
    sys.exit(main())
