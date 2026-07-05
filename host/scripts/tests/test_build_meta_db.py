#!/usr/bin/env python3
"""TDD for build_meta_db.py — machine-friendly-exports W2b.

meta.db is a generated SQLite projection of the release: one typed
table per schema_v1 TSV (+ the entity bridge when present), a `meta`
pins table, and the canonical join views. The TSVs remain the model
of record — the db is derived, never edited, and --check verifies its
contents against the TSVs and its pin against the release record.

Run: python3 host/scripts/tests/test_build_meta_db.py
"""

from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS_DIR))

import build_meta_db as bmd  # noqa: E402
import content_hash  # noqa: E402
import schema_v1  # noqa: E402

# Rows with real-looking values so the join views have something to
# resolve. Unlisted columns get filler; unlisted files get one row.
FIXTURE_ROWS = {
    "files.tsv": [
        {"file_number": "2", "file_name": "PATIENT",
         "global_root": "^DPT(", "field_count": "3"},
        {"file_number": "52", "file_name": "PRESCRIPTION",
         "global_root": "^PSRX(", "field_count": "5"},
    ],
    "piks.tsv": [
        {"file_number": "2", "piks": "P"},
        {"file_number": "52", "piks": "P"},
    ],
    "routines.tsv": [{"routine_name": "ORWPT", "line_count": "120"}],
    "routines-comprehensive.tsv": [
        {"routine_name": "ORWPT", "package": "Order Entry",
         "line_count": "120", "in_degree": "7"}],
    "routine-globals.tsv": [
        {"routine_name": "ORWPT", "package": "Order Entry",
         "global_name": "DPT", "ref_count": "9"}],
    "rpcs.tsv": [
        {"ien": "1", "name": "ORWPT SELECT", "tag": "SELECT",
         "routine_name": "ORWPT"}],
    "options.tsv": [
        {"ien": "1", "name": "DG LOAD", "routine_name": "ORWPT"}],
    "packages.tsv": [{"package": "Order Entry", "routine_count": "1"}],
    "package-namespace.tsv": [
        {"package": "Order Entry", "namespace": "OR", "prefixes": "OR"}],
    "package-piks-summary.tsv": [
        {"package": "Order Entry", "p_files": "2"}],
}


def _filler(spec: schema_v1.FileSpec, col: str, i: int) -> str:
    t = spec.effective_type(col)
    if t in ("int", "float"):
        return str(i + 1)
    if t == "bool":
        return "Y"
    return f"x{i}"


def make_tree(with_bridge: bool = True) -> Path:
    root = Path(tempfile.mkdtemp())
    for name, spec in schema_v1.FILES.items():
        d = root / spec.model
        d.mkdir(exist_ok=True)
        lines = ["\t".join(spec.columns)]
        for row in FIXTURE_ROWS.get(name, [{}]):
            lines.append("\t".join(
                row.get(c, "" if c in spec.nullable
                        else _filler(spec, c, i))
                for i, c in enumerate(spec.columns)))
        (d / name).write_text("\n".join(lines) + "\n", encoding="utf-8")
    if with_bridge:
        b = root / "bridge"
        b.mkdir()
        (b / "entity-bridge.tsv").write_text(
            "entity_id\tentity_type\tcanonical_name\tmention_count\t"
            "vista_tsv\tvista_key_column\tvista_key_value\tjoin_method\t"
            "join_confidence\n"
            "rpc:ORWPT SELECT\trpc\tORWPT SELECT\t5\tcode-model/rpcs.tsv"
            "\tname\tORWPT SELECT\texact-name-ci\thigh\n",
            encoding="utf-8")
    return root


def make_record(root: Path) -> dict:
    return {"tag": "data-v1", "schema_version": 1,
            "content_hash": content_hash.compute(root),
            "db_state_fingerprint": "f" * 64,
            "extraction_timestamp": "2026-07-03T21:03:48Z"}


