#!/usr/bin/env python3
"""Tests for zwr_merge.py.

Covers the canonical 3-way merge scenarios:
- Non-overlapping edits (clean merge, both changes preserved)
- Same edit on both sides (no conflict)
- Conflicting edit (conflict markers)
- Addition by one side (clean)
- Deletion by one side (clean)
- Delete vs modify (conflict)

Run: python3 host/scripts/test_zwr_merge.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

_here = Path(__file__).resolve().parent
sys.path.insert(0, str(_here))
import zwr_merge


def _write(tmp: Path, name: str, content: str) -> Path:
    p = tmp / name
    p.write_text(content, encoding="utf-8")
    return p


def run_case(case_name: str, base: str, ours: str, theirs: str,
              expect_conflict: bool, expected_contains: list[str]) -> bool:
    with tempfile.TemporaryDirectory() as tmp_str:
        tmp = Path(tmp_str)
        b = _write(tmp, "base.zwr", base)
        o = _write(tmp, "ours.zwr", ours)
        t = _write(tmp, "theirs.zwr", theirs)
        merged, conflict = zwr_merge.merge(b, o, t)
        ok_conflict = conflict == expect_conflict
        ok_contents = all(s in merged for s in expected_contains)
        if ok_conflict and ok_contents:
            print(f"  [PASS] {case_name}")
            return True
        print(f"  [FAIL] {case_name}")
        print(f"    expected conflict={expect_conflict}, got {conflict}")
        print(f"    merged output:\n{merged}")
        print(f"    expected contains: {expected_contains}")
        return False


def main() -> int:
    passed = 0
    total = 0

    # Case 1: Non-overlapping edits (clean)
    total += 1
    if run_case(
        "non-overlapping edits → clean merge",
        base='"BLD",1,0)="A"\n"KRN",19,1,0)="OPT A"\n',
        ours='"BLD",1,0)="B"\n"KRN",19,1,0)="OPT A"\n',
        theirs='"BLD",1,0)="A"\n"KRN",19,1,0)="OPT Z"\n',
        expect_conflict=False,
        expected_contains=['"BLD",1,0)="B"', '"KRN",19,1,0)="OPT Z"'],
    ):
        passed += 1

    # Case 2: Same edit on both sides (clean, merge to agreed value)
    total += 1
    if run_case(
        "identical edits on both sides → clean",
        base='"KRN",19,1,0)="OPT A"\n',
        ours='"KRN",19,1,0)="OPT X"\n',
        theirs='"KRN",19,1,0)="OPT X"\n',
        expect_conflict=False,
        expected_contains=['"KRN",19,1,0)="OPT X"'],
    ):
        passed += 1

    # Case 3: Conflicting edits (conflict)
    total += 1
    if run_case(
        "conflicting edits → conflict markers",
        base='"KRN",19,1,0)="OPT A"\n',
        ours='"KRN",19,1,0)="OPT X"\n',
        theirs='"KRN",19,1,0)="OPT Y"\n',
        expect_conflict=True,
        expected_contains=["<<<<<<< ours", "=======", ">>>>>>> theirs"],
    ):
        passed += 1

    # Case 4: Addition by one side (clean)
    total += 1
    if run_case(
        "addition by one side → clean",
        base='"BLD",1,0)="A"\n',
        ours='"BLD",1,0)="A"\n"KRN",19,1,0)="NEW OPT"\n',
        theirs='"BLD",1,0)="A"\n',
        expect_conflict=False,
        expected_contains=['"BLD",1,0)="A"', '"KRN",19,1,0)="NEW OPT"'],
    ):
        passed += 1

    # Case 5: Deletion by one side (clean)
    total += 1
    if run_case(
        "deletion by one side → clean",
        base='"BLD",1,0)="A"\n"KRN",19,1,0)="OLD"\n',
        ours='"BLD",1,0)="A"\n',  # deleted KRN entry
        theirs='"BLD",1,0)="A"\n"KRN",19,1,0)="OLD"\n',
        expect_conflict=False,
        expected_contains=['"BLD",1,0)="A"'],
    ):
        passed += 1

    # Case 6: Delete vs modify (conflict)
    total += 1
    if run_case(
        "delete-vs-modify → conflict",
        base='"KRN",19,1,0)="A"\n',
        ours='',  # deleted
        theirs='"KRN",19,1,0)="B"\n',  # modified
        expect_conflict=True,
        expected_contains=["<<<<<<<", ">>>>>>>"],
    ):
        passed += 1

    # Case 7: Both add same key, different values (add-add conflict)
    total += 1
    if run_case(
        "both add same key different values → conflict",
        base='',
        ours='"KRN",19,1,0)="A"\n',
        theirs='"KRN",19,1,0)="B"\n',
        expect_conflict=True,
        expected_contains=["<<<<<<<", ">>>>>>>"],
    ):
        passed += 1

    print()
    print(f"Passed: {passed}/{total}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
