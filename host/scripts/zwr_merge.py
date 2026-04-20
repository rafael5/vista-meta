#!/usr/bin/env python3
# Phase 8d of kids-vc: git merge driver for ZWR files.
# Spec: docs/kids-vc-guide.md §5.4, §6.2

"""Entry-level 3-way merge for ZWR files.

ZWR files (produced by kids-vc decompose) have the shape
`<subscript>="<value>"` per line. Line-based 3-way merge (git's default)
fails badly on these because adjacent entries are independent — a
conflict on entry A shouldn't prevent a clean merge of entry B.

This driver parses each side into a subscript → value dict and merges
entry-by-entry. A conflict only fires when the same subscript has
different non-base values in ours and theirs.

Invocation (git merge driver protocol):
  zwr_merge.py <base> <ours> <theirs>

Writes the merged result to `<ours>` (git's convention). Exit 0 on
clean merge, 1 on conflict.

Install via .gitattributes + .git/config:
  echo '*.zwr merge=zwr' >> .gitattributes
  git config merge.zwr.name "ZWR entry-level merge"
  git config merge.zwr.driver "python3 host/scripts/zwr_merge.py %O %A %B"

Alternatively: kids_vc.py setup-git-merge — one-shot installer.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Re-use the KIDS-level subscript parser from kids_vc.py.
_here = Path(__file__).resolve().parent
sys.path.insert(0, str(_here))
from kids_vc import _parse_zwr_line, _format_subscript, _zwr_line, _sort_key  # noqa: E402


def _load(path: Path) -> dict[tuple, str]:
    """Load a ZWR file into {subs: value}. Non-ZWR lines are preserved as
    comments via a sentinel key."""
    out: dict[tuple, str] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            subs, value = _parse_zwr_line(line)
        except Exception:
            # Treat as a comment; preserve under synthetic key.
            out[("_RAW", hash(line))] = line
            continue
        out[subs] = value
    return out


def _emit_conflict(subs: tuple, ours: str, theirs: str) -> str:
    """Produce git-style conflict markers for a single entry."""
    key_line = _format_subscript(subs)
    return (
        f"<<<<<<< ours\n"
        f'{key_line}="{ours.replace(chr(34), chr(34)*2)}"\n'
        f"=======\n"
        f'{key_line}="{theirs.replace(chr(34), chr(34)*2)}"\n'
        f">>>>>>> theirs\n"
    )


def merge(base_path: Path, ours_path: Path, theirs_path: Path) -> tuple[str, bool]:
    """Do the 3-way merge. Returns (merged_content, has_conflict)."""
    base = _load(base_path)
    ours = _load(ours_path)
    theirs = _load(theirs_path)

    all_keys = set(base) | set(ours) | set(theirs)
    # Separate raw (non-ZWR) keys; preserve them from 'ours' side (heuristic).
    tuple_keys = [k for k in all_keys if not (isinstance(k, tuple) and len(k) >= 1 and k[0] == "_RAW")]
    raw_keys = [k for k in all_keys if isinstance(k, tuple) and len(k) >= 1 and k[0] == "_RAW"]

    output_lines: list[str] = []
    # Preserve comment/raw lines from ours if present.
    for k in raw_keys:
        if k in ours:
            output_lines.append(ours[k])

    conflict = False
    for k in sorted(tuple_keys, key=_sort_key):
        in_b, in_o, in_t = k in base, k in ours, k in theirs
        b, o, t = base.get(k), ours.get(k), theirs.get(k)

        # Classification per 3-way merge semantics:
        if not in_b:
            # Not in base — added by one or both sides.
            if in_o and in_t:
                if o == t:
                    output_lines.append(_zwr_line(k, o))
                else:
                    output_lines.append(_emit_conflict(k, o, t).rstrip("\n"))
                    conflict = True
            elif in_o:
                output_lines.append(_zwr_line(k, o))
            elif in_t:
                output_lines.append(_zwr_line(k, t))
        else:
            # Was in base.
            if in_o and in_t:
                if o == t:
                    output_lines.append(_zwr_line(k, o))  # both agree (either kept or both changed same way)
                elif o == b:
                    output_lines.append(_zwr_line(k, t))  # only theirs changed
                elif t == b:
                    output_lines.append(_zwr_line(k, o))  # only ours changed
                else:
                    output_lines.append(_emit_conflict(k, o, t).rstrip("\n"))
                    conflict = True
            elif in_o:
                # theirs deleted it; did ours change it from base?
                if o == b:
                    pass  # both agree on deletion (theirs) but ours didn't change → delete
                else:
                    # ours modified, theirs deleted → conflict
                    output_lines.append(
                        f"<<<<<<< ours\n{_zwr_line(k, o)}\n======= (theirs deleted)\n>>>>>>> theirs"
                    )
                    conflict = True
            elif in_t:
                if t == b:
                    pass  # ours deleted, theirs unchanged → delete
                else:
                    output_lines.append(
                        f"<<<<<<< (ours deleted)\n======= \n{_zwr_line(k, t)}\n>>>>>>> theirs"
                    )
                    conflict = True
            # else: both deleted, agree → nothing to output

    return "\n".join(output_lines) + ("\n" if output_lines else ""), conflict


def main(argv: list[str] | None = None) -> int:
    argv = argv or sys.argv[1:]
    if len(argv) != 3:
        print("usage: zwr_merge.py <base> <ours> <theirs>", file=sys.stderr)
        return 2
    base_path, ours_path, theirs_path = map(Path, argv)
    merged, conflict = merge(base_path, ours_path, theirs_path)
    # Git's merge-driver convention: write result to `ours_path`.
    ours_path.write_text(merged, encoding="utf-8")
    return 1 if conflict else 0


if __name__ == "__main__":
    sys.exit(main())