class TestBuild(unittest.TestCase):
    def setUp(self):
        self.root = make_tree()
        self.record = make_record(self.root)
        self.db = self.root / "meta.db"
        bmd.build(self.root, self.db, self.record)
        self.con = sqlite3.connect(self.db)

    def tearDown(self):
        self.con.close()

    def q(self, sql):
        return self.con.execute(sql).fetchall()

    def test_one_table_per_tsv_with_measured_rows(self):
        tables = {r[0] for r in self.q(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        for name in schema_v1.FILES:
            self.assertIn(bmd.table_name(name), tables)
        self.assertEqual(self.q("SELECT COUNT(*) FROM files")[0][0], 2)
        self.assertEqual(self.q("SELECT COUNT(*) FROM xindex_tags")[0][0], 1)

    def test_columns_typed_and_null_semantics(self):
        cols = {r[1]: r[2] for r in self.q("PRAGMA table_info(rpcs)")}
        self.assertEqual(cols["ien"], "INTEGER")
        self.assertEqual(cols["name"], "TEXT")
        # blank nullable columns land as NULL, not ''
        self.assertEqual(self.q(
            "SELECT COUNT(*) FROM rpcs WHERE version IS NULL")[0][0], 1)
        # int columns round-trip as ints
        self.assertEqual(self.q(
            "SELECT line_count FROM routines WHERE routine_name='ORWPT'"
        )[0][0], 120)

    def test_bridge_table_loaded(self):
        self.assertEqual(self.q(
            "SELECT vista_key_value, mention_count FROM entity_bridge"
        ), [("ORWPT SELECT", 5)])

    def test_meta_pins(self):
        meta = dict(self.q("SELECT key, value FROM meta"))
        self.assertEqual(meta["content_hash"], self.record["content_hash"])
        self.assertEqual(meta["tag"], "data-v1")
        self.assertEqual(meta["canonical_format"],
                         "TSV (this database is a generated projection)")

    def test_view_rpc_impl_joins_routine_metrics(self):
        rows = self.q("SELECT rpc, tag, routine_name, package, in_degree "
                      "FROM v_rpc_impl")
        self.assertEqual(rows, [("ORWPT SELECT", "SELECT", "ORWPT",
                                 "Order Entry", 7)])

    def test_view_global_file_piks_normalizes_global_root(self):
        rows = dict(self.q(
            "SELECT global_key, piks FROM v_global_file_piks"))
        self.assertEqual(rows.get("DPT"), "P")   # from ^DPT(
        self.assertEqual(rows.get("PSRX"), "P")  # from ^PSRX(

    def test_view_routine_global_piks_transitive(self):
        rows = self.q(
            "SELECT routine_name, global_name, file_number, piks "
            "FROM v_routine_global_piks WHERE routine_name='ORWPT'")
        self.assertEqual(rows, [("ORWPT", "DPT", "2", "P")])

    def test_view_rpc_data_piks_full_path(self):
        rows = self.q("SELECT rpc, global_name, piks FROM v_rpc_data_piks")
        self.assertEqual(rows, [("ORWPT SELECT", "DPT", "P")])

    def test_view_package_overview(self):
        rows = self.q("SELECT package, namespace, p_files "
                      "FROM v_package_overview WHERE package='Order Entry'")
        self.assertEqual(rows, [("Order Entry", "OR", 2)])

    def test_build_without_bridge_still_works(self):
        root = make_tree(with_bridge=False)
        db = root / "meta.db"
        bmd.build(root, db, make_record(root))
        con = sqlite3.connect(db)
        try:
            self.assertEqual(con.execute(
                "SELECT COUNT(*) FROM entity_bridge").fetchone()[0], 0)
        finally:
            con.close()


class TestCheck(unittest.TestCase):
    def setUp(self):
        self.root = make_tree()
        self.record = make_record(self.root)
        self.db = self.root / "meta.db"
        bmd.build(self.root, self.db, self.record)

    def test_green_on_fresh_build(self):
        self.assertEqual(bmd.check(self.root, self.db, self.record), [])

    def test_red_on_row_count_drift(self):
        p = self.root / "data-model/files.tsv"
        with p.open("a", encoding="utf-8") as f:
            f.write("\t".join("9" for _ in
                              schema_v1.spec_for("files.tsv").columns)
                    + "\n")
        record = make_record(self.root)  # re-pin so only the db is stale
        errs = bmd.check(self.root, self.db, record)
        self.assertTrue(any("files" in e for e in errs))

    def test_red_on_pin_mismatch(self):
        errs = bmd.check(self.root, self.db,
                         {**self.record, "content_hash": "0" * 64})
        self.assertTrue(any("content_hash" in e for e in errs))

    def test_red_on_missing_db(self):
        errs = bmd.check(self.root, self.root / "absent.db", self.record)
        self.assertTrue(errs)


if __name__ == "__main__":
    unittest.main()
