#!/usr/bin/env python3
# The declarative schema_version 1 registry — single source of truth
# for the 24-TSV export contract.
# Spec: docs/proposals/schema-v1-normalization-spec.md
# Plan: docs/proposals/producer-contracts-implementation-plan.md § V1

"""Final column order, primary keys, renames, booleans and enum labels
for every schema_version 1 file.

Producers emit through tsvio using these specs; V3's typed column
manifest and V6's validate step are derived from this module, so a
schema change is made exactly once, here.

Conventions (spec § 5): UTF-8, tab-separated, LF; blank = null (the
one exception: rpcs.inactive, where blank is documented as 0/ACTIVE);
rows sorted bytewise on `sort` (defaults to `pk`); `pk = ()` means no
uniqueness is asserted yet (piks-triage until V2's red-gate).

Primary keys below were verified unique on the live 2026-07-03 export
before being declared (zero duplicate keys per candidate, measured).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class FileSpec:
    name: str                      # basename, e.g. "rpcs.tsv"
    model: str                     # "data-model" | "code-model"
    producer: str                  # "host" | "m-dump" (origin toolchain)
    columns: tuple[str, ...]       # final v1 emit order
    pk: tuple[str, ...]            # declared unique key (V6 asserts)
    sort: tuple[str, ...] = ()     # sort key; defaults to pk
    renames: dict[str, str] = field(default_factory=dict)  # raw → final
    booleans: tuple[str, ...] = ()  # Y/N/blank columns
    labels: dict[str, tuple[str, dict[str, str]]] = field(
        default_factory=dict)      # code col → (label col, code → label)
    dropped: tuple[str, ...] = ()  # raw columns removed at emit

    def __post_init__(self):
        if not self.sort:
            object.__setattr__(self, "sort", self.pk)


RPC_RETURN_TYPE_LABELS = {
    "1": "SINGLE VALUE",
    "2": "ARRAY",
    "3": "WORD PROCESSING",
    "4": "GLOBAL ARRAY",
    "5": "GLOBAL INSTANCE",
}

# Blank is documented as 0 for this field (File 8994, INACTIVE) — the
# one enum where blank is a value, not null.
RPC_INACTIVE_LABELS = {
    "": "ACTIVE",
    "0": "ACTIVE",
    "1": "INACTIVE",
    "2": "LOCAL-INACTIVE",
    "3": "REMOTE-INACTIVE",
}

# V2/B1: where a piks.tsv classification came from.
PIKS_SOURCES = ("auto", "triage", "inherited")

FILES_TSV_DROPPED = (
    "piks", "piks_method", "piks_confidence", "piks_evidence",
    "piks_secondary", "volatility", "sensitivity", "portability",
    "volume", "subdomain",
)

_SPECS = (
    # ── data-model ────────────────────────────────────────────────
    FileSpec(
        name="field-piks.tsv", model="data-model", producer="m-dump",
        columns=("file_number", "field_number", "field_name", "data_type",
                 "file_piks", "pointer_target", "ref_piks", "cross_piks",
                 "sensitivity_flag"),
        pk=("file_number", "field_number"),
        booleans=("sensitivity_flag",),
    ),
    FileSpec(
        name="files.tsv", model="data-model", producer="m-dump",
        columns=("file_number", "file_name", "global_root", "parent_file",
                 "field_count", "pointer_in", "pointer_out", "record_count",
                 "is_dinum", "status"),
        pk=("file_number",),
        booleans=("is_dinum",),
        dropped=FILES_TSV_DROPPED,
    ),
    FileSpec(
        # Hand-curated provenance input. file_number became assertable
        # at V2: the live 107.3 conflict was resolved and the merge
        # red-gates any future duplicate.
        name="piks-triage.tsv", model="data-model", producer="host",
        columns=("file_number", "piks", "piks_method", "piks_confidence",
                 "piks_evidence"),
        pk=("file_number",),
    ),
    FileSpec(
        # V2/B1: materialized merge (triage > auto > inherited) —
        # consumers read one authoritative value, never re-merge.
        name="piks.tsv", model="data-model", producer="m-dump",
        columns=("file_number", "piks", "piks_method", "piks_confidence",
                 "piks_evidence", "piks_source"),
        pk=("file_number",),
    ),
    # ── code-model ────────────────────────────────────────────────
    FileSpec(
        name="options.tsv", model="code-model", producer="m-dump",
        columns=("ien", "name", "menu_text", "type", "package",
                 "routine_raw", "tag", "routine_name", "package_dir"),
        pk=("ien",),
        renames={"routine": "routine_name"},
    ),
    FileSpec(
        name="package-data.tsv", model="code-model", producer="host",
        columns=("package", "kind", "file_number", "chunk", "entity_name",
                 "source_path", "byte_size"),
        pk=("package", "kind", "file_number", "chunk", "entity_name"),
    ),
    FileSpec(
        name="package-edge-matrix.tsv", model="code-model", producer="host",
        columns=("source_package", "dest_package", "call_edges",
                 "distinct_caller_routines", "distinct_callee_routines"),
        pk=("source_package", "dest_package"),
    ),
    FileSpec(
        name="package-manifest.tsv", model="code-model", producer="host",
        columns=("package", "routine_count", "total_lines", "files_shipped",
                 "p_files", "i_files", "k_files", "s_files", "rpc_routines",
                 "option_routines", "distinct_globals_touched",
                 "outbound_edges", "outbound_cross_pkg"),
        pk=("package",),
    ),
    FileSpec(
        name="package-namespace.tsv", model="code-model", producer="host",
        columns=("package", "package_name", "namespace", "prefixes",
                 "app_code", "vdl_id"),
        pk=("package",),
    ),
    FileSpec(
        name="package-piks-summary.tsv", model="code-model", producer="host",
        columns=("package", "p_files", "i_files", "k_files", "s_files",
                 "unclassified", "total_distinct_files"),
        pk=("package",),
    ),
    FileSpec(
        name="packages.tsv", model="code-model", producer="host",
        columns=("package", "routine_count", "percent_routine_count",
                 "total_lines", "total_bytes"),
        pk=("package",),
    ),
    FileSpec(
        name="protocol-calls.tsv", model="code-model", producer="host",
        columns=("protocol_name", "protocol_package", "action_kind",
                 "callee_tag", "callee_routine", "call_kind", "ref_count"),
        pk=("protocol_name", "action_kind", "callee_tag", "callee_routine",
            "call_kind"),
    ),
    FileSpec(
        name="protocols.tsv", model="code-model", producer="m-dump",
        columns=("ien", "name", "item_text", "type", "package",
                 "entry_action", "exit_action", "package_dir"),
        pk=("ien",),
    ),
    FileSpec(
        name="routine-calls.tsv", model="code-model", producer="host",
        columns=("caller_routine", "caller_package", "callee_tag",
                 "callee_routine", "kind", "ref_count"),
        pk=("caller_routine", "callee_tag", "callee_routine", "kind"),
        renames={"caller_name": "caller_routine"},
    ),
    FileSpec(
        name="routine-globals.tsv", model="code-model", producer="host",
        columns=("routine_name", "package", "global_name", "ref_count"),
        pk=("routine_name", "global_name"),
    ),
    FileSpec(
        name="routines-comprehensive.tsv", model="code-model",
        producer="host",
        columns=("routine_name", "package", "source_path", "line_count",
                 "byte_size", "tag_count", "comment_line_count",
                 "version_line", "is_percent_routine", "in_file_9_8",
                 "file_9_8_type", "rpc_count", "option_count",
                 "protocol_invoked_count", "out_degree", "in_degree",
                 "out_calls_total", "in_calls_total",
                 "distinct_globals_touched", "global_ref_total"),
        pk=("routine_name",),
        booleans=("is_percent_routine", "in_file_9_8"),
    ),
    FileSpec(
        name="routines.tsv", model="code-model", producer="host",
        columns=("routine_name", "package", "source_path", "line_count",
                 "byte_size", "first_line_comment", "version_line",
                 "tag_count", "comment_line_count", "is_percent_routine"),
        pk=("routine_name",),
        booleans=("is_percent_routine",),
    ),
    FileSpec(
        name="rpcs.tsv", model="code-model", producer="m-dump",
        columns=("ien", "name", "tag", "routine_name",
                 "return_type", "return_type_label",
                 "availability", "inactive", "inactive_label",
                 "version", "package", "package_dir"),
        pk=("ien",),
        renames={"routine": "routine_name"},
        labels={
            "return_type": ("return_type_label", RPC_RETURN_TYPE_LABELS),
            "inactive": ("inactive_label", RPC_INACTIVE_LABELS),
        },
    ),
    FileSpec(
        name="vista-file-9-8.tsv", model="code-model", producer="m-dump",
        columns=("ien", "routine_name", "type", "byte_size", "rsum_value",
                 "checksum_value"),
        pk=("ien",),
        renames={"name": "routine_name", "size_bytes": "byte_size"},
    ),
    FileSpec(
        name="xindex-errors.tsv", model="code-model", producer="m-dump",
        columns=("routine_name", "entry_index", "line_text", "tag_offset",
                 "error_text"),
        pk=("routine_name", "entry_index"),
        renames={"routine": "routine_name"},
    ),
    FileSpec(
        name="xindex-routines.tsv", model="code-model", producer="m-dump",
        columns=("routine_name", "line_count", "tag_count", "xref_count",
                 "error_count", "rsum_value"),
        pk=("routine_name",),
        renames={"routine": "routine_name"},
    ),
    FileSpec(
        name="xindex-tags.tsv", model="code-model", producer="m-dump",
        columns=("routine_name", "tag", "data"),
        pk=("routine_name", "tag"),
        renames={"routine": "routine_name"},
    ),
    FileSpec(
        name="xindex-validation.tsv", model="code-model", producer="host",
        columns=("routine_name", "package", "lines_ours", "lines_xindex",
                 "lines_match", "tags_ours", "tags_xindex", "tags_match",
                 "callees_ours_count", "callees_xindex_count",
                 "callees_match_count", "callees_ours_only_count",
                 "callees_xindex_only_count", "callees_agreement_ratio"),
        pk=("routine_name",),
        renames={"routine": "routine_name"},
        booleans=("lines_match", "tags_match"),
    ),
    FileSpec(
        name="xindex-xrefs.tsv", model="code-model", producer="m-dump",
        columns=("routine_name", "ref", "location_list"),
        pk=("routine_name", "ref"),
        renames={"routine": "routine_name"},
    ),
)

FILES: dict[str, FileSpec] = {s.name: s for s in _SPECS}


def spec_for(name: str) -> FileSpec:
    """Look up the FileSpec for a basename; KeyError if not in v1."""
    return FILES[name]
