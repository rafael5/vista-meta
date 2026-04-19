# vista-meta — Research Log

Append-only journal of analytical discoveries about VistA metadata.
This is the project's primary intellectual output — verified knowledge
about how VistA's FileMan data structures actually work.

Spec: docs/vista-meta-spec-v0.4.md § 11

Entry format: RF-NNN with scope, method, finding, evidence, implications.
Entries are append-only and reverse-chronological within each session block.
Status: provisional | verified | superseded by RF-NNN.

---

## 2026-04-19 — First analytical session

### RF-011: Static routine features — structural shape of the corpus

- **Date**: 2026-04-19
- **Scope**: All 39,330 routines inventoried in RF-010. Features extracted
  strictly mechanically from each `.m` file (no heuristics, no role
  inference) — Phase 2a of ADR-045.
- **Method**: `host/scripts/build_routine_inventory.py` extended to
  capture four additional columns per routine (`version_line`,
  `tag_count`, `comment_line_count`, `is_percent_routine`) plus one
  package aggregate (`percent_routine_count`). Run via `make inventory`.
- **Finding** (all derived by strict extraction, not interpretation):
  - **Tags (column-0 labels)**: 396,441 total across 39,330 routines,
    averaging ~10 tags per routine. Tag counts distinguish routines
    with many public entry points from single-entry routines.
  - **Comment lines**: 1,511,879 out of 4,138,428 total lines = **36.5%
    comment density** across the corpus. MUMPS style here is heavily
    commented by modern-code standards.
  - **Version line coverage**: 35,706 routines (**90.8%**) have a
    VistA-convention `;;VERSION;PACKAGE;SEQ;BUILDDATE` line 2.
    3,624 routines (**9.2%**) do not — candidates for future
    investigation (may be generated code, older routines pre-dating the
    convention, or package-specific exceptions).
  - **Percent routines in MANIFEST**: **0**. All `_*.m` files live
    outside `Packages/*/Routines/` so none appear in this inventory.
    Confirms that the +8 compiled `.o` divergence flagged in T-001 is
    almost certainly from percent routines installed via `$ydb_dist`
    or an equivalent path outside `Packages/`.
  - Packages with percent routines: 0 (consistent with the above).
- **Evidence**: `routines.tsv` now 10 columns including the 4 new
  feature columns; `packages.tsv` now 5 columns including
  `percent_routine_count`.
- **Implications**:
  - Feature columns are the honest foundation for human-driven
    exploration (sort by size, by tag count, by comment density).
    No "role" label has been assigned — role classification requires
    call-graph and VistA metadata, deferred to Phase 4+ per ADR-045.
  - The 9.2% of routines lacking a `;;` version line are a
    well-defined cohort worth reviewing before any cleanup work.
  - RF-011 is observational and stable: the same extraction against
    the same sources will produce identical outputs. No heuristic
    drift.
- **Status**: verified

### RF-010: Host-side routine inventory — 39,330 routines across 174 packages

- **Date**: 2026-04-19
- **Scope**: All `.m` routines in `/opt/VistA-M/Packages/*/Routines/` from the
  VEHU image baseline, synced to host at `vista/vista-m-host/` via
  `make sync-routines` (ADR-045, Phase 1a).
- **Method**: `host/scripts/build_routine_inventory.py` reads the
  Dockerfile-generated `MANIFEST.tsv`, stats each source file for
  byte size and line count, and captures the first-line comment.
- **Finding**:
  - **39,330 routines** in source `.m` files under `Packages/*/Routines/`
  - Container-side counts for cross-reference:
    `/opt/VistA-M/r/` symlinks = 39,331 (+1 vs source);
    `/opt/VistA-M/o/` compiled objects = 39,338 (+8 vs source);
    MANIFEST.tsv entries = 39,330 (matches source)
  - Source and MANIFEST agree exactly. The +1 symlink and +8 compiled
    objects beyond the source set are open questions — see TODO below.
  - **176 package directories**; **174 contain routines**. Two are
    data-only (Globals/ but no Routines/): "Altoona VA" and
    "VA-DOD Sharing"
  - **4,138,428 total lines** of MUMPS source; **162 MB** on disk
  - Largest packages by routine count:
    - Automated Information Collection System — 3,147
    - Integrated Billing — 2,451
    - Registration — 2,179
    - Scheduling — 1,798
    - IFCAP — 1,640
    - Order Entry Results Reporting — 1,394
    - Lab Service — 1,369
    - Automated Medical Information Exchange — 977
    - Kernel — 934
    - Nursing Service — 922
- **Evidence**: `vista/export/normalized/routines.tsv` (39,330 rows),
  `vista/export/normalized/packages.tsv` (174 rows). MANIFEST row count
  equals `routines.tsv` row count — no partial sync, no orphaned entries.
