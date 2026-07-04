# V4 session kickoff — fidelity declarations (R2 + F9)

> **SPENT (closed 2026-07-04).** One-shot session handoff prompt; its work landed as
> Track V4 (b119bd1, fidelity declarations, gate PASS).


Handoff prompt for the next session. Paste the block below verbatim into a
fresh Claude session opened in `~/projects/vista-meta`. Written 2026-07-03,
after V1–V3 completed (`main` through `f73b2d4`).

---

Continue Track V4 of the producer-contracts plan in ~/projects/vista-meta.

CONTEXT
- Plan: docs/proposals/producer-contracts-implementation-plan.md — read §V4 and
  risk-register rows F9/F8 first. Spec: docs/proposals/schema-v1-normalization-spec.md §6 R2.
- V1–V3 are COMPLETE and pushed (main, through f73b2d4; see memory
  project_vista_meta.md entries (f)–(h) for the full trail):
  * schema_v1.py = typed declarative registry of all 24 TSVs (coltypes/nullable/fks,
    SHARED_VOCABULARIES); tsvio.py = canonical writer; normalize_dumps.py;
    materialize_piks.py (V2: piks.tsv = 8,261 rows, piks_source auto/triage/inherited);
    build_column_manifest.py (V3: meta/column-manifest.json, 186 cols, --check gate green).
  * The current committed data IS the single-run V1.8 emission (R3 sidecar at
    vista/export/raw/extraction.json, db_fp b8518a87f50f…). raw/ still holds the
    same-vintage extraction intermediates (gitignored but on disk) — use them; do NOT
    re-extract. The engine (vista-vehu) is STOPPED and V4 needs no engine: it is
    host-side measurement + declaration only.

V4 SCOPE (gate: all three declarations present, rates re-measured on the CURRENT
emission, never stale numbers):
1. Open-world FK declaration — re-measure the callee_routine unresolved rate against
   the post-R4 census (pre-R4 it was ~2.3% = 472/20,974 distinct callees; the
   %-census (11 routines) moves it). Also measure the other declared-fk open-world
   edges from schema_v1.fks (options.package_dir 1 outside, package-data.package 2
   outside, vista-file-9-8.routine_name, files.parent_file orphans, etc.).
2. Static-call XINDEX authority — declare XINDEX authoritative for statically
   expressed calls only; indirection (DO @X), XECUTE, option/protocol/RPC dispatch
   OUT OF SCOPE. Re-measure divergence from the emitted xindex-validation.tsv
   (pre-R4: 2,032/29,098 routines diverged on callees; line/tag counts agreed 100% —
   re-verify both).
3. F9: xindex COVERAGE scope — this emission: xindex-routines 29,097 of 39,373 census
   routines; the gap is the T-002 cohort (ZLINK fails, e.g. KMPPS44*) + the 11
   %-routines. Declare which subset xindex describes and why, and DECIDE + declare
   whether %-routines are in the divergence denominator (they are almost certainly
   not XINDEX-processed — verify, don't assume).

SUGGESTED SHAPE (decide yourself, but keep house style): a measurement script
host/scripts/build_fidelity.py that computes all rates from the emitted TSVs and
emits vista/export/meta/fidelity.json (machine-checkable, re-runnable — V6 will
assert its presence/freshness), plus the prose declarations added to the spec §6 R2
area. TDD hard rule: unittest, run as `python3 host/scripts/tests/test_X.py`;
write tests red-first. meta/ and the two finals dirs are host-owned (uid 1000);
vista/export root is uid 1001 — don't write there directly.

GOTCHAS
- An engine-stack-guard hook blocks raw `docker exec` into engine containers; V4
  shouldn't need docker at all. If a one-off read-only peek is unavoidable, add a
  `# stack-exempt: <reason>` marker.
- xindex-validation.tsv already carries per-routine callees_* columns — derive
  divergence from it rather than recomputing joins.
- The running container named `vehu` is the org's upstream shared engine, NOT the
  emission engine. Leave it alone.
- Commit + push proactively per increment (stage only files you touched,
  Co-Authored-By: Claude … trailer). Update ~/claude/memory/project_vista_meta.md
  status line when V4 completes. Next after V4: V5 (content hash — its normative
  recipe is already specified in plan §V5).
