#!/usr/bin/env python3
"""TDD for validate_against_xindex.py's population-coverage report.

The report states what it measured — counts and names — never a
fixed explanation of why a routine is missing.

Run: python3 host/scripts/tests/test_validate_against_xindex.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS_DIR))

import validate_against_xindex as v  # noqa: E402


class TestCoverageReport(unittest.TestCase):
    def test_names_the_routines_on_each_side(self):
        text = "\n".join(v.coverage_report({"A", "B", "KFAIL"},
                                           {"A", "B", "ZEXTRA"}))
        self.assertIn("in the census but not processed by XINDEX: 1", text)
        self.assertIn("KFAIL", text)
        self.assertIn("processed by XINDEX but not in the census: 1", text)
        self.assertIn("ZEXTRA", text)

    def test_states_no_cause_it_did_not_measure(self):
        text = "\n".join(v.coverage_report({"A", "KFAIL"}, {"A"}))
        for guess in ("ZLINK", "T-002", "cohort"):
            self.assertNotIn(guess, text)

    def test_a_long_list_is_cut_and_counted(self):
        census = {f"R{i:03d}" for i in range(30)}
        text = "\n".join(v.coverage_report(census, set()))
        self.assertIn("R009", text)
        self.assertNotIn("R010", text)
        self.assertIn("20 more", text)


class TestValidatedNames(unittest.TestCase):
    def test_a_routine_in_no_package_is_skipped_by_name(self):
        ours = {"A": {"package": "Kernel"}, "%YDBX": {"package": ""},
                "NOTX": {"package": "Kernel"}}
        names, skipped = v.validated_names(ours, {"A", "%YDBX", "ZEXT"})
        self.assertEqual(names, ["A"])
        self.assertEqual(skipped, ["%YDBX"])


SOURCE = {
    "CALLER": ["CALLER ;demo", " Q", "EN ;entry", " S X=1",
               " D ^DIC,LIST^ORWPT", " S Y=$$FMTE^XLFDT(X)",
               "IND D @RTN", " D EN1^@RTN"],
}


def xref(ref: str, locations: str, routine: str = "CALLER") -> dict:
    return {"routine_name": routine, "ref": ref, "location_list": locations}


class TestCallSiteMisses(unittest.TestCase):
    def misses(self, rows):
        return v.call_site_misses(rows, SOURCE.get)

    def test_a_location_naming_the_callee_is_no_miss(self):
        checked, indirect, misses = self.misses([
            xref("DIC ", "EN+2,"), xref("ORWPT LIST", "EN+2,"),
            xref("XLFDT $$FMTE", "EN+3,")])
        self.assertEqual((checked, indirect, misses), (3, 0, []))

    def test_a_bare_label_is_the_label_line_itself(self):
        _, _, misses = self.misses([xref("DIC ", "IND,")])
        self.assertEqual(misses, ["CALLER IND -> DIC "])
        _, _, misses = self.misses([xref("XLFDT $$FMTE", "EN+3,")])
        self.assertEqual(misses, [])

    def test_xindex_flags_after_a_location_are_ignored(self):
        _, _, misses = self.misses([xref("XLFDT $$FMTE", "EN+3~,EN+3*,")])
        self.assertEqual(misses, [])

    def test_a_wrong_line_or_unknown_label_is_a_miss(self):
        _, _, misses = self.misses([xref("XLFDT $$FMTE", "EN+1,NOPE+2,0,")])
        self.assertEqual(misses, ["CALLER EN+1 -> XLFDT $$FMTE",
                                  "CALLER NOPE+2 -> XLFDT $$FMTE",
                                  "CALLER 0 -> XLFDT $$FMTE"])

    def test_a_caller_without_source_is_a_miss(self):
        checked, _, misses = self.misses([xref("DIC ", "A+1,", "GONE")])
        self.assertEqual((checked, misses), (1, ["GONE A+1 -> DIC "]))

    def test_an_indirect_ref_is_counted_not_checked(self):
        checked, indirect, misses = self.misses([xref("@(", "IND+1,")])
        self.assertEqual((checked, indirect, misses), (0, 1, []))


class TestCallSiteReport(unittest.TestCase):
    def test_passes_within_the_tolerance_and_names_the_misses(self):
        lines, ok = v.call_site_report(10_000, 2, ["CALLER EN+1 -> DIC "])
        self.assertTrue(ok)
        text = "\n".join(lines)
        self.assertIn("10,000", text)
        self.assertIn("CALLER EN+1 -> DIC ", text)
        self.assertIn("indirect", text)

    def test_fails_past_the_tolerance(self):
        _, ok = v.call_site_report(100, 0, ["a", "b"])
        self.assertFalse(ok)

    def test_fails_when_nothing_was_checked(self):
        _, ok = v.call_site_report(0, 0, [])
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