- **Implications**:
  - Foundation for Phase 2+ of ADR-045 (role classification, globals-
    touched extraction, call graph). All downstream routine-side work
    joins against this inventory.
  - Code-side mass (39k routines, 4M lines) is roughly ~4-5x the
    file-side mass by artifact count (8,261 files). Any code↔data
    tooling should plan for that asymmetry.
  - Data-only packages (2 of 176) confirm that "package" is already the
    right unifying bridge: some packages own only data, some own both —
    classifying per artifact type and joining at the package level
    (per ADR-045) is the honest shape.
- **TODO (post-session)**: chase down the +1 symlink and +8 compiled-
  object files beyond the 39,330 source set. Hypotheses to test:
  percent routines (`_ZOSF`, `_ZUTIL`, etc.) installed outside the
  Packages/ tree; YottaDB utility routines inherited via $ZRO search
  path; or artifacts of the Dockerfile's build steps (Octo/VistA
  Octo wrapper at Dockerfile:173). Resolution should identify which
  "routines" are real code vs toolchain artifacts, and whether this is
  a VEHU distribution quirk, a YottaDB behavior, or a build-time
  side effect. See TODO.md.
- **Status**: verified (for source/MANIFEST counts); +1/+8 object-side
  divergence flagged for follow-up

### RF-009: Cross-PIKS matrix recalculated after File 200 reclassification

- **Date**: 2026-04-19
- **Scope**: All 69,809 fields, updated with File 200 = I (not S)
- **Method**: Reran VMPIKS (H-04b for File 200 = I, H-09 downgraded to
  low/I instead of high/S), then reran VMFPIKS
- **Finding**: Cross-PIKS matrix changed dramatically:
  - Total cross-PIKS fields: 5,055 → 3,868 (-23%)
  - P→I: 868 → 1,477 (+609) — patient→provider is now P→I, not P→S
  - S→I: 1,520 → 58 (-1,462) — most were I files, not S
  - S→P: 461 → 36 (-425) — the "security concern" was mostly I files
  - Fewer cross-boundary pointers = cleaner PIKS boundaries
  - PIKS distribution: S dropped from 32% to 10%; I rose from 18% to 35%
- **Evidence**: Updated piks.tsv, field-piks.tsv
- **Implications**:
  - The original S→P "security concern" (461 fields) was largely a
    misclassification artifact. True S→P is only 36 fields.
  - P→I (1,477) is now the dominant cross-PIKS pattern — clinical
    records referencing providers/staff. This is correct and expected.
  - The remaining 36 S→P fields deserve individual security review.
  - VistA's true System category is much smaller than initially measured —
    ~10% of files, not 32%.
- **Status**: verified

### RF-008: File 200 (NEW PERSON) is staff/provider PII, not system data

- **Date**: 2026-04-19
- **Scope**: File 200 (NEW PERSON), 1,551 entries, 203 fields
- **Method**: Direct global interrogation (VMINV200, VMINV2B routines)
- **Finding**: File 200 contains staff/provider demographics and credentials:
  - 1,551 entries (providers, clerks, techs, nurses, pharmacists, programmers)
  - SSN: 1,462 populated (94%)
  - DOB: 1,151 populated (74%)
  - Address: 119, Phone: 132, Email: 2
  - Also: access codes, verify codes, security keys, menu options, DEA#, NPI
  - NO patients. IEN overlap with ^DPT is coincidental (31 shared IENs,
    different people).
  - File 200 is VistA's most-referenced file (1,244 inbound pointers) —
    every file that references a user/provider points here.
- **Evidence**: VMINV200.m + VMINV2B.m output; direct ^VA(200,*) queries
- **Fix**: Reclassified from S to I (primary), S (secondary). Updated
  H-09 heuristic: pointer to File 200 now classifies as I (low confidence)
  instead of S (high confidence). Added H-04b for File 200 = I (certain).
  Cascade effect: 783 files reclassified, S category dropped from 32% to 10%.
- **Implications**:
  - Sensitivity = protected regardless of PIKS category (1,462 SSNs)
  - The 1,244 inbound pointers mean File 200's PIKS classification
    cascades to a large fraction of the database via H-09
  - Any PIKS classifier MUST handle File 200 correctly or the entire
    distribution is skewed
- **Status**: verified

### RF-007: Field-level cross-PIKS analysis reveals VistA's semantic wiring

- **Date**: 2026-04-19
- **Scope**: All 69,809 fields across 8,261 FileMan files
- **Method**: VMFPIKS routine — classifies each field with file_piks
  (inherited from parent file), ref_piks (target file's PIKS for pointer
  fields), cross_piks flag, and sensitivity_flag.
