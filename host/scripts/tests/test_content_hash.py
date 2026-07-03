#!/usr/bin/env python3
"""TDD for content_hash.py — V5 data fingerprint.

Normative recipe (plan § V5, not an "e.g."): content_hash = sha256
over the LF-joined lines "<filename>\t<sha256(file-bytes)>",
filenames included and sorted bytewise; scope = the 24 data TSVs
only, so a manifest-only correction never moves data identity.

The V5 gate requires two independent implementations to agree: this
file carries both — a hand-rolled hashlib recomputation and a shell
sha256sum pipeline — and checks them against the module.

Run: python3 host/scripts/tests/test_content_hash.py
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS_DIR))

import content_hash as ch  # noqa: E402
import schema_v1  # noqa: E402


def make_tree() -> Path:
    """All 24 files present, each with distinct header-derived bytes."""
    root = Path(tempfile.mkdtemp())
    for name, spec in schema_v1.FILES.items():
        d = root / spec.model
        d.mkdir(exist_ok=True)
        (d / name).write_text("\t".join(spec.columns) + "\n")
    (root / "meta").mkdir()
    (root / "meta/column-manifest.json").write_text("{}\n")
    return root


class TestRecipe(unittest.TestCase):
    """The pure recipe over name → bytes."""

    def test_known_vector_recomputed_independently(self):
        files = {"a.tsv": b"x\n", "b.tsv": b"y\n"}
        lines = "\n".join(
            f"{n}\t{hashlib.sha256(files[n]).hexdigest()}"
            for n in sorted(files))
        want = hashlib.sha256(lines.encode("ascii")).hexdigest()
        self.assertEqual(ch.content_hash(files), want)

    def test_identical_inputs_identical_hash(self):
        files = {"a.tsv": b"x\n"}
        self.assertEqual(ch.content_hash(files),
                         ch.content_hash(dict(files)))

    def test_single_byte_change_changes_hash(self):
        self.assertNotEqual(ch.content_hash({"a.tsv": b"x\n"}),
                            ch.content_hash({"a.tsv": b"y\n"}))

    def test_filename_change_with_identical_bytes_changes_hash(self):
        self.assertNotEqual(ch.content_hash({"a.tsv": b"x\n"}),
                            ch.content_hash({"b.tsv": b"x\n"}))

    def test_sort_is_bytewise_not_locale(self):
        # "Z" < "a" bytewise; insertion order must not matter either
        one = ch.content_hash({"a.tsv": b"1", "Z.tsv": b"2"})
        two = ch.content_hash({"Z.tsv": b"2", "a.tsv": b"1"})
        self.assertEqual(one, two)


class TestTreeScope(unittest.TestCase):
    """compute() walks exactly the 24 schema_v1 TSVs."""

    def test_meta_json_and_strays_do_not_move_data_identity(self):
        root = make_tree()
        before = ch.compute(root)
        (root / "meta/column-manifest.json").write_text('{"x": 1}\n')
        (root / "meta/fidelity.json").write_text("{}\n")
        (root / "code-model/stray.tsv").write_text("stray\n")
        self.assertEqual(ch.compute(root), before)

    def test_any_single_tsv_change_moves_the_hash(self):
        root = make_tree()
        before = ch.compute(root)
        p = root / "data-model/piks.tsv"
        p.write_bytes(p.read_bytes() + b"9\tP\tm\thigh\te\tauto\n")
        self.assertNotEqual(ch.compute(root), before)

    def test_missing_file_is_an_error_not_a_skip(self):
        root = make_tree()
        (root / "data-model/piks.tsv").unlink()
        with self.assertRaises(FileNotFoundError):
            ch.compute(root)

    def test_shell_sha256sum_implementation_agrees(self):
        """Second independent implementation (the V5 gate)."""
        root = make_tree()
        script = (
            'cd "$1"; for f in $(ls data-model/*.tsv code-model/*.tsv '
            "| xargs -n1 basename | LC_ALL=C sort); do "
            'p=$(ls data-model/$f code-model/$f 2>/dev/null | head -1); '
            'printf "%s\\t%s\\n" "$f" "$(sha256sum < "$p" | cut -d" " -f1)"; '
            "done | head -c -1 | sha256sum | cut -d' ' -f1")
        got = subprocess.run(
            ["bash", "-c", script, "--", str(root)],
            capture_output=True, text=True, check=True).stdout.strip()
        self.assertEqual(ch.compute(root), got)


if __name__ == "__main__":
    unittest.main()
