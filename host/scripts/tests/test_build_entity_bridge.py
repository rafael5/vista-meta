#!/usr/bin/env python3
"""TDD for build_entity_bridge.py — machine-friendly-exports W3.

The bridge is a generated projection over TWO pinned releases: every
vdocs data-v1 entity gets exactly one row mapping it (or declining to,
`undetermined` is legal) onto a vista-meta data-v1 vocabulary value.
Floors are regression tripwires on measured rates, never aspirations;
the gate extends Gate R — the bridge meta must carry both fingerprints
and they must match the in-repo pin records.

Run: python3 host/scripts/tests/test_build_entity_bridge.py
"""

from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS_DIR))

import build_entity_bridge as beb  # noqa: E402
import content_hash  # noqa: E402
import schema_v1  # noqa: E402

# Rows the join TSVs need so the fixture entities below have targets.
JOIN_ROWS = {
    "routines.tsv": [{"routine_name": "ORWPT"}],
    "rpcs.tsv": [{"name": "ORWPT SELECT"}],
    "options.tsv": [{"name": "DG LOAD PATIENT"}],
    "files.tsv": [{"file_number": "200"}],
    "routine-globals.tsv": [{"global_name": "DPT"}],
    "package-namespace.tsv": [
        {"package": "Registration", "namespace": "DG",
         "prefixes": "DG,DGQE,!DGBT"},
        {"package": "Order Entry Results Reporting", "namespace": "OR",
         "prefixes": "OR"},
    ],
}

ENTITIES = [
    # (entity_id, type, canonical_name, mention_count)
    ("routine:ORWPT", "routine", "ORWPT", 12),
    ("routine:ZZNOPE", "routine", "ZZNOPE", 1),
    ("global:^DPT", "global", "^DPT", 44),
    ("global:^ZZX", "global", "^ZZX", 2),
    ("fileman_file:200", "fileman_file", "200", 68),
    ("rpc:ORWPT SELECT", "rpc", "ORWPT SELECT", 5),
    ("package_namespace:DG", "package_namespace", "DG", 30),
    ("package_namespace:DGQE", "package_namespace", "DGQE", 3),
    ("build:DG*5.3*100", "build", "DG*5.3*100", 4),
    ("hl7_segment:PID", "hl7_segment", "PID", 9),
]


def make_export_tree() -> Path:
    """All 24 schema_v1 TSVs; join TSVs get real-looking rows."""
    root = Path(tempfile.mkdtemp())
    for name, spec in schema_v1.FILES.items():
        d = root / spec.model
        d.mkdir(exist_ok=True)
        lines = ["\t".join(spec.columns)]
        for row in JOIN_ROWS.get(name, [{}]):
            lines.append("\t".join(row.get(c, f"x{i}")
                                    for i, c in enumerate(spec.columns)))
        (d / name).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return root


def make_peer_tree(entities=ENTITIES) -> tuple[Path, dict]:
    """An unpacked vdocs bundle (index.db + manifest.json) + peers record."""
    peer = Path(tempfile.mkdtemp()) / "vdocs-data-v1"
    peer.mkdir()
    con = sqlite3.connect(peer / "index.db")
    con.execute("CREATE TABLE entities (entity_id TEXT PRIMARY KEY, "
                "type TEXT, canonical_name TEXT, mention_count INTEGER)")
    con.executemany("INSERT INTO entities VALUES (?,?,?,?)", entities)
    con.commit()
    con.close()
    manifest = {"artifact": "vdocs-data", "tag": "data-v1",
                "corpus_content_hash": "c" * 64}
    (peer / "manifest.json").write_text(json.dumps(manifest),
                                        encoding="utf-8")
    peers_record = {"peers": {"vdocs-data:data-v1": {
        "corpus_content_hash": "c" * 64,
        "bundle_sha256": "b" * 64,
        "release": "https://github.com/rafael5/vdocs/releases/tag/data-v1",
    }}}
    return peer, peers_record


def make_fixture():
    export = make_export_tree()
    peer, peers_record = make_peer_tree()
    release_record = {"tag": "data-v1", "schema_version": 1,
                      "content_hash": content_hash.compute(export)}
    return export, peer, peers_record, release_record


