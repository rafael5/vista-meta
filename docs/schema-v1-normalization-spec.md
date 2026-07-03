# vista-meta — schema_version 1 Normalization Spec

Defines the normalization applied **before freezing** `schema_version 1`, making the
export internally consistent for consumers. We are pre-first-release (no consumer pinned),
so these changes fold into v1 rather than deferring to a v2 break.

Scope: vista-meta internal consistency only (cross-producer entity linking is out of scope).
Planning/specification only; no code.

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
- **Drop** `vista-fileman-piks-comprehensive.csv` (untraceable producer, redundant join,
  lone CSV). Export becomes **23 TSV files**, format-uniform (all tab-separated, all LF).
- **Deterministic row order** → each file sorted by its primary key before emission. Makes
  version-to-version diffs meaningful and builds byte-reproducible, which directly
  strengthens the content-hash and the review posture. One sort at emit time; high leverage.
- **Declare conventions in the schema doc** (documentation only, no data change): files are
  **UTF-8**, **tab-separated**, **LF**-terminated; **blank = null** (never the literal
  `null`/`NULL`); every file always carries all its columns in fixed order.

---

## 6. Adversarial-review mandates (required before freeze)

These three land in v1 alongside the normalization above; the frozen contract includes them.

**B1 — Materialize PIKS classification (remove the doc-only merge rule).** The
triage-overrides-automated rule must not live only in prose. Merge `piks-triage.tsv` into
`piks.tsv` at emit time (triage wins) and add a **`piks_source`** column (`auto` / `triage`).
`piks-triage.tsv` is retained as provenance. Consumers then read one authoritative `piks`
value and never reimplement the merge. *(This supersedes the earlier "consumer merge rule"
treatment — precedence is now materialized, not delegated.)*

**R1 — Ship a typed column manifest (make it a validatable schema, not a naming convention).**
Emit a per-file column manifest as data: for every file, each column's `name`, `type`
(str/int/float/enum/bool), `nullable`, and `key_role` (pk / fk→target / none). This is the
machine-checkable contract a consumer validates an artifact against. Minimal — a typed column
list, **not** a full JSON-schema. Part of `schema_version 1`; the validate step asserts the
artifact matches it.

**R2 — Declare the two measured data-fidelity facts in the schema (so consumers don't read
them as bugs).**
- **FK open-world:** `callee_routine` may not resolve — ~2.3% of call targets (measured: 472
  of 20,974 distinct callees) are external/unmapped routines. Declare these FKs as open-world;
  a failed join is expected, not an error.
- **Call-graph divergence:** vista-meta's callee set diverges from the XINDEX reference for
  ~7% of routines (measured: 2,032 of 29,098). Declare the divergence rate and that **XINDEX
  is the reference authority** for callees. (Line/tag counts agree 100% — divergence is
  callees only.)

---

## 7. Frozen schema_version 1 — resulting state

`schema_version 1` = **23 TSV files** (+ a typed column manifest), all UTF-8 / tab-separated / LF, with:
- one canonical routine token (`routine_name`) and unified role suffixes (`_routine`),
- unified `byte_size` naming (per-item), `total_bytes` kept for aggregates,
- integer enums carrying sibling `_label` columns,
- uniform `Y/N` booleans with explicit null semantics (blank = null),
- the canonical-key vocabulary of §1 used identically throughout,
- deterministic row order (sorted by primary key) for reproducible, diffable builds,
- **materialized PIKS** with `piks_source` (B1),
- a **typed column manifest** as the machine-checkable contract (R1),
- declared **open-world FKs** and **call-graph divergence vs XINDEX** (R2).

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
  column names, `_label` columns, Y/N booleans, and LF endings.
- Remove the CSV producer path (or the file) so it is no longer emitted.
- Materialize merged PIKS with `piks_source` (B1).
- Generate the typed column manifest (R1).
- Add the open-world-FK and call-graph-divergence declarations to the schema doc (R2).
- Extend the vista-meta validate step (doctor-equivalent) to assert the normalized headers
  **and** the typed column manifest as the `schema_version 1` contract.
