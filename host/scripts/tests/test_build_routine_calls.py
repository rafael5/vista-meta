#!/usr/bin/env python3
"""TDD for build_routine_calls.py's per-line call detection.

Every argument of a DO / GOTO / JOB is a call, not only the first:
`D ^A,^B` calls both. Measured 2026-11-09 against XINDEX: reading only
the first argument missed 4,784 caller→callee pairs.

Run: python3 host/scripts/tests/test_build_routine_calls.py
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS_DIR))

import build_routine_calls as b  # noqa: E402


def calls(line: str) -> list[tuple[str, str, str]]:
    return b.calls_in_line(line)


class TestCallsInLine(unittest.TestCase):
    def test_single_do_goto_job_and_function(self):
        self.assertEqual(calls(" D EN^ORWPT G ^DIC J Q^XUTMQ"),
                         [("EN", "ORWPT", "do"), ("", "DIC", "goto"),
                          ("Q", "XUTMQ", "job")])
        self.assertEqual(calls(" S Y=$$FMTE^XLFDT(X)"),
                         [("FMTE", "XLFDT", "func")])

    def test_every_argument_of_a_command_is_a_call(self):
        self.assertEqual(calls(" D ^A1AXCNST,^A1AXCNSM,EXIT1,CLOSE1^A1AXUTL"),
                         [("", "A1AXCNST", "do"), ("", "A1AXCNSM", "do"),
                          ("CLOSE1", "A1AXUTL", "do")])

    def test_commas_inside_actual_parameters_do_not_split(self):
        self.assertEqual(calls(" D EN^R1(A,$$X^R2(B,C)),EN^R3"),
                         [("EN", "R1", "do"), ("EN", "R3", "do"),
                          ("X", "R2", "func")])

    def test_postconditions_on_the_command_and_each_argument(self):
        self.assertEqual(calls(" D:X>1 ^A:Y,B^C:Z=2 Q"),
                         [("", "A", "do"), ("B", "C", "do")])

    def test_the_argument_list_ends_at_a_space(self):
        self.assertEqual(calls(" G ^A S X=1,Y=B^C"), [("", "A", "goto")])

    def test_strings_comments_and_indirection_are_not_calls(self):
        self.assertEqual(calls(' W "D ^NOT" D @X,^@Y ; D ^NOPE'), [])

    def test_a_line_offset_call_counts_toward_its_tag(self):
        self.assertEqual(calls(" D TAG+3^R"), [("TAG", "R", "do")])

    def test_a_job_argument_keeps_its_routine_not_its_parameters(self):
        self.assertEqual(calls(" J EN^R(A,B)::5,^S"),
                         [("EN", "R", "job"), ("", "S", "job")])

    def test_a_command_word_inside_another_commands_arguments_is_not_one(self):
        self.assertEqual(calls(" K DD,DO D FILE^DICN"),
                         [("FILE", "DICN", "do")])

    def test_a_job_with_an_environment_in_brackets(self):
        self.assertEqual(calls(' J ^A1BUJOB["MGR","SMZ"],AUTO^SSD["M",X]::10'),
                         [("", "A1BUJOB", "job"), ("AUTO", "SSD", "job")])

    def test_a_command_right_after_block_dots(self):
        self.assertEqual(calls(" ..D EN^R . G ^S"),
                         [("EN", "R", "do"), ("", "S", "goto")])

    def test_a_contains_operator_in_a_postcondition_ends_nothing(self):
        self.assertEqual(
            calls(' G M^DIE17:DV,^DIE3:DV["V",P:DV\'["S" I X D SET^DIED'),
            [("M", "DIE17", "goto"), ("", "DIE3", "goto"),
             ("SET", "DIED", "do")])

    def test_a_variable_named_like_a_command_is_an_argument(self):
        self.assertEqual(calls(" K DO D FILE^DICN"), [("FILE", "DICN", "do")])

    def test_a_label_named_like_a_command_is_a_label(self):
        self.assertEqual(calls("D G D^DGPTFM0"), [("D", "DGPTFM0", "goto")])
        self.assertEqual(calls("D D:'$D(DJRJ) ^DENTDPAR Q"),
                         [("", "DENTDPAR", "do")])

    def test_an_argumentless_command_then_a_call(self):
        self.assertEqual(calls(" D  G ^X"), [("", "X", "goto")])

    def test_a_numeric_label_is_a_tag(self):
        self.assertEqual(calls(" D 6^VADPT G 101^DGPTFJC:X S Y=$$2^R"),
                         [("6", "VADPT", "do"), ("101", "DGPTFJC", "goto"),
                          ("2", "R", "func")])



class TestCallers(unittest.TestCase):
    """The scanned population is the routine census, %-routines kept
    outside Packages/ included."""

    def test_census_routines_with_their_host_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Packages/Kernel/Routines").mkdir(parents=True)
            (root / "Packages/Kernel/Routines/XUA.m").write_text("X ;\n")
            (root / "PercentRoutines").mkdir()
            (root / "PercentRoutines/_DT.m").write_text("%DT ;\n")
            census = [
                {"routine_name": "XUA", "package": "Kernel",
                 "source_path": "/opt/VistA-M/Packages/Kernel/Routines/XUA.m"},
                {"routine_name": "%DT", "package": "VA FileMan",
                 "source_path": "/opt/VistA-M/o/_DT.m"},
                {"routine_name": "%YDBX", "package": "",
                 "source_path": "/opt/VistA-M/r/_YDBX.m"},
                {"routine_name": "GONE", "package": "Kernel",
                 "source_path": "/opt/VistA-M/Packages/Kernel/Routines/GONE.m"},
            ]
            found, no_package, missing = b.callers(census, root)
        self.assertEqual([(n, p) for n, p, _ in found],
                         [("XUA", "Kernel"), ("%DT", "VA FileMan")])
        self.assertEqual(found[1][2], root / "PercentRoutines/_DT.m")
        self.assertEqual((no_package, missing), (["%YDBX"], ["GONE"]))


if __name__ == "__main__":
    unittest.main()
