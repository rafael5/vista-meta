# vista-meta — schema_version 1 Normalization Spec

Defines the normalization applied **before freezing** `schema_version 1`, making the
export internally consistent for consumers. We are pre-first-release (no consumer pinned),
so these changes fold into v1 rather than deferring to a v2 break.

Scope: vista-meta internal consistency only (cross-producer entity linking is out of scope,
except the R1 key-vocabulary declaration added 2026-07-03). Planning/specification only; no code.

> **Amended 2026-07-03** per the measured adversarial review
> (vista-cloud-dev `docs/proposals/considering/vista-meta-hardening-adversarial-review.md`):
> file count corrected to 24; B1 gains a triage-conflict red-gate + subfile-inheritance
> coverage rule; R1 gains cross-producer key targets; R2 reworded to static-call authority;
> new **R3** (engine/state pinning) and **R4** (%-routine census completeness); §5/§7/§10
> updated accordingly.

## Decisions locked
1. Canonical routine identifier → **`routine_name`** everywhere.
2. Edge columns → standardize suffix to **`_routine`** (keep caller/callee split).
3. Integer-coded enums → **both** (raw code column + `_label` column).
4. **Full sweep** — one unified canonical-key vocabulary across all files.
5. Booleans → **`Y/N`** (most prevalent), blank = null.

---

## 1. Unified canonical-key vocabulary

Every file uses these exact tokens for the canonical entities; role-qualified variants keep
their prefix but share the base token:

| Entity | Canonical column | Legitimate role variants (kept) |
|---|---|---|
| Routine | **`routine_name`** | `caller_routine`, `callee_routine` |
| Package | **`package`** | `caller_package`, `callee_package`, `source_package`, `dest_package`, `protocol_package` |
| FileMan file | **`file_number`** | `parent_file`, `pointer_target` (FK→file_number) |
| Field | **`field_number`** (+ `file_number`) | — |
| Tag | **`tag`** | `callee_tag` |
| Internal entry | **`ien`** | — |

Package, file_number, field_number, ien, tag are **already consistent** — no change.
The routine identifier is the one requiring the sweep.

---

## 2. Rename map (routine identifier)

| File | Current | → |
|---|---|---|
| rpcs.tsv | `routine` | `routine_name` |
| options.tsv | `routine` | `routine_name` (note: `routine_raw` kept — it is the distinct raw/unparsed action string, not the resolved routine) |
| vista-file-9-8.tsv | `name` | `routine_name` (File 9.8 = the ROUTINE file; `name` *is* the routine) |
| xindex-routines.tsv | `routine` | `routine_name` |
| xindex-tags.tsv | `routine` | `routine_name` |
| xindex-xrefs.tsv | `routine` | `routine_name` |
| xindex-errors.tsv | `routine` | `routine_name` |
| xindex-validation.tsv | `routine` | `routine_name` |
| routine-calls.tsv | `caller_name` | `caller_routine` (`callee_routine` already correct) |

Already correct (no change): routines, routines-comprehensive, routine-globals (`routine_name`).

**Also unify the "bytes" concept** (same idea, swapped word order): `size_bytes` →
**`byte_size`** in vista-file-9-8.tsv, matching routines / routines-comprehensive /
package-data. Keep `total_bytes` (packages.tsv) as-is — it is a genuine aggregate (sum),
not the same per-item concept.

---

## 3. Integer-coded enums → code + label

Add a sibling `_label` column beside each integer code (raw code retained):

| File | Code column | New label column | Label values |
|---|---|---|---|
| rpcs.tsv | `return_type` (1–5) | `return_type_label` | SINGLE / ARRAY / WORD-PROC / GLOBAL-ARRAY / GLOBAL-INSTANCE |
| rpcs.tsv | `inactive` (0–3, blank=0) | `inactive_label` | ACTIVE / INACTIVE / LOCAL-INACTIVE / REMOTE-INACTIVE |

(Character-coded enums — option `type`, protocol `type`, `availability`, `piks`, `kind`,
`action_kind`, `data_type` — stay as their documented codes; the schema doc + addendum are
their label dictionary. Only the *integer*-coded fields get sibling labels, per decision 3.)

---

## 4. Boolean normalization

All boolean flags → **`Y` / `N`**, with **blank = null** (genuinely unknown/not-applicable):

`is_percent_routine`, `in_file_9_8`, `lines_match`, `tags_match`, `is_dinum`,
`sensitivity_flag`. Most are already Y/N; this makes the representation uniform and declares
blank-as-null explicitly so consumers don't read blank as `N`.

Per-column null semantics documented: e.g. `sensitivity_flag` blank = "not flagged",
`is_dinum` blank = "unknown" — both remain blank (null), only populated values use Y/N.

---

## 5. Mechanical cleanups

