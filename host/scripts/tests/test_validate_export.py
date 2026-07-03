#!/usr/bin/env python3
"""TDD for validate_export.py — V6 validate step (doctor-equivalent).

The gate: validate passes on a good emission and FAILS LOUDLY on
seeded defects — duplicated PK, stray CRLF, manifest/header mismatch,
missing piks row, ragged row, absent engine fields, an edge row
naming a routine outside the census (the plan §V6 list), plus the
supporting contract checks (extra/missing files, sort order, nulls,
booleans, meta freshness).

Run: python3 host/scripts/tests/test_validate_export.py
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS_DIR))

import build_column_manifest as bcm  # noqa: E402
import build_fidelity as bf  # noqa: E402
import schema_v1  # noqa: E402
import tsvio  # noqa: E402
import validate_export as vx  # noqa: E402

SIDE_CAR = {
    "engine": "ydb",
    "engine_image": "vista-meta:latest",
    "engine_image_id": "sha256:abc",
    "container_id": "c0ffee000000",
    "extraction_timestamp": "2026-07-03T00:00:00Z",
    "db_state_fingerprint": "f" * 64,
    "source_commit": "0" * 40,
}


def _defaults(spec: schema_v1.FileSpec, **given: str) -> dict:
    """A contract-conforming row: given cells + type-correct filler."""
    row = {}
    for c in spec.columns:
        if c in given:
            row[c] = given[c]
        elif c in spec.nullable:
            row[c] = ""
        elif c in spec.booleans:
            row[c] = "N"
        elif (spec.name, c) in schema_v1.ENUM_DOMAINS:
            row[c] = schema_v1.ENUM_DOMAINS[(spec.name, c)][0]
        elif spec.effective_type(c) == "int":
            row[c] = "1"
        elif spec.effective_type(c) == "float":
            row[c] = "1.0"
        else:
            row[c] = "x"
    return row


def make_tree() -> Path:
    """A conforming mini-emission: consistent joins, fresh meta."""
    root = Path(tempfile.mkdtemp())
    rows: dict[str, list[dict]] = {name: [] for name in schema_v1.FILES}

    rows["packages.tsv"] = [_defaults(
        schema_v1.spec_for("packages.tsv"), package="Kernel")]
    rspec = schema_v1.spec_for("routines.tsv")
    rows["routines.tsv"] = [
        _defaults(rspec, routine_name=n, package="Kernel")
        for n in ("ALPHA", "BRAVO")]
    cspec = schema_v1.spec_for("routines-comprehensive.tsv")
    rows["routines-comprehensive.tsv"] = [
        _defaults(cspec, routine_name=n, package="Kernel",
                  in_file_9_8="Y", file_9_8_type="R")
        for n in ("ALPHA", "BRAVO")]
    rows["files.tsv"] = [_defaults(
        schema_v1.spec_for("files.tsv"), file_number="1")]
    rows["piks.tsv"] = [_defaults(
        schema_v1.spec_for("piks.tsv"), file_number="1", piks="P",
        piks_source="auto")]
    rows["routine-calls.tsv"] = [_defaults(
        schema_v1.spec_for("routine-calls.tsv"),
        caller_routine="ALPHA", caller_package="Kernel",
        callee_routine="BRAVO", kind="do")]
    rows["routine-globals.tsv"] = [_defaults(
        schema_v1.spec_for("routine-globals.tsv"),
        routine_name="ALPHA", package="Kernel", global_name="^DPT")]
    rows["xindex-routines.tsv"] = [_defaults(
        schema_v1.spec_for("xindex-routines.tsv"),
        routine_name="ALPHA")]
    rows["xindex-validation.tsv"] = [_defaults(
        schema_v1.spec_for("xindex-validation.tsv"),
        routine_name="ALPHA", package="Kernel",
        lines_match="Y", tags_match="Y",
        callees_ours_only_count="0", callees_xindex_only_count="0")]

    for name, spec in schema_v1.FILES.items():
        d = root / spec.model
        d.mkdir(exist_ok=True)
        tsvio.write_spec(d / name, spec, rows[name])

    meta = root / "meta"
    meta.mkdir()
    (meta / "column-manifest.json").write_text(bcm.render(),
                                               encoding="utf-8")
    (meta / "fidelity.json").write_text(bf.render(root), encoding="utf-8")
    raw = root / "raw"
    raw.mkdir()
    (raw / "extraction.json").write_text(
        json.dumps(SIDE_CAR, indent=2) + "\n", encoding="utf-8")
    return root


def errs(root: Path) -> list[str]:
    return vx.validate(root).errors


class TestGoodEmissionPasses(unittest.TestCase):
    def test_no_errors_no_warnings(self):
        report = vx.validate(make_tree())
        self.assertEqual(report.errors, [])
        self.assertEqual(report.warnings, [])


class TestSeededDefectsFailLoudly(unittest.TestCase):
    """One test per plan §V6 seeded defect, plus supporting checks."""

    def setUp(self):
        self.root = make_tree()

    def _append(self, name: str, line: str) -> None:
        spec = schema_v1.spec_for(name)
        p = self.root / spec.model / name
        p.write_text(p.read_text() + line + "\n", encoding="utf-8")

    def assert_error(self, fragment: str):
        found = errs(self.root)
        self.assertTrue(any(fragment in e for e in found),
                        f"no error containing {fragment!r} in {found}")

    def test_duplicated_pk(self):
        p = self.root / "data-model/piks.tsv"
        lines = p.read_text().splitlines()
        p.write_text("\n".join(lines + [lines[-1]]) + "\n")
        self.assert_error("duplicate")

    def test_stray_crlf(self):
        p = self.root / "data-model/piks.tsv"
        p.write_bytes(p.read_bytes().replace(b"\n", b"\r\n"))
        self.assert_error("CR")

    def test_missing_final_newline(self):
        p = self.root / "data-model/piks.tsv"
        p.write_bytes(p.read_bytes().rstrip(b"\n"))
        self.assert_error("newline")

    def test_header_mismatch(self):
        p = self.root / "code-model/rpcs.tsv"
        p.write_text(p.read_text().replace("routine_name", "routine"))
        self.assert_error("header")

    def test_missing_piks_row(self):
        p = self.root / "data-model/piks.tsv"
        lines = p.read_text().splitlines()
        p.write_text(lines[0] + "\n")  # drop the data row
        self.assert_error("coverage")

    def test_ragged_row(self):
        self._append("piks.tsv", "9\tP\tm")
        self.assert_error("cells")

    def test_absent_engine_fields(self):
        side = self.root / "raw/extraction.json"
        doc = json.loads(side.read_text())
        del doc["db_state_fingerprint"]
        side.write_text(json.dumps(doc))
        self.assert_error("db_state_fingerprint")

    def test_missing_sidecar(self):
        (self.root / "raw/extraction.json").unlink()
        self.assert_error("extraction.json")

    def test_edge_row_naming_routine_outside_census(self):
        spec = schema_v1.spec_for("routine-calls.tsv")
        row = _defaults(spec, caller_routine="ZZOUT",
                        caller_package="Kernel", callee_routine="BRAVO",
                        kind="do")
        self._append("routine-calls.tsv",
                     "\t".join(row[c] for c in spec.columns))
        self.assert_error("caller_routine")

    def test_open_world_edge_does_not_error(self):
        # same shape, but on the DECLARED open edge: callee unresolved
        spec = schema_v1.spec_for("routine-calls.tsv")
        row = _defaults(spec, caller_routine="ALPHA",
                        caller_package="Kernel", callee_routine="ZZEXT",
                        kind="do")
        self._append("routine-calls.tsv",
                     "\t".join(row[c] for c in spec.columns))
        # keep meta fresh so the only candidate failure is the FK check
        (self.root / "meta/fidelity.json").write_text(
            bf.render(self.root), encoding="utf-8")
        self.assertFalse(
            [e for e in errs(self.root) if "callee_routine" in e])

    def test_missing_file(self):
        (self.root / "data-model/field-piks.tsv").unlink()
        self.assert_error("missing")

    def test_extra_file(self):
        (self.root / "code-model/stray.tsv").write_text("x\n")
        self.assert_error("stray.tsv")

    def test_unsorted_rows(self):
        p = self.root / "code-model/routines.tsv"
        lines = p.read_text().splitlines()
        lines[1], lines[2] = lines[2], lines[1]
        p.write_text("\n".join(lines) + "\n")
        self.assert_error("sort")

    def test_non_nullable_blank(self):
        p = self.root / "code-model/routines.tsv"
        # blank out source_path (not in nullable) on the ALPHA row
        lines = p.read_text().splitlines()
        cells = lines[1].split("\t")
        spec = schema_v1.spec_for("routines.tsv")
        cells[spec.columns.index("source_path")] = ""
        lines[1] = "\t".join(cells)
        p.write_text("\n".join(lines) + "\n")
        self.assert_error("null")

    def test_boolean_junk(self):
        p = self.root / "code-model/routines.tsv"
        lines = p.read_text().splitlines()
        cells = lines[1].split("\t")
        spec = schema_v1.spec_for("routines.tsv")
        cells[spec.columns.index("is_percent_routine")] = "Q"
        lines[1] = "\t".join(cells)
        p.write_text("\n".join(lines) + "\n")
        self.assert_error("boolean")

    def test_comprehensive_census_set_inequality(self):
        p = self.root / "code-model/routines-comprehensive.tsv"
        lines = p.read_text().splitlines()
        p.write_text("\n".join(lines[:2]) + "\n")  # drop BRAVO
        self.assert_error("routines-comprehensive")

    def test_stale_column_manifest(self):
        (self.root / "meta/column-manifest.json").write_text("{}\n")
        self.assert_error("column-manifest")

    def test_stale_fidelity(self):
        doc = json.loads(
            (self.root / "meta/fidelity.json").read_text())
        doc["declarations"]["xindex_coverage"]["measured"][
            "covered_routines"] += 1
        (self.root / "meta/fidelity.json").write_text(json.dumps(doc))
        self.assert_error("fidelity")


class TestEnumWarnings(unittest.TestCase):
    def test_out_of_domain_enum_warns_not_errors(self):
        root = make_tree()
        p = root / "data-model/piks.tsv"
        lines = p.read_text().splitlines()
        spec = schema_v1.spec_for("piks.tsv")
        cells = lines[1].split("\t")
        cells[spec.columns.index("piks_confidence")] = "wild"
        lines[1] = "\t".join(cells)
        p.write_text("\n".join(lines) + "\n")
        # refresh fidelity (piks values unchanged, but be safe)
        (root / "meta/fidelity.json").write_text(bf.render(root),
                                                 encoding="utf-8")
        report = vx.validate(root)
        self.assertFalse(
            [e for e in report.errors if "piks_confidence" in e])
        self.assertTrue(
            [w for w in report.warnings if "piks_confidence" in w])


class TestR3SourceManifest(unittest.TestCase):
    """A consumer tree (unpacked bundle) has no raw/ sidecar — the R3
    fields live in the bundle's manifest.json instead (V7)."""

    def setUp(self):
        self.root = make_tree()
        (self.root / "raw/extraction.json").unlink()

    def test_manifest_json_satisfies_r3(self):
        doc = dict(SIDE_CAR)
        (self.root / "manifest.json").write_text(json.dumps(doc))
        self.assertFalse([e for e in errs(self.root)
                          if "extraction.json" in e or "R3" in e])

    def test_manifest_json_missing_field_fails(self):
        doc = dict(SIDE_CAR)
        del doc["db_state_fingerprint"]
        (self.root / "manifest.json").write_text(json.dumps(doc))
        self.assertTrue([e for e in errs(self.root)
                         if "db_state_fingerprint" in e])

    def test_neither_source_fails(self):
        self.assertTrue([e for e in errs(self.root)
                         if "extraction.json" in e])



if __name__ == "__main__":
    unittest.main()
