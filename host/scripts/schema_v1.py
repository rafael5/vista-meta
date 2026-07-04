#!/usr/bin/env python3
# The declarative schema_version 1 registry — single source of truth
# for the 24-TSV export contract.
# Spec: docs/reference/schema-v1-normalization-spec.md
# Plan: docs/historical/producer-contracts-implementation-plan.md § V1

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
    # V3/R1 typing. coltypes holds only non-str declarations (int /
    # float / enum); booleans are typed via `booleans`; identifiers
    # (file_number, decimal ids) are deliberately str — 21.09 != 21.090.
    coltypes: dict[str, str] = field(default_factory=dict)
    # Columns that MAY be blank (null). Everything else is asserted
    # non-null (measured on the live emission; V6 gates it).
    nullable: tuple[str, ...] = ()
    # Semantic FK targets, "file.tsv:column". Open-world edges (rates,
    # exceptions) are R2/V4 fidelity declarations, not withheld here.
    fks: dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        if not self.sort:
            object.__setattr__(self, "sort", self.pk)

    def effective_type(self, col: str) -> str:
        if col in self.booleans:
            return "bool"
        return self.coltypes.get(col, "str")

    def key_role(self, col: str) -> str:
        if col in self.pk:
            return "pk"
        if col in self.fks:
            return "fk"
        return "none"


# The four cross-producer join vocabularies (R1 amendment): the keys
# vdocs entities resolve against. Declared as data in both producers'
# manifests — the thin, non-deferred slice of entity identity.
SHARED_VOCABULARIES = (
    ("routines.tsv", "routine_name"),
    ("files.tsv", "file_number"),
    ("options.tsv", "name"),
    ("rpcs.tsv", "name"),
)


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

# V6: the open/closed FK boundary is DECLARED here, not measured —
# a closed edge that stops resolving must FAIL validate, never
# silently become open-world. These 12 were measured open on the V4
# emission (rates + cause notes live in meta/fidelity.json).
OPEN_WORLD_FKS = frozenset({
    ("field-piks.tsv", "pointer_target"),
    ("files.tsv", "parent_file"),
    ("options.tsv", "package_dir"),
    ("options.tsv", "routine_name"),
    ("package-data.tsv", "file_number"),
    ("package-data.tsv", "package"),
    ("package-manifest.tsv", "package"),
    ("package-piks-summary.tsv", "package"),
    ("protocol-calls.tsv", "callee_routine"),
    ("routine-calls.tsv", "callee_routine"),
    ("rpcs.tsv", "routine_name"),
    ("vista-file-9-8.tsv", "routine_name"),
})

PIKS_CATEGORIES = ("I", "K", "P", "S")
PIKS_CONFIDENCES = ("certain", "high", "low", "moderate")

