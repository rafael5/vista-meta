# ADR-046: kids-vc undo — pre-install snapshot for reversible declarative patches

Date: 2026-04-20
Status: Proposed

## Context

VistA's KIDS install is forward-only and destructive. RF-033 finalized
the Tier-1 kids-vc framework (decompose/assemble/merge/CI, 100% corpus
pass), but nothing in it gives a site a way to *undo* an installed
patch. The user asked whether uninstall is possible. The honest answer:
KIDS itself has no uninstall, and there's a concrete reason — KIDS
install is an imperative sequence that:

- Overwrites routine source in `^ROUTINE` / `.m` files
- Merges FileMan DD changes directly into `^DD`
- Adds/modifies entries in File 19 (OPTION), 101 (PROTOCOL), 8994 (RPC)
- Runs pre-install and post-install MUMPS routines that can do arbitrary
  data transformation, MailMan messages, `^XTMP` scratch, etc.

KIDS keeps no previous-state snapshot. File 9.7 (INSTALL) records what
happened, not what the prior state was. Field 6.2 "DELETED BY PATCH"
is a forward-delete marker, not undo.

Sites currently handle rollback via:
- Full globals-volume backup immediately pre-install (SOP)
- Parallel TEST VistAs (catch bugs before production)
- Global-volume snapshots (YottaDB/Caché feature; our Docker setup uses
  this via `make snapshot-globals`)
- Manual reverse-patch authorship (VA publishes a follow-up patch that
  explicitly undoes a regression)

None of these is a surgical per-patch undo.

**What kids-vc already enables**: if the pre-install source is
git-tracked (via `kids-vc decompose` before install), `git revert` +
`kids-vc assemble` produces a reverse delta on routines, options,
protocols, and RPCs. Good for declarative content. Doesn't cover
FileMan data mutations or pre/post-install side effects.

## Decision

Build a **Phase 9 "kids-vc undo"** tool that automates pre-install
snapshot and reverse-install for the declarative surface of a KIDS
patch. In-VistA MUMPS hook plus Python orchestration.

**Architecture**:

1. **Pre-install hook** — new MUMPS routine `VMKVCUNDO` under
   `vista/dev-r/`. Called just before `D ^XPDIP` (install). For each
   component named in the transport global (routines, options,
   protocols, RPCs, FileMan file DDs), it snapshots the current
   pre-install state into `^XTMP("KVC-UNDO",<patch-name>,<section>,...)`.
2. **Snapshot format is KIDS-compatible**. The snapshot reuses the
   same ZWR-per-subscript layout KIDS transport globals use. So the
   "undo snapshot" is literally a KIDS-shaped transport global, and
   can be exported via `kids_vc.py decompose`.
3. **Undo operation** — re-materialize the snapshot as a KIDS
   transport global and run KIDS INSTALL on it. KIDS overwrites
   post-state with pre-state for the declarative components.
4. **Extraction side** — `kids-vc undo` command:
   - Reads snapshot from `^XTMP("KVC-UNDO",<patch>,...)`
   - Builds a reverse `.KID` file via `assemble`
   - Tags it "UNDO-<original-patch>" so sites can install it through
     normal KIDS tooling

**Explicit scope — what undo handles**:
- Routine source restoration
- FileMan DD reversal (for added fields — delete them; for modified
  fields — restore prior definition from snapshot)
- Option / Protocol / RPC / Security-key restoration
- Deletion of entries that didn't exist pre-install

**Explicit scope — what undo does NOT handle**:
- Pre-install / post-install MUMPS code side effects. Imperative MUMPS
  that modifies data, sends MailMan messages, transforms records, or
  mutates `^XTMP` is NOT reversed. The undo snapshot captures the
  PRE-state of declarative KIDS components; imperative run-time
  mutations are out of reach.
- FileMan DATA sections (seed data merged into records). Patch-shipped
  seed data may have overwritten site-local values; the undo doesn't
  know what values were there before the merge.
- Cascading data effects. If post-install created 10,000 new records
  in a patient file based on a new field, undoing the field definition
  doesn't undo the records.
- Install-time IEN assignments. If the patch's post-install pointed
  records to IENs it just created, undoing won't unwind those pointers.

## Consequences

**Positive**:

- Surgical per-patch rollback for the declarative surface — no
  backup-and-restore-everything needed for common mistakes.
- Reverse-install uses existing KIDS machinery — no parallel install
  infrastructure to maintain.
- The "UNDO-<patch>.KID" artifact is a normal KIDS build; can be
  reviewed, transmitted via FORUM, installed by standard IRM process.
- Snapshots are KIDS-shape → `kids_vc.py decompose` works on them →
  they're version-controllable as additional fixtures in the repo.
- Documents exactly what IS and IS NOT reversible per install.

**Negative**:

- Requires pre-install hook installation at each site. Not automatic
  — needs VMKVCUNDO routine shipped and registered to fire on
  `^XPDI` calls (via Kernel option or patch-install callback).
- Additional disk/globals space for snapshots. For a large patch
  affecting many routines and DDs, snapshot size ≈ pre-install
  content size. `^XTMP` auto-cleanup after 90 days mitigates
  long-term cost but means undos must be done within the window.