- **Line endings** → normalize all files to **LF** (fixes the mixed CRLF/LF finding).
  *Measured 2026-07-03: 12 of 24 TSVs are CRLF and the xindex family itself splits
  (xindex-validation CRLF, the other four LF) — at least two emission toolchains. The fix
  lands **in every emitting producer**, not as a one-time re-save.*
- **Drop** `vista-fileman-piks-comprehensive.csv` (untraceable producer, redundant join,
  lone CSV). Export becomes **24 TSV files** (count corrected 2026-07-03: the original
  "23" predated `package-namespace.tsv`, added 2026-05-30), format-uniform (all
  tab-separated, all LF). The authoritative file set is the R1 manifest's; the validate
  step asserts tree ≡ manifest, so a count drift like this one fails loudly.
- **files.tsv classification columns**: `files.tsv` carries `piks`/`piks_method`/… columns
  that are **empty** while `piks.tsv` holds the real values (measured 2026-07-03). Drop
  them from files.tsv (preferred — one authoritative surface, per B1's principle) or
  populate them from the B1 merge; never ship half-present duplicates.
- **Deterministic row order** → each file sorted by its primary key before emission. Makes
  version-to-version diffs meaningful and builds byte-reproducible, which directly
  strengthens the content-hash and the review posture. One sort at emit time; high leverage.
- **Declare conventions in the schema doc** (documentation only, no data change): files are
  **UTF-8**, **tab-separated**, **LF**-terminated; **blank = null** (never the literal
  `null`/`NULL`); every file always carries all its columns in fixed order.

---

## 6. Adversarial-review mandates (required before freeze)

These five (B1, R1–R4) land in v1 alongside the normalization above; the frozen contract
includes them. R3/R4 were added 2026-07-03 from the measured review.

**B1 — Materialize PIKS classification (remove the doc-only merge rule).** The
triage-overrides-automated rule must not live only in prose. Merge `piks-triage.tsv` into
`piks.tsv` at emit time (triage wins) and add a **`piks_source`** column (`auto` / `triage`
/ `inherited`). `piks-triage.tsv` is retained as provenance. Consumers then read one
authoritative `piks` value and never reimplement the merge. *(This supersedes the earlier
"consumer merge rule" treatment — precedence is now materialized, not delegated.)*
Two additions (2026-07-03, both defects measured live):
- **Triage-conflict red-gate**: conflicting triage rows for one file (measured: file
  107.3 appears twice with different method/confidence/evidence) must FAIL the merge,
  not silently pick a winner. Resolve in `piks-triage.tsv`, re-run.
- **Coverage rule — every file classified**: 141 of 8,261 files currently have no piks
  row, and all 141 are **subfiles**. A subfile with no explicit classification inherits
  its parent's `piks` with `piks_source=inherited`. Post-merge invariant:
  `piks.tsv` rows ≡ `files.tsv` rows, exactly.

**R1 — Ship a typed column manifest (make it a validatable schema, not a naming convention).**
Emit a per-file column manifest as data: for every file, each column's `name`, `type`
(str/int/float/enum/bool), `nullable`, and `key_role` (pk / fk→target / none). This is the
machine-checkable contract a consumer validates an artifact against. Minimal — a typed column
list, **not** a full JSON-schema. Part of `schema_version 1`; the validate step asserts the
artifact matches it.
*Addition (2026-07-03) — cross-producer key targets:* the manifest's `key_role` fk targets
may name **external vocabularies**, not just sibling files: `routine_name`, `file_number`,
option `name`, rpc `name` are the join keys vdocs entities resolve against (measured join
rates 2026-07-03: fileman_file 85.3%, rpc 73.0%, routine 57.7% — rising to ~high-90s with
R4 — option 1.6%, a vdocs-side entity-quality problem). Declaring the shared vocabulary in
both producers' manifests is the thin, non-deferred slice of the cross-producer
entity-identity contract; full identity semantics remain deferred.

**R2 — Declare the two measured data-fidelity facts in the schema (so consumers don't read
them as bugs).**
- **FK open-world:** `callee_routine` may not resolve — ~2.3% of call targets (measured: 472
  of 20,974 distinct callees) are external/unmapped routines. Declare these FKs as open-world;
  a failed join is expected, not an error.
- **Call-graph divergence:** vista-meta's callee set diverges from the XINDEX reference for
  ~7% of routines (measured: 2,032 of 29,098). Declare the divergence rate and that **XINDEX
  is the reference authority for *statically expressed* calls** (reworded 2026-07-03): XINDEX
  is a static source cross-referencer; calls made through indirection (`DO @X`), XECUTE
  strings, and option/protocol/RPC dispatch are invisible to it and to this export —
  dynamic dispatch is **declared out of scope**, not covered-by-authority. (Line/tag counts
  agree 100% — divergence is callees only. Part of the open-world FK rate also stems from
  the %-routine census gap fixed by R4.)

**R3 — Pin the upstream engine identity and state (added 2026-07-03).** The export is
derived from a live engine, and engine state drifts: measured against the org gold-master
vehu, every `record_count` differs and CPT (#81) is off by >10× (export 2,361 vs live
26,877) — the export's sandbox engine is a *different instance* than the org's pinned vehu,
and nothing in the contract reveals it. The `manifest.json` MUST carry: `engine`
(ydb/iris), the engine **image digest / instance identifier**, the **extraction
timestamp**, and a **DB-state fingerprint** (hash of the sorted per-file record counts —
cheap, and any data change moves it). `record_count` columns are declared **as-of
extraction**. Without R3, `source_commit` pins code that describes unidentifiable data;
R3 is also the precondition for any reproducible re-emission (the v-db graduation gate).

**R4 — Complete the routine census: %-routines (added 2026-07-03).** The census holds
39,330 routines with **zero** %-routines (`is_percent_routine`="N" on every row — a
vestigial column): the source-tree walk misses the Kernel %-namespace entirely, which is
what documentation cites most (%DT, %DTC…). Include %-routines in the census (and make
`is_percent_routine` real), or — if excluded deliberately — declare the exclusion in the
schema doc the way R2 declares open-world FKs. Inclusion is preferred: it is the largest
single downstream-integration win available (routine join rate 57.7% → ~high-90s).

---

## 7. Frozen schema_version 1 — resulting state

`schema_version 1` = **24 TSV files** (+ a typed column manifest), all UTF-8 / tab-separated / LF, with:
- one canonical routine token (`routine_name`) and unified role suffixes (`_routine`),
- unified `byte_size` naming (per-item), `total_bytes` kept for aggregates,
- integer enums carrying sibling `_label` columns,
- uniform `Y/N` booleans with explicit null semantics (blank = null),
- the canonical-key vocabulary of §1 used identically throughout,
- deterministic row order (sorted by primary key) for reproducible, diffable builds,
- **materialized PIKS** with `piks_source` incl. `inherited`, conflict-gated, coverage ≡
  files.tsv (B1),
- a **typed column manifest** as the machine-checkable contract, naming cross-producer
  key targets (R1),
- declared **open-world FKs** and **static-call-scoped XINDEX authority** (R2),
- a **pinned upstream engine** (engine, image digest/instance, extraction timestamp,
  DB-state fingerprint; record counts as-of extraction) (R3),
- a **complete routine census incl. %-routines** (R4),
- files.tsv free of empty duplicate classification columns (§5).

**Declared roadmap (non-normative):** `schema_version 2` is expected to add the
**provenance axis** (national / local / runtime, with `undetermined` a legitimate value;
measured derivability floors: 76.4% of options build-covered, 87.9% of drugs NDF-linked).
Placement (columns vs sibling table) is an open v2 design decision; consumers should not
assume the v1 column set is final beyond v1's own guarantee.

This is the definition frozen into the publication contract's `schema_version 1`. Any later
change to file set, column names, or column order increments to `schema_version 2`.

---

## 9. Consumer impact

The Compass PoC currently reads pre-normalization column names (`routine`, `caller_name`,
`name`). Because we are pre-release, these renames land in v1 and the Compass extraction
(Phase 1) reads the normalized names from the start — no lockstep migration, no dual support.
This is exactly why normalizing now, before any consumer pins v1, is the low-cost path.

---

## 10. Producer work implied (implementation, later)

Sequencing belongs to the implementation plan, not this spec. The work items:
- Update the emitting producers (M routines / Python builders) to write the normalized
  column names, `_label` columns, Y/N booleans, and LF endings (**every** producer — the
  CRLF split proves at least two toolchains emit).
- Remove the CSV producer path (or the file) so it is no longer emitted; drop (or
  populate) files.tsv's empty classification columns.
- Materialize merged PIKS with `piks_source` incl. subfile inheritance; red-gate triage
  conflicts (B1).
- Generate the typed column manifest with cross-producer key targets (R1).
- Add the open-world-FK and static-call-authority declarations to the schema doc (R2).
- Capture and emit the engine identity/state fields into `manifest.json`; **archive the
  raw extraction intermediates** alongside the release so re-emission (and the v-db
  graduation's content-hash gate) never depends on re-extracting a live engine (R3).
- Extend the routine census walker to the %-namespace (R4).
- Extend the vista-meta validate step (doctor-equivalent) to assert: normalized headers
  **and** typed manifest ≡ tree (incl. the 24-file set), PK uniqueness (would have caught
  the live 107.3 duplicate), piks coverage ≡ files.tsv, per-row column-count consistency,
  LF/sort order — the full `schema_version 1` contract.
