#!/usr/bin/env python3
"""TDD for augment_registries.py (P1 + P2).

P1: rpcs.tsv gains a `package` association.
P2: options/protocols/rpcs gain a `package_dir` (canonical directory name)
    column that joins byte-identically against packages.tsv.

Run: python3 host/scripts/tests/test_augment_registries.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS_DIR))

import augment_registries as ar  # noqa: E402

# dir -> upper #9.4 name, as parse_packages_csv yields (subset).
PARSED = {
    "Outpatient Pharmacy": {"package_name": "OUTPATIENT PHARMACY"},
    "Order Entry Results Reporting": {"package_name": "ORDER ENTRY/RESULTS REPORTING"},
    "Kernel": {"package_name": "KERNEL"},
}
# routine -> directory name, from routines.tsv.
ROUTINE2DIR = {
    "PSORX": "Outpatient Pharmacy",
    "ORWORR": "Order Entry Results Reporting",
    "XUS": "Kernel",
}


class Maps(unittest.TestCase):
    def test_name_to_dir_inverts_parsed(self) -> None:
        n2d = ar.build_name_to_dir(PARSED)
        self.assertEqual(n2d["OUTPATIENT PHARMACY"], "Outpatient Pharmacy")
        self.assertEqual(n2d["ORDER ENTRY/RESULTS REPORTING"],
                         "Order Entry Results Reporting")

    def test_dir_to_name(self) -> None:
        d2n = ar.build_dir_to_name(PARSED)
        self.assertEqual(d2n["Kernel"], "KERNEL")


class AugmentOptions(unittest.TestCase):
    def setUp(self) -> None:
        self.n2d = ar.build_name_to_dir(PARSED)
        self.rows = [
            # upper package present -> map via #9.4 name
            {"ien": "1", "name": "PSO FOO", "package": "OUTPATIENT PHARMACY",
             "routine": "PSORX"},
            # no package, but routine present -> fall back to routine->dir
            {"ien": "2", "name": "OR BAR", "package": "", "routine": "ORWORR"},
            # neither -> empty
            {"ien": "3", "name": "ORPHAN", "package": "", "routine": ""},
        ]
        self.fields = ["ien", "name", "package", "routine"]

    def test_appends_package_dir_column_last(self) -> None:
        fields, _ = ar.augment_options(self.fields, self.rows, self.n2d, ROUTINE2DIR)
        self.assertEqual(fields, ["ien", "name", "package", "routine", "package_dir"])

    def test_resolution_paths(self) -> None:
        _, rows = ar.augment_options(self.fields, self.rows, self.n2d, ROUTINE2DIR)
        self.assertEqual(rows[0]["package_dir"], "Outpatient Pharmacy")
        self.assertEqual(rows[1]["package_dir"], "Order Entry Results Reporting")
        self.assertEqual(rows[2]["package_dir"], "")

    def test_existing_package_column_untouched(self) -> None:
        _, rows = ar.augment_options(self.fields, self.rows, self.n2d, ROUTINE2DIR)
        self.assertEqual(rows[0]["package"], "OUTPATIENT PHARMACY")

    def test_idempotent_on_rerun(self) -> None:
        f1, r1 = ar.augment_options(self.fields, self.rows, self.n2d, ROUTINE2DIR)
        f2, r2 = ar.augment_options(f1, r1, self.n2d, ROUTINE2DIR)
        self.assertEqual(f2, f1)
        self.assertEqual([r["package_dir"] for r in r2],
                         ["Outpatient Pharmacy", "Order Entry Results Reporting", ""])


class AugmentProtocols(unittest.TestCase):
    def test_package_dir_from_name_only(self) -> None:
        n2d = ar.build_name_to_dir(PARSED)
        fields = ["ien", "name", "package", "entry_action"]
        rows = [
            {"ien": "9", "name": "OR EVT", "package": "ORDER ENTRY/RESULTS REPORTING",
             "entry_action": "D EN^X"},
            {"ien": "10", "name": "X", "package": "", "entry_action": ""},
        ]
        f, r = ar.augment_protocols(fields, rows, n2d)
        self.assertEqual(f[-1], "package_dir")
        self.assertEqual(r[0]["package_dir"], "Order Entry Results Reporting")
        self.assertEqual(r[1]["package_dir"], "")


class AugmentRpcs(unittest.TestCase):
    def setUp(self) -> None:
        self.n2d = ar.build_name_to_dir(PARSED)
        self.d2n = ar.build_dir_to_name(PARSED)
        self.fields = ["ien", "name", "tag", "routine"]
        self.rows = [
            {"ien": "1", "name": "ORWORR AGET", "tag": "AGET", "routine": "ORWORR"},
            {"ien": "2", "name": "NO ROUTINE", "tag": "", "routine": ""},
            # routine not in routines.tsv -> both empty
            {"ien": "3", "name": "MYSTERY", "tag": "T", "routine": "ZZUNKNOWN"},
        ]

    def test_appends_both_columns(self) -> None:
        fields, _ = ar.augment_rpcs(self.fields, self.rows, ROUTINE2DIR, self.d2n)
        self.assertEqual(fields[-2:], ["package", "package_dir"])

    def test_p1_package_and_p2_dir_resolved_via_routine(self) -> None:
        _, rows = ar.augment_rpcs(self.fields, self.rows, ROUTINE2DIR, self.d2n)
        # P2: canonical directory name (joins packages.tsv)
        self.assertEqual(rows[0]["package_dir"], "Order Entry Results Reporting")
        # P1: upper #9.4 name, uniform with options/protocols `package`
        self.assertEqual(rows[0]["package"], "ORDER ENTRY/RESULTS REPORTING")

    def test_no_routine_is_empty(self) -> None:
        _, rows = ar.augment_rpcs(self.fields, self.rows, ROUTINE2DIR, self.d2n)
        self.assertEqual(rows[1]["package"], "")
        self.assertEqual(rows[1]["package_dir"], "")

    def test_unknown_routine_dir_empty(self) -> None:
        _, rows = ar.augment_rpcs(self.fields, self.rows, ROUTINE2DIR, self.d2n)
        self.assertEqual(rows[2]["package_dir"], "")
        self.assertEqual(rows[2]["package"], "")

    def test_idempotent(self) -> None:
        f1, r1 = ar.augment_rpcs(self.fields, self.rows, ROUTINE2DIR, self.d2n)
        f2, r2 = ar.augment_rpcs(f1, r1, ROUTINE2DIR, self.d2n)
        self.assertEqual(f2, f1)
        self.assertEqual(r2[0]["package_dir"], "Order Entry Results Reporting")


class RawIoBytePreservation(unittest.TestCase):
    # An options-shaped table whose menu_text contains a `"` — the case that
    # broke the csv-writer approach (it would quote/double the field).
    TSV = (
        'ien\tname\tmenu_text\ttype\tpackage\troutine_raw\ttag\troutine\n'
        '1\tPSO FOO\tSay "hi" now\tR\tOUTPATIENT PHARMACY\tEN^PSORX\tEN\tPSORX\n'
        '2\tOR BAR\tplain\tM\t\t\t\tORWORR\n'
    )

    def setUp(self) -> None:
        import tempfile
        self.tmp = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.path = self.tmp / "options.tsv"
        self.path.write_text(self.TSV, encoding="utf-8")
        self.n2d = ar.build_name_to_dir(PARSED)

    def _augment_once(self) -> None:
        header, data, nl = ar.split_table(self.path.read_text())
        base_header, base_data = ar.strip_tail_added(header, data, ["package_dir"])
        rows = ar.parse_rows(base_header, base_data)
        full, rows = ar.augment_options(base_header, rows, self.n2d, ROUTINE2DIR)
        self.path.write_text(
            ar.render_table(base_header, base_data, ["package_dir"], rows, nl)
        )

    def test_existing_bytes_preserved(self) -> None:
        self._augment_once()
        out = self.path.read_text()
        # every original line is a byte-exact prefix of the new line
        orig = self.TSV.rstrip("\n").split("\n")
        new = out.rstrip("\n").split("\n")
        self.assertEqual(new[0], orig[0] + "\tpackage_dir")
        self.assertTrue(new[1].startswith(orig[1] + "\t"))
        self.assertIn('Say "hi" now', new[1])  # quote NOT escaped/doubled
        self.assertTrue(new[1].endswith("\tOutpatient Pharmacy"))

    def test_idempotent_bytes(self) -> None:
        self._augment_once()
        once = self.path.read_text()
        self._augment_once()
        twice = self.path.read_text()
        self.assertEqual(once, twice)

    def test_trailing_newline_preserved(self) -> None:
        self._augment_once()
        self.assertTrue(self.path.read_text().endswith("\n"))


if __name__ == "__main__":
    unittest.main()
