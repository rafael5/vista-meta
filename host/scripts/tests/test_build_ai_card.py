#!/usr/bin/env python3
"""TDD for build_ai_card.py — machine-friendly-exports W1.

The AI card (AI-CARD.md) + ai-manifest.json are generated projections:
schema_v1 supplies structure, the live TSVs supply row counts, and the
in-repo release record supplies the provenance pin (hashes copied
verbatim). The gate is mechanical: committed artifacts ≡ regeneration,
and the live tree's content_hash ≡ the release record's.

Run: python3 host/scripts/tests/test_build_ai_card.py
"""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS_DIR))

import build_ai_card as bai  # noqa: E402
import content_hash  # noqa: E402
import schema_v1  # noqa: E402

ROW_COUNTS = {"rpcs.tsv": 3, "piks.tsv": 2}  # everything else: 1


def make_tree() -> tuple[Path, dict]:
    """A conforming miniature export tree + its matching release record."""
    root = Path(tempfile.mkdtemp())
    for name, spec in schema_v1.FILES.items():
        d = root / spec.model
        d.mkdir(exist_ok=True)
        lines = ["\t".join(spec.columns)]
        for i in range(ROW_COUNTS.get(name, 1)):
            lines.append("\t".join(f"v{i}" for _ in spec.columns))
        (d / name).write_text("\n".join(lines) + "\n", encoding="utf-8")
    record = {
        "artifact": "vista-meta-data",
        "tag": "data-v1",
        "schema_version": 1,
        "content_hash": content_hash.compute(root),
        "db_state_fingerprint": "f" * 64,
        "extraction_timestamp": "2026-07-03T21:03:48Z",
        "engine": "ydb",
        "engine_image": "vista-meta:latest",
        "source_commit": "a" * 40,
        "files": {
            f"{spec.model}/{name}": {
                "sha256": hashlib.sha256(
                    (root / spec.model / name).read_bytes()).hexdigest(),
                "bytes": (root / spec.model / name).stat().st_size,
            }
            for name, spec in schema_v1.FILES.items()},
    }
    return root, record


class TestManifestDoc(unittest.TestCase):
    def setUp(self):
        self.root, self.record = make_tree()
        self.doc = bai.build_manifest_doc(self.root, self.record)

    def test_header_and_release_pin(self):
        self.assertEqual(self.doc["schema_version"], 1)
        rel = self.doc["release"]
        self.assertEqual(rel["tag"], "data-v1")
        self.assertEqual(rel["content_hash"], self.record["content_hash"])
        self.assertEqual(rel["db_state_fingerprint"], "f" * 64)
        self.assertEqual(rel["extraction_timestamp"],
                         "2026-07-03T21:03:48Z")
        self.assertEqual(rel["engine"], "ydb")

    def test_covers_all_24_tables_keyed_by_model_path(self):
        self.assertEqual(len(self.doc["tables"]), 24)
        self.assertIn("code-model/rpcs.tsv", self.doc["tables"])
        self.assertIn("data-model/piks.tsv", self.doc["tables"])

    def test_rows_measured_live_hashes_copied_from_record(self):
        t = self.doc["tables"]["code-model/rpcs.tsv"]
        self.assertEqual(t["rows"], 3)
        self.assertEqual(
            t["sha256"],
            self.record["files"]["code-model/rpcs.tsv"]["sha256"])
        self.assertEqual(
            t["bytes"],
            self.record["files"]["code-model/rpcs.tsv"]["bytes"])
        self.assertEqual(self.doc["tables"]["data-model/piks.tsv"]["rows"], 2)

    def test_table_structure_from_schema_v1(self):
        t = self.doc["tables"]["code-model/rpcs.tsv"]
        spec = schema_v1.spec_for("rpcs.tsv")
        self.assertEqual(t["pk"], list(spec.pk))
        self.assertEqual(t["columns"], list(spec.columns))

    def test_citation_contract(self):
        c = self.doc["citation"]
        self.assertIn("data-v1", c["format"])
        self.assertEqual(c["no_answer"], "not measured in vista-meta data-v1")

    def test_join_key_registry_derived_from_fks(self):
        reg = {e["target"]: e["referenced_by"]
               for e in self.doc["join_keys"]}
        self.assertIn("code-model/rpcs.tsv:routine_name",
                      reg["routines.tsv:routine_name"])
        self.assertIn("data-model/field-piks.tsv:pointer_target",
                      reg["files.tsv:file_number"])

    def test_shared_vocabularies_carried(self):
        self.assertEqual(
            self.doc["shared_vocabularies"],
            [{"file": f, "column": c}
             for f, c in schema_v1.SHARED_VOCABULARIES])


