#!/usr/bin/env python3
"""TDD for build_column_manifest.py — V3/R1 typed column manifest.

The manifest is generated from schema_v1 (single source of truth) and
must list every column of every file in emit order; the gate is a
mechanical manifest ≡ actual-headers check over the emitted tree.

Run: python3 host/scripts/tests/test_build_column_manifest.py
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS_DIR))

import build_column_manifest as bcm  # noqa: E402
import schema_v1  # noqa: E402


class TestManifestShape(unittest.TestCase):
    def setUp(self):
        self.doc = bcm.build_manifest()

    def test_covers_all_24_files_keyed_by_model_path(self):
        self.assertEqual(len(self.doc["files"]), 24)
        self.assertIn("code-model/rpcs.tsv", self.doc["files"])
        self.assertIn("data-model/piks.tsv", self.doc["files"])

    def test_schema_version(self):
        self.assertEqual(self.doc["schema_version"], 1)

    def test_columns_in_emit_order_with_full_typing(self):
        entry = self.doc["files"]["code-model/rpcs.tsv"]
        spec = schema_v1.spec_for("rpcs.tsv")
        self.assertEqual([c["name"] for c in entry["columns"]],
                         list(spec.columns))
        self.assertEqual(entry["pk"], ["ien"])
        by = {c["name"]: c for c in entry["columns"]}
        self.assertEqual(by["ien"],
                         {"name": "ien", "type": "int",
                          "nullable": False, "key_role": "pk"})
        self.assertEqual(by["return_type"]["type"], "enum")
        self.assertTrue(by["return_type"]["nullable"])
        self.assertEqual(by["routine_name"]["key_role"], "fk")
        self.assertEqual(by["routine_name"]["fk_target"],
                         "routines.tsv:routine_name")

    def test_shared_vocabulary_marked_on_authoritative_columns(self):
        rc = self.doc["files"]["code-model/routines.tsv"]["columns"]
        self.assertTrue(
            next(c for c in rc if c["name"] == "routine_name")
            .get("shared_vocabulary"))
        self.assertEqual(
            self.doc["shared_vocabularies"],
            [{"file": "routines.tsv", "column": "routine_name"},
             {"file": "files.tsv", "column": "file_number"},
             {"file": "options.tsv", "column": "name"},
             {"file": "rpcs.tsv", "column": "name"}])

    def test_bool_columns_typed_bool(self):
        rc = self.doc["files"]["code-model/routines.tsv"]["columns"]
        self.assertEqual(
            next(c for c in rc if c["name"] == "is_percent_routine")["type"],
            "bool")


class TestHeaderGate(unittest.TestCase):
    """The V3 gate: manifest ≡ actual emitted headers."""

    def make_tree(self):
        root = Path(tempfile.mkdtemp())
        for name, spec in schema_v1.FILES.items():
            d = root / spec.model
            d.mkdir(exist_ok=True)
            (d / name).write_text("\t".join(spec.columns) + "\n")
        return root

    def test_passes_on_conforming_tree(self):
        self.assertEqual(bcm.check_headers(self.make_tree()), [])

    def test_fails_on_header_drift(self):
        root = self.make_tree()
        p = root / "code-model/rpcs.tsv"
        p.write_text(p.read_text().replace("routine_name", "routine"))
        errs = bcm.check_headers(root)
        self.assertTrue(any("rpcs.tsv" in e for e in errs))

    def test_fails_on_missing_file(self):
        root = self.make_tree()
        (root / "data-model/piks.tsv").unlink()
        errs = bcm.check_headers(root)
        self.assertTrue(any("piks.tsv" in e for e in errs))

    def test_deterministic_serialization(self):
        self.assertEqual(bcm.render(), bcm.render())


if __name__ == "__main__":
    unittest.main()
