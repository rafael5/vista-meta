#!/usr/bin/env python3
# V2/B1 of the producer-contracts plan: materialize the PIKS merge.
# Spec: docs/reference/schema-v1-normalization-spec.md § 6 B1 (amended)

"""Merge auto + triage + inheritance into the one authoritative
piks.tsv, so consumers never reimplement the precedence rule.

Precedence per file, applied after transitive closure:
    triage > auto > inherited (parent's RESOLVED classification)

Red-gates — the merge FAILS, it never silently picks (the live
defects that motivated each: 107.3 conflicting triage rows; 4
subfiles whose parents are absent from the DD):
  - duplicate or conflicting triage rows for one file_number
  - triage or auto rows naming files absent from files.tsv
  - a subfile whose parent chain ends outside files.tsv (orphan)
  - an unclassifiable top-level file (no auto, no triage)
  - a parent_file cycle

Post-merge invariant: exactly one row per files.tsv file_number.
"""

from __future__ import annotations

PAYLOAD = ("piks", "piks_method", "piks_confidence", "piks_evidence")


class MergeError(Exception):
    """A red-gate fired; resolve in piks-triage.tsv and re-run."""


def _payload(row: dict) -> dict:
    return {k: row.get(k, "") for k in PAYLOAD}


def merge(files_rows: list[dict], auto_rows: list[dict],
          triage_rows: list[dict]) -> list[dict]:
    """Return one classified row per files.tsv entry (see module doc)."""
    parent = {r["file_number"]: r.get("parent_file", "")
              for r in files_rows}

    # ── Red-gate: triage duplicates/conflicts ─────────────────────
    triage_by: dict[str, dict] = {}
    for row in triage_rows:
        fn = row["file_number"]
        if fn in triage_by:
            kind = ("conflicting" if _payload(triage_by[fn]) != _payload(row)
                    else "duplicate")
            raise MergeError(
                f"{kind} triage rows for file {fn} — resolve in "
                "piks-triage.tsv and re-run")
        triage_by[fn] = row

    # ── Red-gate: rows naming unknown files ───────────────────────
    for label, rows in (("triage", triage_by.values()), ("auto", auto_rows)):
        unknown = sorted(r["file_number"] for r in rows
                         if r["file_number"] not in parent)
        if unknown:
            raise MergeError(f"{label} rows not in files.tsv: {unknown}")

    auto_by = {r["file_number"]: r for r in auto_rows}

    # ── Resolve every file: triage > auto > inherited ─────────────
    resolved: dict[str, dict] = {}

    def resolve(fn: str, chain: tuple[str, ...]) -> dict:
        if fn in resolved:
            return resolved[fn]
        if fn in chain:
            raise MergeError(
                f"parent_file cycle: {' -> '.join(chain + (fn,))}")
        if fn in triage_by:
            row = {**_payload(triage_by[fn]), "piks_source": "triage"}
        elif fn in auto_by:
            row = {**_payload(auto_by[fn]), "piks_source": "auto"}
        else:
            par = parent.get(fn, "")
            if not par:
                raise MergeError(
                    f"unclassifiable top-level file {fn}: no auto, no "
                    "triage — classify in piks-triage.tsv")
            if par not in parent:
                path = " -> ".join(chain + (fn,)) if chain else fn
                raise MergeError(
                    f"orphan subfile {path}: parent {par} absent from "
                    "files.tsv — resolve in piks-triage.tsv")
            got = resolve(par, chain + (fn,))
            row = {
                "piks": got["piks"],
                "piks_method": "inherited-parent",
                "piks_confidence": got["piks_confidence"],
                "piks_evidence": f"inherits from {par}",
                "piks_source": "inherited",
            }
        resolved[fn] = row
        return row

    out = []
    for fn in parent:
        row = resolve(fn, ())
        out.append({"file_number": fn, **row})
    return out
