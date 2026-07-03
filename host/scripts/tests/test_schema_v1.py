#!/usr/bin/env python3
"""TDD for schema_v1.py — the declarative schema_version 1 registry.

The registry is the single source of truth for the 24-TSV export:
final column order, primary key, rename map, booleans, enum labels.
V3's typed manifest and V6's validate step derive from it.

Spec: docs/proposals/schema-v1-normalization-spec.md
Plan: docs/proposals/producer-contracts-implementation-plan.md § V1

Run: python3 host/scripts/tests/test_schema_v1.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS_DIR))

import schema_v1 as sv  # noqa: E402

# The frozen schema_version 1 file set (spec § 5/§ 7: 24 TSVs, no CSV).
EXPECTED_FILES = {
    "data-model": {
        "field-piks.tsv",
        "files.tsv",
        "piks-triage.tsv",
        "piks.tsv",
    },
    "code-model": {
        "options.tsv",
        "package-data.tsv",
        "package-edge-matrix.tsv",
        "package-manifest.tsv",
        "package-namespace.tsv",
        "package-piks-summary.tsv",
        "packages.tsv",
        "protocol-calls.tsv",
        "protocols.tsv",
        "routine-calls.tsv",
        "routine-globals.tsv",
        "routines-comprehensive.tsv",
        "routines.tsv",
        "rpcs.tsv",
        "vista-file-9-8.tsv",
        "xindex-errors.tsv",
        "xindex-routines.tsv",
        "xindex-tags.tsv",
        "xindex-validation.tsv",
        "xindex-xrefs.tsv",
    },
}


class TestFileSet(unittest.TestCase):
    def test_exactly_24_files(self):
        self.assertEqual(len(sv.FILES), 24)

    def test_file_set_matches_frozen_contract(self):
        for model, names in EXPECTED_FILES.items():
            got = {s.name for s in sv.FILES.values() if s.model == model}
            self.assertEqual(got, names, model)

    def test_no_csv(self):
        self.assertFalse(any(n.endswith(".csv") for n in sv.FILES))

    def test_lookup_by_name(self):
        self.assertIs(sv.spec_for("rpcs.tsv"), sv.FILES["rpcs.tsv"])
        with self.assertRaises(KeyError):
            sv.spec_for("vista-fileman-piks-comprehensive.csv")


class TestSpecInvariants(unittest.TestCase):
    """Structural rules every FileSpec must satisfy."""

    def test_pk_subset_of_columns(self):
        for s in sv.FILES.values():
            self.assertTrue(set(s.pk) <= set(s.columns), s.name)

    def test_every_file_declares_a_sort_key(self):
        # V6 asserts uniqueness only where pk is declared, but every
        # file must sort deterministically (spec § 5).
        for s in sv.FILES.values():
            self.assertTrue(s.sort, s.name)
            self.assertTrue(set(s.sort) <= set(s.columns), s.name)

    def test_no_duplicate_columns(self):
        for s in sv.FILES.values():
            self.assertEqual(len(s.columns), len(set(s.columns)), s.name)

    def test_booleans_subset_of_columns(self):
        for s in sv.FILES.values():
            self.assertTrue(set(s.booleans) <= set(s.columns), s.name)

    def test_rename_targets_present_sources_absent(self):
        for s in sv.FILES.values():
            for old, new in s.renames.items():
                self.assertIn(new, s.columns, f"{s.name}: {new}")
                self.assertNotIn(old, s.columns, f"{s.name}: {old}")

    def test_label_columns_follow_their_code_column(self):
        for s in sv.FILES.values():
            for code_col, (label_col, mapping) in s.labels.items():
                i = s.columns.index(code_col)
                self.assertEqual(
                    s.columns[i + 1], label_col, f"{s.name}: {code_col}"
                )
                self.assertTrue(mapping, f"{s.name}: {code_col}")

    def test_producer_is_known(self):
        for s in sv.FILES.values():
            self.assertIn(s.producer, ("host", "m-dump"), s.name)


class TestCanonicalVocabulary(unittest.TestCase):
    """Spec § 1/§ 2 — one canonical routine token everywhere."""

    def test_no_legacy_routine_identifier_columns(self):
        for s in sv.FILES.values():
            for forbidden in ("routine", "caller_name", "size_bytes"):
                self.assertNotIn(forbidden, s.columns, s.name)

    def test_vista_file_9_8_renames(self):
        s = sv.spec_for("vista-file-9-8.tsv")
        self.assertNotIn("name", s.columns)
        self.assertIn("routine_name", s.columns)
        self.assertIn("byte_size", s.columns)
        self.assertEqual(s.renames["name"], "routine_name")
        self.assertEqual(s.renames["size_bytes"], "byte_size")

    def test_routine_calls_rename(self):
        s = sv.spec_for("routine-calls.tsv")
        self.assertEqual(s.renames["caller_name"], "caller_routine")
        self.assertEqual(
            s.pk, ("caller_routine", "callee_tag", "callee_routine", "kind")
        )

    def test_xindex_family_renamed(self):
        for name in (
            "xindex-errors.tsv",
            "xindex-routines.tsv",
            "xindex-tags.tsv",
            "xindex-validation.tsv",
            "xindex-xrefs.tsv",
        ):
            s = sv.spec_for(name)
            self.assertEqual(s.renames.get("routine"), "routine_name", name)

    def test_options_keeps_raw_action_string(self):
        # `routine_raw` is the distinct raw/unparsed action string —
        # deliberately NOT renamed (spec § 2 note).
        s = sv.spec_for("options.tsv")
        self.assertIn("routine_raw", s.columns)
        self.assertIn("routine_name", s.columns)


class TestFilesTsvCleanup(unittest.TestCase):
    """Spec § 5 — files.tsv drops its 10 measured-empty classification
    columns (piks.tsv is the one authoritative surface, per B1)."""

    DROPPED = (
        "piks", "piks_method", "piks_confidence", "piks_evidence",
        "piks_secondary", "volatility", "sensitivity", "portability",
        "volume", "subdomain",
    )

    def test_empty_classification_columns_dropped(self):
        s = sv.spec_for("files.tsv")
        for col in self.DROPPED:
            self.assertNotIn(col, s.columns, col)
        self.assertEqual(s.dropped, self.DROPPED)

    def test_populated_columns_kept(self):
        s = sv.spec_for("files.tsv")
        self.assertEqual(
            s.columns,
            ("file_number", "file_name", "global_root", "parent_file",
             "field_count", "pointer_in", "pointer_out", "record_count",
             "is_dinum", "status"),
        )


class TestRpcEnumLabels(unittest.TestCase):
    """Spec § 3 — integer enums gain sibling _label columns."""

    def test_return_type_label(self):
        s = sv.spec_for("rpcs.tsv")
        label_col, mapping = s.labels["return_type"]
        self.assertEqual(label_col, "return_type_label")
        self.assertEqual(
            mapping,
            {"1": "SINGLE VALUE", "2": "ARRAY", "3": "WORD PROCESSING",
             "4": "GLOBAL ARRAY", "5": "GLOBAL INSTANCE"},
        )

    def test_inactive_label_blank_means_active(self):
        # Field-level doc: inactive is 0-3 with blank = 0 (ACTIVE) —
        # the one field where blank is a value, not null (spec § 3).
        s = sv.spec_for("rpcs.tsv")
        label_col, mapping = s.labels["inactive"]
        self.assertEqual(label_col, "inactive_label")
        self.assertEqual(mapping[""], "ACTIVE")
        self.assertEqual(mapping["0"], "ACTIVE")
        self.assertEqual(mapping["1"], "INACTIVE")
        self.assertEqual(mapping["2"], "LOCAL-INACTIVE")
        self.assertEqual(mapping["3"], "REMOTE-INACTIVE")

    def test_rpcs_final_column_order(self):
        s = sv.spec_for("rpcs.tsv")
        self.assertEqual(
            s.columns,
            ("ien", "name", "tag", "routine_name",
             "return_type", "return_type_label",
             "availability", "inactive", "inactive_label",
             "version", "package", "package_dir"),
        )


class TestDeclaredBooleans(unittest.TestCase):
    """Spec § 4 — Y/N with blank = null, declared per file."""

    def test_boolean_columns_declared(self):
        expect = {
            "routines.tsv": ("is_percent_routine",),
            "routines-comprehensive.tsv": ("is_percent_routine",
                                           "in_file_9_8"),
            "files.tsv": ("is_dinum",),
            "field-piks.tsv": ("sensitivity_flag",),
            "xindex-validation.tsv": ("lines_match", "tags_match"),
        }
        for name, cols in expect.items():
            self.assertEqual(sv.spec_for(name).booleans, cols, name)


class TestPrimaryKeys(unittest.TestCase):
    def test_declared_pks(self):
        expect = {
            "files.tsv": ("file_number",),
            "piks.tsv": ("file_number",),
            "field-piks.tsv": ("file_number", "field_number"),
            "routines.tsv": ("routine_name",),
            "routines-comprehensive.tsv": ("routine_name",),
            "packages.tsv": ("package",),
            "package-edge-matrix.tsv": ("source_package", "dest_package"),
            "routine-globals.tsv": ("routine_name", "global_name"),
            "rpcs.tsv": ("ien",),
            "options.tsv": ("ien",),
            "protocols.tsv": ("ien",),
            "vista-file-9-8.tsv": ("ien",),
            "xindex-routines.tsv": ("routine_name",),
            "xindex-validation.tsv": ("routine_name",),
        }
        for name, pk in expect.items():
            self.assertEqual(sv.spec_for(name).pk, pk, name)

    def test_piks_triage_declares_no_pk_until_v2(self):
        # The live 107.3 conflict means uniqueness on file_number is
        # not yet assertable; V2's red-gate resolves it. Sort is still
        # deterministic via the declared sort key.
        s = sv.spec_for("piks-triage.tsv")
        self.assertEqual(s.pk, ())
        self.assertTrue(s.sort)


if __name__ == "__main__":
    unittest.main()
