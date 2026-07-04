#!/usr/bin/env python3
# Canonical schema_version 1 TSV emission.
# Spec: docs/reference/schema-v1-normalization-spec.md § 5

"""The one writer every final export artifact flows through.

Enforces the emission contract so LF/sort/format compliance is a
property of the pipeline choke point, not of each producer's
discipline (the CRLF split proved at least two toolchains emit):

  - UTF-8, tab-separated, LF line endings, trailing newline
  - rows sorted bytewise (LC_ALL=C semantics: UTF-8 encoded bytes)
    on the declared key, full-row tiebreak for duplicate keys
  - blank = null (None serializes to the empty string)
  - values may not contain tabs or line breaks (the tab-in-value
    guard V6 gates on)
  - every row carries exactly the declared columns
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Sequence


class TsvValueError(ValueError):
    """A value or row violates the emission contract."""


def _serialize(value: Any) -> str:
    if value is None:
        return ""
    return value if isinstance(value, str) else str(value)


def write_tsv(
    path: Path | str,
    columns: Sequence[str],
    rows: Iterable[Sequence[Any]],
    key: Sequence[str],
) -> int:
    """Write rows to path per the contract. Returns the row count."""
    columns = list(columns)
    key_idx = [columns.index(k) if k in columns else _missing(k)
               for k in key]

    ncols = len(columns)
    prepared: list[list[str]] = []
    for row in rows:
        cells = [_serialize(v) for v in row]
        if len(cells) != ncols:
            raise TsvValueError(
                f"{path}: row has {len(cells)} cells, expected {ncols}: "
                f"{cells[:4]}…"
            )
        for cell in cells:
            if "\t" in cell or "\n" in cell or "\r" in cell:
                raise TsvValueError(
                    f"{path}: tab/newline inside value: {cell!r}"
                )
        prepared.append(cells)

    def sort_key(cells: list[str]) -> tuple:
        primary = tuple(cells[i].encode("utf-8") for i in key_idx)
        tiebreak = tuple(c.encode("utf-8") for c in cells)
        return primary + tiebreak

    prepared.sort(key=sort_key)

    out = Path(path)
    with out.open("w", encoding="utf-8", newline="\n") as f:
        f.write("\t".join(columns) + "\n")
        for cells in prepared:
            f.write("\t".join(cells) + "\n")
    return len(prepared)


def _missing(k: str):
    raise KeyError(f"sort key column not in columns: {k!r}")


def write_spec(path: Path | str, spec, rows: Iterable[dict]) -> int:
    """Write dict rows per a schema_v1.FileSpec. Returns the row count.

    Enforces the spec on top of write_tsv's format contract:
      - cells ordered by spec.columns; missing keys emit blank (null)
      - unknown keys are rejected (they would be silently dropped)
      - _label columns are derived from their code column via
        spec.labels unless the row provides an explicit value
      - boolean columns must be Y / N / blank
    """
    columns = spec.columns
    known = set(columns)

    prepared: list[list[str]] = []
    for row in rows:
        extra = set(row) - known
        if extra:
            raise TsvValueError(
                f"{path}: keys not in {spec.name} columns: {sorted(extra)}"
            )
        cells = {c: _serialize(row.get(c)) for c in columns}
        for code_col, (label_col, mapping) in spec.labels.items():
            if label_col not in row or row.get(label_col) is None:
                cells[label_col] = mapping.get(cells[code_col], "")
        for col in spec.booleans:
            if cells[col] not in ("", "Y", "N"):
                raise TsvValueError(
                    f"{path}: {spec.name}.{col} must be Y/N/blank, "
                    f"got {cells[col]!r}"
                )
        prepared.append([cells[c] for c in columns])

    return write_tsv(path, columns, prepared, key=spec.sort)


def read_tsv(path: Path | str) -> tuple[list[str], list[list[str]]]:
    """Read a TSV; tolerates legacy CRLF input. Returns (columns, rows)."""
    with Path(path).open("r", encoding="utf-8", newline="") as f:
        lines = f.read().splitlines()
    if not lines:
        return [], []
    header = lines[0].split("\t")
    rows = [line.split("\t") for line in lines[1:]]
    return header, rows