# V6: documented enum value domains, keyed (file, column). Blank is
# null (never a domain member); out-of-domain values are tolerated
# with a WARNING (open-world), per plan § V6. Domains were measured
# on the V4/V5 emission and frozen as the v1 documented sets.
ENUM_DOMAINS: dict[tuple[str, str], tuple[str, ...]] = {
    ("field-piks.tsv", "data_type"): (
        "COMPUTED", "DATE", "FREE-TEXT", "MUMPS", "NUMERIC", "OTHER",
        "POINTER", "SET", "VARIABLE-POINTER", "WORD-PROCESSING"),
    ("field-piks.tsv", "file_piks"): PIKS_CATEGORIES,
    ("field-piks.tsv", "ref_piks"): PIKS_CATEGORIES,
    ("field-piks.tsv", "cross_piks"): ("Y",),
    ("files.tsv", "status"): ("extracted",),
    ("piks-triage.tsv", "piks"): PIKS_CATEGORIES,
    ("piks-triage.tsv", "piks_confidence"): PIKS_CONFIDENCES,
    ("piks.tsv", "piks"): PIKS_CATEGORIES,
    ("piks.tsv", "piks_confidence"): PIKS_CONFIDENCES,
    ("piks.tsv", "piks_source"): PIKS_SOURCES,
    ("options.tsv", "type"): (
        "A", "B", "C", "E", "I", "M", "O", "P", "Q", "R", "S", "X"),
    ("package-data.tsv", "kind"): ("file", "global"),
    ("protocol-calls.tsv", "action_kind"): ("entry", "exit"),
    ("protocol-calls.tsv", "call_kind"): ("do", "func", "goto"),
    ("protocols.tsv", "type"): (
        "A", "D", "E", "L", "M", "O", "Q", "S", "X"),
    ("routine-calls.tsv", "kind"): ("do", "func", "goto", "job"),
    ("routines-comprehensive.tsv", "file_9_8_type"): ("PK", "R"),
    ("vista-file-9-8.tsv", "type"): ("PK", "R"),
    ("rpcs.tsv", "return_type"): tuple(sorted(RPC_RETURN_TYPE_LABELS)),
    ("rpcs.tsv", "return_type_label"):
        tuple(sorted(set(RPC_RETURN_TYPE_LABELS.values()))),
    ("rpcs.tsv", "inactive"):
        tuple(sorted(k for k in RPC_INACTIVE_LABELS if k)),
    ("rpcs.tsv", "inactive_label"):
        tuple(sorted(set(RPC_INACTIVE_LABELS.values()))),
    ("rpcs.tsv", "availability"): ("A", "P", "R", "S"),
}

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
        coltypes={"data_type": "enum", "file_piks": "enum",
                  "ref_piks": "enum", "cross_piks": "enum"},
        nullable=("field_name", "file_piks", "pointer_target",
                  "ref_piks", "cross_piks", "sensitivity_flag"),
        fks={"file_number": "files.tsv:file_number",
             "pointer_target": "files.tsv:file_number"},
    ),
    FileSpec(
        name="files.tsv", model="data-model", producer="m-dump",
        columns=("file_number", "file_name", "global_root", "parent_file",
                 "field_count", "pointer_in", "pointer_out", "record_count",
                 "is_dinum", "status"),
        pk=("file_number",),
        booleans=("is_dinum",),
        dropped=FILES_TSV_DROPPED,
        coltypes={"field_count": "int", "pointer_in": "int",
                  "pointer_out": "int", "record_count": "int",
                  "status": "enum"},
        nullable=("file_name", "global_root", "parent_file",
                  "record_count", "is_dinum"),
        fks={"parent_file": "files.tsv:file_number"},
    ),
    FileSpec(
        # Hand-curated provenance input. file_number became assertable
        # at V2: the live 107.3 conflict was resolved and the merge
        # red-gates any future duplicate.
        name="piks-triage.tsv", model="data-model", producer="host",
        columns=("file_number", "piks", "piks_method", "piks_confidence",
                 "piks_evidence"),
        pk=("file_number",),
        coltypes={"piks": "enum", "piks_confidence": "enum"},
        fks={"file_number": "files.tsv:file_number"},
    ),
    FileSpec(
        # V2/B1: materialized merge (triage > auto > inherited) —
        # consumers read one authoritative value, never re-merge.
        name="piks.tsv", model="data-model", producer="m-dump",
        columns=("file_number", "piks", "piks_method", "piks_confidence",
                 "piks_evidence", "piks_source"),
        pk=("file_number",),
        coltypes={"piks": "enum", "piks_confidence": "enum",
                  "piks_source": "enum"},
        fks={"file_number": "files.tsv:file_number"},
    ),
    # ── code-model ────────────────────────────────────────────────
    FileSpec(
        name="options.tsv", model="code-model", producer="m-dump",
        columns=("ien", "name", "menu_text", "type", "package",
                 "routine_raw", "tag", "routine_name", "package_dir"),
        pk=("ien",),
        renames={"routine": "routine_name"},
        coltypes={"ien": "int", "type": "enum"},
        nullable=("menu_text", "type", "package", "routine_raw", "tag",
                  "routine_name", "package_dir"),
        fks={"routine_name": "routines.tsv:routine_name",
             "package_dir": "packages.tsv:package"},
    ),
    FileSpec(
        name="package-data.tsv", model="code-model", producer="host",
        columns=("package", "kind", "file_number", "chunk", "entity_name",
                 "source_path", "byte_size"),
        pk=("package", "kind", "file_number", "chunk", "entity_name"),
        coltypes={"kind": "enum", "chunk": "int", "byte_size": "int"},
        nullable=("file_number", "chunk"),
        fks={"package": "packages.tsv:package",
             "file_number": "files.tsv:file_number"},
    ),
    FileSpec(
        name="package-edge-matrix.tsv", model="code-model", producer="host",
        columns=("source_package", "dest_package", "call_edges",
                 "distinct_caller_routines", "distinct_callee_routines"),
        pk=("source_package", "dest_package"),
        coltypes={"call_edges": "int", "distinct_caller_routines": "int",
                  "distinct_callee_routines": "int"},
        fks={"source_package": "packages.tsv:package",
             "dest_package": "packages.tsv:package"},
    ),
    FileSpec(
        name="package-manifest.tsv", model="code-model", producer="host",
        columns=("package", "routine_count", "total_lines", "files_shipped",
                 "p_files", "i_files", "k_files", "s_files", "rpc_routines",
                 "option_routines", "distinct_globals_touched",
                 "outbound_edges", "outbound_cross_pkg"),
        pk=("package",),
        coltypes={c: "int" for c in (
            "routine_count", "total_lines", "files_shipped", "p_files",
            "i_files", "k_files", "s_files", "rpc_routines",
            "option_routines", "distinct_globals_touched",
            "outbound_edges", "outbound_cross_pkg")},
        fks={"package": "packages.tsv:package"},
    ),
    FileSpec(
        name="package-namespace.tsv", model="code-model", producer="host",
        columns=("package", "package_name", "namespace", "prefixes",
                 "app_code", "vdl_id"),
        pk=("package",),
        coltypes={"vdl_id": "int"},
        nullable=("package_name", "namespace", "prefixes", "app_code",
                  "vdl_id"),
        fks={"package": "packages.tsv:package"},
    ),
    FileSpec(
        name="package-piks-summary.tsv", model="code-model", producer="host",
        columns=("package", "p_files", "i_files", "k_files", "s_files",
                 "unclassified", "total_distinct_files"),
        pk=("package",),
        coltypes={c: "int" for c in (
            "p_files", "i_files", "k_files", "s_files", "unclassified",
            "total_distinct_files")},
        fks={"package": "packages.tsv:package"},
    ),
    FileSpec(
        name="packages.tsv", model="code-model", producer="host",
        columns=("package", "routine_count", "percent_routine_count",
                 "total_lines", "total_bytes"),
        pk=("package",),
        coltypes={"routine_count": "int", "percent_routine_count": "int",
                  "total_lines": "int", "total_bytes": "int"},
    ),
    FileSpec(
        name="protocol-calls.tsv", model="code-model", producer="host",
        columns=("protocol_name", "protocol_package", "action_kind",
                 "callee_tag", "callee_routine", "call_kind", "ref_count"),
        pk=("protocol_name", "action_kind", "callee_tag", "callee_routine",
            "call_kind"),
        coltypes={"action_kind": "enum", "call_kind": "enum",
                  "ref_count": "int"},
        nullable=("protocol_package", "callee_tag"),
        # protocol_package carries the upper #9.4 NAME vocabulary
        # (measured), not the packages.tsv directory — no fk.
        fks={"protocol_name": "protocols.tsv:name",
             "callee_routine": "routines.tsv:routine_name"},
    ),
    FileSpec(
        name="protocols.tsv", model="code-model", producer="m-dump",
        columns=("ien", "name", "item_text", "type", "package",
                 "entry_action", "exit_action", "package_dir"),
        pk=("ien",),
        coltypes={"ien": "int", "type": "enum"},
        nullable=("item_text", "type", "package", "entry_action",
                  "exit_action", "package_dir"),
        fks={"package_dir": "packages.tsv:package"},
    ),
    FileSpec(
        name="routine-calls.tsv", model="code-model", producer="host",
        columns=("caller_routine", "caller_package", "callee_tag",
                 "callee_routine", "kind", "ref_count"),
        pk=("caller_routine", "callee_tag", "callee_routine", "kind"),
        renames={"caller_name": "caller_routine"},
        coltypes={"kind": "enum", "ref_count": "int"},
        nullable=("callee_tag",),
        fks={"caller_routine": "routines.tsv:routine_name",
             "callee_routine": "routines.tsv:routine_name",
             "caller_package": "packages.tsv:package"},
    ),
    FileSpec(
        name="routine-globals.tsv", model="code-model", producer="host",
        columns=("routine_name", "package", "global_name", "ref_count"),
        pk=("routine_name", "global_name"),
        coltypes={"ref_count": "int"},
        fks={"routine_name": "routines.tsv:routine_name",
             "package": "packages.tsv:package"},
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
        coltypes={c: "int" for c in (
            "line_count", "byte_size", "tag_count", "comment_line_count",
            "rpc_count", "option_count", "protocol_invoked_count",
            "out_degree", "in_degree", "out_calls_total", "in_calls_total",
            "distinct_globals_touched", "global_ref_total")} |
        {"file_9_8_type": "enum"},
        nullable=("package", "version_line", "file_9_8_type"),
        fks={"routine_name": "routines.tsv:routine_name",
             "package": "packages.tsv:package"},
    ),
    FileSpec(
        name="routines.tsv", model="code-model", producer="host",
        columns=("routine_name", "package", "source_path", "line_count",
                 "byte_size", "first_line_comment", "version_line",
                 "tag_count", "comment_line_count", "is_percent_routine"),
        pk=("routine_name",),
        booleans=("is_percent_routine",),
        coltypes={"line_count": "int", "byte_size": "int",
                  "tag_count": "int", "comment_line_count": "int"},
        nullable=("package", "first_line_comment", "version_line"),
        fks={"package": "packages.tsv:package"},
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
        coltypes={"ien": "int", "return_type": "enum", "inactive": "enum",
                  "return_type_label": "enum", "inactive_label": "enum",
                  "availability": "enum"},
        nullable=("tag", "routine_name", "return_type",
                  "return_type_label", "availability", "inactive",
                  "version", "package", "package_dir"),
        fks={"routine_name": "routines.tsv:routine_name",
             "package_dir": "packages.tsv:package"},
    ),
    FileSpec(
        name="vista-file-9-8.tsv", model="code-model", producer="m-dump",
        columns=("ien", "routine_name", "type", "byte_size", "rsum_value",
                 "checksum_value"),
        pk=("ien",),
        renames={"name": "routine_name", "size_bytes": "byte_size"},
        coltypes={"ien": "int", "type": "enum", "byte_size": "int"},
        nullable=("type", "byte_size", "rsum_value", "checksum_value"),
        fks={"routine_name": "routines.tsv:routine_name"},
    ),
    FileSpec(
        name="xindex-errors.tsv", model="code-model", producer="m-dump",
        columns=("routine_name", "entry_index", "line_text", "tag_offset",
                 "error_text"),
        pk=("routine_name", "entry_index"),
        renames={"routine": "routine_name"},
        # line_text holds line NUMBERS (measured all-int) despite the
        # name; naming is frozen with v1, typing is honest.
        coltypes={"entry_index": "int", "line_text": "int"},
        nullable=("line_text", "tag_offset"),
        fks={"routine_name": "routines.tsv:routine_name"},
    ),
    FileSpec(
        name="xindex-routines.tsv", model="code-model", producer="m-dump",
        columns=("routine_name", "line_count", "tag_count", "xref_count",
                 "error_count", "rsum_value"),
        pk=("routine_name",),
        renames={"routine": "routine_name"},
        coltypes={"line_count": "int", "tag_count": "int",
                  "xref_count": "int", "error_count": "int"},
        fks={"routine_name": "routines.tsv:routine_name"},
    ),
    FileSpec(
        name="xindex-tags.tsv", model="code-model", producer="m-dump",
        columns=("routine_name", "tag", "data"),
        pk=("routine_name", "tag"),
        renames={"routine": "routine_name"},
        nullable=("data",),
        fks={"routine_name": "routines.tsv:routine_name"},
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
        coltypes={c: "int" for c in (
            "lines_ours", "lines_xindex", "tags_ours", "tags_xindex",
            "callees_ours_count", "callees_xindex_count",
            "callees_match_count", "callees_ours_only_count",
            "callees_xindex_only_count")} |
        {"callees_agreement_ratio": "float"},
        fks={"routine_name": "routines.tsv:routine_name",
             "package": "packages.tsv:package"},
    ),
    FileSpec(
        name="xindex-xrefs.tsv", model="code-model", producer="m-dump",
        columns=("routine_name", "ref", "location_list"),
        pk=("routine_name", "ref"),
        renames={"routine": "routine_name"},
        fks={"routine_name": "routines.tsv:routine_name"},
    ),
)

FILES: dict[str, FileSpec] = {s.name: s for s in _SPECS}


def spec_for(name: str) -> FileSpec:
    """Look up the FileSpec for a basename; KeyError if not in v1."""
    return FILES[name]
