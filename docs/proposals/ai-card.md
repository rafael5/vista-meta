# vista-meta — AI card (the measured model of VistA)

> **STATUS: hand-drafted proposal, 2026-07-05** (lives in `docs/proposals/` for now).
> This card is the *spec* for a generated artifact: once adopted, the export pipeline
> should emit it as `vista/export/AI-CARD.md` beside the TSVs (like vdocs regenerates
> `CORPUS.md`) — note `vista/export/` is container-owned (uid 1001), so only the
> pipeline can write there, which is exactly the right ownership for a drift-proof
> card. Until then, trust the TSV headers over this card if they disagree.

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
| manifest | `dist/vista-meta-data-v1.manifest.json` (per-file sha256) |
| schema contract | `docs/reference/schema-v1-normalization-spec.md` |

*(Generated versions of this card must copy hashes from the manifest verbatim.)*

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
   `pkg <name>` package overview · `file <N> [--fields N]` FileMan file + PIKS +
   pointers · `where TAG^ROUTINE` locate source · `callers [TAG^]ROUTINE` reverse call
   graph · `search <regex> [--package P] [--tags-only]` annotated corpus grep ·
   `context <pkg> [--with-source]` AI context pack · `doctor` health check.
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

## Data dictionary

### data-model/ (PIKS classification — 100% file coverage: auto + triage + subfile inheritance)

| TSV | rows | key | columns |
|---|---|---|---|
| `files.tsv` | 8,261 | `file_number` | file_number · file_name · global_root · parent_file · field_count · pointer_in · pointer_out · record_count · is_dinum · status |
| `piks.tsv` | 8,261 | `file_number` | file_number · piks (`P`/`I`/`K`/`S`) · piks_method · piks_confidence · piks_evidence · piks_source |
| `piks-triage.tsv` | 220 | `file_number` | the hand-triaged subset: file_number · piks · piks_method · piks_confidence · piks_evidence |
| `field-piks.tsv` | 69,809 | `file_number`+`field_number` | file_number · field_number · field_name · data_type · file_piks · pointer_target · ref_piks · cross_piks · sensitivity_flag |

**PIKS in one line each** (full guide: `docs/guides/piks-analysis-guide.md`):
**P** Patient — clinical data about identified individuals (PHI). **I** Institution —
facilities, staff (File 200), schedules, assets. **K** Knowledge — terminologies, code
tables, templates, rules. **S** System — Kernel/FileMan plumbing, menus, queues, config.

### code-model/ (per-routine intelligence, ~1.0M rows)

| TSV | rows | key | columns |
|---|---|---|---|
| `routines.tsv` | 39,373 | `routine_name` | routine_name · package · source_path · line_count · byte_size · first_line_comment · version_line · tag_count · comment_line_count · is_percent_routine |
| `routines-comprehensive.tsv` | 39,373 | `routine_name` | adds: in_file_9_8 · file_9_8_type · rpc_count · option_count · protocol_invoked_count · out_degree · in_degree · out_calls_total · in_calls_total · distinct_globals_touched · global_ref_total |
| `routine-calls.tsv` | 241,781 | caller→callee edge | caller_routine · caller_package · callee_tag · callee_routine · kind · ref_count |
| `routine-globals.tsv` | 77,939 | routine→global edge | routine_name · package · global_name (bare, no `^`) · ref_count |
| `rpcs.tsv` | 4,501 | `name` (file #8994) | ien · name · tag · routine_name · return_type(+label) · availability · inactive(+label) · version · package · package_dir |
| `options.tsv` | 13,163 | `name` (file #19) | ien · name · menu_text · type · package · routine_raw · tag · routine_name · package_dir |
| `protocols.tsv` | 6,556 | `name` (file #101) | ien · name · item_text · type · package · entry_action · exit_action · package_dir |
| `protocol-calls.tsv` | 5,081 | protocol→callee edge | protocol_name · protocol_package · action_kind · callee_tag · callee_routine · call_kind · ref_count |
| `packages.tsv` | 174 | `package` | package · routine_count · percent_routine_count · total_lines · total_bytes |
| `package-manifest.tsv` | 175 | `package` | + files_shipped · p/i/k/s_files · rpc_routines · option_routines · distinct_globals_touched · outbound_edges · outbound_cross_pkg |
| `package-namespace.tsv` | 174 | `package` | package · package_name · namespace · prefixes · **app_code** · **vdl_id** ← the vdocs bridge |
| `package-edge-matrix.tsv` | 1,875 | pkg→pkg edge | source_package · dest_package · call_edges · distinct_caller/callee_routines |
| `package-piks-summary.tsv` | 120 | `package` | p/i/k/s_files · unclassified · total_distinct_files |
| `package-data.tsv` | 3,140 | package+entity | package · kind · file_number · chunk · entity_name · source_path · byte_size |
| `vista-file-9-8.tsv` | 30,665 | `routine_name` | ROUTINE file (#9.8) registry: ien · routine_name · type · byte_size · rsum_value · checksum_value |
| `xindex-errors.tsv` | 6,907 | routine+entry | routine_name · entry_index · line_text · tag_offset · error_text |
| `xindex-routines.tsv` | 29,097 | `routine_name` | line_count · tag_count · xref_count · error_count · rsum_value |
| `xindex-tags.tsv` | 292,138 | routine+tag | routine_name · tag · data |
| `xindex-xrefs.tsv` | 214,101 | routine+ref | routine_name · ref · location_list |
| `xindex-validation.tsv` | 29,097 | `routine_name` | ours-vs-XINDEX agreement: lines/tags/callees counts + callees_agreement_ratio |

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

If no row answers the question, the correct answer is **"not measured in vista-meta
data-v1"** — say so and stop; do not substitute general knowledge.
