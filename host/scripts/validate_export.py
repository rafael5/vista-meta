#!/usr/bin/env python3
# V6 of the producer-contracts plan: the validate step.
# Plan: docs/historical/producer-contracts-implementation-plan.md § V6

"""Pre-release validation of the full schema_version 1 contract.

Asserts, against the emitted tree:
  - file set ≡ schema (all 24 TSVs, no extras)
  - headers ≡ schema (R1)
  - per-row column-count consistency (tab-in-value guard)
  - PK uniqueness on every declared pk
  - non-nullable columns carry no blanks
  - booleans ∈ {Y, N, blank}
  - LF-only bytes, final newline, canonical bytewise sort (tsvio order)
  - enum values ∈ documented domains — WARNING only (open-world)
  - PIKS materialized: piks.tsv coverage ≡ files.tsv (B1)
  - cross-file referential integrity (F8): every FK edge NOT declared
    open-world in schema_v1.OPEN_WORLD_FKS must resolve 100% — this is
    the vintage-skew catch (files emitted from different engine states)
  - routines-comprehensive keys ≡ routines keys
  - meta freshness: column-manifest.json and fidelity.json ≡ tree
  - R3 engine-identity fields present (raw/extraction.json until V7
    folds them into manifest.json)

Exit 0 with "PASS" on a good emission; exit 1 listing every defect.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

import build_column_manifest
import build_fidelity
import schema_v1
from capture_extraction import R3_FIELDS

PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXPORT_DIR = PROJECT_ROOT / "vista/export"


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    rows_checked: int = 0


def _sort_key(cells: list[str], key_idx: list[int]) -> tuple:
    # Mirrors tsvio.write_tsv exactly: declared key, full-row tiebreak,
    # UTF-8 bytes (LC_ALL=C semantics).
    return (tuple(cells[i].encode("utf-8") for i in key_idx)
            + tuple(c.encode("utf-8") for c in cells))


def _check_file(spec: schema_v1.FileSpec, path: Path,
                report: Report) -> list[list[str]] | None:
    """Per-file contract checks. Returns rows for cross-file checks,
    or None if the file is unusable (missing / header drift)."""
    name = spec.name
    if not path.exists():
        report.errors.append(f"{name}: missing from tree")
        return None

    data = path.read_bytes()
    if b"\r" in data:
        report.errors.append(f"{name}: CR byte found (LF-only contract)")
    if not data.endswith(b"\n"):
        report.errors.append(f"{name}: missing final newline")

    lines = data.decode("utf-8").split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    header = lines[0].split("\t") if lines else []
    if header != list(spec.columns):
        report.errors.append(
            f"{name}: header != schema columns "
            f"(+{set(header) - set(spec.columns) or '{}'} "
            f"-{set(spec.columns) - set(header) or '{}'})")
        return None

    ncols = len(spec.columns)
    pk_idx = [spec.columns.index(c) for c in spec.pk]
    key_idx = [spec.columns.index(c) for c in spec.sort]
    non_null_idx = [(i, c) for i, c in enumerate(spec.columns)
                    if c not in spec.nullable]
    bool_idx = [spec.columns.index(c) for c in spec.booleans]
    enum_idx = [(spec.columns.index(c), c, dom)
                for (f, c), dom in schema_v1.ENUM_DOMAINS.items()
                if f == name]

    rows: list[list[str]] = []
    seen_pks: set[tuple] = set()
    prev_key: tuple | None = None
    sort_ok = True
    enum_offenders: dict[str, set[str]] = {}
    for lineno, line in enumerate(lines[1:], start=2):
        cells = line.split("\t")
        if len(cells) != ncols:
            report.errors.append(
                f"{name}: row at line {lineno} has {len(cells)} cells, "
                f"expected {ncols}")
            continue
        rows.append(cells)
        if pk_idx:
            pk = tuple(cells[i] for i in pk_idx)
            if pk in seen_pks:
                report.errors.append(
                    f"{name}: duplicate primary key {pk} at line {lineno}")
            seen_pks.add(pk)
        for i, col in non_null_idx:
            if cells[i] == "":
                report.errors.append(
                    f"{name}.{col}: blank value in non-nullable column "
                    f"at line {lineno}")
        for i in bool_idx:
            if cells[i] not in ("", "Y", "N"):
                report.errors.append(
                    f"{name}.{spec.columns[i]}: boolean column must be "
                    f"Y/N/blank, got {cells[i]!r} at line {lineno}")
        for i, col, dom in enum_idx:
            if cells[i] and cells[i] not in dom:
                enum_offenders.setdefault(col, set()).add(cells[i])
        if sort_ok:
            k = _sort_key(cells, key_idx)
            if prev_key is not None and k < prev_key:
                report.errors.append(
                    f"{name}: rows not in canonical sort order "
                    f"(first violation at line {lineno})")
                sort_ok = False
            prev_key = k

    for col, vals in sorted(enum_offenders.items()):
        report.warnings.append(
            f"{name}.{col}: value(s) outside the documented enum domain "
            f"(open-world, tolerated): {sorted(vals)[:6]}")
    report.rows_checked += len(rows)
    return rows


def _cross_file_checks(tables: dict[str, list[list[str]] | None],
                       report: Report) -> None:
    def column(name: str, col: str) -> list[str] | None:
        rows = tables.get(name)
        if rows is None:
            return None
        i = schema_v1.spec_for(name).columns.index(col)
        return [r[i] for r in rows]

    # Closed-world referential integrity (F8) — the vintage-skew catch.
    for name, spec in sorted(schema_v1.FILES.items()):
        for col, target in sorted(spec.fks.items()):
            if (name, col) in schema_v1.OPEN_WORLD_FKS:
                continue
            tf, tc = target.split(":")
            values, targets = column(name, col), column(tf, tc)
            if values is None or targets is None:
                continue  # already reported as missing/header drift
            unresolved = {v for v in values if v} - set(targets)
            if unresolved:
                report.errors.append(
                    f"{name}.{col}: {len(unresolved)} value(s) not in "
                    f"{target} (closed-world FK), e.g. "
                    f"{sorted(unresolved)[:5]}")

    # B1: PIKS materialized, coverage ≡ files.tsv (both directions).
    piks = column("piks.tsv", "file_number")
    files = column("files.tsv", "file_number")
    if piks is not None and files is not None and set(piks) != set(files):
        only_f = len(set(files) - set(piks))
        only_p = len(set(piks) - set(files))
        report.errors.append(
            f"piks.tsv coverage != files.tsv: {only_f} file(s) without a "
            f"piks row, {only_p} piks row(s) without a file")

    # F8: the comprehensive view keys ≡ the census keys.
    comp = column("routines-comprehensive.tsv", "routine_name")
    census = column("routines.tsv", "routine_name")
    if comp is not None and census is not None and set(comp) != set(census):
        report.errors.append(
            f"routines-comprehensive.tsv keys != routines.tsv census "
            f"({len(set(census) - set(comp))} missing, "
            f"{len(set(comp) - set(census))} extra)")


def _meta_checks(export_dir: Path, report: Report) -> None:
    cm = export_dir / "meta/column-manifest.json"
    if (not cm.exists()
            or cm.read_text(encoding="utf-8")
            != build_column_manifest.render()):
        report.errors.append(
            "meta/column-manifest.json: missing or stale (!= schema_v1)")
    try:
        report.errors.extend(
            f"fidelity.json: {e}"
            for e in build_fidelity.check(export_dir,
                                          export_dir / "meta/fidelity.json"))
    except Exception as exc:  # unreadable tree already reported above
        report.errors.append(f"fidelity.json: could not re-measure ({exc})")

    # R3 source: a producer tree carries raw/extraction.json; a
    # consumer tree (unpacked V7 bundle) carries manifest.json, which
    # holds the same engine-pinning fields (extraction_source_commit
    # aliases the sidecar's source_commit there).
    manifest = export_dir / "manifest.json"
    sidecar = export_dir / "raw/extraction.json"
    if manifest.exists():
        src, doc = "manifest.json", json.loads(
            manifest.read_text(encoding="utf-8"))
        doc.setdefault("source_commit",
                       doc.get("extraction_source_commit"))
    elif sidecar.exists():
        src, doc = "raw/extraction.json", json.loads(
            sidecar.read_text(encoding="utf-8"))
    else:
        report.errors.append(
            "raw/extraction.json: missing (and no manifest.json) — R3 "
            "engine identity cannot be reconstructed after the fact")
        return
    for f in R3_FIELDS:
        if not doc.get(f):
            report.errors.append(
                f"{src}: R3 field {f} missing or empty")


def validate(export_dir: Path) -> Report:
    report = Report()
    tables: dict[str, list[list[str]] | None] = {}
    for name, spec in sorted(schema_v1.FILES.items()):
        tables[name] = _check_file(spec, export_dir / spec.model / name,
                                   report)
    for model in ("data-model", "code-model"):
        for p in sorted((export_dir / model).glob("*.tsv")):
            spec = schema_v1.FILES.get(p.name)
            if spec is None or spec.model != model:
                report.errors.append(
                    f"{model}/{p.name}: not part of schema_version 1")
    _cross_file_checks(tables, report)
    _meta_checks(export_dir, report)
    return report


def main() -> int:
    report = validate(EXPORT_DIR)
    for w in report.warnings:
        print(f"WARN: {w}")
    for e in report.errors:
        print(f"ERROR: {e}", file=sys.stderr)
    n = len(schema_v1.FILES)
    print(f"validate: "
          + ("FAIL" if report.errors else "PASS")
          + f" ({n} files, {report.rows_checked} rows, "
          f"{len(report.errors)} error(s), "
          f"{len(report.warnings)} warning(s))")
    return 1 if report.errors else 0


if __name__ == "__main__":
    sys.exit(main())
