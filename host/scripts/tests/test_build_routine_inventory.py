#!/usr/bin/env python3
"""TDD for the R4 %-routine census extension (V1.5 of the
producer-contracts plan; spec § 6 R4).

Boundary under test: %-routines enter the census ONLY via the synced
PercentRoutines/MANIFEST.tsv (extracted from the image's VistA dirs) —
never by walking $ydb_dist. Package attribution comes from each
routine's own version line (`;;<ver>;<PACKAGE>;…`), mapped through
docs/Packages.csv; unmappable packages stay blank (null).

Run: python3 host/scripts/tests/test_build_routine_inventory.py
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS_DIR))

import build_routine_inventory as bri  # noqa: E402

NAME_TO_DIR = {"KERNEL": "Kernel", "VA FILEMAN": "VA FileMan"}


class TestVersionLinePackage(unittest.TestCase):
    def test_standard_version_line(self):
        self.assertEqual(
            bri.version_line_package(";;22.2;VA FileMan;**14**;Jan 05, 2016"),
            "VA FileMan")
        self.assertEqual(
            bri.version_line_package(";;8.0;KERNEL;**275**;Jul 10, 1995;"),
            "KERNEL")

    def test_missing_or_malformed(self):
        self.assertEqual(bri.version_line_package(""), "")
        self.assertEqual(bri.version_line_package(";;8.0"), "")
        self.assertEqual(bri.version_line_package("; plain comment"), "")


class TestPercentCensus(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        (self.dir / "_DT.m").write_bytes(
            b"DIDT ;SFISC/GFT-DATE/TIME UTILITY ;2014-12-26\n"
            b" ;;22.2;VA FileMan;**14**;Jan 05, 2016;Build 8\n"
            b"Q ;\n")
        (self.dir / "_YDBX.m").write_bytes(
            b"%YDBX ; YDB - not a VA package ;2024\n"
            b" ;;1.0;YOTTADB WIDGETS;;\n"
            b"Q\n")
        # A stray file NOT in the mini-manifest must be ignored —
        # presence in the manifest is the census boundary.
        (self.dir / "_STRAY.m").write_bytes(b"STRAY ;\n ;;1;KERNEL;\nQ\n")
        (self.dir / "MANIFEST.tsv").write_text(
            "routine\tsource\n"
            "%DT\t/opt/VistA-M/o/_DT.m\n"
            "%YDBX\t/opt/VistA-M/r/_YDBX.m\n")
        self.rows = bri.percent_rows(self.dir, NAME_TO_DIR)

    def test_only_manifest_entries_included(self):
        self.assertEqual([r["routine_name"] for r in self.rows],
                         ["%DT", "%YDBX"])

    def test_flag_and_source_path(self):
        r = self.rows[0]
        self.assertEqual(r["is_percent_routine"], "Y")
        self.assertEqual(r["source_path"], "/opt/VistA-M/o/_DT.m")

    def test_package_from_version_line_via_map(self):
        self.assertEqual(self.rows[0]["package"], "VA FileMan")

    def test_unmapped_package_blank(self):
        self.assertEqual(self.rows[1]["package"], "")

    def test_scan_stats_populated(self):
        r = self.rows[0]
        self.assertEqual(r["line_count"], 3)
        self.assertTrue(r["version_line"].startswith(";;22.2;VA FileMan"))
        self.assertEqual(r["tag_count"], 2)  # DIDT label + Q label


if __name__ == "__main__":
    unittest.main()
