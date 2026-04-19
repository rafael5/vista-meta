#!/usr/bin/env python3
# Phase 5 of ADR-045: routine → routine call-graph edges.
# Spec: docs/vista-meta-spec-v0.4.md § 11

"""Scan every .m routine for calls to other routines.

Detects two MUMPS call patterns:
  - `D|DO|G|GOTO|J|JOB [:postcond] [TAG]^ROU`
  - `$$[TAG]^ROU[(args)]`

Known limitations (MVP, acknowledged):
  - Comma-continuation in DO-arg lists (`D A^R1,B^R2`) catches only
    the first call; subsequent callees are missed.
  - Line-offset calls (`D TAG+3^ROU`) are skipped (rare in practice).
  - Indirection (`D @X`, `D @^ROU`) is undecidable statically.
  - Strings and comments are stripped per line before matching.

Reads:
  - vista/vista-m-host/MANIFEST.tsv
  - Each .m file under vista/vista-m-host/Packages/.../Routines/

Writes:
  - vista/export/normalized/routine-calls.tsv
    columns: caller_name, caller_package, callee_tag, callee_routine,
             kind (do/goto/job/func), ref_count
    one row per unique (caller, tag, callee, kind) tuple
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
OUT_TSV = PROJECT_ROOT / "vista/export/normalized/routine-calls.tsv"

CONTAINER_PREFIX = "/opt/VistA-M/"
HOST_PREFIX = str(HOST_SNAPSHOT) + "/"

# `DO`, `GOTO`, `JOB` (and their short forms D/G/J) with optional
# post-conditional, followed by [TAG]^ROUTINE.
CALL_RE = re.compile(
    r"\b(D|DO|G|GOTO|J|JOB)\b(?::\S+)? +"
    r"([A-Z%][A-Z0-9]*)?\^(%?[A-Z][A-Z0-9]*)"
)

# `$$[TAG]^ROUTINE` — extrinsic function call.
FUNC_RE = re.compile(
    r"\$\$([A-Z%][A-Z0-9]*)?\^(%?[A-Z][A-Z0-9]*)"
)

KIND_MAP = {"D": "do", "DO": "do", "G": "goto", "GOTO": "goto",
            "J": "job", "JOB": "job"}

FIELDS = ["caller_name", "caller_package", "callee_tag", "callee_routine",
          "kind", "ref_count"]


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
    """Return Counter keyed by (callee_tag, callee_routine, kind)."""
    counts: Counter = Counter()
    try:
        text = host_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return counts
    for line in text.splitlines():
        clean = strip_strings_and_comments(line)
        for m in CALL_RE.finditer(clean):
            cmd, tag, rou = m.group(1), m.group(2) or "", m.group(3)
            counts[(tag, rou, KIND_MAP[cmd])] += 1
        for m in FUNC_RE.finditer(clean):
            tag, rou = m.group(1) or "", m.group(2)
            counts[(tag, rou, "func")] += 1
    return counts


def main() -> int:
    if not MANIFEST.exists():
        print(f"ERROR: {MANIFEST} missing. Run `make sync-routines` first.",
              file=sys.stderr)
        return 1

    OUT_TSV.parent.mkdir(parents=True, exist_ok=True)

    out_rows: list[dict] = []
    routines_with_calls = 0
    total_calls = 0

    with MANIFEST.open(newline="", encoding="utf-8") as fh:
        for entry in csv.DictReader(fh, delimiter="\t"):
            name, pkg, src = entry["routine"], entry["package"], entry["source"]
            counts = scan_routine(translate(src))
            if counts:
                routines_with_calls += 1
            for (tag, rou, kind), cnt in counts.items():
                out_rows.append({
                    "caller_name": name,
                    "caller_package": pkg,
                    "callee_tag": tag,
                    "callee_routine": rou,
                    "kind": kind,
                    "ref_count": cnt,
                })
                total_calls += cnt

    out_rows.sort(key=lambda r: (r["caller_name"], r["callee_routine"],
                                  r["callee_tag"], r["kind"]))

    with OUT_TSV.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, delimiter="\t")
        w.writeheader()
        w.writerows(out_rows)

    by_kind: Counter = Counter()
    for r in out_rows:
        by_kind[r["kind"]] += 1
    distinct_callees = len({r["callee_routine"] for r in out_rows})

    print(f"routine-calls.tsv:  {len(out_rows):,} edges")
    print(f"  callers with ≥1 call: {routines_with_calls:,}")
    print(f"  distinct callees:     {distinct_callees:,}")
    print(f"  total calls (summed): {total_calls:,}")
    print(f"  by kind: " + ", ".join(f"{k}={v:,}" for k, v in sorted(by_kind.items())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
