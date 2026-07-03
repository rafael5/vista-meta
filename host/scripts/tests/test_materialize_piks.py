#!/usr/bin/env python3
"""TDD for materialize_piks.py — V2/B1 of the producer-contracts plan.

The merge under test (spec § 6 B1, amended):
  precedence per file, after transitive closure: triage > auto >
  inherited. Red-gates (never silently pick): duplicate/conflicting
  triage rows, triage for unknown files, subfiles whose parent chain
  ends in an orphan, unclassifiable top-level files, parent cycles.
Post-merge invariant: exactly one row per files.tsv file_number.

Run: python3 host/scripts/tests/test_materialize_piks.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS_DIR))

import materialize_piks as mp  # noqa: E402


def files(*pairs):
    """files.tsv skeleton rows: (file_number, parent_file)."""
    return [{"file_number": fn, "parent_file": par} for fn, par in pairs]


def auto(fn, piks="P", method="H-01", conf="certain", ev="auto ev"):
    return {"file_number": fn, "piks": piks, "piks_method": method,
            "piks_confidence": conf, "piks_evidence": ev}


def triage(fn, piks="S", method="manual", conf="low", ev="triage ev"):
    return {"file_number": fn, "piks": piks, "piks_method": method,
            "piks_confidence": conf, "piks_evidence": ev}


class TestPrecedence(unittest.TestCase):
    def test_auto_rows_pass_through_with_source_auto(self):
        out = mp.merge(files(("2", "")), [auto("2")], [])
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["piks_source"], "auto")
        self.assertEqual(out[0]["piks"], "P")

    def test_triage_wins_over_auto(self):
        out = mp.merge(files(("2", "")), [auto("2", piks="P")],
                       [triage("2", piks="S")])
        self.assertEqual(out[0]["piks"], "S")
        self.assertEqual(out[0]["piks_source"], "triage")

    def test_every_triage_record_reflected(self):
        out = mp.merge(files(("2", ""), ("3", "")),
                       [auto("2"), auto("3")],
                       [triage("3", ev="specific")])
        by = {r["file_number"]: r for r in out}
        self.assertEqual(by["3"]["piks_evidence"], "specific")


class TestInheritance(unittest.TestCase):
    def test_subfile_inherits_parent(self):
        out = mp.merge(files(("2", ""), ("2.01", "2")), [auto("2")], [])
        by = {r["file_number"]: r for r in out}
        self.assertEqual(by["2.01"]["piks"], "P")
        self.assertEqual(by["2.01"]["piks_source"], "inherited")
        self.assertIn("2", by["2.01"]["piks_evidence"])

    def test_transitive_chain(self):
        # 17 of the live 141 nest: parent itself unclassified.
        out = mp.merge(
            files(("64", ""), ("64.7", "64"), ("64.701", "64.7")),
            [auto("64", piks="K")], [])
        by = {r["file_number"]: r for r in out}
        self.assertEqual(by["64.701"]["piks"], "K")
        self.assertEqual(by["64.701"]["piks_source"], "inherited")
        self.assertEqual(by["64.7"]["piks_source"], "inherited")

    def test_inherits_from_resolved_value_not_raw_auto(self):
        # Parent is triage-overridden; the child inherits the RESOLVED
        # (triage) classification.
        out = mp.merge(files(("2", ""), ("2.01", "2")),
                       [auto("2", piks="P")], [triage("2", piks="S")])
        by = {r["file_number"]: r for r in out}
        self.assertEqual(by["2.01"]["piks"], "S")

    def test_triaged_subfile_keeps_triage_over_inheritance(self):
        out = mp.merge(files(("2", ""), ("2.01", "2")),
                       [auto("2", piks="P")], [triage("2.01", piks="I")])
        by = {r["file_number"]: r for r in out}
        self.assertEqual(by["2.01"]["piks"], "I")
        self.assertEqual(by["2.01"]["piks_source"], "triage")


class TestRedGates(unittest.TestCase):
    def test_conflicting_triage_rows_fail(self):
        # The live 107.3 defect shape: same file, different payloads.
        with self.assertRaisesRegex(mp.MergeError, "107.3"):
            mp.merge(files(("107.3", "")), [],
                     [triage("107.3", method="a"), triage("107.3", method="b")])

    def test_identical_duplicate_triage_rows_also_fail(self):
        with self.assertRaisesRegex(mp.MergeError, "duplicate"):
            mp.merge(files(("2", "")), [auto("2")],
                     [triage("2"), triage("2")])

    def test_triage_for_unknown_file_fails(self):
        with self.assertRaisesRegex(mp.MergeError, "not in files"):
            mp.merge(files(("2", "")), [auto("2")], [triage("99")])

    def test_orphan_parent_fails_loudly(self):
        # The live shape: 500004.01 → parent 500004 absent from DD.
        with self.assertRaisesRegex(mp.MergeError, "500004.01"):
            mp.merge(files(("2", ""), ("500004.01", "500004")),
                     [auto("2")], [])

    def test_nested_chain_to_orphan_fails(self):
        with self.assertRaisesRegex(mp.MergeError, "9.02"):
            mp.merge(files(("9.02", "9.01"), ("9.01", "9")), [], [])

    def test_unclassified_top_level_fails(self):
        with self.assertRaisesRegex(mp.MergeError, "unclassifiable"):
            mp.merge(files(("2", "")), [], [])

    def test_parent_cycle_fails(self):
        with self.assertRaisesRegex(mp.MergeError, "cycle"):
            mp.merge(files(("1.1", "1.2"), ("1.2", "1.1")), [], [])

    def test_auto_row_for_unknown_file_fails(self):
        # Same-extraction discipline: the auto dump and files.tsv come
        # from one engine state, so drift between them is a defect.
        with self.assertRaisesRegex(mp.MergeError, "not in files"):
            mp.merge(files(("2", "")), [auto("2"), auto("3")], [])


class TestInvariant(unittest.TestCase):
    def test_exactly_one_row_per_file(self):
        out = mp.merge(
            files(("1", ""), ("1.01", "1"), ("2", ""), ("2.01", "2")),
            [auto("1"), auto("2")], [triage("2.01")])
        self.assertEqual(sorted(r["file_number"] for r in out),
                         ["1", "1.01", "2", "2.01"])
        sources = {r["file_number"]: r["piks_source"] for r in out}
        self.assertEqual(sources,
                         {"1": "auto", "1.01": "inherited",
                          "2": "auto", "2.01": "triage"})


if __name__ == "__main__":
    unittest.main()