class TestJoins(unittest.TestCase):
    def setUp(self):
        (self.export, self.peer, self.peers_record,
         self.release_record) = make_fixture()
        self.rows = beb.build_rows(self.export, self.peer)
        self.by_id = {r["entity_id"]: r for r in self.rows}

    def test_one_row_per_entity_sorted_by_entity_id(self):
        self.assertEqual(len(self.rows), len(ENTITIES))
        ids = [r["entity_id"] for r in self.rows]
        self.assertEqual(ids, sorted(ids))

    def test_routine_exact_ci_high(self):
        r = self.by_id["routine:ORWPT"]
        self.assertEqual(r["vista_tsv"], "code-model/routines.tsv")
        self.assertEqual(r["vista_key_column"], "routine_name")
        self.assertEqual(r["vista_key_value"], "ORWPT")
        self.assertEqual(r["join_method"], "exact-name-ci")
        self.assertEqual(r["join_confidence"], "high")
        self.assertEqual(r["mention_count"], 12)

    def test_fileman_file_exact_key(self):
        r = self.by_id["fileman_file:200"]
        self.assertEqual(r["vista_tsv"], "data-model/files.tsv")
        self.assertEqual(r["vista_key_column"], "file_number")
        self.assertEqual(r["join_method"], "exact-key")
        self.assertEqual(r["join_confidence"], "high")

    def test_global_caret_strip_positive_only(self):
        r = self.by_id["global:^DPT"]
        self.assertEqual(r["vista_tsv"], "code-model/routine-globals.tsv")
        self.assertEqual(r["vista_key_value"], "DPT")
        self.assertEqual(r["join_method"], "global-caret-strip-ci")
        self.assertEqual(r["join_confidence"], "moderate")

    def test_package_namespace_via_namespace_then_prefix(self):
        ns = self.by_id["package_namespace:DG"]
        self.assertEqual(ns["vista_tsv"], "code-model/package-namespace.tsv")
        self.assertEqual(ns["vista_key_column"], "package")
        self.assertEqual(ns["vista_key_value"], "Registration")
        self.assertEqual(ns["join_method"], "namespace-ci")
        pref = self.by_id["package_namespace:DGQE"]
        self.assertEqual(pref["vista_key_value"], "Registration")
        self.assertEqual(pref["join_method"], "prefix-ci")
        self.assertEqual(pref["join_confidence"], "moderate")

    def test_excluded_prefix_never_joins(self):
        # !DGBT in the prefixes list is an exclusion marker, not a prefix
        peer2, _ = make_peer_tree(
            [("package_namespace:DGBT", "package_namespace", "DGBT", 1)])
        rows = beb.build_rows(self.export, peer2)
        self.assertEqual(rows[0]["join_method"], "none")

    def test_unmatched_floor_verified_is_undetermined(self):
        r = self.by_id["routine:ZZNOPE"]
        self.assertEqual(r["join_method"], "none")
        self.assertEqual(r["join_confidence"], "undetermined")
        self.assertEqual(r["vista_tsv"], "")
        self.assertEqual(r["vista_key_value"], "")

    def test_no_vocabulary_types_are_undetermined(self):
        for eid in ("build:DG*5.3*100", "hl7_segment:PID"):
            r = self.by_id[eid]
            self.assertEqual(r["join_method"], "none")
            self.assertEqual(r["join_confidence"], "undetermined")


class TestMeta(unittest.TestCase):
    def setUp(self):
        (self.export, self.peer, self.peers_record,
         self.release_record) = make_fixture()
        rows = beb.build_rows(self.export, self.peer)
        self.meta = beb.build_meta(rows, self.peers_record,
                                   self.release_record)

    def test_carries_both_pins(self):
        self.assertEqual(self.meta["pins"]["vista_meta"]["content_hash"],
                         self.release_record["content_hash"])
        self.assertEqual(self.meta["pins"]["vdocs"]["corpus_content_hash"],
                         "c" * 64)
        self.assertEqual(self.meta["pins"]["vdocs"]["bundle_sha256"],
                         "b" * 64)

    def test_per_type_rates_measured(self):
        t = self.meta["types"]["routine"]
        self.assertEqual((t["count"], t["joined"]), (2, 1))
        self.assertEqual(t["rate"], 0.5)
        self.assertEqual(t["status"], "floor-verified")
        pn = self.meta["types"]["package_namespace"]
        self.assertEqual((pn["count"], pn["joined"]), (2, 2))
        self.assertEqual(pn["status"], "positive-only")
        self.assertEqual(self.meta["types"]["build"]["status"],
                         "no-vocabulary")

    def test_option_absent_from_pin_rates_vacuously(self):
        # published vdocs data-v1 quarantined option entities (count 0)
        t = self.meta["types"]["option"]
        self.assertEqual(t["count"], 0)
        self.assertEqual(t["rate"], 1.0)

    def test_totals(self):
        self.assertEqual(self.meta["counts"]["entities"], len(ENTITIES))
        # ORWPT, ^DPT, 200, ORWPT SELECT, DG, DGQE
        self.assertEqual(self.meta["counts"]["joined"], 6)

    def test_canonicalization_published_as_data(self):
        # Consumers apply this DECLARED spec to raw tokens — they never
        # re-implement the algorithm (producer-side indexing directive).
        can = self.meta["canonicalization"]
        self.assertEqual(can["types"]["global"]["steps"],
                         ["strip-leading-caret", "uppercase"])
        self.assertEqual(can["types"]["routine"]["steps"], ["uppercase"])
        self.assertEqual(can["types"]["routine"]["vocabulary"],
                         "routines.tsv:routine_name")
        self.assertIn("uppercase", can["vocabulary_matching"])
        # package_namespace resolves namespace-then-prefix; declared too
        self.assertEqual(can["types"]["package_namespace"]["resolution"],
                         "namespace-then-prefix")

    def test_canonicalize_interprets_the_declared_steps(self):
        # The emitter itself runs on the declared spec — one source of truth.
        self.assertEqual(beb.canonicalize("global", "^dpt"), "DPT")
        self.assertEqual(beb.canonicalize("global", "DPT"), "DPT")
        self.assertEqual(beb.canonicalize("routine", "orwpt"), "ORWPT")
        self.assertEqual(beb.canonicalize("fileman_file", "200"), "200")


