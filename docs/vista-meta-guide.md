# vista-meta — Project Guide

**What this project is.** A comprehensive, deterministic, machine-
readable model of VistA — both the data it stores and the code that
manipulates that data — produced by extracting, reducing, analyzing,
and interlinking every available metadata surface of a running
YottaDB-hosted VEHU instance. The result is a flat set of TSVs and
JSON artifacts that a developer, auditor, or AI agent can query to
answer questions that used to require weeks of archaeology: *"what
data does this routine touch? who calls into this file? what kind of
data (clinical, administrative, terminology, system) lives in this
global?"*

On top of that model the project ships two operational products:

1. **kids-vc** — a decompose/assemble pipeline that turns monolithic
   `.KID` patch bundles into git-diffable on-disk trees, removing the
   single longest-standing roadblock to VistA's codebase evolution.
2. **VSCode extension + CLI** — an offline, instant developer
   surface that lets you browse a 40,000-routine corpus with full
   situational awareness of every call, pointer, cross-reference,
   and global each routine touches.

This guide is the authoritative map of the whole thing.

---

## Table of contents

- [1. The thesis — why code and data must be modeled together](#1-the-thesis--why-code-and-data-must-be-modeled-together)
- [2. Scope and non-goals](#2-scope-and-non-goals)
- [3. Architecture at a glance](#3-architecture-at-a-glance)
- [4. Part A — The data model](#4-part-a--the-data-model)
  - [4.1 Why FileMan is the unit of analysis](#41-why-fileman-is-the-unit-of-analysis)
  - [4.2 PIKS — the first-pass abstraction](#42-piks--the-first-pass-abstraction)
  - [4.3 The 52 + 6 heuristics across 9 tiers](#43-the-52--6-heuristics-across-9-tiers)
  - [4.4 Four orthogonal properties](#44-four-orthogonal-properties)
  - [4.5 Coverage, triage, and confidence](#45-coverage-triage-and-confidence)
  - [4.6 Novel findings](#46-novel-findings)
  - [4.7 The data-model TSVs](#47-the-data-model-tsvs)
- [5. Part B — The code model](#5-part-b--the-code-model)
  - [5.1 The six extraction layers](#51-the-six-extraction-layers)
  - [5.2 Unified views](#52-unified-views)
  - [5.3 How the pieces interlink](#53-how-the-pieces-interlink)
  - [5.4 Extraction methodology](#54-extraction-methodology)
- [6. How the two models interlink](#6-how-the-two-models-interlink)
- [7. Operational products built on the models](#7-operational-products-built-on-the-models)
  - [7.1 kids-vc — unblocking VistA's patch-management era](#71-kids-vc--unblocking-vistas-patch-management-era)
  - [7.2 The VSCode extension — situational awareness for 40,000 routines](#72-the-vscode-extension--situational-awareness-for-40000-routines)
  - [7.3 The vista-meta CLI — everything else](#73-the-vista-meta-cli--everything-else)
- [8. Methodology and reproducibility](#8-methodology-and-reproducibility)
- [9. What this unlocks](#9-what-this-unlocks)
- [10. Further reading](#10-further-reading)

---

## 1. The thesis — why code and data must be modeled together

VistA is a forty-year-old ambulatory and inpatient electronic health
record system, written in MUMPS (now M), running on a MUMPS engine
(InterSystems IRIS / Caché in production; YottaDB / GT.M in
open-source installs). Data lives in **globals** — hierarchical
key-value trees in the MUMPS database. Code lives in **routines** —
`.m` files with callable tags at column zero. FileMan — VistA's 1982
relational layer — sits on top of globals and imposes a schema
(files, fields, pointers, cross-references).

The central architectural fact is this: **the schema, the data, and
the code that manipulates them are not separable concerns.**

- A **cross-reference** in FileMan is stored data (a secondary index
  in a global) but is maintained by MUMPS code embedded *inside* the
  data dictionary. Deleting a field may require running the code
  that removed its cross-reference first.
- A **pointer field** is both a data-model fact (File X points to
  File Y) and a code-graph fact (routines that write to X are
  transitively coupled to Y's schema).
- A **routine** that writes to `^DPT(patient_id, 0)` is touching
  File 2 (PATIENT) in the schema and the PHI-bearing global in the
  physical store — same thing expressed three ways.
- **KIDS patches** — the VA's native distribution format — carry
  routines, FileMan DD fragments, options, protocols, and
  pre/post-install MUMPS *in a single monolithic text blob*. The
  code and the schema it modifies ship together, intentionally,
  because they cannot be verified in isolation.

You cannot understand the data without the code because the data's
semantics are determined by the routines that read and write it. You
cannot understand the code without the data because the code's
purpose is opaque without the file-level context it operates on.

Previous attempts to model VistA have flattened either one side
(documentation projects like the VistA Document Library catalog
individual files) or the other (static callgraph tools catalog
routines). vista-meta is the first attempt to model **both sides in
the same artifact set**, with explicit joins between them. A
developer or AI agent consuming the model can ask:

> "I'm editing `PSOVCC1.m` — what FileMan files does it touch? What
> PIKS category is each? Does any of my changes cross a PHI
> boundary?"

and get an answer in one query. That is the value proposition.

---

## 2. Scope and non-goals

**In scope:**

- Static analysis of the VEHU (VA Education and Hospital Utility)
  VistA distribution — 39,330 routines, 8,261 FileMan files,
  486 globals, 4,501 RPCs, 13,163 options, 6,556 protocols.
- PIKS classification of every FileMan file and every non-FM global.
- Code-model extraction: calls, pointers, cross-references, globals,
  XINDEX findings, package topology.
- Operational tooling: kids-vc, VSCode extension, CLI, formatter,
  pre-commit hook.
- Documentation: spec, ADRs, research log, per-area guides.

**Not in scope:**

- A production VistA. This is a laboratory for VEHU.
- Runtime integration with the VA's real systems.
- Dynamic analysis (tracing, profiling, runtime instrumentation).
- Competing with FileMan DDR, FMQL, or clinical-content
  tooling — we're the metadata layer underneath those.
- MUMPS semantic parsing (we use regex + XINDEX cross-validation
  for the call graph; full parse is future work).

**Engineering non-goals:**

- No language server, no LSP, no gRPC wrapper over FileMan, no
  always-on daemon. The artifact is **flat TSVs + a CLI + an offline
  VSCode extension.** Stdlib Python, no runtime dependencies.

---

## 3. Architecture at a glance

```
host (git repo)                    container (VEHU on YottaDB)
───────────────                    ────────────────────────────
spec, ADRs, research ──────────▶   routines (/opt/VistA-M/r/)
CLI + extensions                   globals (named volume)
                                   FileMan (DDR, DINUM, x-refs)
                                   XINDEX (VMXIDX bridge)
                                            │
     ┌──────────────────────────────────────┘
     │  bake.sh extraction pipeline
     ▼
vista/export/
├── data-model/        (5 TSVs, ~170k rows)      ◀── Part A
├── code-model/        (19 TSVs, ~1.0M rows)     ◀── Part B
├── RESEARCH.md        (findings RF-001 … RF-033)
└── .vista-meta-initialized  (bake sentinel)

     │
     ▼
Operational tooling built on the model:
    ├── kids-vc          ◀── unblocks VistA patch evolution
    ├── VSCode extension ◀── per-routine situational awareness
    ├── vista-meta CLI   ◀── pkg / context / where / callers / search / file
    └── pre-commit hook  ◀── mfmt + lint + optional XINDEX gate
```

Everything downstream of `vista/export/` is deterministic text that
can be committed to git, diffed across bakes, and fed to AI agents.

---

## 4. Part A — The data model

### 4.1 Why FileMan is the unit of analysis

FileMan (1982, VA's relational layer on top of MUMPS globals)
imposes a table-row-column abstraction over what is otherwise a
loosely typed hierarchical key-value store. Every FileMan **file**
is a logical table with a numeric ID (File 2 = PATIENT, File 200 =
NEW PERSON, File 80 = ICD-9, etc.), a root global, a schema in
`^DD`, and optional data in `^DIC` and the root global itself.

8,261 FileMan files span every clinical, administrative, and
configuration concern in the system. They are the natural unit
for a first-pass classification: coarser than individual fields,
finer than packages.

### 4.2 PIKS — the first-pass abstraction

**PIKS** stands for **Patient, Institution, Knowledge, System** —
the four categories every FileMan file sorts into based on who
owns the data, who may see it, how it moves between sites, and how
often it changes.

| Letter | Category | Examples | Determines |
|---|---|---|---|
| **P** | **Patient** | PATIENT (2), V MEDICATIONS (55), PROBLEM (9000011) | PHI policy, longitudinal retention, exchange (FHIR, CDA) |
| **I** | **Institution** | NEW PERSON (200), HOSPITAL LOCATION (44), INSTITUTION (4) | Staff PII, facility scope, admin reporting |
| **K** | **Knowledge** | ICD-9 (80), RXNORM (176.03), LEXICON (757.01), ORDER DIALOG (101.41) | Terminology, templates, workflow — declarative, site-portable |
| **S** | **System** | KERNEL PARAMETERS (8989.3), OPTION (19), TASKMAN (14.7) | IT/DevOps, site-local configuration, operational state |

The PIKS classification is the first time VistA's data model has
been systematically partitioned on these lines. Before this project,
the partitioning existed only implicitly in package naming and
developer intuition. Now it is an artifact.

### 4.3 The 52 + 6 heuristics across 9 tiers

Classification is done by **VMPIKS**, a MUMPS routine that applies
52 DD-based heuristics (**H-01 … H-52**) to every FileMan-described
file and 6 non-FM heuristics (**G-01 … G-06**) to globals that have
no entry in `^DD`. Heuristics are organized in tiers of increasing
specificity and decreasing structural certainty:

| Tier | Heuristics | What they match |
|---|---|---|
| 1 | H-01–H-04b | Structural identity (global root, anchor files) |
| 2 | H-06–H-09 | Pointer topology to Files 2, 4, 200 |
| 3 | H-10–H-13 | Known global prefixes (`^DPT`, `^SC`, `^ICD`, `^XTV`) |
| 4 | H-14–H-17 | Package namespace (51+ packages mapped to PIKS) |
| 5 | H-18–H-19 | High-in / low-out pointer topology |
| 6 | H-20–H-23 | File-name patterns (TYPE/CODE→K, PARAMETER→S, etc.) |
| 7–8 | (reserved) | — |
| 9 | H-36, H-38–H-40 | Graph propagation post-inheritance |
| pass 2 | H-05 | Subfile inheritance (4,869 files) |

The **G-01 … G-06** non-FM heuristics classify globals that exist
outside FileMan's DD — e.g., Pharmacy (`^PS`) and Lab (`^LR`)
globals that write directly for performance. Before vista-meta, no
VistA analysis treated non-FM data as first-class. 14% of VEHU's
globals fall in this bucket; missing them loses 14% of the picture.

Full heuristic rule set lives in
[docs/vista-meta-spec-v0.4.md](vista-meta-spec-v0.4.md) §11.4–§11.6
and is implemented in
[`vista/dev-r/VMPIKS.m`](../vista/dev-r/VMPIKS.m).

### 4.4 Four orthogonal properties

PIKS answers *what kind of data*. Four additional properties answer
*how this data must be handled*:

| Property | Values | What it drives |
|---|---|---|
| **Volatility** | `static`, `slow`, `dynamic`, `ephemeral` | Backup frequency, archival, cache strategy |
| **Sensitivity** | `protected` (PHI/PII), `operational` (credentials), `public` (terminologies) | Regulatory classification (HIPAA, 38 CFR) |
| **Portability** | `universal`, `national`, `site-specific` | What travels between installations |
| **Volume** | `reference` (<1K), `moderate` (1K–100K), `high-volume` (>100K) | Storage strategy, query patterns |

These are **orthogonal** — a file can be Patient + dynamic + protected
+ high-volume (every clinical observation) or Knowledge + static +
public + high-volume (ICD-9). The Cartesian product is meaningful
and guides the security, retention, and exchange policies VistA
sites need to make site-specific decisions about.

### 4.5 Coverage, triage, and confidence

| Metric | Value |
|---|---|
| Files classified automatically (H-01…H-52) | 7,886 (95.7%) |
| Files classified via manual triage | 217 (2.6%) |
| **Total coverage** | **8,103 / 8,261 (98.3%)** |
| Files unclassified (subfiles pending parent) | 141 (1.7%) |
| Confidence: certain | 61.4% |
| Confidence: high | 15.9% |
| Confidence: moderate | 16.1% |
| Confidence: low | 6.4% |

The triage file ([`piks-triage.tsv`](../vista/export/data-model/piks-triage.tsv),
218 rows) records every manual override, each tagged with a
research-finding reference (`RF-008` etc.) so the reasoning is
inspectable.

### 4.6 Novel findings

Five outcomes that did not exist before this project:

1. **File 200 structural reclassification (RF-008).** VistA's
   most-referenced file (1,244 inbound pointers — 3.3× more than
   PATIENT) was initially classified System by H-09. Re-analyzed as
   Institution: it holds staff/provider PII (1,462 SSNs, 1,151 DOBs),
   not system configuration. Cascade: S shrank from 32% to 10%, S→P
   pointers dropped from 461 to 36, sharpening the security-review
   scope by an order of magnitude.

2. **Cross-PIKS pointer matrix (RF-007, RF-009).** 3,868 pointer
   fields span PIKS boundaries. P→I dominates (1,477: every clinical
   act references a provider or facility); S→P is residual (36: true
   security exposure after File 200 fix); K→P (23) flagged as
   anomalous for architecture review.

3. **Non-FM data quantified (RF-002).** 86% of VEHU's 486 globals
   are FileMan-described; 14% are directly-written non-FM (Pharmacy
   PS, Lab LR). First VistA analysis to treat both as first-class.

4. **98.3% classification coverage.** Heuristics alone achieve
   95.7% with structural evidence; triage closes another 2.6%.
   Remaining 1.7% is subfiles awaiting parent triage.

5. **Site-universal heuristics.** All 58 rules are structural —
   they read `^DD`, global names, package prefixes. No site-specific
   hand-coding. Portable across VEHU, FOIA, production, RPMS.

### 4.7 The data-model TSVs

All under [`vista/export/data-model/`](../vista/export/data-model/):

| File | Rows | Purpose |
|---|---|---|
| `files.tsv` | 8,262 | File inventory: #, name, global_root, field_count, pointer topology, PIKS, confidence, evidence |
| `piks.tsv` | 8,122 | Auto-classified files (VMPIKS output): #, PIKS, method (H-01…H-40), confidence, evidence |
| `piks-triage.tsv` | 218 | Manual overrides: #, PIKS, method (`manual`/`manual-package`), confidence, RF-NNN |
| `field-piks.tsv` | 69,810 | Field-level PIKS: file#, field#, data type, pointer target, cross-PIKS flag, sensitivity |
| `vista-fileman-piks-comprehensive.csv` | 69,840 | Joined 22-column export — every field with every PIKS annotation |

Composition: `piks.tsv` + `piks-triage.tsv` = the classification
source of truth. They merge into `files.tsv` as the `piks`,
`piks_method`, `piks_confidence`, `piks_evidence` columns. The
file-level PIKS propagates to every field via `field-piks.tsv`,
with cross-PIKS flags set for pointer fields whose target sits in a
different PIKS category.

---

## 5. Part B — The code model

### 5.1 The six extraction layers

Nineteen TSVs organized in six layers, totaling ~1.0M rows, all
under [`vista/export/code-model/`](../vista/export/code-model/):

| Layer | Files | Total rows | Source |
|---|---|---|---|
| **Inventory** | `routines.tsv`, `packages.tsv` | 39,505 | Disk scan of `vista/vista-m-host/` |
| **Authoritative metadata** | `vista-file-9-8.tsv`, `rpcs.tsv`, `options.tsv`, `protocols.tsv` | 54,885 | FileMan extraction of Files 9.8, 8994, 19, 101 |
| **Relationships** | `routine-calls.tsv`, `routine-globals.tsv`, `protocol-calls.tsv` | 324,228 | Regex scan of routine source |
| **Code quality** | `xindex-routines.tsv`, `xindex-errors.tsv`, `xindex-xrefs.tsv`, `xindex-tags.tsv`, `xindex-validation.tsv` | 571,273 | XINDEX (VA's official MUMPS analyzer) via VMXIDX bridge |
| **Data integration** | `package-data.tsv`, `package-piks-summary.tsv` | 3,258 | ZWR scans + PIKS joins |
| **Unified** | `routines-comprehensive.tsv`, `package-manifest.tsv`, `package-edge-matrix.tsv` | 41,377 | Multi-way joins over the preceding layers |

Each layer is individually reproducible from `make` targets:
`make sync-routines`, `make inventory`, `make xindex`,
`make routine-calls`, `make routine-globals`, and so on. The full
pipeline rebuild is idempotent.

### 5.2 Unified views

The most frequently queried artifact is
[`routines-comprehensive.tsv`](../vista/export/code-model/routines-comprehensive.tsv):

20 columns per routine, joining every layer above:

```
routine_name | package | source_path | line_count | byte_size |
tag_count | comment_line_count | version_line | is_percent_routine |
in_file_9_8 | file_9_8_type | rpc_count | option_count |
protocol_invoked_count | out_degree | in_degree | out_calls_total |
in_calls_total | distinct_globals_touched | global_ref_total
```

With this one file you can answer:

- "Which routines in Lab Service have more than 50 inbound callers?"
- "Which RPC routines touch more than 10 distinct globals?"
- "Which percent-routines are called by non-Kernel packages?"

[`package-manifest.tsv`](../vista/export/code-model/package-manifest.tsv)
does the same at package granularity (role counts, edge counts,
cross-package coupling). [`package-edge-matrix.tsv`](../vista/export/code-model/package-edge-matrix.tsv)
is the sparse call-edge matrix between packages.

### 5.3 How the pieces interlink

Everything in the code model references everything else through
stable keys:

- **Routines ↔ tags**: `xindex-tags.tsv` maps every tag back to its
  routine, with Supported-Entry-Point classification from VA docs.
- **Routines ↔ callees**: `routine-calls.tsv` (caller, callee,
  kind, ref_count). 241,309 edges. XINDEX call graph
  (`xindex-xrefs.tsv`, 214,011 edges) cross-validates at 98.75%.
- **Routines ↔ globals**: `routine-globals.tsv` (routine, global,
  ref_count). 77,838 edges.
- **Routines ↔ roles**: RPC definitions (`rpcs.tsv`), options
  (`options.tsv`), protocols (`protocols.tsv`) reference their
  implementing routine+tag.
- **Packages ↔ routines**: namespace prefix (`PRCA*` = Accounts
  Receivable) maintained in `packages.tsv` and propagated through
  every other TSV's `package` column.
- **Findings ↔ lines**: `xindex-errors.tsv` carries
  (routine, tag+offset, line, error_text, severity) so errors map
  exactly to source positions.

Every TSV is UTF-8, tab-separated, RFC-4180-ish quoted, with a
header row. Parseable by `pandas`, `duckdb`, `jq` (after
conversion), shell `awk`, or plain Python.

### 5.4 Extraction methodology

| Script | Purpose |
|---|---|
| [`build_routine_inventory.py`](../host/scripts/build_routine_inventory.py) | Disk scan → `routines.tsv` + `packages.tsv` |
| [`build_routine_calls.py`](../host/scripts/build_routine_calls.py) | Regex extract `DO`, `GOTO`, `JOB`, `$$…^ROUTINE` from source |
| [`build_routine_globals.py`](../host/scripts/build_routine_globals.py) | Regex extract `^GLOBAL(subscripts)` references with kind (read/write) |
| [`build_protocol_calls.py`](../host/scripts/build_protocol_calls.py) | Extract protocol ENTRY/EXIT ACTION code and its outbound calls |
| [`build_package_data_inventory.py`](../host/scripts/build_package_data_inventory.py) | Inventory ZWR data exports per package |
| [`build_package_piks_summary.py`](../host/scripts/build_package_piks_summary.py) | Join package → files → PIKS → per-package distribution |
| [`build_package_manifest.py`](../host/scripts/build_package_manifest.py) | Per-package joins: role counts, edge counts, coupling |
| [`build_package_edge_matrix.py`](../host/scripts/build_package_edge_matrix.py) | Sparse source→dest package call matrix |
| [`build_routines_comprehensive.py`](../host/scripts/build_routines_comprehensive.py) | Multi-way join over all 19 layers |
| [`validate_against_xindex.py`](../host/scripts/validate_against_xindex.py) | Cross-check regex extraction against XINDEX — published as `xindex-validation.tsv` |

XINDEX is VA's official static analyzer (part of Kernel); we drive
it through the container via the **VMXIDX bridge**
(`SETUP + PROC + EXTRACT` sequence). Its call graph is the
authoritative reference our regex extraction is validated against.
Where they disagree (1.25% of edges), the regex is accepting calls
XINDEX correctly excludes (e.g., commented-out references).

---

## 6. How the two models interlink

The data model and code model join through four pivot tables:

1. **Globals** in `routine-globals.tsv` (code model) join to the
   owning FileMan file in `files.tsv` (data model) via the global
   root column. A routine touching `^DPT` is a routine touching
   File 2 (PATIENT) is a routine touching PHI.

2. **Packages** in `packages.tsv` (code model) join to the per-
   package PIKS distribution in `package-piks-summary.tsv`. Each
   package gets a count of how many of its owned files sit in each
   PIKS category.

3. **RPCs / options / protocols** in the code model's authoritative
   layer carry their implementing routine + tag, and their called
   routines carry their own globals, which carry their own PIKS.
   The transitive closure tells you: *"this RPC ultimately touches
   these PIKS categories."*

4. **Cross-PIKS pointers** in `field-piks.tsv` (data model) reveal
   which fields cross boundaries; joined with `routine-globals.tsv`
   (code model), you find which routines write those boundary-
   crossing fields. That's the attack-surface analysis the S→P
   reduction finding (RF-009) quantified.

The upshot: a single query joining three or four TSVs can answer
*"which routines write Patient data while being callable from an
Institution-scoped RPC?"* — a security-architecture question that
has, historically, required weeks of manual review.

---

## 7. Operational products built on the models

### 7.1 kids-vc — unblocking VistA's patch-management era

**The problem.** KIDS (Kernel Installation & Distribution System)
is VistA's package manager. It produces `.KID` files — monolithic
text dumps containing routines, FileMan DD fragments, options,
protocols, RPCs, pre/post-install MUMPS, and ZWR data exports.
A `.KID` patch is the unit of distribution between sites.

`.KID` is architecturally incompatible with git: one 50 KB blob
per patch, no decomposition, line-2 patch-list mutations on every
build, IENs that vary per site. You cannot `git diff` two
`.KID` files meaningfully; you cannot merge them; you cannot
cherry-pick a routine out of one and into another. This is the
longest-standing roadblock to VistA's codebase evolution and the
reason patch maintenance at VA sites is, in practice, an expert
craft with zero tooling affordance.

**The solution.** The kids-vc toolchain, implemented in
[`host/scripts/kids_vc.py`](../host/scripts/kids_vc.py), decomposes
any `.KID` file into a directory tree:

```
<PATCH>/KIDComponents/
├── Build.zwr              (^XPD(9.6) entry — version, dependencies, environment)
├── Package.zwr            (^XPD(9.7) — what this patch is part of)
├── EnvironmentCheck.zwr   (pre-install MUMPS)
├── PreInstall.zwr
├── PostInstall.zwr
├── InstallQuestions.zwr
├── Routines/
│   ├── PSOVCC1.m          (one file per routine, line-2 canonicalized)
│   ├── PSOVCC1.header
│   └── ...
├── Files/
│   └── 50+DRUG/
│       ├── DD.zwr         (FileMan data-dictionary entry)
│       ├── Data.zwr       (optional initial data)
│       └── DD-code/       (MUMPS embedded in the DD, extracted to .m files)
│           ├── AIXREF.m
│           └── ...
└── KRN/
    ├── OPTION/<name>.zwr
    ├── PROTOCOL/<name>.zwr
    └── REMOTE-PROCEDURE/<name>.zwr
```

Subcommands:
- `kids_vc.py decompose FILE.KID DIR/` — reverse
- `kids_vc.py assemble DIR/ OUT.KID` — forward
- `kids_vc.py roundtrip FILE.KID` — decompose + re-assemble + byte-semantic diff
- `kids_vc.py canonicalize` — IEN substitution for cross-site
  diff stability

**Canonicalizations applied automatically:**
- Line-2 patch-list strip: `;;VERSION;PACKAGE;**patches**;DATE;…`
  → `;;VERSION;PACKAGE;;` (removes volatile patch list + build date)
- Line-2 Build-N strip (XPDK2VC-compatible inheritance)
- IEN substitution (opt-in)

**Validation.** 100% round-trip pass on a corpus of 2,406 real
WorldVistA patches (3,566,277 ZWR subscripts processed). The
pre-2406-corpus regression suite of 5 fixtures gave 91.15% round-
trip; expanding to corpus-scale testing surfaced four bugs and
pushed the pass rate to 100%. All six structural contracts that
XPDK2VC (VA's 2014 prior art) established are verified in
[`test_xpdk2vc_compat.py`](../host/scripts/test_xpdk2vc_compat.py).
The 7-scenario 3-way ZWR merge driver in
[`zwr_merge.py`](../host/scripts/zwr_merge.py) is verified by
[`test_zwr_merge.py`](../host/scripts/test_zwr_merge.py).

**Beyond XPDK2VC.** kids-vc adds DD-embedded-MUMPS extraction — the
MUMPS code embedded in FileMan data dictionaries (cross-reference
logic, computed fields, triggers) gets extracted to individual `.m`
files in `DD-code/`. Neither SKIDS nor XPDK2VC provided this surface.
DD-embedded code is now git-diffable alongside the routines that
call into it.

Full reference: [docs/kids-vc-guide.md](kids-vc-guide.md).

### 7.2 The VSCode extension — situational awareness for 40,000 routines

**The problem.** Opening `PRCA45PT.m` in any modern editor shows
you 74 lines of MUMPS. It shows you nothing about: who calls this
routine, what routines it calls, what globals it touches, what
FileMan files those globals belong to, what PIKS classification
that data has, or what XINDEX found wrong with the code. In a
40,000-routine corpus where every routine cross-references many
others, this is a productivity cliff. Traditional MUMPS IDEs put
these facts in separate windows that require explicit lookups;
vista-meta puts them in a sidebar that updates with the active
editor.

**What the extension surfaces.** When any `.m` file is the active
editor, a VISTA ROUTINE panel appears in the Explorer sidebar:

- **Header**: routine name, package in brackets, line count, in-
  degree, out-degree, plus `RPC×N` / `OPT×N` badges when the
  routine implements those roles.
- **Tags**: labels parsed from the file on disk. Click to reveal
  the line.
- **Callers**: routines that call *into* this one, aggregated from
  `routine-calls.tsv` and sorted by reference count. Click opens
  the caller.
- **Callees**: routines this one calls, same source, same click
  behavior.
- **Globals**: distinct globals touched, with reference counts
  from `routine-globals.tsv`. No click target (globals aren't
  navigable in MUMPS the way files are).
- **XINDEX**: findings from `xindex-errors.tsv`, auto-expanded so
  Fatal findings can't be missed. Severity maps to icon (F→error,
  W→warning, rest→info). Numeric-line findings click to reveal
  the line.

**No runtime dependency.** The extension reads only the code-model
TSVs under `vista/export/code-model/`. No language server, no
container calls, no MCP, no network. First render happens in
milliseconds; the TSVs stay in memory until
`vista-meta: Reload Code-Model TSVs` invalidates them.

**Why this matters.** Every question a developer has when opening
a routine — *who depends on this? what does this touch? what's
broken here?* — is now one click away. In a codebase where call-
graph navigation has historically been archaeologically expensive,
this compresses a twenty-minute investigation into an eye
movement. Over the course of maintaining any VistA package, the
time saved compounds.

Full reference: [docs/vista-vscode-guide.md](vista-vscode-guide.md)
§2.

### 7.3 The vista-meta CLI — everything else

The CLI ([`host/scripts/vista_meta_cli.py`](../host/scripts/vista_meta_cli.py))
provides ten subcommands for everything the sidebar doesn't cover:

| Subcommand | Purpose |
|---|---|
| `doctor` | Environment health — paths, TSVs, container, hook installation |
| `pkg NAME` | Package overview: routines, PIKS distribution, RPCs, options, top globals, top inbound/outbound edges, entry-point candidates |
| `context NAME` | AI-ready markdown context pack: optionally with full source, budgeted under `--bytes` |
| `where TAG^ROUTINE` | Jump-to-source: emits `path:line` + 6-line snippet |
| `callers TAG^ROUTINE` | Aggregated caller graph, sorted by ref-count |
| `search PATTERN` | Regex scan over the corpus, annotated by package |
| `file N` | FileMan file overview: global root, record count, PIKS, properties, top pointer targets |
| `new-test ROUTINE` | Scaffold an M-Unit test skeleton with one stub per public tag |
| `lint FILES…` | Doc-comment lint: every public tag needs `@summary` or `@test` |
| `xindex FILE` | Drive live XINDEX on a single routine via the container |

Alongside the CLI:
- [`host/scripts/mfmt.py`](../host/scripts/mfmt.py) — deterministic
  idempotent MUMPS formatter (R1–R4 minimal rules, no semantic
  parsing).
- [`hooks/pre-commit`](../hooks/pre-commit) — SAC line-length, tab
  check, bare-HALT check, doc-comment lint, optional live XINDEX.
- GitHub Actions CI enforces the same checks on PRs.

Full reference: [docs/vista-vscode-guide.md](vista-vscode-guide.md)
§§3–5.

---

## 8. Methodology and reproducibility

Everything in vista-meta is governed by three interlocking documents:

1. **[The spec](vista-meta-spec-v0.4.md)** — what to build, what
   contracts hold, what classification rules apply. Referenced
   throughout code (e.g., `# Spec: docs/vista-meta-spec-v0.4.md § 11.5`).
2. **[The ADRs](adr/)** — why specific decisions were made. 45+
   records, each immutable once accepted; supersession happens via
   a new ADR. Covers architecture (`012-zro-layering.md`,
   `010-hybrid-persistence.md`), tooling choices, PIKS
   methodology evolution.
3. **[The research log](../vista/export/RESEARCH.md)** — discovery
   findings (`RF-001` … `RF-033`), each with context, hypothesis,
   evidence, and conclusion. Findings drive spec revisions and new
   ADRs.

Every pipeline step is a `make` target (`make help` lists them).
Every TSV is regeneratable from upstream inputs. Errors and fixes
are logged in [`docs/build-log.md`](build-log.md) with BL-NNN
references. Dependency versions are pinned in
[`docs/dependencies.md`](dependencies.md).

The discipline is strict enough that another team could clone the
repo, run `make build && make run && make bake`, and get the same
TSV outputs.

---

## 9. What this unlocks

Three classes of question the model now answers trivially that
used to require weeks of manual work:

1. **Governance and security.** *"Which RPCs transitively write PHI?
   Which packages hold the most cross-PIKS pointers? Where does
   System data reach into Patient data?"* Four-way TSV join.

2. **Refactoring and evolution.** *"If I remove this tag, which
   routines break? If I delete this FileMan field, which cross-
   references must be unwound? Which XINDEX errors in this package
   block a patch?"* Single TSV lookup + join.

3. **AI-assisted development.** *"Give me an assistant that knows
   every routine, every global, every PIKS category, every caller
   chain, and can answer questions at SQL-join speed."* The
   `vista-meta context` subcommand emits exactly the prompt-pack
   that turns a generalist LLM into a VistA-literate one.

Four classes of product now plausible on this base:

1. A **governance-as-code** pipeline that gates every patch on
   PIKS-boundary and cross-package impact.
2. A **semantic search** surface over the corpus that respects
   PIKS, package, and role scopes.
3. An **agent harness** that takes a clinical/admin request
   (*"add a field to File 2 that stores…"*) and proposes the
   routine changes, FileMan DD additions, cross-reference work,
   and KIDS build — all within the model's known invariants.
4. A **migration tool** from VistA to modern stacks (FHIR, clinical
   data warehouses, OMOP) grounded in the PIKS-classified data map.

---

## 10. Further reading

- [vista-meta-spec-v0.4.md](vista-meta-spec-v0.4.md) — the
  authoritative technical spec. Start at §11 for the analytical
  methodology.
- [vista-developers-guide.md](vista-developers-guide.md) — how a
  Python / JavaScript / Go developer orients in a VistA codebase
  for the first time.
- [vista-vscode-guide.md](vista-vscode-guide.md) — every tool this
  repo ships, end to end.
- [piks-analysis-guide.md](piks-analysis-guide.md) — deep dive on
  PIKS methodology, tier-by-tier heuristic rationale, manual
  triage history.
- [code-model-guide.md](code-model-guide.md) — per-TSV reference
  for the code-model artifacts.
- [kids-vc-guide.md](kids-vc-guide.md) — the full kids-vc
  decompose/assemble/roundtrip toolchain, including the XPDK2VC
  compatibility story.
- [xindex-reference.md](xindex-reference.md) — what XINDEX extracts
  vs what the vista-meta regex-based tools extract.
- [build-log.md](build-log.md) — chronological error + fix log
  (BL-NNN).
- [adr/](adr/) — locked decisions, chronologically indexed.
- [../vista/export/RESEARCH.md](../vista/export/RESEARCH.md) —
  discovery findings (RF-NNN).
