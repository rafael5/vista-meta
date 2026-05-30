#!/usr/bin/env python3
"""TDD for build_package_namespace.py (P3/P4 keystone).

Run: python3 -m unittest host.scripts.tests.test_build_package_namespace
  or: python3 host/scripts/tests/test_build_package_namespace.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS_DIR))

import build_package_namespace as bpn  # noqa: E402


# A minimal slice of docs/Packages.csv, including continuation rows (empty
# Package Name + Directory Name) that carry extra prefixes/files, and the
# "!"-excluded namespace convention.
SAMPLE_CSV = (
    "Package Name,Directory Name,Prefixes,File Numbers,File Names,Globals,VDL ID\n"
    "VA FILEMAN,VA FileMan,DI,0.11,INDEX,DOPT,5\n"
    ",,DD,,,,\n"
    ",,DM,,,,\n"
    "KERNEL,Kernel,XU,3.05,FAILED ACCESS,HOLIDAY,10\n"
    ",,!XQAB,,,,\n"
    ",,ZU,,,,\n"
    "OUTPATIENT PHARMACY,Outpatient Pharmacy,PSO,52,PRESCRIPTION,PSRX,90\n"
)


class ParsePackagesCsv(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(self.enterContext(__import__("tempfile").TemporaryDirectory()))
        self.csv = self.tmp / "Packages.csv"
        self.csv.write_text(SAMPLE_CSV, encoding="utf-8")
        self.parsed = bpn.parse_packages_csv(self.csv)

    def test_keys_are_directory_names(self) -> None:
        self.assertEqual(
            set(self.parsed), {"VA FileMan", "Kernel", "Outpatient Pharmacy"}
        )

    def test_package_name_is_upper_94_name(self) -> None:
        self.assertEqual(self.parsed["VA FileMan"]["package_name"], "VA FILEMAN")

    def test_continuation_rows_accumulate_prefixes(self) -> None:
        self.assertEqual(self.parsed["VA FileMan"]["prefixes"], ["DI", "DD", "DM"])
        self.assertEqual(self.parsed["Kernel"]["prefixes"], ["XU", "!XQAB", "ZU"])

    def test_vdl_id_captured(self) -> None:
        self.assertEqual(self.parsed["Outpatient Pharmacy"]["vdl_id"], "90")


class PrimaryNamespace(unittest.TestCase):
    def test_first_clean_prefix_wins(self) -> None:
        self.assertEqual(bpn.primary_namespace(["DI", "DD", "DM"]), "DI")

    def test_excluded_namespaces_skipped(self) -> None:
        self.assertEqual(bpn.primary_namespace(["!XQAB", "XU", "ZU"]), "XU")

    def test_all_excluded_falls_back_to_first(self) -> None:
        self.assertEqual(bpn.primary_namespace(["!ORRC", "!ORRJ"]), "!ORRC")

    def test_empty(self) -> None:
        self.assertEqual(bpn.primary_namespace([]), "")


class BuildRows(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(self.enterContext(__import__("tempfile").TemporaryDirectory()))
        csvp = self.tmp / "Packages.csv"
        csvp.write_text(SAMPLE_CSV, encoding="utf-8")
        self.parsed = bpn.parse_packages_csv(csvp)
        # packages.tsv directory names — includes one with no CSV match.
        self.pkg_dirs = ["VA FileMan", "Kernel", "Uncategorized"]
        self.rows = bpn.build_rows(self.pkg_dirs, self.parsed)

    def test_one_row_per_package(self) -> None:
        self.assertEqual([r["package"] for r in self.rows], self.pkg_dirs)

    def test_namespace_and_app_code_resolved(self) -> None:
        fm = next(r for r in self.rows if r["package"] == "VA FileMan")
        self.assertEqual(fm["namespace"], "DI")
        self.assertEqual(fm["app_code"], "DI")
        self.assertEqual(fm["package_name"], "VA FILEMAN")
        self.assertEqual(fm["prefixes"], "DI,DD,DM")
        self.assertEqual(fm["vdl_id"], "5")

    def test_unmatched_package_emits_empty_but_present(self) -> None:
        unc = next(r for r in self.rows if r["package"] == "Uncategorized")
        self.assertEqual(unc["namespace"], "")
        self.assertEqual(unc["app_code"], "")
        self.assertEqual(unc["package_name"], "")
        self.assertEqual(unc["prefixes"], "")
        self.assertEqual(unc["vdl_id"], "")

    def test_fieldnames_order(self) -> None:
        self.assertEqual(
            list(self.rows[0]),
            ["package", "package_name", "namespace", "prefixes", "app_code", "vdl_id"],
        )


if __name__ == "__main__":
    unittest.main()
