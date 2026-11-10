#!/usr/bin/env python3
# Phase 5 of ADR-045: routine → routine call-graph edges.
# Spec: docs/reference/model-extraction-contract.md § 11

"""Scan every .m routine for calls to other routines.

Detects two MUMPS call patterns:
  - `D|DO|G|GOTO|J|JOB [:postcond] [TAG]^ROU`
  - `$$[TAG]^ROU[(args)]`

Every argument of a DO / GOTO / JOB is read (`D A^R1,B^R2` is two
calls); a line-offset call (`D TAG+3^ROU`) counts toward TAG.

Known limitations:
  - Indirection (`D @X`, `D @^ROU`) is undecidable statically.
  - Strings and comments are stripped per line before matching.

Reads:
  - vista/export/code-model/routines.tsv — the census: every routine
    with its package and source_path, %-routines in o/ and r/ included
  - Each routine's .m file in the host copy vista/vista-m-host/
    (a routine in no package, or with no host file, is skipped and named)

Writes:
  - vista/export/code-model/routine-calls.tsv
    columns: caller_routine, caller_package, callee_tag, callee_routine,
             kind (do/goto/job/func), ref_count
    one row per unique (caller, tag, callee, kind) tuple
    emitted via tsvio per schema_v1 (LF, bytewise sort on the PK)
"""

from __future__ import annotations

import csv
import re
import sys
from collections import Counter
from pathlib import Path

import schema_v1
import tsvio
from mcp_cards import host_relative

PROJECT_ROOT = Path(__file__).resolve().parents[2]
HOST_SNAPSHOT = PROJECT_ROOT / "vista/vista-m-host"
CENSUS = PROJECT_ROOT / "vista/export/code-model/routines.tsv"
OUT_TSV = PROJECT_ROOT / "vista/export/code-model/routine-calls.tsv"

# A command word and its optional post-conditional; its argument list
# follows the single space after it. Lines are walked command by
# command, so `DO` in `K DO` or a label named `D` is never a command.
COMMAND_RE = re.compile(r"([A-Za-z]+)(?::\S*)?")
# One argument: [TAG][+offset]^ROUTINE (a TAG may be all digits), then
# actual parameters or a JOB's [environment], whose commas split it
# into fragments that match nothing (a local `TAG` or `@X` is no call
# into another routine).
ARG_RE = re.compile(r"([A-Z%][A-Z0-9]*|[0-9]+)?(?:\+\d+)?"
                    r"\^(%?[A-Z][A-Z0-9]*)(?:[(\[].*)?")

# `$$[TAG]^ROUTINE` — extrinsic function call.
FUNC_RE = re.compile(
    r"\$\$([A-Z%][A-Z0-9]*|[0-9]+)?\^(%?[A-Z][A-Z0-9]*)"
)

KIND_MAP = {"D": "do", "DO": "do", "G": "goto", "GOTO": "goto",
            "J": "job", "JOB": "job"}

SPEC = schema_v1.spec_for("routine-calls.tsv")


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
    text = host_path.read_text(encoding="utf-8", errors="replace")
    for line in text.splitlines():
        counts.update(calls_in_line(line))
    return counts


def calls_in_line(line: str) -> list[tuple[str, str, str]]:
    """(callee_tag, callee_routine, kind) for each call on one line:
    every DO/GOTO/JOB argument in order, then every `$$` function."""
    clean = strip_strings_and_comments(line)
    found: list[tuple[str, str, str]] = []
    for command, args in _commands(clean):
        kind = KIND_MAP.get(command.upper())
        for arg in args if kind else ():
            if a := ARG_RE.fullmatch(_before_colon(arg)):
                found.append((a.group(1) or "", a.group(2), kind))
    for f in FUNC_RE.finditer(clean):
        found.append((f.group(1) or "", f.group(2), "func"))
    return found


