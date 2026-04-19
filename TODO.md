# vista-meta — open follow-ups

Post-session items flagged during analysis. Not tracked in ADRs (not
decisions yet) or RESEARCH.md (not verified findings yet). Each item
owns enough context to be picked up cold in a future session.

---

## T-001: Reconcile routine counts — source vs symlinks vs compiled

**Flagged**: 2026-04-19, during RF-010 (Phase 1b of ADR-045).

**Observation**:
- Source `.m` files in `/opt/VistA-M/Packages/*/Routines/`: **39,330**
- Symlinks in `/opt/VistA-M/r/`: **39,331** (+1 vs source)
- Compiled `.o` files in `/opt/VistA-M/o/`: **39,338** (+8 vs source)
- MANIFEST.tsv entries: **39,330** (matches source exactly)

Source and MANIFEST agree exactly — the routine farm build (Dockerfile
~L110-125) is consistent with itself. But the symlink farm has one
extra entry and the object directory has eight extra entries. These
discrepancies are small but real and currently unexplained.

**Why it matters**: any downstream routine-side analysis (Phase 2+ of
ADR-045 — role classification, globals-touched extraction, call graph)
needs to know whether the 39,330 source set is the complete universe
of routines executable inside this VEHU, or whether there are routines
present at runtime that aren't visible in `Packages/`. If the latter,
the inventory is incomplete.

**Hypotheses to test**:
1. **Percent routines** (`_ZOSF`, `_ZUTIL`, `_DI*`, etc.) — YottaDB
   system routines that may be copied into `/opt/VistA-M/o/` during
   build but whose source lives in `$ydb_dist`, not `Packages/`. The
   Dockerfile explicitly reports "Percent routines: N installed"
   around L163 — check that number against the +8 delta.
2. **Octo/VistA-Octo bridge** — Dockerfile ~L173 mentions
   `_YDBOCTOVISTAM.m` and an `ddl/` directory. A late-build step may
   add generated routines into `/opt/VistA-M/r/` after MANIFEST has
   been frozen. Check whether `_YDBOCTOVISTAM` and friends appear in
   `/opt/VistA-M/r/` but not in MANIFEST.
3. **Build-time side effect** — the compilation pass might emit auxiliary
   `.o` files (e.g., for routines pulled in by indirection, or for
   toolchain helpers) that have no corresponding `.m` in Packages/.
4. **Symlink oddity** — the +1 in `/r/` may be the MANIFEST.tsv itself
   or a stray helper file. Quick to confirm with `ls /opt/VistA-M/r/`
   filtered against MANIFEST.

**Concrete steps when picking this up**:
```bash
# Identify the +1 in /opt/VistA-M/r/
docker exec vista-meta bash -c '
  comm -23 \
    <(ls /opt/VistA-M/r/*.m | xargs -n1 basename | sed "s/\.m$//" | sort) \
    <(tail -n +2 /opt/VistA-M/r/MANIFEST.tsv | cut -f1 | sort)
'

# Identify the +8 in /opt/VistA-M/o/
docker exec vista-meta bash -c '
  comm -23 \
    <(ls /opt/VistA-M/o/*.o | xargs -n1 basename | sed "s/\.o$//" | sort) \
    <(tail -n +2 /opt/VistA-M/r/MANIFEST.tsv | cut -f1 | sort)
'

# Cross-check Dockerfile build output
docker logs vista-meta 2>&1 | grep -iE "routine farm|compiled|percent"
```

**Resolution criteria**:
- Each of the +1 symlink and +8 object files is named and classified
  as either (a) legitimate runtime code to be added to the inventory,
  or (b) toolchain artifact to be documented and excluded.
- If (a): extend `host/scripts/build_routine_inventory.py` and
  `make sync-routines` to cover those sources and update RF-010.
- If (b): document in RESEARCH.md as a new RF entry and note in
  ADR-045 that the inventory scope is intentionally
  `Packages/*/Routines/*.m`.

**Not a blocker for Phase 2** — Phase 2 (role classification) can
proceed on the 39,330 MANIFEST set. But this should be resolved before
any claim of "complete routine coverage" is made externally.

**Correction note**: during the Phase 1b session, an earlier
hallucinated estimate of "~24,000 routines" was repeatedly cited as
a reference point. That figure had no source — it was a fabricated
estimate by the AI assistant. The real numbers are above. T-001 is
about the small real +1/+8 divergence, not the nonexistent 24k/39k
gap.