- **Finding**: 5,055 pointer fields cross PIKS boundaries. The cross-PIKS
  matrix reveals VistA's structural wiring patterns:
  - S→I (1,520): System infrastructure heavily references facilities
  - P→I (868): Patient records reference where care happened
  - P→S (489): Patient data references system entities (protocols, options)
  - S→P (461): System files reference patient data — security concern
  - P→K (362): Clinical data coded with terminologies (ICD, CPT, drugs)
  - I→K (340): Facility setup uses knowledge tables
  - K→P (22): Knowledge pointing to patient data — rare and worth investigating
- **Evidence**: `normalized/field-piks.tsv` (69,810 rows)
- **Implications**:
  - The 461 S→P fields need security review — system files holding patient references
  - The 362 P→K fields are the FHIR terminology binding points
  - The 22 K→P fields may indicate misclassified files (knowledge should be patient-independent)
  - 866 sensitivity flags found (protected person data in non-P files) but
    over-flagged — .01 NAME fields in template/entity files aren't person names
- **Status**: provisional — sensitivity flag logic needs refinement

### RF-006: PIKS classification complete — 98.3% coverage

- **Date**: 2026-04-19
- **Scope**: All 8,261 FileMan files (2,954 top-level + 5,307 subfiles)
- **Method**: VMPIKS routine (Tiers 1-6, 9) + manual triage (217 files)
- **Finding**: 8,120 of 8,261 files classified (98.3%). Distribution:
  - P (Patient):     2,815 (34.1%) — clinical care data
  - S (System):      2,671 (32.3%) — config, ops, VistA internals
  - I (Institution): 1,539 (18.6%) — facility/org structure
  - K (Knowledge):   1,096 (13.3%) — terminologies, templates, workflows
  - Unclassified:      141 (1.7%) — subfiles awaiting inheritance
- **Evidence**: `normalized/piks.tsv` + `normalized/piks-triage.tsv`
- **Implications**:
  - System is the second-largest category (32.3%) — VistA has massive
    infrastructure overhead relative to clinical data
  - Patient + Knowledge together = 47.4% — the clinically relevant data
  - Institution (18.6%) is larger than expected — many facility config files
  - Every classification has piks_method + piks_evidence for traceability
- **Status**: verified (for classified files; 141 subfiles pending)

### RF-005: Heuristic accuracy — Tier 2 (pointer-to-anchor) is the strongest signal

