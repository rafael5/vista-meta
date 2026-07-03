#!/usr/bin/env python3
"""TDD for normalize_dumps.py — host-side normalization of the
M-dump-origin TSVs (V1.4 of the producer-contracts plan).

Flow under test: read raw dump (old headers, container-emitted) →
augment (rpcs/options/protocols package columns) → rename per
schema_v1 → drop per schema_v1 → emit final via tsvio.write_spec.

Run: python3 host/scripts/tests/test_normalize_dumps.py
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS_DIR))

import normalize_dumps as nd  # noqa: E402
import tsvio  # noqa: E402


def write_raw(dirpath: Path, name: str, header: str, lines: list[str],
              crlf=False) -> Path:
    eol = "\r\n" if crlf else "\n"
    p = dirpath / name
    p.write_bytes((eol.join([header] + lines) + eol).encode("utf-8"))
    return p


class Env:
    """A miniature raw/final tree with the lookup inputs."""

    def __init__(self):
        self.root = Path(tempfile.mkdtemp())
        self.raw = self.root / "raw"
        self.data = self.root / "data-model"
        self.code = self.root / "code-model"
        for d in (self.raw, self.data, self.code):
            d.mkdir()
        # routines.tsv final (new headers) — routine→package lookup.
        write_raw(self.code, "routines.tsv",
                  "routine_name\tpackage\tsource_path\tline_count\t"
                  "byte_size\tfirst_line_comment\tversion_line\ttag_count\t"
                  "comment_line_count\tis_percent_routine",
                  ["ORWORR\tOrder Entry Results Reporting\tp\t1\t1\t\t\t1\t0\tN",
                   "PSORX\tOutpatient Pharmacy\tp\t1\t1\t\t\t1\t0\tN"])
        # name→dir map, as parse_packages_csv would produce it.
        self.parsed = {
            "Order Entry Results Reporting": {
                "package_name": "ORDER ENTRY/RESULTS REPORTING"},
            "Outpatient Pharmacy": {"package_name": "OUTPATIENT PHARMACY"},
        }


class TestRpcs(unittest.TestCase):
    def setUp(self):
        self.env = Env()
        # Raw dump shape: no package columns, old `routine` header,
        # deliberately unsorted, CRLF to prove reader tolerance.
        write_raw(self.env.raw, "rpcs.tsv",
                  "ien\tname\ttag\troutine\treturn_type\tavailability\t"
                  "inactive\tversion",
                  ["2\tORWORR AGET\tAGET\tORWORR\t2\tPUBLIC\t\t",
                   "10\tPSO X\tX\tPSORX\t1\tPUBLIC\t1\t",
                   "1\tZZ NOROU\t\t\t\t\t\t"],
                  crlf=True)
        nd.normalize_file("rpcs.tsv", self.env.raw, self.env.data,
                          self.env.code, self.env.parsed)
        cols, rows = tsvio.read_tsv(self.env.code / "rpcs.tsv")
        self.cols, self.rows = cols, [dict(zip(cols, r)) for r in rows]

    def test_final_columns_match_spec(self):
        self.assertEqual(self.cols, [
            "ien", "name", "tag", "routine_name",
            "return_type", "return_type_label",
            "availability", "inactive", "inactive_label",
            "version", "package", "package_dir"])

    def test_sorted_bytewise_by_ien(self):
        self.assertEqual([r["ien"] for r in self.rows], ["1", "10", "2"])

    def test_labels_derived(self):
        by_ien = {r["ien"]: r for r in self.rows}
        self.assertEqual(by_ien["2"]["return_type_label"], "ARRAY")
        self.assertEqual(by_ien["10"]["inactive_label"], "INACTIVE")
        self.assertEqual(by_ien["2"]["inactive_label"], "ACTIVE")  # blank
        self.assertEqual(by_ien["1"]["return_type_label"], "")

    def test_package_augmented_via_routine(self):
        by_ien = {r["ien"]: r for r in self.rows}
        self.assertEqual(by_ien["2"]["package_dir"],
                         "Order Entry Results Reporting")
        self.assertEqual(by_ien["2"]["package"],
                         "ORDER ENTRY/RESULTS REPORTING")
        self.assertEqual(by_ien["1"]["package_dir"], "")

    def test_idempotent_when_rerun_on_augmented_raw(self):
        # Bootstrap mode: raw/ seeded from a current (already augmented,
        # already renamed) final. Re-normalizing must be a fixpoint.
        first = (self.env.code / "rpcs.tsv").read_bytes()
        (self.env.raw / "rpcs.tsv").write_bytes(first)
        nd.normalize_file("rpcs.tsv", self.env.raw, self.env.data,
                          self.env.code, self.env.parsed)
        self.assertEqual((self.env.code / "rpcs.tsv").read_bytes(), first)


class TestFilesTsv(unittest.TestCase):
    def test_drops_empty_classification_columns(self):
        env = Env()
        write_raw(env.raw, "files.tsv",
                  "file_number\tfile_name\tglobal_root\tparent_file\t"
                  "field_count\tpointer_in\tpointer_out\trecord_count\t"
                  "is_dinum\tpiks\tpiks_method\tpiks_confidence\t"
                  "piks_evidence\tpiks_secondary\tvolatility\tsensitivity\t"
                  "portability\tvolume\tsubdomain\tstatus",
                  [  # 20 columns: 9 values, 10 empty classification, status
                   "11\tX\t^X(\t\t2\t0\t0\t5\tN" + "\t" * 11 + "ACTIVE",
                   "2\tPATIENT\t^DPT(\t\t594\t1\t1\t1811\t"
                   + "\t" * 11 + "ACTIVE"])
        nd.normalize_file("files.tsv", env.raw, env.data, env.code,
                          env.parsed)
        cols, rows = tsvio.read_tsv(env.data / "files.tsv")
        self.assertEqual(cols, [
            "file_number", "file_name", "global_root", "parent_file",
            "field_count", "pointer_in", "pointer_out", "record_count",
            "is_dinum", "status"])
        # bytewise: "11" < "2"
        self.assertEqual([r[0] for r in rows], ["11", "2"])


class TestXindexRename(unittest.TestCase):
    def test_routine_renamed(self):
        env = Env()
        write_raw(env.raw, "xindex-errors.tsv",
                  "routine\tentry_index\tline_text\ttag_offset\terror_text",
                  ["ZWB\t1\tL\tT+1\tE"])
        nd.normalize_file("xindex-errors.tsv", env.raw, env.data, env.code,
                          env.parsed)
        cols, rows = tsvio.read_tsv(env.code / "xindex-errors.tsv")
        self.assertEqual(cols[0], "routine_name")
        self.assertEqual(rows[0][0], "ZWB")


class TestPiksMaterialization(unittest.TestCase):
    """V2/B1: normalize_file('piks.tsv') runs the full merge."""

    def setUp(self):
        self.env = Env()
        write_raw(self.env.raw, "files.tsv",
                  "file_number\tfile_name\tglobal_root\tparent_file\t"
                  "field_count\tpointer_in\tpointer_out\trecord_count\t"
                  "is_dinum\tpiks\tpiks_method\tpiks_confidence\t"
                  "piks_evidence\tpiks_secondary\tvolatility\tsensitivity\t"
                  "portability\tvolume\tsubdomain\tstatus",
                  ["2\tPATIENT\t^DPT(\t\t594\t1\t1\t1811\t"
                   + "\t" * 11 + "ACTIVE",
                   "2.01\tALIAS SUB-FIELD\t\t2\t3\t0\t0\t\t"
                   + "\t" * 11 + "ACTIVE",
                   "107.3\tMICOM\t^MICOM(\t\t2\t0\t0\t\t"
                   + "\t" * 11 + "ACTIVE"])
        write_raw(self.env.raw, "piks.tsv",
                  "file_number\tpiks\tpiks_method\tpiks_confidence\t"
                  "piks_evidence",
                  ["2\tP\tH-01\tcertain\tpatient file"])
        write_raw(self.env.data, "piks-triage.tsv",
                  "file_number\tpiks\tpiks_method\tpiks_confidence\t"
                  "piks_evidence",
                  ["107.3\tS\tmanual-vestigial\tlow\tMICOM PORT"])

    def test_merged_output(self):
        nd.normalize_file("piks.tsv", self.env.raw, self.env.data,
                          self.env.code, self.env.parsed)
        cols, rows = tsvio.read_tsv(self.env.data / "piks.tsv")
        self.assertEqual(cols[-1], "piks_source")
        by = {r[0]: dict(zip(cols, r)) for r in rows}
        self.assertEqual(len(by), 3)  # coverage == files.tsv, exactly
        self.assertEqual(by["2"]["piks_source"], "auto")
        self.assertEqual(by["107.3"]["piks_source"], "triage")
        self.assertEqual(by["2.01"]["piks_source"], "inherited")
        self.assertEqual(by["2.01"]["piks"], "P")

    def test_seeded_triage_conflict_fails_loudly(self):
        write_raw(self.env.data, "piks-triage.tsv",
                  "file_number\tpiks\tpiks_method\tpiks_confidence\t"
                  "piks_evidence",
                  ["107.3\tS\tmanual-a\tlow\tx",
                   "107.3\tS\tmanual-b\tmoderate\ty"])
        import materialize_piks as mp
        with self.assertRaises(mp.MergeError):
            nd.normalize_file("piks.tsv", self.env.raw, self.env.data,
                              self.env.code, self.env.parsed)


class TestTriage(unittest.TestCase):
    def test_triage_canonicalized_in_place_keeps_duplicates(self):
        # piks-triage is hand-curated source: sorted deterministically,
        # never deduplicated (V2's red-gate owns conflicts).
        env = Env()
        write_raw(env.data, "piks-triage.tsv",
                  "file_number\tpiks\tpiks_method\tpiks_confidence\t"
                  "piks_evidence",
                  ["107.3\tS\tmanual-vestigial\tlow\tMICOM",
                   "107.3\tS\tmanual-package\tmoderate\tprefix"])
        nd.normalize_file("piks-triage.tsv", env.raw, env.data, env.code,
                          env.parsed)
        _, rows = tsvio.read_tsv(env.data / "piks-triage.tsv")
        self.assertEqual(len(rows), 2)
        # full-row tiebreak: manual-package row first.
        self.assertEqual(rows[0][2], "manual-package")


class TestDriver(unittest.TestCase):
    def test_normalize_all_covers_every_m_dump_file_plus_triage(self):
        # xindex-validation.tsv is host-built (validate_against_xindex),
        # not an M dump — deliberately absent here.
        self.assertEqual(sorted(nd.NORMALIZED_FILES), sorted([
            "field-piks.tsv", "files.tsv", "piks.tsv", "piks-triage.tsv",
            "options.tsv", "protocols.tsv", "rpcs.tsv",
            "vista-file-9-8.tsv", "xindex-errors.tsv",
            "xindex-routines.tsv", "xindex-tags.tsv", "xindex-xrefs.tsv"]))


if __name__ == "__main__":
    unittest.main()
