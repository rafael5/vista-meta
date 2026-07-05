# vista-meta — AI card (the measured model of VistA)

> **GENERATED — do not edit.** Emitted by `host/scripts/build_ai_card.py`
> from `schema_v1` + the live TSVs + the pinned release record
> (`docs/releases/data-v1.manifest.json`). Regenerate with `make ai-card`;
> drift-gated by `make card-check` (stale card = RED, card pin must equal
> the release manifest's `content_hash`). Machine-readable twin:
> `vista/export/ai-manifest.json`.

## What this is

`vista-meta` is a deterministic, **measured** model of VistA — extracted from a pinned
VEHU instance (YottaDB), not transcribed from documentation. It answers *what the code
and data actually are*: which routine calls which, which package owns what, how every
FileMan file is classified (PIKS), where every RPC/option/protocol lands.

**Contract:** answer measured questions from these TSVs (or the CLI over them), cite the
row you read, and never fill a gap with general VistA knowledge. This card is the
orientation — read it instead of re-exploring the export tree.

Companion source: the **vdocs gold corpus** (`~/data/vdocs/`) holds what the VA
*documentation says*. vista-meta holds what the system *measurably is*. When they
conflict, report both sides labeled `documented:` vs `measured:` — do not reconcile
silently.

## Provenance (pin this in answers)

| Field | Value |
|---|---|
| release | `data-v1` (`schema_version: 1`) |
| content_hash | `23d037f1e08adc206d251eea9adb4ec62051032c06b593737bebfcaf67e4c754` |
| db_state_fingerprint | `b8518a87f50f0f14186f3f3da97155345979d6d6c5d2878d6a379b74e9fe0d32` |
| extracted | 2026-07-03T21:03:48Z, engine `ydb`, image `vista-meta:latest` |
| manifest | `docs/releases/data-v1.manifest.json` (in-repo record; per-file sha256) |
| schema contract | `docs/reference/schema-v1-normalization-spec.md` |

**Scope caveats (state these when they matter):**
- Measured on the **VEHU demo instance** — `record_count` and data-bearing counts reflect
  VEHU's demo data, not any production site. Structure (DD, routines, options, RPCs) is
  the shipped VistA code base; record volumes are not.
- The routine census contains only **11 `%`-routines** (`is_percent_routine=Y`) — Kernel
  `%`-utilities largely live outside the extracted source tree, so call edges *into* them
  are visible but their own rows/edges mostly are not.
- XINDEX outputs are cross-validated against our parser in `xindex-validation.tsv`; when
  a per-routine claim is load-bearing, check its `callees_agreement_ratio` there.

## Query paths (in order of preference)

1. **CLI** — `~/projects/vista-meta/bin/vista-meta <verb>` (not on `$PATH`):
   `pkg <name>` package overview (namespace, footprint, PIKS mix) ·
   `file <N> [--fields N]` FileMan file + PIKS + pointers + fields ·
   `where TAG^ROUTINE` locate source ·
   `callers [TAG^]ROUTINE` reverse call graph (measured, ranked) ·
   `search <regex> [--package P] [--tags-only]` annotated corpus grep ·
   `context <pkg> [--with-source]` AI context pack ·
   `doctor` environment health check.
2. **TSVs directly** — `vista/export/{data-model,code-model}/*.tsv`, tab-separated,
   header row, deterministic sort. Fine for `awk -F'\t'` single-file lookups.
3. **Joins** — load into in-memory SQLite (no build step; first row becomes column
   names when the table doesn't pre-exist):
   ```bash
   cd ~/projects/vista-meta/vista/export
   sqlite3 :memory: <<'SQL'
   .mode tabs
   .import code-model/rpcs.tsv rpcs
   .import code-model/routines-comprehensive.tsv r
   SELECT rpcs.name, rpcs.tag, rpcs.routine_name, r.package, r.line_count
   FROM rpcs JOIN r ON r.routine_name = rpcs.routine_name
   WHERE rpcs.name LIKE 'ORWPT%' LIMIT 20;
   SQL
   ```
   Or generate the one-file projection: `make meta-db` →
   `dist/vista-meta-data-v1.db` (all tables typed + the entity bridge + join
   views `v_rpc_impl`, `v_routine_global_piks`, `v_rpc_data_piks`,
   `v_package_overview`, …). The TSVs stay canonical; the db is derived.
4. **MCP** — `python3 host/scripts/mcp_server.py` (stdio; wired by the repo's
   `.mcp.json`): tools `query` (read-only SQL over the db above, self-building)
   · `lookup` (keyed, returns the citation line ready-made) · `bridge` (vdocs
   entity → vista-meta row) · `orientation` (pins + surface + contract).

## Data dictionary

### data-model/ (PIKS classification — 100% file coverage: auto + triage + subfile inheritance)

| TSV | rows | key | columns |
|---|---|---|---|
| `field-piks.tsv` | 69,809 | `file_number`+`field_number` | file_number · field_number · field_name · data_type · file_piks · pointer_target · ref_piks · cross_piks · sensitivity_flag |
| `files.tsv` | 8,261 | `file_number` | file_number · file_name · global_root · parent_file · field_count · pointer_in · pointer_out · record_count · is_dinum · status |
| `piks-triage.tsv` | 220 | `file_number` | file_number · piks · piks_method · piks_confidence · piks_evidence |
| `piks.tsv` | 8,261 | `file_number` | file_number · piks · piks_method · piks_confidence · piks_evidence · piks_source |

**PIKS in one line each** (full guide: `docs/guides/piks-analysis-guide.md`):
**P** Patient — clinical data about identified individuals (PHI). **I** Institution —
facilities, staff (File 200), schedules, assets. **K** Knowledge — terminologies, code
tables, templates, rules. **S** System — Kernel/FileMan plumbing, menus, queues, config.

### code-model/ (per-routine intelligence)

| TSV | rows | key | columns |
|---|---|---|---|
| `options.tsv` | 13,163 | `ien` | ien · name · menu_text · type · package · routine_raw · tag · routine_name · package_dir |
| `package-data.tsv` | 3,140 | `package`+`kind`+`file_number`+`chunk`+`entity_name` | package · kind · file_number · chunk · entity_name · source_path · byte_size |
| `package-edge-matrix.tsv` | 1,875 | `source_package`+`dest_package` | source_package · dest_package · call_edges · distinct_caller_routines · distinct_callee_routines |
| `package-manifest.tsv` | 175 | `package` | package · routine_count · total_lines · files_shipped · p_files · i_files · k_files · s_files · rpc_routines · option_routines · distinct_globals_touched · outbound_edges · outbound_cross_pkg |
| `package-namespace.tsv` | 174 | `package` | package · package_name · namespace · prefixes · app_code · vdl_id |
| `package-piks-summary.tsv` | 120 | `package` | package · p_files · i_files · k_files · s_files · unclassified · total_distinct_files |
| `packages.tsv` | 174 | `package` | package · routine_count · percent_routine_count · total_lines · total_bytes |
| `protocol-calls.tsv` | 5,081 | `protocol_name`+`action_kind`+`callee_tag`+`callee_routine`+`call_kind` | protocol_name · protocol_package · action_kind · callee_tag · callee_routine · call_kind · ref_count |
| `protocols.tsv` | 6,556 | `ien` | ien · name · item_text · type · package · entry_action · exit_action · package_dir |
| `routine-calls.tsv` | 241,781 | `caller_routine`+`callee_tag`+`callee_routine`+`kind` | caller_routine · caller_package · callee_tag · callee_routine · kind · ref_count |
| `routine-globals.tsv` | 77,939 | `routine_name`+`global_name` | routine_name · package · global_name · ref_count |
| `routines-comprehensive.tsv` | 39,373 | `routine_name` | routine_name · package · source_path · line_count · byte_size · tag_count · comment_line_count · version_line · is_percent_routine · in_file_9_8 · file_9_8_type · rpc_count · option_count · protocol_invoked_count · out_degree · in_degree · out_calls_total · in_calls_total · distinct_globals_touched · global_ref_total |
| `routines.tsv` | 39,373 | `routine_name` | routine_name · package · source_path · line_count · byte_size · first_line_comment · version_line · tag_count · comment_line_count · is_percent_routine |
| `rpcs.tsv` | 4,501 | `ien` | ien · name · tag · routine_name · return_type · return_type_label · availability · inactive · inactive_label · version · package · package_dir |
| `vista-file-9-8.tsv` | 30,665 | `ien` | ien · routine_name · type · byte_size · rsum_value · checksum_value |
| `xindex-errors.tsv` | 6,907 | `routine_name`+`entry_index` | routine_name · entry_index · line_text · tag_offset · error_text |
| `xindex-routines.tsv` | 29,097 | `routine_name` | routine_name · line_count · tag_count · xref_count · error_count · rsum_value |
| `xindex-tags.tsv` | 292,138 | `routine_name`+`tag` | routine_name · tag · data |
| `xindex-validation.tsv` | 29,097 | `routine_name` | routine_name · package · lines_ours · lines_xindex · lines_match · tags_ours · tags_xindex · tags_match · callees_ours_count · callees_xindex_count · callees_match_count · callees_ours_only_count · callees_xindex_only_count · callees_agreement_ratio |
| `xindex-xrefs.tsv` | 214,101 | `routine_name`+`ref` | routine_name · ref · location_list |

## Join keys

- **`routine_name`** — routines* ↔ routine-calls (`caller_routine`/`callee_routine`) ↔
  routine-globals ↔ rpcs ↔ options ↔ vista-file-9-8 ↔ xindex-*.
- **`package`** — every code-model TSV; `package-namespace.tsv` maps it to
  namespace/prefixes and to **`app_code`/`vdl_id`**, which join to vdocs hits
  (`vdocs search` results carry `app_code`).
- **`file_number`** — files ↔ piks ↔ field-piks ↔ package-data;
  `field-piks.pointer_target` is itself a file_number (the pointer graph).
- **`TAG^ROUTINE`** — rpcs/options/protocol-calls (`tag`+`routine_name`) ↔
  routine-calls (`callee_tag`+`callee_routine`).
- **Global names** — `routine-globals.global_name` is bare (`DPT`); `files.global_root`
  is a global reference (may be empty, may carry `^`/subscripts) — normalize before
  joining.

- **vdocs entities** — the generated bridge `bridge/entity-bridge.tsv` maps every
  vdocs `data-v1` entity (`<type>:<canonical_name>`) to its vista-meta row
  (`vista_tsv` + `vista_key_column`=`vista_key_value`, with `join_method` /
  `join_confidence`; `undetermined` is legal). Dual release pins + measured join
  rates: `bridge/entity-bridge.meta.json`.

The full FK registry (every declared edge, machine-readable) lives in
`ai-manifest.json` under `join_keys`.

## Recipes

```bash
VM=~/projects/vista-meta/bin/vista-meta
X=~/projects/vista-meta/vista/export

$VM pkg PSO                        # package overview (Outpatient Pharmacy)
$VM file 52 --fields 15            # file #52 + PIKS + pointers + first fields
$VM callers SITE^VASITE            # who calls TAG^ROUTINE (measured, ranked)
$VM search 'MERGE \^DPT' --package DG   # annotated regex over package source
$VM context OR --routines ORWPT    # AI context pack incl. budgeted source

# Which routine implements an RPC?
awk -F'\t' '$2=="ORWPT SELECT"{print $3"^"$4}' $X/code-model/rpcs.tsv
# PIKS class + evidence for a file
awk -F'\t' '$1=="200"' $X/data-model/piks.tsv
# Top globals a routine touches
awk -F'\t' '$1=="ORWPT"' $X/code-model/routine-globals.tsv | sort -t$'\t' -k4,4nr | head
# Cross-package coupling into FileMan
awk -F'\t' '$2=="VA FileMan"' $X/code-model/package-edge-matrix.tsv | sort -t$'\t' -k3,3nr | head
```

## Citation contract

Cite every measured claim as:

> **vista-meta data-v1** · `<tsv path>` · `<key>=<value>` — *or* the exact CLI command run.

Example: *"ORWPT SELECT is served by SELECT^ORWPT"* →
**vista-meta data-v1** · `code-model/rpcs.tsv` · `name=ORWPT SELECT`.

If no row answers the question, the correct answer is
**"not measured in vista-meta data-v1"** — say so and stop; do not substitute
general knowledge.
