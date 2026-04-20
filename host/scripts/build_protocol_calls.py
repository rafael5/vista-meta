#!/usr/bin/env python3
# Phase 5b of ADR-045: protocol → routine edges (closes RF-022 gap).
# Spec: docs/vista-meta-spec-v0.4.md § 11

"""Scan protocol ENTRY_ACTION and EXIT_ACTION for routine calls.

Same regex patterns as Phase 5 (routine-calls), applied to the MUMPS-
code strings stored in protocols.tsv. These invocations are invisible
to Phase 5 because it only parses .m source — protocol ENTRY ACTIONs
live in FileMan data, not in routine source.

Reads:
  - vista/export/code-model/protocols.tsv

Writes:
  - vista/export/code-model/protocol-calls.tsv
    columns: protocol_name, protocol_package, action_kind (entry|exit),
             callee_tag, callee_routine, call_kind (do/goto/job/func),
             ref_count
"""

from __future__ import annotations

import csv
import re
import sys
from collections import Counter
from pathlib import Path

NORM = Path(__file__).resolve().parents[2] / "vista/export/code-model"
IN_TSV = NORM / "protocols.tsv"
OUT_TSV = NORM / "protocol-calls.tsv"

CALL_RE = re.compile(
    r"\b(D|DO|G|GOTO|J|JOB)\b(?::\S+)? +"
    r"([A-Z%][A-Z0-9]*)?\^(%?[A-Z][A-Z0-9]*)"
)
FUNC_RE = re.compile(r"\$\$([A-Z%][A-Z0-9]*)?\^(%?[A-Z][A-Z0-9]*)")
KIND_MAP = {"D": "do", "DO": "do", "G": "goto", "GOTO": "goto",
            "J": "job", "JOB": "job"}

FIELDS = ["protocol_name", "protocol_package", "action_kind",
          "callee_tag", "callee_routine", "call_kind", "ref_count"]


def strip_strings_and_comments(line: str) -> str:
    out: list[str] = []
    i, n, in_string = 0, len(line), False
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


def scan(text: str) -> list[tuple[str, str, str]]:
    """Return list of (tag, callee, kind) for a single action string."""
    clean = strip_strings_and_comments(text)
    found: list[tuple[str, str, str]] = []
    for m in CALL_RE.finditer(clean):
        found.append((m.group(2) or "", m.group(3), KIND_MAP[m.group(1)]))
    for m in FUNC_RE.finditer(clean):
        found.append((m.group(1) or "", m.group(2), "func"))
    return found


def main() -> int:
    if not IN_TSV.exists():
        print(f"ERROR: {IN_TSV} missing.", file=sys.stderr)
        return 1

    agg: Counter = Counter()
    with IN_TSV.open(newline="", encoding="utf-8") as fh:
        for p in csv.DictReader(fh, delimiter="\t"):
            name, pkg = p["name"], p["package"]
            for action_kind, text in (("entry", p.get("entry_action", "")),
                                       ("exit", p.get("exit_action", ""))):
                if not text:
                    continue
                for tag, callee, call_kind in scan(text):
                    agg[(name, pkg, action_kind, tag, callee, call_kind)] += 1

    rows = [
        {"protocol_name": n, "protocol_package": pk, "action_kind": ak,
         "callee_tag": tg, "callee_routine": cn, "call_kind": ck,
         "ref_count": cnt}
        for (n, pk, ak, tg, cn, ck), cnt in agg.items()
    ]
    rows.sort(key=lambda r: (r["protocol_name"], r["action_kind"],
                              r["callee_routine"], r["callee_tag"]))

    with OUT_TSV.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS, delimiter="\t")
        w.writeheader()
        w.writerows(rows)

    distinct_callees = {r["callee_routine"] for r in rows}
    distinct_protocols = {r["protocol_name"] for r in rows}
    by_action = Counter(r["action_kind"] for r in rows)
    by_kind = Counter(r["call_kind"] for r in rows)

    print(f"protocol-calls.tsv: {len(rows):,} edges")
    print(f"  distinct protocols with calls: {len(distinct_protocols):,}")
    print(f"  distinct callee routines:      {len(distinct_callees):,}")
    print(f"  by action_kind: " + ", ".join(f"{k}={v:,}" for k, v in by_action.most_common()))
    print(f"  by call_kind:   " + ", ".join(f"{k}={v:,}" for k, v in by_kind.most_common()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
