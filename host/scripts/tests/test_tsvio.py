#!/usr/bin/env python3
"""TDD for tsvio.py — the canonical schema_version 1 TSV writer/reader.

Every final artifact flows through write_tsv, which enforces the
emission contract (spec § 5): UTF-8, tab-separated, LF-terminated,
rows sorted bytewise on the declared key, blank = null, no tabs or
line breaks inside values.

Run: python3 host/scripts/tests/test_tsvio.py
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS_DIR))

import tsvio  # noqa: E402


def tmppath(suffix=".tsv"):
    f = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    f.close()
    return Path(f.name)


class TestWriteFormat(unittest.TestCase):
    def test_lf_only_tab_separated_trailing_newline(self):
        p = tmppath()
        tsvio.write_tsv(p, ("a", "b"), [["2", "y"], ["1", "x"]], key=("a",))
        raw = p.read_bytes()
        self.assertNotIn(b"\r", raw)
        self.assertEqual(raw, b"a\tb\n1\tx\n2\ty\n")

    def test_utf8(self):
        p = tmppath()
        tsvio.write_tsv(p, ("a",), [["café"]], key=("a",))
        self.assertIn("café".encode("utf-8"), p.read_bytes())

    def test_non_string_values_coerced_none_is_blank(self):
        p = tmppath()
        tsvio.write_tsv(p, ("a", "b"), [[3, None]], key=("a",))
        self.assertEqual(p.read_bytes(), b"a\tb\n3\t\n")


class TestSorting(unittest.TestCase):
    def test_bytewise_not_numeric(self):
        # Bytewise (LC_ALL=C) collation: "107.3" < "11" < "2".
        p = tmppath()
        rows = [["2"], ["11"], ["107.3"]]
        tsvio.write_tsv(p, ("file_number",), rows, key=("file_number",))
        _, out = tsvio.read_tsv(p)
        self.assertEqual([r[0] for r in out], ["107.3", "11", "2"])

    def test_bytewise_on_utf8_bytes_not_codepoints(self):
        p = tmppath()
        tsvio.write_tsv(p, ("a",), [["é"], ["z"]], key=("a",))
        _, out = tsvio.read_tsv(p)
        # 'z' (0x7a) sorts before 'é' (0xc3 0xa9) bytewise.
        self.assertEqual([r[0] for r in out], ["z", "é"])

    def test_duplicate_keys_full_row_tiebreak(self):
        # piks-triage's 107.3 conflict must still emit deterministically.
        p = tmppath()
        rows = [["107.3", "b"], ["107.3", "a"]]
        tsvio.write_tsv(p, ("k", "v"), rows, key=("k",))
        _, out = tsvio.read_tsv(p)
        self.assertEqual(out, [["107.3", "a"], ["107.3", "b"]])

    def test_multi_column_key(self):
        p = tmppath()
        rows = [["b", "1", "x"], ["a", "2", "y"], ["a", "10", "z"]]
        tsvio.write_tsv(p, ("p", "q", "r"), rows, key=("p", "q"))
        _, out = tsvio.read_tsv(p)
        self.assertEqual([r[2] for r in out], ["z", "y", "x"])


class TestValueGuards(unittest.TestCase):
    def test_rejects_tab_in_value(self):
        with self.assertRaises(tsvio.TsvValueError):
            tsvio.write_tsv(tmppath(), ("a",), [["x\ty"]], key=("a",))

    def test_rejects_newline_and_cr_in_value(self):
        for bad in ("x\ny", "x\ry"):
            with self.assertRaises(tsvio.TsvValueError):
                tsvio.write_tsv(tmppath(), ("a",), [[bad]], key=("a",))

    def test_rejects_ragged_row(self):
        with self.assertRaises(tsvio.TsvValueError):
            tsvio.write_tsv(tmppath(), ("a", "b"), [["only-one"]],
                            key=("a",))

    def test_rejects_unknown_key_column(self):
        with self.assertRaises(KeyError):
            tsvio.write_tsv(tmppath(), ("a",), [["x"]], key=("nope",))


class TestRead(unittest.TestCase):
    def test_roundtrip(self):
        p = tmppath()
        rows = [["1", "x"], ["2", ""]]
        tsvio.write_tsv(p, ("a", "b"), rows, key=("a",))
        cols, out = tsvio.read_tsv(p)
        self.assertEqual(cols, ["a", "b"])
        self.assertEqual(out, rows)

    def test_reads_legacy_crlf_input(self):
        # Raw/legacy inputs may still be CRLF; the reader normalizes.
        p = tmppath()
        p.write_bytes(b"a\tb\r\n1\tx\r\n")
        cols, out = tsvio.read_tsv(p)
        self.assertEqual(cols, ["a", "b"])
        self.assertEqual(out, [["1", "x"]])

    def test_rewrite_of_own_output_is_byte_identical(self):
        # Idempotence: read → write must reproduce the exact bytes,
        # the property the V5 content hash depends on.
        p = tmppath()
        tsvio.write_tsv(p, ("a", "b"), [["2", "y"], ["1", "x"]], key=("a",))
        first = p.read_bytes()
        cols, rows = tsvio.read_tsv(p)
        tsvio.write_tsv(p, tuple(cols), rows, key=("a",))
        self.assertEqual(p.read_bytes(), first)


if __name__ == "__main__":
    unittest.main()
