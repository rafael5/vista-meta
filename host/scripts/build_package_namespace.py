#!/usr/bin/env python3
# P3/P4 of upstream-data-fixes: per-package namespace + VDL app_code.
# Spec: docs/reference/model-extraction-contract.md § 11 (PACKAGE-file linkage)
# ADR-045 companion: package → namespace/app_code bridge for vista-info-hub.

"""Emit package-namespace.tsv — namespace/app_code per code-model package.

The authoritative bridge is host/vendor/Packages.csv, the FOIA build manifest that
*created* the source-tree directory names. It maps, per package:

  Package Name   — the upper-case PACKAGE-file (#9.4) NAME ("VA FILEMAN")
  Directory Name — the source-tree / export directory ("VA FileMan")
  Prefixes       — the package namespace(s); primary == VDL app_code
  VDL ID         — the numeric VistA Document Library application id

This solves three downstream gaps at the source (see
upstream-data-fixes-prompt.md):

  P3  namespace + app_code per package (only 17/174 were resolvable before)
  P4  reconcile "VA FileMan" (dir) vs "FILEMAN"/"VA FILEMAN" (name) — the CSV
      carries both columns, so no string-munging heuristic is needed.

Reads:
  - host/vendor/Packages.csv                              (authoritative manifest)
  - vista/export/code-model/packages.tsv           (the 174 export packages)

Writes:
  - vista/export/code-model/package-namespace.tsv  (one row per package,
                                                    joined by `package`)

Additive-only: a brand-new file; packages.tsv is left byte-for-byte
unchanged, so neither downstream tool's byte-parity goldens move.
"""

from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

import schema_v1
import tsvio

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PACKAGES_CSV = PROJECT_ROOT / "host/vendor/Packages.csv"
# The export tree is uid-1001-owned (in-container vehu); VM_CODE_MODEL_DIR lets
# the operator point reads/writes at a writable staging dir, then copy in via
# the make target's docker/1001 path. Defaults to the real export tree.
CODE_MODEL_DIR = Path(
    os.environ.get(
        "VM_CODE_MODEL_DIR", str(PROJECT_ROOT / "vista/export/code-model")
    )
)
PACKAGES_TSV = CODE_MODEL_DIR / "packages.tsv"
OUT_TSV = CODE_MODEL_DIR / "package-namespace.tsv"

SPEC = schema_v1.spec_for("package-namespace.tsv")


def parse_packages_csv(path: Path) -> dict[str, dict]:
    """Group Packages.csv into one entry per Directory Name.

    Continuation rows (empty Package Name *and* Directory Name) belong to the
    package most recently opened; their Prefixes accumulate in order.
    """
    out: dict[str, dict] = {}
    cur: str | None = None
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            pkg_name = (row.get("Package Name") or "").strip()
            dir_name = (row.get("Directory Name") or "").strip()
            prefix = (row.get("Prefixes") or "").strip()
            vdl_id = (row.get("VDL ID") or "").strip()
            if dir_name:
                cur = dir_name
                out[dir_name] = {
                    "package_name": pkg_name,
                    "prefixes": [prefix] if prefix else [],
                    "vdl_id": vdl_id,
                }
            elif cur is not None and prefix:
                out[cur]["prefixes"].append(prefix)
    return out


def primary_namespace(prefixes: list[str]) -> str:
    """The package's primary namespace: first non-excluded prefix.

    A leading "!" marks an EXCLUDED NAME SPACE (a namespace the package does
    *not* own); skip those. If every prefix is excluded, return the first as a
    last resort rather than emitting empty.
    """
    for p in prefixes:
        if not p.startswith("!"):
            return p
    return prefixes[0] if prefixes else ""


def build_rows(pkg_dirs: list[str], parsed: dict[str, dict]) -> list[dict]:
    rows: list[dict] = []
    for d in pkg_dirs:
        entry = parsed.get(d)
        if entry is None:
            rows.append({
                "package": d, "package_name": "", "namespace": "",
                "prefixes": "", "app_code": "", "vdl_id": "",
            })
            continue
        prefixes = entry["prefixes"]
        ns = primary_namespace(prefixes)
        rows.append({
            "package": d,
            "package_name": entry["package_name"],
            "namespace": ns,
            "prefixes": ",".join(prefixes),
            "app_code": ns,  # VDL doc app_code == primary namespace
            "vdl_id": entry["vdl_id"],
        })
    return rows


def read_package_dirs(path: Path) -> list[str]:
    with path.open(newline="", encoding="utf-8") as fh:
        return [r["package"] for r in csv.DictReader(fh, delimiter="\t")]


def main() -> int:
    if not PACKAGES_CSV.exists():
        print(f"ERROR: {PACKAGES_CSV} not found.", file=sys.stderr)
        return 1
    if not PACKAGES_TSV.exists():
        print(f"ERROR: {PACKAGES_TSV} not found. Run `make inventory` first.",
              file=sys.stderr)
        return 1

    parsed = parse_packages_csv(PACKAGES_CSV)
    pkg_dirs = read_package_dirs(PACKAGES_TSV)
    rows = build_rows(pkg_dirs, parsed)

    tsvio.write_spec(OUT_TSV, SPEC, rows)

    resolved = sum(1 for r in rows if r["namespace"])
    print(f"package-namespace.tsv: {len(rows):,} rows "
          f"({resolved} with namespace, {len(rows) - resolved} unmatched)")
    unmatched = [r["package"] for r in rows if not r["namespace"]]
    if unmatched:
        print(f"  unmatched: {', '.join(unmatched)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
