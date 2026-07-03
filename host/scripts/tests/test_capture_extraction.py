#!/usr/bin/env python3
"""TDD for capture_extraction.py — the R3 engine identity/state sidecar
(V1.6 of the producer-contracts plan; spec § 6 R3).

The DB-state fingerprint is the contract-specified cheap pin: sha256
over the LF-joined, bytewise-sorted `<file_number>\t<record_count>`
lines from the raw files.tsv dump. Any data change moves it.

Run: python3 host/scripts/tests/test_capture_extraction.py
"""

from __future__ import annotations

import hashlib
import sys
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS_DIR))

import capture_extraction as ce  # noqa: E402


class TestDbFingerprint(unittest.TestCase):
    ROWS = [
        {"file_number": "2", "record_count": "1811"},
        {"file_number": "11", "record_count": ""},
        {"file_number": "81", "record_count": "2361"},
    ]

    def test_recipe_is_normative(self):
        # sorted bytewise: "11" < "2" < "81"
        expect = hashlib.sha256(
            b"11\t\n2\t1811\n81\t2361").hexdigest()
        self.assertEqual(ce.db_fingerprint(self.ROWS), expect)

    def test_any_count_change_moves_it(self):
        moved = [dict(r) for r in self.ROWS]
        moved[0]["record_count"] = "1812"
        self.assertNotEqual(ce.db_fingerprint(moved),
                            ce.db_fingerprint(self.ROWS))

    def test_order_of_input_rows_is_irrelevant(self):
        self.assertEqual(ce.db_fingerprint(list(reversed(self.ROWS))),
                         ce.db_fingerprint(self.ROWS))


class TestSidecarShape(unittest.TestCase):
    def test_required_r3_fields(self):
        doc = ce.build_sidecar(
            engine="ydb", image="vista-meta:latest",
            image_id="sha256:abc", container_id="deadbeef",
            source_commit="0123abc", db_fp="f" * 64,
            timestamp="2026-07-03T12:00:00Z")
        for field in ("engine", "engine_image", "engine_image_id",
                      "container_id", "extraction_timestamp",
                      "db_state_fingerprint", "source_commit"):
            self.assertIn(field, doc)
        self.assertEqual(doc["engine"], "ydb")
        self.assertEqual(doc["db_state_fingerprint"], "f" * 64)


if __name__ == "__main__":
    unittest.main()