class TestCard(unittest.TestCase):
    def setUp(self):
        self.root, self.record = make_tree()
        self.card = bai.render_card(self.root, self.record)

    def test_generated_banner_and_regen_command(self):
        self.assertIn("GENERATED", self.card)
        self.assertIn("make ai-card", self.card)

    def test_provenance_pinned_from_record(self):
        self.assertIn(self.record["content_hash"], self.card)
        self.assertIn("f" * 64, self.card)
        self.assertIn("data-v1", self.card)
        self.assertIn("2026-07-03T21:03:48Z", self.card)

    def test_data_dictionary_covers_every_tsv_with_rows_and_key(self):
        for name in schema_v1.FILES:
            self.assertIn(f"`{name}`", self.card)
        # rpcs row: measured count + pk + first column visible
        rpcs_line = next(ln for ln in self.card.splitlines()
                         if ln.startswith("| `rpcs.tsv`"))
        self.assertIn("| 3 |", rpcs_line)
        self.assertIn("`ien`", rpcs_line)

    def test_citation_and_no_answer_contract(self):
        self.assertIn("not measured in vista-meta data-v1", self.card)
        self.assertIn("vista-meta data-v1", self.card)

    def test_deterministic(self):
        self.assertEqual(self.card, bai.render_card(self.root, self.record))
        doc = bai.build_manifest_doc(self.root, self.record)
        self.assertEqual(bai.render_manifest(doc), bai.render_manifest(doc))


class TestGate(unittest.TestCase):
    def setUp(self):
        self.root, self.record = make_tree()
        bai.emit(self.root, self.record)

    def test_green_on_fresh_emission(self):
        self.assertEqual(bai.check(self.root, self.record), [])

    def test_red_on_hand_edited_card(self):
        p = self.root / bai.CARD_NAME
        p.write_text(p.read_text(encoding="utf-8") + "tampered\n",
                     encoding="utf-8")
        errs = bai.check(self.root, self.record)
        self.assertTrue(any(bai.CARD_NAME in e for e in errs))

    def test_red_on_stale_manifest(self):
        p = self.root / bai.MANIFEST_NAME
        doc = json.loads(p.read_text(encoding="utf-8"))
        doc["release"]["tag"] = "data-v0"
        p.write_text(json.dumps(doc), encoding="utf-8")
        errs = bai.check(self.root, self.record)
        self.assertTrue(any(bai.MANIFEST_NAME in e for e in errs))

    def test_red_on_missing_card(self):
        (self.root / bai.CARD_NAME).unlink()
        errs = bai.check(self.root, self.record)
        self.assertTrue(any(bai.CARD_NAME in e for e in errs))

    def test_red_when_live_tsvs_drift_from_release_pin(self):
        p = self.root / "code-model/rpcs.tsv"
        with p.open("a", encoding="utf-8") as f:
            f.write("\t".join("x" for _ in
                              schema_v1.spec_for("rpcs.tsv").columns) + "\n")
        errs = bai.check(self.root, self.record)
        self.assertTrue(any("content_hash" in e for e in errs))


if __name__ == "__main__":
    unittest.main()
