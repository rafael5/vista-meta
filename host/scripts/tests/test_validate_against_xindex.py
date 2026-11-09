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


if __name__ == "__main__":
    unittest.main()
