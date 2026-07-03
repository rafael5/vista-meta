#!/usr/bin/env python3
"""TDD for build_release.py — V7 release assembly (data-v1).

The V7 corrections under test: bundle_sha256 lives OUTSIDE the bundle
(in-bundle vs standalone manifest variants); per-file sha256 + R3
engine-pinning fields in the manifest; deterministic bundle bytes;
the bundle unpacks to a validate-passing tree.

Run: python3 host/scripts/tests/test_build_release.py
"""

from __future__ import annotations

import hashlib
import io
import json
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_release as br  # noqa: E402
import content_hash as ch  # noqa: E402
import validate_export as vx  # noqa: E402
from test_validate_export import SIDE_CAR, make_tree  # noqa: E402

RELEASE_COMMIT = "5" * 40


class TestManifest(unittest.TestCase):
    def setUp(self):
        self.root = make_tree()
        self.doc = br.build_manifest(self.root, SIDE_CAR, RELEASE_COMMIT)

    def test_contract_fields(self):
        self.assertEqual(self.doc["schema_version"], 1)
        self.assertEqual(self.doc["tag"], "data-v1")
        self.assertEqual(self.doc["source_commit"], RELEASE_COMMIT)
        self.assertEqual(self.doc["content_hash"], ch.compute(self.root))

    def test_r3_engine_pinning_fields(self):
        for f in ("engine", "engine_image", "engine_image_id",
                  "container_id", "extraction_timestamp",
                  "db_state_fingerprint"):
            self.assertEqual(self.doc[f], SIDE_CAR[f])
        self.assertEqual(self.doc["extraction_source_commit"],
                         SIDE_CAR["source_commit"])

    def test_per_file_sha256_over_full_payload(self):
        files = self.doc["files"]
        self.assertEqual(len(files), 26)  # 24 TSVs + 2 meta JSONs
        p = self.root / "data-model/piks.tsv"
        self.assertEqual(files["data-model/piks.tsv"]["sha256"],
                         hashlib.sha256(p.read_bytes()).hexdigest())
        self.assertEqual(files["data-model/piks.tsv"]["bytes"],
                         len(p.read_bytes()))
        self.assertIn("meta/fidelity.json", files)

    def test_in_bundle_variant_has_no_bundle_sha256(self):
        self.assertNotIn("bundle_sha256", self.doc)

    def test_standalone_variant_adds_the_outside_hashes(self):
        st = br.standalone_manifest(self.doc, "b" * 64, "r" * 64)
        self.assertEqual(st["bundle_sha256"], "b" * 64)
        self.assertEqual(st["raw_archive_sha256"], "r" * 64)
        self.assertNotIn("bundle_sha256", self.doc)  # original untouched


class TestBundle(unittest.TestCase):
    def setUp(self):
        self.root = make_tree()
        self.doc = br.build_manifest(self.root, SIDE_CAR, RELEASE_COMMIT)
        self.out = Path(tempfile.mkdtemp()) / br.BUNDLE_NAME

    def test_deterministic_bytes(self):
        br.write_bundle(self.root, self.doc, self.out)
        one = self.out.read_bytes()
        br.write_bundle(self.root, self.doc, self.out)
        self.assertEqual(one, self.out.read_bytes())

    def test_member_metadata_pinned(self):
        br.write_bundle(self.root, self.doc, self.out)
        with tarfile.open(self.out) as tf:
            for m in tf.getmembers():
                self.assertTrue(m.name.startswith(br.BUNDLE_ROOT + "/"))
                self.assertEqual((m.uid, m.gid), (0, 0))
                self.assertEqual(m.mtime, br.sidecar_epoch(SIDE_CAR))

    def test_unpacks_to_validate_passing_tree(self):
        br.write_bundle(self.root, self.doc, self.out)
        dest = Path(tempfile.mkdtemp())
        with tarfile.open(self.out) as tf:
            tf.extractall(dest)
        report = vx.validate(dest / br.BUNDLE_ROOT)
        self.assertEqual(report.errors, [])

    def test_in_bundle_manifest_lacks_bundle_sha256(self):
        br.write_bundle(self.root, self.doc, self.out)
        with tarfile.open(self.out) as tf:
            raw = tf.extractfile(f"{br.BUNDLE_ROOT}/manifest.json").read()
        doc = json.loads(raw)
        self.assertNotIn("bundle_sha256", doc)
        self.assertEqual(doc["content_hash"], self.doc["content_hash"])


class TestSums(unittest.TestCase):
    def test_sha256sums_is_sha256sum_checkable_format(self):
        d = Path(tempfile.mkdtemp())
        (d / "a.bin").write_bytes(b"x")
        text = br.sha256sums([d / "a.bin"])
        line = text.splitlines()[0]
        self.assertEqual(
            line, hashlib.sha256(b"x").hexdigest() + "  a.bin")
        self.assertTrue(text.endswith("\n"))


if __name__ == "__main__":
    unittest.main()