class TestGate(unittest.TestCase):
    def setUp(self):
        (self.export, self.peer, self.peers_record,
         self.release_record) = make_fixture()
        beb.emit(self.export, self.peer, self.peers_record,
                 self.release_record)

    def check(self, peer=True):
        return beb.check(self.export, self.peer if peer else None,
                         self.peers_record, self.release_record)

    def test_green_on_fresh_emission(self):
        self.assertEqual(self.check(), [])

    def test_green_without_peer_input(self):
        # fresh clone: dist/peers absent — pins + recounted rates + floors
        # still verified from the committed artifacts alone
        self.assertEqual(self.check(peer=False), [])

    def test_red_on_tampered_bridge_row(self):
        p = self.export / "bridge/entity-bridge.tsv"
        p.write_text(p.read_text(encoding="utf-8")
                     .replace("exact-name-ci", "none"), encoding="utf-8")
        self.assertTrue(self.check())
        self.assertTrue(self.check(peer=False))  # rate recount catches it too

    def test_red_on_pin_mismatch(self):
        p = self.export / "bridge/entity-bridge.meta.json"
        doc = json.loads(p.read_text(encoding="utf-8"))
        doc["pins"]["vdocs"]["corpus_content_hash"] = "d" * 64
        p.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n",
                     encoding="utf-8")
        errs = self.check(peer=False)
        self.assertTrue(any("pin" in e for e in errs))

    def test_red_on_floor_regression(self):
        floors = {**beb.FLOORS, "routine": 0.99}  # measured 0.5 in fixture
        errs = beb.check(self.export, self.peer, self.peers_record,
                         self.release_record, floors=floors)
        self.assertTrue(any("floor" in e for e in errs))

    def test_red_on_live_tsv_drift(self):
        p = self.export / "code-model/routines.tsv"
        with p.open("a", encoding="utf-8") as f:
            f.write("\t".join("z" for _ in
                              schema_v1.spec_for("routines.tsv").columns)
                    + "\n")
        errs = self.check(peer=False)
        self.assertTrue(any("content_hash" in e for e in errs))

    def test_red_on_peer_manifest_mismatch(self):
        m = self.peer / "manifest.json"
        doc = json.loads(m.read_text(encoding="utf-8"))
        doc["corpus_content_hash"] = "e" * 64
        m.write_text(json.dumps(doc), encoding="utf-8")
        errs = self.check()
        self.assertTrue(any("peer" in e for e in errs))

    def test_emit_refuses_mismatched_peer(self):
        m = self.peer / "manifest.json"
        doc = json.loads(m.read_text(encoding="utf-8"))
        doc["corpus_content_hash"] = "e" * 64
        m.write_text(json.dumps(doc), encoding="utf-8")
        with self.assertRaises(SystemExit):
            beb.emit(self.export, self.peer, self.peers_record,
                     self.release_record)

    def test_deterministic_emission(self):
        tsv = (self.export / "bridge/entity-bridge.tsv").read_bytes()
        meta = (self.export / "bridge/entity-bridge.meta.json").read_bytes()
        beb.emit(self.export, self.peer, self.peers_record,
                 self.release_record)
        self.assertEqual(
            (self.export / "bridge/entity-bridge.tsv").read_bytes(), tsv)
        self.assertEqual(
            (self.export / "bridge/entity-bridge.meta.json").read_bytes(),
            meta)


if __name__ == "__main__":
    unittest.main()