- Site IRMs need to understand the scope boundary. A site that
  expects "undo everything" will be disappointed when post-install
  data mutations persist.
- Additional MUMPS code under `vista/dev-r/` that has to be
  maintained against VistA-M lineage evolution.
- Snapshots themselves are fragile — if a site's `^XTMP` gets
  cleaned manually, undo becomes impossible.

**Neutral**:

- Extends the kids-vc portfolio from purely decompose/assemble into
  a live-VistA-integrated tool. This is the first feature requiring
  actual in-VistA infrastructure.
- Changes the project's scope from "source-control bridge" to
  "source-control bridge + limited install lifecycle management".

## Alternatives considered

**A. Rely solely on globals-volume backup / snapshot**. What VA sites
do today. Works for complete rollback but not surgical per-patch
undo. No source-control involvement. Not pursued here because it
doesn't leverage the kids-vc infrastructure and doesn't give
reviewable artifacts.

**B. Git-revert + assemble — no snapshot needed**. If all patches were
git-committed at decompose time, `git revert` + re-assemble reverses
declarative changes. Works today, no new code. **Rejected as the
primary solution** because it requires every site to have pre-install
decomposed source — a discipline that sites don't currently maintain.
Pre-install snapshotting works even without prior source-control
adoption.

**C. Transactional install — wrap the whole KIDS install in a database
transaction, abort to rollback**. Theoretically cleanest. Rejected:
(i) KIDS install isn't designed to be rolled back via transaction;
(ii) pre-install and post-install routines may themselves start/end
transactions, causing nested-transaction issues; (iii) FileMan DD
changes interact with global structures in ways that don't play well
with long transactions. Would require a KIDS rewrite, not an add-on.

**D. Record every mutation at install time, replay in reverse**. Like
a database undo log. Would require hooking every SET/KILL/MERGE in
the install sequence. Rejected as too invasive — we'd be wrapping
^XPDIP and potentially every M SET command at the install level.
Snapshot-before approach captures the needed state without
instrumentation.

**E. Do nothing. Document the limitation and redirect users to
backup/restore**. Perfectly defensible given the current kids-vc
scope. Rejected because user explicitly asked whether undo is
possible and what's involved; having a designed answer is more
useful than "no, use backups".

## Scope boundaries (restated for clarity)

Phase 9 kids-vc undo is **not** a general-purpose VistA rollback. It
is specifically:

- **Per-patch** (not per-install-event across patches)
- **Declarative content only** (routines, DDs, options, protocols,
  RPCs, security keys)
- **Pre-install state restoration** (not log-based replay in reverse)
- **KIDS-compatible output** (uses existing KIDS install mechanism)
- **Within `^XTMP` retention window** (typically 90 days)

Any goal beyond these (undoing pre/post-install MUMPS effects,
reverting FileMan data changes, undoing beyond the `^XTMP` retention
window) requires full backup/restore.

## Open questions to resolve during implementation

1. **Snapshot granularity**: whole-routine vs per-changed-line?
   Whole-routine is simpler but larger; per-line is harder to
   restore correctly. Pick whole-routine for MVP.
2. **Trigger mechanism**: How does VMKVCUNDO get called pre-install?
   Candidates: (a) Kernel option that wraps `^XPDIP`, (b) site adds
   a pre-install routine that chains to the patch's own pre-install,
   (c) `kids-vc pre-install` CLI that loads the transport + snapshots
   + calls ^XPDIP. MVP: option (c) — leaves normal KIDS flow intact
   for non-kids-vc-aware installs.
3. **Multi-patch stacking**: can you undo patch A if patch B was
   installed after? Only if B's pre-state snapshot didn't overwrite
   A's snapshot. Either: (a) keep all snapshots distinctly (namespace
   by patch name in `^XTMP`), (b) require LIFO undo (undo B first,
   then A). MVP: (a) — distinct namespace per patch.
4. **Cross-site portability**: if site X creates an undo-snapshot for
   a patch, can site Y use it? Probably not, because pre-install state
   differs by site (local customizations). Snapshots are site-local.
   Document this.
5. **Patch-author cooperation**: some patch authors know their patches
   are not safely undoable. Should KIDS patches carry a "not
   undoable" flag? MVP: no; caller's discretion.
6. **Testing**: how do you unit-test an undo tool that needs a live
   VistA? Decompose paths testable offline; in-VistA snapshot +
   replay needs a VEHU-like container. Can leverage vista-meta's
   Docker infrastructure.

## Relationship to other ADRs

- **ADR-045** (separate data and code classification): Phase 9 undo
  operates on the code-model side (routines, DDs, Kernel components).
  Doesn't cross into data-model PIKS classification.
- **ADR-029** (symlink farm for routines): snapshots of routines live
  in `^XTMP`, not in the routine namespace; no conflict.
- **ADR-012** ($ZRO layering): dev-r takes precedence over VistA-M,
  so `VMKVCUNDO` installed in `vista/dev-r/` will shadow any
  upstream VistA-M routine by the same name without conflict.
- **ADR-018** (first-run XINDEX baseline: auto + manual rebake):
  similar pattern — pre-install snapshot is a bake-like operation,
  could be exposed via Makefile target consistent with existing
  `make bake-*` targets.
