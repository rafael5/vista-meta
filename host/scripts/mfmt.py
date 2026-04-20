#!/usr/bin/env python3
# Spec: docs/vista-developers-guide.md §Tier 2 #5 — canonical MUMPS formatter
#
# Deterministic, idempotent, minimal formatter for .m routines.
# The rules are intentionally conservative — they must never change
# what the code *does*. If in doubt, leave it alone.
#
# Rules applied:
#   R1: Strip trailing whitespace from every line.
#   R2: Replace any leading tabs on a line with spaces (1 tab -> 1 space).
#   R3: Ensure file ends with exactly one newline.
#   R4: Normalize line endings to LF (drop CR).
#
# Rules NOT applied (deliberately out of scope — require parsing MUMPS):
#   - Command-case normalization (would need string-literal awareness)
#   - Body indent normalization (DO-block `.` depth is semantic)
#   - Line-2 reshape (version line reflects real patch state)
#   - Trailing-comment spacing
#
# Exit codes:
#   0  clean (nothing to change) OR files rewritten (default mode)
#   1  --check mode, changes would be made
#   2  I/O error

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def format_text(text: str) -> tuple[str, int]:
    """Apply the formatter rules to `text`; return (new_text, changed_lines)."""
    # R4: normalize CRLF/CR -> LF
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    out_lines: list[str] = []
    changed = 0

    for raw in text.split("\n"):
        new = raw

        # R2: leading tabs -> spaces (preserve everything after the
        # first non-whitespace char untouched).
        i = 0
        while i < len(new) and new[i] == "\t":
            i += 1
        if i:
            new = (" " * i) + new[i:]

        # R1: strip trailing whitespace
        new = new.rstrip(" \t")

        if new != raw:
            changed += 1
        out_lines.append(new)

    # R3: exactly one trailing newline
    while out_lines and out_lines[-1] == "":
        out_lines.pop()
    result = "\n".join(out_lines) + "\n"

    if result != text.replace("\r\n", "\n").replace("\r", "\n"):
        # count file-level CR/trailing-blank fixes as at least one change
        changed = max(changed, 1)

    return result, changed


def process(path: Path, *, check: bool) -> tuple[bool, int]:
    """Return (changed, line_count_changed). On --check, do not write."""
    try:
        orig = path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        print(f"{path}: read error: {e}", file=sys.stderr)
        return False, 0

    new, changed = format_text(orig)
    if new == orig:
        return False, 0

    if check:
        print(f"would reformat: {path}  ({changed} line(s))")
    else:
        path.write_text(new, encoding="utf-8")
        print(f"reformatted:    {path}  ({changed} line(s))")
    return True, changed


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="mfmt",
        description="Canonical formatter for MUMPS (.m) routines.")
    p.add_argument("paths", nargs="+", help="Files or directories")
    p.add_argument("--check", action="store_true",
                   help="Do not write; exit 1 if any file would change")
    args = p.parse_args(argv)

    targets: list[Path] = []
    for a in args.paths:
        pa = Path(a)
        if pa.is_dir():
            targets.extend(pa.rglob("*.m"))
        elif pa.is_file():
            targets.append(pa)
        else:
            print(f"skip: {pa} (not a file or directory)", file=sys.stderr)

    any_changed = False
    for t in targets:
        changed, _ = process(t, check=args.check)
        any_changed = any_changed or changed

    if args.check and any_changed:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