- **Date**: 2026-04-19
- **Scope**: 8,261 files, 24 heuristics across 6 tiers + propagation
- **Method**: VMPIKS run analysis — which heuristics classified the most files
- **Finding**: Heuristic contributions ranked by file count:
  - H-05 (subfile inheritance): 4,424 — the workhorse (53.6% of all classifications)
  - H-09 (pointer→File 200): 783 — many files reference NEW PERSON
  - H-14 (Patient package prefix): 603 — package namespace is high-yield
  - H-06 (pointer→File 2/PATIENT): 360 — direct patient reference
  - H-08 (pointer→File 4/INSTITUTION): 284 — facility reference
  - H-10 (Patient global root): 236
  - H-15 (Institution package prefix): 202
  - H-12 (Knowledge global root): 197
  - H-02 (file# < 2, FM meta): 127
  - H-13 (System global root): 119
  - H-39 (orphan→S): 114
- **Evidence**: VMPIKS run output; `piks.tsv` piks_method column
- **Implications**:
  - Inheritance (H-05) dominates because VistA has 5,307 subfiles — each
    inherits from parent. This is the right behavior.
  - Pointer-to-anchor (Tier 2) is the most reliable single-pass signal.
    File 200 (NEW PERSON) with 1,244 inbound pointers is VistA's most
    central file — it's the user/provider reference for everything.
  - Package namespace (Tier 4) was high-yield after expanding the prefix
    lists. Initial lists were too narrow — needed 3 iterations to cover
    the major packages.
- **Status**: verified

### RF-004: File 200 (NEW PERSON) is VistA's most-referenced file

- **Date**: 2026-04-19
- **Scope**: pointer_in counts from files.tsv (8,261 files)
- **Method**: VMFILES extraction, sorted by pointer_in descending
- **Finding**: Top 10 most-referenced files by inbound pointer count:
  1. File 200 (NEW PERSON): 1,244 inbound pointers
  2. File 2 (PATIENT): 379
  3. File 4 (INSTITUTION): 321
  4. File 44 (HOSPITAL LOCATION): 248
  5. File 5 (STATE): 124
  6. File 80 (ICD DIAGNOSIS): 117
  7. File 40.8 (MEDICAL CENTER DIVISION): 85
  8. File 50 (DRUG): 83
  9. File 60 (LABORATORY TEST): 81
  10. File 3.5 (DEVICE): 73
- **Evidence**: `normalized/files.tsv` pointer_in column
- **Implications**:
  - File 200 has 3.3x more inbound pointers than File 2 (PATIENT). This
    makes it VistA's structural hub — not Patient, not Institution, but
    the user/provider identity file.
  - File 200 is classified S (System) with secondary I (Institution) —
    it serves both user management and provider identity.
  - The top 10 list cleanly maps to PIKS anchors: 200=S, 2=P, 4=I,
    44=I, 5=K, 80=K, 40.8=I, 50=K, 60=K, 3.5=S
- **Status**: verified

### RF-003: VistA has 8,261 FileMan files — widest is 2,603 fields

- **Date**: 2026-04-19
- **Scope**: Complete ^DD walk
- **Method**: VMFILES extraction
- **Finding**:
  - 8,261 total files: 2,954 top-level + 5,307 subfiles (ratio 1:1.8)
  - Widest files: Generic Code Sheet (2,603 fields), Oncology Primary
    (1,902), CHEM/HEM Lab (965), PAID Employee (769), Surgery (761),
    Patient (594)
  - Largest tables by record count: Lexicon 757.x (~900K), RxNorm 129.x
    (~500K), ICD DRG 83.51 (1M)
  - Mean field count: ~8.5 fields per file (heavily skewed — median likely ~4)
- **Evidence**: `normalized/files.tsv` (8,262 rows including header)
- **Implications**:
  - The 1:1.8 top-level to subfile ratio means VistA is deeply hierarchical.
    Subfile inheritance (H-05) is the most important PIKS heuristic because
    it covers 64% of all files.
  - Lexicon and RxNorm dominate record counts — these are Knowledge tables
    that account for the bulk of the database by row count, even though
    Patient data dominates by file count and clinical importance.
- **Status**: verified

### RF-002: 86% of VEHU globals are FileMan-described

- **Date**: 2026-04-19
- **Scope**: All 486 globals in the VEHU database
- **Method**: VMCENSUS Phase 1 recon — enumerate via `mupip size`,
  match against ^DIC(file,0,"GL")
- **Finding**:
  - 486 total globals (1 scratch/temp excluded)
  - 418 FileMan-matched (86.0%)
  - 67 non-FileMan (13.8%)
  - Non-FM globals are mostly small: largest is ^DMRTRACE (778 nodes)
  - ZZ* globals (23 globals, ~200 nodes) are site-specific artifacts
  - %Z* globals are Kernel system globals
- **Evidence**: VMCENSUS Phase 1 output
- **Implications**:
  - The spec's concern about massive non-FM Pharmacy/Lab data does NOT
    materialize in VEHU. All Pharmacy (^PS*, ^PSR*) and Lab (^LR*, ^LA*)
    globals are FileMan-matched.
  - Non-FM data may be a production-runtime phenomenon (data written
    during clinical operations outside DD control) rather than structural.
  - The DD-based heuristics (H-01 through H-52) cover the vast majority
    of the database. The 6 non-FM heuristics (G-01 through G-06) are
    available but less needed than anticipated.
- **Status**: verified for VEHU; may differ on production systems

### RF-001: mupip load silently fails on paths with spaces — 94% of globals not loaded

- **Date**: 2026-04-19
- **Scope**: VEHU-M global import during Docker build
- **Method**: Quality check comparing Packages.csv against ^DD/$D checks
- **Finding**: First builds loaded only 176 of 3,138 ZWR files. 2,962
  files failed because `mupip load` on YottaDB r2.02 treats spaces in
  file paths as parameter separators even when quoted. Packages with
  spaces in directory names (VA FileMan, Lab Service, Mental Health,
  Scheduling, etc.) ALL failed silently — the `|| echo WARN` in the
  Dockerfile caught each failure but the build continued per
  continue-on-error policy.
  
  Most critically, `^DD` (Data Dictionary — 859K entries, 44MB) was
  empty, meaning no file structure metadata was available despite
  FileMan routines loading successfully.
- **Evidence**: BL-012; build output grep showing 2,962 WARN lines
- **Fix**: Symlink each ZWR to `/tmp/_load.zwr` before calling mupip load.
  Post-fix: 2,607/2,608 files load successfully.
- **Implications**:
  - This is a YottaDB r2.02 bug or undocumented limitation.
  - Any VistA-on-YottaDB project using mupip load with OSEHRA/WorldVistA
    archives will hit this. The workaround (symlink to space-free path)
    should be documented upstream.
  - The continue-on-error policy (ADR-023) masked a critical failure —
    the build "succeeded" but the database was essentially empty.
    Quality checks (like the Packages.csv comparison) are essential.
- **Status**: verified; fix confirmed working
