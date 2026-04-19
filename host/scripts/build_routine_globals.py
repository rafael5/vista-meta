#!/usr/bin/env python3
# Phase 3a of ADR-045: routine → global edges (subscripted refs only).
# Spec: docs/vista-meta-spec-v0.4.md § 11

"""Scan every .m routine for subscripted global references.

MVP scope: only matches `^IDENT(` — a caret followed by an identifier
followed by an open paren. That pattern is unambiguously a global
reference; routine references (`DO ^ROU`, `$$TAG^ROU`) never have a
paren immediately after the name (args come via $$TAG^ROU(args), where
the paren follows the tag, not the routine name).

Known limitations (acknowledged, not fixed):
  - Bare-global refs like `K ^FOO` or `S X=^FOO` (no subscripts) are
    missed. Most real global access in VistA is subscripted.
  - Indirection (`^@X`, naked `^(subs)`) is undecidable statically.
  - Strings and comments are stripped per-line to avoid false
    positives from `^` characters inside `"..."` or after `;`.

Reads:
  - vista/vista-m-host/MANIFEST.tsv  (from `make sync-routines`)
  - Each .m file under vista/vista-m-host/Packages/.../Routines/

Writes:
  - vista/export/normalized/routine-globals.tsv
    columns: routine_name, package, global_name, ref_count
    one row per (routine, global) pair
"""

from __future__ import annotations

import csv
import re
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
HOST_SNAPSHOT = PROJECT_ROOT / "vista/vista-m-host"
MANIFEST = HOST_SNAPSHOT / "MANIFEST.tsv"
OUT_TSV = PROJECT_ROOT / "vista/export/normalized/routine-globals.tsv"

CONTAINER_PREFIX = "/opt/VistA-M/"
HOST_PREFIX = str(HOST_SNAPSHOT) + "/"

# Subscripted global: ^ + identifier + open-paren, where the `^` is
# NOT preceded by an alphanumeric char or `$`. The lookbehind excludes:
#   - `$$TAG^ROU(args)` — TAG ends in a letter → routine call
#   - `$$^ROU(args)`    — `$$` ends in `$`     → routine call
# Leaves in:
#   - ` ^DPT(DFN)`  (after space, =, comma, (, etc.) — global
#   - `+^DPT(...)`  (numeric-eval prefix) — global
# Note: this does NOT catch `D ^ROU(args)` / `J ^ROU(args)` style DO/JOB
# calls with an args paren — those are rare in VistA and produce the
# minority of false positives. Accepted trade-off for MVP simplicity.
GLOBAL_RE = re.compile(r"(?<![A-Z0-9$])\^(%?[A-Z][A-Z0-9]*)\(")

FIELDS = ["routine_name", "package", "global_name", "ref_count"]


def translate(container_path: str) -> Path:
    return Path(HOST_PREFIX + container_path[len(CONTAINER_PREFIX):])


def strip_strings_and_comments(line: str) -> str:
    """Remove `"..."` strings (with `""` escape) and trailing `;comment`."""
    out: list[str] = []
    i = 0
    n = len(line)
    in_string = False
    while i < n:
        c = line[i]
        if in_string:
            if c == '"':
                if i + 1 < n and line[i + 1] == '"':
                    i += 2
                    continue
                in_string = False
            i += 1
            continue
        if c == '"':
            in_string = True
            i += 1
            continue
        if c == ';':
            break
        out.append(c)
        i += 1
    return "".join(out)


def scan_routine(host_path: Path) -> Counter:
    counts: Counter = Counter()
    try:
        text = host_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return counts
    for line in text.splitlines():
        clean = strip_strings_and_comments(line)
        for m in GLOBAL_RE.finditer(clean):
            counts[m.group(1)] += 1
    return counts


def main() -> int:
    if not MANIFEST.exists():
        print(f"ERROR: {MANIFEST} missing. Run `make sync-routines` first.",
              file=sys.stderr)
        return 1

    OUT_TSV.parent.mkdir(parents=True, exist_ok=True)

    out_rows: list[dict] = []
    routines_with_refs = 0
    total_refs = 0
    unique_globals: set[str] = set()

    with MANIFEST.open(newline="", encoding="utf-8") as fh:
        for entry in csv.DictReader(fh, delimiter="\t"):
            name, pkg, src = entry["routine"], entry["package"], entry["source"]
            host_path = translate(src)
            counts = scan_routine(host_path)
            if counts:
                routines_with_refs += 1
            for gname, cnt in counts.items():
                out_rows.append({
                    "routine_name": name,
                    "package": pkg,
                    "global_name": gname,
                    "ref_count": cnt,
                })
                unique_globals.add(gname)
                total_refs += cnt

    out_rows.sort(key=lambda r: (r["routine_name"], r["global_name"]))
    with OUT_TSV.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, delimiter="\t")
        w.writeheader()
        w.writerows(out_rows)

    print(f"routine-globals.tsv: {len(out_rows):,} edges")
    print(f"  routines with ≥1 global ref: {routines_with_refs:,}")
    print(f"  distinct globals referenced:  {len(unique_globals):,}")
    print(f"  total references (summed):    {total_refs:,}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
