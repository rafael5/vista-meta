#!/usr/bin/env python3
"""TDD for release_id.py — the one place the data release tag lives.

Every script that names a release asset or record (build_release,
build_meta_db, build_ai_card, build_entity_bridge) and the Makefile
derive it from release_id, so cutting a release is one edit.

Run: python3 host/scripts/tests/test_release_id.py
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS_DIR))

import build_ai_card  # noqa: E402
import build_entity_bridge  # noqa: E402
import build_meta_db  # noqa: E402
import build_release  # noqa: E402
import release_id  # noqa: E402

PROJECT_ROOT = SCRIPTS_DIR.parents[1]


class TestReleaseId(unittest.TestCase):
    def test_names_derive_from_the_tag(self):
        version = release_id.TAG.removeprefix("data-")
        self.assertEqual(release_id.STEM, f"vista-meta-data-{version}")
        releases = PROJECT_ROOT / "docs/releases"
        self.assertEqual(release_id.RECORD_JSON,
                         releases / f"{release_id.TAG}.manifest.json")
        self.assertEqual(release_id.PEERS_JSON,
                         releases / f"{release_id.TAG}-peers.json")
        self.assertEqual(release_id.DERIVED_JSON,
                         releases / f"{release_id.TAG}-derived.json")

    def test_every_script_reads_it(self):
        self.assertEqual(build_release.TAG, release_id.TAG)
        self.assertEqual(build_release.BUNDLE_NAME,
                         f"{release_id.STEM}.tar.gz")
        self.assertEqual(build_release.RAW_NAME,
                         f"{release_id.STEM}-raw.tar.gz")
        self.assertEqual(build_meta_db.OUT_DB.name, f"{release_id.STEM}.db")
        for mod in (build_release, build_meta_db, build_ai_card,
                    build_entity_bridge):
            self.assertEqual(mod.RECORD_JSON, release_id.RECORD_JSON,
                             mod.__name__)
        self.assertEqual(build_entity_bridge.PEERS_JSON,
                         release_id.PEERS_JSON)

    def test_makefile_spells_no_release_tag_of_its_own(self):
        # The vdocs peer keeps its own tag (vdocs-data-v1); only this
        # project's release names must come from release_id.
        text = (PROJECT_ROOT / "Makefile").read_text(encoding="utf-8")
        own = re.findall(r"vista-meta-data-v[0-9]|docs/releases/data-v|"
                         r"release upload data-v|'release':'data-v", text)
        self.assertEqual(own, [])


if __name__ == "__main__":
    unittest.main()
