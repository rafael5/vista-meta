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

---

## T-002: MANIFEST ↔ File 9.8 delta — investigate the two legitimate cohorts

**Flagged**: 2026-04-19, during RF-016 (Phase 4a of ADR-045).

**Observation** (from Phase 4a cross-reference):
- Intersection (known to both): **29,102 routines**
- **MANIFEST-only (shipped but not in File 9.8): 10,228**
- **File 9.8-only (registered in Kernel but not shipped): 1,563**

These are legitimate differences — MANIFEST and File 9.8 measure
different things — but the cohorts themselves are interesting and
may carry signal about package install conventions.

**Worth investigating (post-session)**:
1. **MANIFEST-only cohort (10,228)**: routines shipped under
   `Packages/*/Routines/` that Kernel never registered. Sample names
   in the cohort start with `A1A1*` (Albany OIFO). Hypotheses:
   - Field-OIFO add-ons / IRM local modifications shipped for
     reference but not part of the formal install path.
   - Test/sample routines that never get DIFROM-registered.
   - Routines whose packages use a non-FileMan install route.
2. **File 9.8-only cohort (1,563)**: routines Kernel knows about
   that don't appear under `Packages/*/Routines/`. Top prefixes:
   PSN (304 — Pharmacy National), MAG (149 — Imaging), PRA (126),
   LBR (75), ABS (74 — IHS), DSI (59), QAC (58), ONC (57), QAN (53),
   SOW (52). Hypotheses:
   - Routines installed directly into ^ROU globals from sources
     outside `Packages/`.
   - Patch-only or stub entries retained for compatibility.
   - References to routines expected but not present in this build.

**Resolution criteria**:
- Each cohort gets a characterization: what kind of routines, from
  what sources, why they diverge. A small number of sub-cohort RF
  entries or package-level breakdown is probably enough.
- No code changes expected — this is a documentation and
  understanding exercise, not a correction.

**Not a blocker** for any later phase. Phase 6 joins will flag cross-
references that sit on only one side, which is the visible surface.

---

## T-003: Characterize the 14,658 truly-unreferenced routine cohort

**Flagged**: 2026-04-19, during RF-024 (Phase 6 closure).

**Observation**: after Phase 5 (routine→routine call graph) and
Phase 5b (protocol→routine from File 101 ENTRY/EXIT ACTION), 14,658
routines still have:
- `in_degree` = 0 (no `.m`-source caller found)
- `rpc_count` = 0 (no RPC backs them)
- `option_count` = 0 (no TYPE=R option backs them)
- `protocol_invoked_count` = 0 (no File 101 protocol invokes them)

Yet many are clearly live code (Kernel utilities, FileMan routines,
clinical modules). The reference must be arriving via paths the
current extractors don't see.

**Hypotheses to test**:
1. **FileMan DD-embedded MUMPS** — `^DD(file,field,0)` node 6+
   contains input transforms, computed-field code, and cross-reference
   SET/KILL logic. These are MUMPS strings executed at FileMan time,
   and often reference routines via `D ^NAME`. Extract all `^DD`
   executable subnodes and run the Phase 5 regex against them.
2. **KIDS install-time dispatch** — package installation runs
   routines via `D ^XPDIL`, `X $G(^DIC(9.4,...))`, and similar
   late-bound mechanisms. These are not in ENTRY/EXIT ACTION or
   plain `.m` source.
3. **XECUTE of dynamic MUMPS** — any `X STR` where STR is computed
   at runtime is undecidable statically. Accept as a floor.
4. **Comma-continuation in DO** — `D A^R1,B^R2,C^R3` — Phase 5
   catches only the first callee. Fix the regex to walk past commas.
5. **Line-offset calls** — `D TAG+3^ROU` — Phase 5 skips.
6. **Event drivers via subscribers** — protocol E/S pairs — already
   captured via Phase 5b, but the indirect chain (protocol A drives,
   B subscribes, B calls routine) may break visibility.

**Quick wins before a full investigation**:
- Fix the comma-continuation regex in `build_routine_calls.py`. Cost:
  ~5 lines. Expected absorption: a few hundred to a few thousand
  routines shifting out of the cohort.
- Extract DD-embedded MUMPS and scan — new `VMDDCODE.m` extractor
  pulling from `^DD(fnum,fld,>=6)` nodes. Cost: a day of work.
  Expected absorption: meaningful (FileMan cross-refs and computed
  fields reach thousands of routines).

**Resolution criteria**:
- Reduce the truly-unreferenced cohort to something under 5% of
  MANIFEST (~1,500 routines), OR
- Definitively characterize the residual as dead code by triangulating
  against File 9.8 (never registered in Kernel = stronger dead
  signal) and XINDEX (VistA's own code analyzer).

**Impact**: not a correctness blocker — the existing artifacts are
correct about what they measure. T-003 is about completeness of the
call graph, which affects decomposition/modernization analysis but
not the package manifest's basic utility.
