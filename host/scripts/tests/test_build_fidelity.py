#!/usr/bin/env python3
"""TDD for build_fidelity.py — V4/R2+F9 fidelity declarations.

The three declarations (open-world FKs, static-call XINDEX authority,
xindex coverage scope) are emitted as data with rates measured from
the emitted TSVs at build time — never stale numbers; --check
re-measures and fails on drift (a V6 validate input).

Run: python3 host/scripts/tests/test_build_fidelity.py
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS_DIR))

import build_fidelity as bf  # noqa: E402
import schema_v1  # noqa: E402


def _row(spec: schema_v1.FileSpec, **vals: str) -> str:
    return "\t".join(vals.get(c, "") for c in spec.columns)


def make_tree() -> Path:
    """A minimal 24-file tree exercising every measurement path.

    Census (5): ALPHA, BRAVO, CHARLIE, KFAIL, %DT.
    XINDEX covers ALPHA (clean) + CHARLIE (callee-divergent);
    KFAIL is File 9.8 type-R but uncovered (the ZLINK-fail cohort);
    BRAVO and %DT are not File 9.8-registered.
    """
    root = Path(tempfile.mkdtemp())
    for name, spec in schema_v1.FILES.items():
        d = root / spec.model
        d.mkdir(exist_ok=True)
        (d / name).write_text("\t".join(spec.columns) + "\n")

    def fill(name: str, rows: list[dict]) -> None:
        spec = schema_v1.spec_for(name)
        p = root / spec.model / name
        body = "".join(_row(spec, **r) + "\n" for r in rows)
        p.write_text("\t".join(spec.columns) + "\n" + body)

    fill("packages.tsv", [{"package": "Kernel"}])
    fill("routines.tsv", [
        {"routine_name": n, "package": "Kernel",
         "is_percent_routine": "Y" if n == "%DT" else "N"}
        for n in ("%DT", "ALPHA", "BRAVO", "CHARLIE", "KFAIL")])
    fill("routines-comprehensive.tsv", [
        {"routine_name": "%DT", "package": "Kernel",
         "is_percent_routine": "Y", "in_file_9_8": "N"},
        {"routine_name": "ALPHA", "package": "Kernel",
         "is_percent_routine": "N", "in_file_9_8": "Y",
         "file_9_8_type": "R"},
        {"routine_name": "BRAVO", "package": "Kernel",
         "is_percent_routine": "N", "in_file_9_8": "N"},
        {"routine_name": "CHARLIE", "package": "Kernel",
         "is_percent_routine": "N", "in_file_9_8": "Y",
         "file_9_8_type": "PK"},
        {"routine_name": "KFAIL", "package": "Kernel",
         "is_percent_routine": "N", "in_file_9_8": "Y",
         "file_9_8_type": "R"},
    ])
    fill("xindex-routines.tsv", [
        {"routine_name": "ALPHA"}, {"routine_name": "CHARLIE"}])
    fill("xindex-validation.tsv", [
        {"routine_name": "ALPHA", "package": "Kernel",
         "lines_match": "Y", "tags_match": "Y",
         "callees_ours_only_count": "0",
         "callees_xindex_only_count": "0"},
        {"routine_name": "CHARLIE", "package": "Kernel",
         "lines_match": "N", "tags_match": "Y",
         "callees_ours_only_count": "1",
         "callees_xindex_only_count": "0"},
    ])
    fill("routine-calls.tsv", [
        {"caller_routine": "ALPHA", "caller_package": "Kernel",
         "callee_routine": "BRAVO", "kind": "do", "ref_count": "1"},
        {"caller_routine": "ALPHA", "caller_package": "Kernel",
         "callee_routine": "ZZEXT", "kind": "do", "ref_count": "1"},
    ])
    return root


class TestFkOpenWorld(unittest.TestCase):
    def setUp(self):
        self.doc = bf.build_fidelity(make_tree())
        self.edges = {(e["file"], e["column"]): e
                      for e in self.doc["declarations"]
                      ["fk_open_world"]["edges"]}

    def test_every_declared_fk_edge_measured(self):
        want = {(name, col)
                for name, spec in schema_v1.FILES.items()
                for col in spec.fks}
        self.assertEqual(set(self.edges), want)

    def test_unresolved_edge_marked_open_world_with_rate(self):
        e = self.edges[("routine-calls.tsv", "callee_routine")]
        self.assertEqual(e["target"], "routines.tsv:routine_name")
        self.assertEqual(e["distinct_values"], 2)
        self.assertEqual(e["unresolved"], 1)
        self.assertEqual(e["unresolved_rate"], 0.5)
        self.assertTrue(e["open_world"])

    def test_resolved_edge_is_closed(self):
        e = self.edges[("routine-calls.tsv", "caller_routine")]
        self.assertEqual((e["unresolved"], e["open_world"]), (0, False))

    def test_empty_file_edge_measures_zero(self):
        e = self.edges[("protocol-calls.tsv", "callee_routine")]
        self.assertEqual(e["distinct_values"], 0)
        self.assertEqual(e["unresolved_rate"], 0.0)

    def test_blank_values_not_counted(self):
        # options.tsv is header-only; its nullable fk stays at zero
        e = self.edges[("options.tsv", "routine_name")]
        self.assertEqual(e["distinct_values"], 0)

    def test_characterized_edges_carry_note(self):
        self.assertIn("note",
                      self.edges[("vista-file-9-8.tsv", "routine_name")])


class TestXindexAuthority(unittest.TestCase):
    def setUp(self):
        self.d = bf.build_fidelity(make_tree())["declarations"][
            "xindex_static_call_authority"]

    def test_dynamic_dispatch_declared_out_of_scope(self):
        blob = " ".join(self.d["out_of_scope"])
        for phrase in ("DO @", "XECUTE", "dispatch"):
            self.assertIn(phrase, blob)

    def test_divergence_measured_from_validation(self):
        m = self.d["measured"]
        self.assertEqual(m["validated_routines"], 2)
        self.assertEqual(m["callee_divergent_routines"], 1)
        self.assertEqual(m["callee_divergence_rate"], 0.5)
        self.assertEqual(m["lines_mismatch"], 1)
        self.assertEqual(m["tags_mismatch"], 0)


class TestXindexCoverage(unittest.TestCase):
    def setUp(self):
        self.d = bf.build_fidelity(make_tree())["declarations"][
            "xindex_coverage"]

    def test_coverage_counts(self):
        m = self.d["measured"]
        self.assertEqual(m["census_routines"], 5)
        self.assertEqual(m["covered_routines"], 2)
        self.assertEqual(m["coverage_rate"], 0.4)

    def test_gap_decomposition_sums_to_gap(self):
        g = self.d["measured"]["gap"]
        self.assertEqual(g["not_in_file_9_8"], 2)
        self.assertEqual(g["file_9_8_non_r_uncovered"], 0)
        self.assertEqual(g["file_9_8_r_uncovered"], 1)
        self.assertEqual(g["file_9_8_r_uncovered_routines"], ["KFAIL"])
        self.assertEqual(sum((g["not_in_file_9_8"],
                              g["file_9_8_non_r_uncovered"],
                              g["file_9_8_r_uncovered"])), 5 - 2)

    def test_percent_routines_verified_outside_xindex(self):
        m = self.d["measured"]
        self.assertEqual(m["percent_routines_in_census"], 1)
        self.assertEqual(m["percent_routines_covered"], 0)

    def test_divergence_denominator_excludes_percent_routines(self):
        self.assertIn("%-routines", self.d["divergence_denominator"])
        self.assertIn("excluded", self.d["divergence_denominator"])


class TestDeclarationsPresent(unittest.TestCase):
    """The V4 gate: all three declarations present, with prose."""

    def test_three_declarations_with_statements(self):
        decls = bf.build_fidelity(make_tree())["declarations"]
        self.assertEqual(
            set(decls),
            {"fk_open_world", "xindex_static_call_authority",
             "xindex_coverage"})
        for d in decls.values():
            self.assertTrue(d["statement"].strip())

    def test_schema_version(self):
        self.assertEqual(bf.build_fidelity(make_tree())["schema_version"], 1)


class TestFreshnessGate(unittest.TestCase):
    """--check re-measures; stale numbers fail (the V4 gate clause)."""

    def setUp(self):
        self.root = make_tree()
        self.out = self.root / "meta/fidelity.json"
        self.out.parent.mkdir(exist_ok=True)
        self.out.write_text(bf.render(self.root), encoding="utf-8")

    def test_fresh_file_passes(self):
        self.assertEqual(bf.check(self.root, self.out), [])

    def test_stale_numbers_fail(self):
        doc = json.loads(self.out.read_text())
        doc["declarations"]["xindex_coverage"]["measured"][
            "covered_routines"] += 1
        self.out.write_text(json.dumps(doc), encoding="utf-8")
        errs = bf.check(self.root, self.out)
        self.assertTrue(any("xindex_coverage" in e for e in errs))

    def test_missing_file_fails(self):
        self.out.unlink()
        self.assertTrue(bf.check(self.root, self.out))

    def test_deterministic_serialization(self):
        self.assertEqual(bf.render(self.root), bf.render(self.root))


if __name__ == "__main__":
    unittest.main()