def _commands(text: str) -> list[tuple[str, list[str]]]:
    """Each command on a line, with its arguments: a line is an
    optional label, then commands separated by spaces (and leading
    block dots); an argumentless command is followed by two spaces."""
    out: list[tuple[str, list[str]]] = []
    i = text.find(" ") if text[:1] not in (" ", ".", "") else 0
    while 0 <= i < len(text):
        while i < len(text) and text[i] in " .":
            i += 1
        m = COMMAND_RE.match(text, i)
        if not m:
            break
        args: list[str] = []
        i = m.end()
        if text[i:i + 1] == " ":
            args, i = _argument_list(text, i + 1)
        out.append((m.group(1), args))
    return out


def _argument_list(text: str, start: int) -> tuple[list[str], int]:
    """The comma-separated arguments from start to the first space
    outside parentheses, and the position after them. (A `[` is not
    counted: it is also the contains operator, as in `G A^R:X["Y"`.)"""
    args, depth, begin, i = [], 0, start, start
    while i < len(text) and not (text[i] == " " and depth == 0):
        c = text[i]
        depth += (c == "(") - (c == ")")
        if c == "," and depth == 0:
            args.append(text[begin:i])
            begin = i + 1
        i += 1
    if i > start:
        args.append(text[begin:i])
    return args, i


def _before_colon(arg: str) -> str:
    """An argument without its post-conditional or JOB parameters."""
    depth = 0
    for i, c in enumerate(arg):
        depth += (c == "(") - (c == ")")
        if c == ":" and depth == 0:
            return arg[:i]
    return arg


def callers(census: list[dict], source_root: Path
            ) -> tuple[list[tuple[str, str, Path]], list[str], list[str]]:
    """(routine, package, host file) for each census routine to scan,
    plus the routines skipped for having no package (caller_package is
    a non-null FK) and those whose host file is missing."""
    found, no_package, missing = [], [], []
    for r in census:
        name, rel = r["routine_name"], host_relative(r["source_path"])
        if not r["package"]:
            no_package.append(name)
        elif rel is None or not (source_root / rel).is_file():
            missing.append(name)
        else:
            found.append((name, r["package"], source_root / rel))
    return found, no_package, missing


def main() -> int:
    if not CENSUS.exists():
        print(f"ERROR: {CENSUS} missing. Run `make inventory` first.",
              file=sys.stderr)
        return 1
    with CENSUS.open(newline="", encoding="utf-8") as fh:
        census = list(csv.DictReader(fh, delimiter="\t"))
    found, no_package, missing = callers(census, HOST_SNAPSHOT)

    OUT_TSV.parent.mkdir(parents=True, exist_ok=True)

    out_rows: list[dict] = []
    routines_with_calls = 0
    total_calls = 0

    for name, pkg, path in found:
        counts = scan_routine(path)
        if counts:
            routines_with_calls += 1
        for (tag, rou, kind), cnt in counts.items():
            out_rows.append({
                "caller_routine": name,
                "caller_package": pkg,
                "callee_tag": tag,
                "callee_routine": rou,
                "kind": kind,
                "ref_count": cnt,
            })
            total_calls += cnt

    tsvio.write_spec(OUT_TSV, SPEC, out_rows)

    by_kind: Counter = Counter()
    for r in out_rows:
        by_kind[r["kind"]] += 1
    distinct_callees = len({r["callee_routine"] for r in out_rows})

    print(f"routine-calls.tsv:  {len(out_rows):,} edges")
    print(f"  callers with ≥1 call: {routines_with_calls:,}")
    print(f"  distinct callees:     {distinct_callees:,}")
    print(f"  total calls (summed): {total_calls:,}")
    print(f"  by kind: " + ", ".join(f"{k}={v:,}" for k, v in sorted(by_kind.items())))
    print(f"  skipped, no package: {len(no_package):,}"
          + (f" — {', '.join(no_package)}" if no_package else ""))
    print(f"  skipped, no host file: {len(missing):,}"
          + (f" — {', '.join(missing[:10])}" if missing else ""))
    if missing:
        print("ERROR: census routines missing from the host tree — "
              "run `make sync-routines`", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
