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

### RF-026: XINDEX batch run and ad-hoc parser validation

- **Date**: 2026-04-19
- **Scope**: Run XINDEX (Toolkit XT*7.3*158) on the full VEHU
  routine corpus to produce an authoritative reference dataset,
  then validate all our regex-based extractions (Phases 1b, 2a, 5)
  against that dataset.
- **Method**:
  - New MUMPS wrapper `vista/dev-r/VMXIDX.m` drives XINDEX
    non-interactively. Follows the `XINDX7` programmatic contract:
    pre-loads each routine's source into `^UTILITY($J,1,RTN,0,...)`
    via `ZLINK @(""""_RTN_"""")` + `$TEXT(+N^RTN)`, then calls
    `BEG^XINDEX` per routine. Bypasses `LOAD1^XINDEX`'s native ZL
    which has YDB indirection quirks.
  - Four non-trivial YDB/VEHU issues worked around in the wrapper:
    (a) missing `^%ZIS` (device handler) — set IO/IOM/IOSL/IOF
    manually; (b) `@IOF` indirection needs IOF to be a MUMPS
    expression string, not a literal char (use `"!"` for a
    newline); (c) YDB's `ZL @RTN` with RTN as variable triggers
    LVUNDEF (evaluates @RTN as expression looking up the named
    local); use quoted-string indirection `@(""""_RTN_"""")`
    instead; (d) `^%ZOSF("TEST")` / `^%ZOSV2` partial — skip the
    native LOAD path entirely.
  - Extraction layer `EXTRACT` walks `^UTILITY($J,1,...)` after
    the run, writing four TSVs to `/tmp` before job exit (scratch
    global is job-scoped).
  - Makefile target `make xindex` runs the bake, docker-cp's the
    four TSVs to `vista/export/normalized/`.
  - Makefile target `make validate-xindex` runs
    `host/scripts/validate_against_xindex.py` to join our data
    against XINDEX output.
- **XINDEX run performance**:
  - **30,255 type=R routines seeded from File 9.8.**
  - **29,098 processed successfully** (96.2%).
  - **1,157 failed** — T-002 cohort (File 9.8-only routines whose
    source isn't in `$ydb_routines` — ABS*, A1A*, %A1*, A7R*, etc.).
  - **Elapsed: 92 seconds.** 3.0 ms/routine.
  - Output TSVs:
    - `xindex-routines.tsv` — 29,098 rows × 6 cols
    - `xindex-errors.tsv` — 6,918 rows × 5 cols (errors by line)
    - `xindex-xrefs.tsv` — 214,011 rows × 3 cols (call graph)
    - `xindex-tags.tsv` — 292,148 rows × 3 cols (labels/entry points)
- **Validation results — static features (our regex vs XINDEX parser)**:
  - **line_count: 100.00% match** (29,098 / 29,098)
  - **tag_count: 100.00% match** (29,098 / 29,098)
  - Our Phase 1b line-counting (`\n` count) and Phase 2a
    tag-counting (column-0 alphanumeric-start detection) are
    **byte-for-byte identical** to XINDEX's MUMPS parser. Zero
    errors in our mechanical extraction.
- **Validation results — call graph (Phase 5 vs XINDEX)**:
  - Our callee edges summed:        **155,911**
  - XINDEX callee edges summed:     **158,486**
  - Matched (both agree):           **155,892**
  - Our-only (false positives):     **19** (0.012%)
  - XINDEX-only (we missed):        **2,594** (1.66%)
  - Average per-routine agreement ratio: **0.9875** (98.75%)
  - Distribution of per-routine XINDEX-only misses:
    - 27,082 routines (93.1%): perfect match
    - 1,644 routines (5.6%): miss 1 callee
    - 258 routines (0.9%): miss 2 callees
    - Long tail with 3-15 misses on a few hundred routines
- **Nature of the gap (why we miss 2,594 edges)**: traced to a
  specific pattern class — `$TEXT(+N^ROUTINE)` / `$T(+N^ROUTINE)`
  calls, used commonly for patch-version checks (e.g.,
  `$T(+2^IBCF2P)` reads the ;;version line of routine IBCF2P).
  Example: IBYPENV (Integrated Billing patch environment check) —
  our regex found 0 callees, XINDEX found 15. Every one was a
  `$T(+2^ROU)` patch check. Secondary gap class: comma-continuation
  in DO commands (`D A^R1,B^R2`), already documented as a Phase 5
  MVP limitation in RF-020.
- **Nature of our false positives (19 routines, 1 each)**: all in
  Kernel-namespace networking code (ZTM5, ZOSVGUT2, ZISTCPS,
  XMRINETD, XWBTCPL, etc.). Likely XINDEX's parser correctly
  excludes some construct we include.
- **Population coverage**:
  - MANIFEST routines XINDEX couldn't process: **10,232** (T-002
    A-cohort — shipped .m files whose names aren't ZLINK-able in
    this VEHU runtime).
  - XINDEX routines not in MANIFEST: **0** (XINDEX only succeeded
    where ZLINK did, and ZLINK needs source in `$ydb_routines`
    which covers MANIFEST).
- **Per-package agreement observations** (lowest first):
  - MASH Utilities: 0.20 agreement (13 routines, many failures)
  - Patient Assessment Documentation: 0.80
  - Most clinical packages: 0.93-0.97+
- **Outstanding XINDEX output NOT in our extraction**:
  The `xindex-errors.tsv` contains **6,918 errors** — the code-
  quality dataset we didn't previously have. 66 error types
  (F/S/W/I severity, per RF-025). This is authoritative VistA code
  quality data not available from any other source and genuinely
  novel to our project.
- **Evidence**:
  - `vista/dev-r/VMXIDX.m` (wrapper)
  - `vista/export/normalized/xindex-routines.tsv` (29,098)
  - `vista/export/normalized/xindex-errors.tsv` (6,918)
  - `vista/export/normalized/xindex-xrefs.tsv` (214,011)
  - `vista/export/normalized/xindex-tags.tsv` (292,148)
  - `vista/export/normalized/xindex-validation.tsv` (29,098)
- **Implications**:
  - **Our Phase 1b/2a static feature extraction is validated as
    perfectly accurate** against XINDEX ground truth — zero
    discrepancies across 29,098 routines. The mechanical
    extraction approach is sound.
  - **Our Phase 5 call graph is 98.75% accurate.** The 1.66% gap
    is concentrated in the `$TEXT()` pattern class, which a small
    regex addition (single new pattern) could address. Phase 5b
    (protocol ENTRY ACTION) similarly benefits.
  - **T-003 (14,658 truly-unreferenced) reduction potential** —
    the XINDEX xref data provides authoritative callers that our
    regex missed. Joining xindex-xrefs.tsv into
    routines-comprehensive.tsv would reduce the orphan cohort by
    the count of routines that appear as XINDEX-xref targets.
  - The **xindex-errors.tsv code-quality surface** is a new
    deliverable worth a dedicated analysis — which packages have
    the most SAC violations, which routines most Fatal errors, etc.
    This was the primary value XINDEX offers that we couldn't
    produce ourselves.
- **Status**: verified (cross-checked against XINDEX batch run)

### RF-025: XINDEX reference — comprehensive catalog of its metrics and outputs

- **Date**: 2026-04-19
- **Scope**: Investigate every metric, parameter, and output surface
  produced by XINDEX — VistA's own static analyzer (Toolkit
  XT*7.3*158). Contextualized by the DOX web surface
  (vivian.worldvista.org/dox/) which uses XINDEX as one of its data
  sources but surfaces only a subset.
- **Method**: Read the 17 `XIND*.m` routines under
  `/opt/VistA-M/Packages/Toolkit/Routines/`, enumerate
  `^UTILITY($J,...)` scratch-global usage patterns, walk File 9.8
  DD including subfiles 9.801/9.803/9.804/9.805/9.806/9.808/9.818/
  9.819, and fetch DOX sample pages for comparison.
- **Findings recorded in `docs/xindex-reference.md`** (full catalog;
  ~270 lines). Highlights:
  - **66 distinct error/warning codes** across four severity levels
    (F=Fatal, S=Standard/SAC-violation, W=Warning, I=Info). Codes 1-66
    in XINDX1's ERROR label. Some codes have namespace exclude lists.
  - **Twelve INP() parameters** control XINDEX's run — print detail,
    summary-only, index-called-routines, include-compiled-templates,
    and critically **INP(7) "save parameters in ROUTINE file"** which
    causes File 9.8 subfiles to be populated.
  - **Scratch global structure** — `^UTILITY($J,1,RTN,...)` holds
    everything XINDEX computes per routine: line-by-line errors with
    severity and text, tag/label inventory, external cross-references,
    local-variable usage, global access, RSUM checksum. A rollup at
    `^UTILITY($J,1,"***",LOC,S)` aggregates references across the
    whole run, by LOC ∈ {G=global, L=local, T=tag, X=external}.
  - **File 9.8 persistent writes** (when INP(7)=Y): top-level
    1.2/1.4/1.5/7.x metadata fields plus six subfiles: 5 TAG (9.801),
    19 ROUTINE INVOKED (9.803), 20 INVOKED BY (9.804), 21 VARIABLES
    (9.805), 22 GLOBALS (9.806), 2.1 BRIEF DESCRIPTION (9.808). Each
    subfile row has a `FOUND BY %INDEX` provenance flag.
  - **DOX uses XINDEX as primarily a call-graph data source** —
    surfaces the caller-graph PNG, entry points, and RPC/FileMan
    bindings, but **discards** all 66 error/severity data, line
    counts, checksums, and the VARIABLES/GLOBALS subfile content.
    Our project already surpasses DOX in the per-routine data we
    capture (RF-022's 20-column comprehensive TSV).
- **VEHU population state**: File 9.8 subfiles are almost entirely
  empty in our current bake:
  - 34 / 30,665 rows have SIZE (BYTES)
  - 24 / 30,665 have CHECKSUM VALUE; 0 have RSUM VALUE
  - 27 routines have any ROUTINE INVOKED entries
  - 21 routines have any INVOKED BY entries
  - 0 routines have any TAG subfile entries
  - The bake sentinel shows `"xindex": "pending"` — XINDEX has
    **not** been run batch-wide with INP(7)=Y against this VEHU.
- **Implications for our artifact set**:
  - **XINDEX would be a strict accuracy upgrade** to Phase 3a
    (globals) and Phase 5 (call graph). XINDEX is a proper parser:
    catches comma-continuation in DO args, indirection (`D @X`),
    line-offset calls (`D TAG+3^ROU`), naked refs (`^(N)`), and
    extended refs (`^|pkg|NAME`) — all MVP limitations of our regex
    scans.
  - **T-003 ("truly unreferenced" 14,658 routines) would almost
    certainly shrink** once File 9.8 subfile 20 (INVOKED BY) is
    populated by an XINDEX run. A fair portion of our residual
    orphan cohort likely has callers XINDEX would find that our
    regex misses.
  - **Phase 4 (VistA metadata) and Phase 5b (protocol parsing) are
    unaffected** — XINDEX doesn't parse File 101 ENTRY ACTION; our
    approach stands for that surface.
  - **Nothing XINDEX produces obviates our existing artifacts** —
    it refines, not replaces. routines-comprehensive.tsv's 20
    columns already go beyond what DOX surfaces; XINDEX would add
    accuracy to in_degree/out_degree/distinct_globals_touched and
    enable a severity-graded error view per routine.
- **Next-step paths documented in xindex-reference.md §11**:
  1. Short path — `make bake-xindex` + extend VMDUMP98.m to emit
     subfile TSVs (invoked, invoked-by, variables, globals). Four
     new TSVs, zero new MUMPS parsing.
  2. Longer path — extract the scratch-global `"E"` subtree during
     a fresh XINDEX run to get per-line error classifications
     across all 39,330 routines. Code-quality heatmap.
- **Not acting on this now** — this is a reference/catalog finding.
  Acting requires the user's decision on whether to invest in an
  XINDEX bake run (~30+ minutes per ADR-018) and associated
  extraction tooling.
- **Evidence**: `docs/xindex-reference.md` (comprehensive catalog),
  Toolkit routine source `/opt/VistA-M/Packages/Toolkit/Routines/
  XIND*.m`, DD introspection of File 9.8 subfiles, bake sentinel.
- **Status**: verified (research output; no data artifacts changed)

### RF-024: Phase 6 closure — protocol invocations, role matrix, reconciliation

- **Date**: 2026-04-19
- **Scope**: Close the biggest Phase 6 gap (protocol ENTRY ACTION
  invocations missing from the call graph, RF-022), refresh the
  per-routine view with that signal, compute the complete role
  intersection matrix, and reconcile every count across phases.
- **Method**:
  - New **Phase 5b** extractor `build_protocol_calls.py` applies
    the Phase 5 call regex to the entry_action + exit_action MUMPS
    text from `protocols.tsv`. Output:
    `vista/export/normalized/protocol-calls.tsv`.
  - `build_routines_comprehensive.py` extended with one new column
    (`protocol_invoked_count`) that joins protocol-calls edges back
    to their callee routines.
  - Role intersection matrix computed from the refreshed
    comprehensive TSV.
- **Phase 5b findings**:
  - **5,081 protocol → routine edges** across **4,631 protocols**
    with at least one call. **1,189 distinct callee routines**
    invoked from File 101 ENTRY or EXIT ACTION.
  - Split: 4,685 from entry actions, 396 from exit actions.
  - Call kinds: do=5,025 (99%), func=53, goto=3. Protocols
    overwhelmingly call out with plain `D TAG^ROUTINE`.
  - Top protocol-invoked routines:
    - VALM1 (112 protocols) — List Manager
    - GMTS (67) — Health Summary
    - FSCLMP (47) — National Online Info Sharing
    - GMRCP (36) — Consult Request Tracking
    - ORCHART (29) — OE/RR chart driver
- **Orphan cohort refinement (closes RF-022's open item)**:
  - Before Phase 5b: 15,010 "truly unreferenced" routines
    (in_degree=0, no RPC, no option).
  - After Phase 5b: **14,658 truly unreferenced** (also no
    protocol invocation). 352 routines moved out of the cohort.
  - The residual 14,658 are still large and likely include:
    indirection (`D @X`), XECUTE of dynamic MUMPS strings,
    FileMan DD callbacks (computed fields, cross-refs, input
    transforms — MUMPS code stored in ^DD), KIDS install-time
    dispatch, comma-continuation misses in Phase 5. Further
    reduction requires either DD-code parsing (^DD traversal) or
    the XECUTE surface — both non-trivial and deferred to T-003.
- **Role intersection matrix** (complete, from
  routines-comprehensive.tsv):

  | Role combination | Count |
  |---|---|
  | RPC only | 1,388 |
  | Option only | 4,602 |
  | Protocol only | 992 |
  | RPC + Option | 49 |
  | RPC + Protocol | 9 |
  | Option + Protocol | 165 |
  | **All three** | **0** |
  | **Backing ≥1 user-facing role** | **7,205** (18.3%) |

  Zero routines back all three surfaces simultaneously — a clean
  architectural observation. Dual-role sets are small but
  concentrated: the 49 RPC+Option set is the primary
  modernization-candidate cohort already identified (RF-022); the
  165 Option+Protocol set is a larger group of routines that
  serve legacy terminal menus AND CPRS context — worth a named
  follow-up.
- **Cross-phase reconciliation — all totals tie**:

  | Measure | Value | First source | Cross-check source |
  |---|---|---|---|
  | Total routines (MANIFEST) | 39,330 | RF-010 | All phase outputs |
  | Distinct files shipped | 2,899 | RF-013 | RF-014 (P+I+K+S+unclass) |
  | PIKS split (P/I/K/S) | 1287/822/393/377 | RF-014 | RF-021 (package manifest) |
  | Routines in File 9.8 | 30,665 | RF-016 | — |
  | MANIFEST ∩ File 9.8 | 29,102 | RF-016 | RF-022 in_file_9_8=Y |
  | RPCs total | 4,501 | RF-017 | — |
  | RPC-backing routines in MANIFEST | 1,446 | RF-017 | RF-021, RF-022 |
  | Options total | 13,163 | RF-018 | — |
  | Option-backing routines (TYPE=R ∩ MANIFEST) | 4,816 | RF-018 | RF-021, RF-022 |
  | Protocols total | 6,556 | RF-019 | — |
  | Routine→global edges | 77,838 | RF-015 | — |
  | Routine→routine edges | 241,309 | RF-020 | RF-021 outbound sum |
  | Protocol→routine edges | 5,081 | **RF-024** | RF-024 |
  | Package-edge matrix rows | 1,872 | RF-023 | — |
  | Intra + inter + unknown-callee-pkg | 112,215 + 105,750 + 23,344 | RF-023 | = 241,309 ✓ |

  Every total propagates correctly across all join artifacts.
- **Evidence**: `vista/export/normalized/protocol-calls.tsv` (5,081
  rows × 7 cols). Refreshed `routines-comprehensive.tsv` now 20
  columns including `protocol_invoked_count`.
- **Outstanding items promoted to TODO**:
  - **T-003** (new): characterize the 14,658 residual
    truly-unreferenced cohort. Hypotheses to test:
    indirection, XECUTE dynamic dispatch, DD-embedded MUMPS,
    KIDS install-time dispatch, comma-continuation.
  - **T-001** (unchanged): +1/+8 Dockerfile build-artifact
    divergence.
  - **T-002** (unchanged): MANIFEST ↔ File 9.8 cohort
    characterization (10,228 ship-only, 1,563 reg-only).
- **Phase 6 is closed.** No further specific gaps identified
  within the ADR-045 scope. All documented outputs reconcile
  cleanly. Residual limitations are all captured in TODO.md as
  separate investigations that don't block the artifact set's
  correctness.
- **Status**: verified (reconciliation confirmed)

### RF-023: Package-to-package edge matrix — VistA's dependency shape

- **Date**: 2026-04-19
- **Scope**: Aggregate routine-calls.tsv up to the package level.
  Sparse matrix: one row per (src_pkg, dst_pkg) pair with edge
  count > 0. Phase 6c of ADR-045.
- **Method**: `host/scripts/build_package_edge_matrix.py` joins
  routine-calls.tsv with routines.tsv (for callee → package
  resolution) and aggregates. Runtime <1s.
- **Finding**:
  - **1,872 non-zero pairs** out of 175 × 175 = 30,625 possible —
    the matrix is ~94% sparse.
  - **172 packages make outbound calls, 144 receive them.** Some
    packages appear only as sources (small code-only add-ons),
    some only as destinations (pure libraries nothing in VEHU
    calls them from).
  - **Edge reconciliation**:
    - Intra-package edges: 112,215 (51.5%)
    - Cross-package edges: 105,750 (48.5%)
    - Edges skipped (callee's package unknown — T-002 cohort):
      23,344 (these are real calls to routines not shipped in
      `Packages/`, so no canonical package to assign)
    - Total: 217,965 + 23,344 = 241,309 — matches RF-020 exactly.
    - The 48.5% figure has the intra/inter denominator; RF-021's
      43.8% had the full denominator including unknowns. Both
      correct, different scopes.
- **Top cross-package edges — all top destinations are FileMan
  or Kernel**:
  - Integrated Billing → VA FileMan: 5,961 edges from 1,782
    distinct caller routines to just 38 FileMan routines
  - Registration → VA FileMan: 5,010
  - IFCAP → VA FileMan: 3,688
  - Scheduling → VA FileMan: 3,076
  - Integrated Billing → Kernel: 2,048
  - Lab Service → VA FileMan: 1,918
- **Fan-in ranking — "VistA's operating system"**:
  - **VA FileMan: 55,477 inbound cross-pkg edges (52.5%)**
  - **Kernel: 24,216 (22.9%)**
  - **FileMan + Kernel together absorb 75.4% of all cross-package
    traffic.** These two packages are effectively the shared
    substrate — every other package depends on them.
  - After those two: Registration (5,588 — everyone needs
    patient data), List Manager (4,324 — UI framework), MailMan
    (2,416), Toolkit (1,561), HL7 (1,249), DRG Grouper (838),
    Scheduling (746), Pharmacy Data Management (735).
- **Fan-out ranking — heavy consumers of the VistA OS**:
  - Integrated Billing (10,591 outbound), Registration (8,329),
    Scheduling (6,160), Order Entry Results Reporting (4,414),
    IFCAP (4,375), Outpatient Pharmacy (4,337), Lab Service
    (3,554), Accounts Receivable (2,990), Lexicon Utility
    (2,375), TIU (2,013). The classic clinical-administrative
    workhorses.
  - **Lexicon Utility is #9 in fan-out despite being a small
    package** (539 routines, 10th by routine count) — confirms
    RF-021's 63.3% cross-package finding. A small but
    fan-out-heavy terminology service.
- **Intra-package coupling (tight internal cohesion)**:
  - Integrated Billing → itself: 8,566 edges
  - Scheduling → itself: 6,699
  - IFCAP → itself: 6,521
  - Registration → itself: 6,172
  - Lab Service → itself: 5,132
  - These big clinical-admin packages are simultaneously
    internally cohesive AND externally broadcast-heavy.
- **Evidence**: `vista/export/normalized/package-edge-matrix.tsv`
  — 1,872 rows × 5 columns (source_package, dest_package,
  call_edges, distinct_caller_routines,
  distinct_callee_routines).
- **Implications — the architectural picture is clear**:
  - **VistA has three structural layers visible from the call
    graph**:
    1. **Foundation layer**: VA FileMan + Kernel. 75% of
       cross-package traffic terminates here. These are the
       substrate; nothing happens without them.
    2. **Shared service layer**: List Manager, MailMan, Toolkit,
       HL7, Lexicon Utility, Registration-as-lookup. Moderate
       fan-in; provide specialized services across domains.
    3. **Domain layer**: Integrated Billing, Scheduling,
       Pharmacy, Lab, etc. High fan-out to the layers below,
       high internal cohesion, moderate cross-domain coupling.
  - **Any decomposition or modernization plan starts with the
    foundation layer.** You cannot extract Billing without
    bringing FileMan + Kernel with it (or replacing them).
  - **The shared service layer (List Manager, MailMan etc.) is
    the likely candidate for the next extraction wave** after the
    foundation — they're moderately fan-in'd but well-defined
    with tight surfaces.
  - The matrix itself is a straightforward input to graph
    analysis tools (Structure101, Gephi, NetworkX) for cluster
    detection, cycle analysis, centrality metrics — all of which
    are natural next steps if the project goes deeper into
    architecture analysis.
- **Status**: verified

### RF-022: Per-routine comprehensive view — 39,330 rows × 19 columns

- **Date**: 2026-04-19
- **Scope**: Every routine in the MANIFEST inventory, one row,
  with every per-routine signal from prior phases joined in.
  Phase 6b of ADR-045.
- **Method**: `host/scripts/build_routines_comprehensive.py` joins
  routines.tsv (base + static features), vista-file-9-8.tsv (Kernel
  knowledge), rpcs.tsv (File 8994), options.tsv TYPE=R (File 19),
  routine-calls.tsv (degrees + volumes), routine-globals.tsv
  (data breadth). 19 columns. Run via
  `make routines-comprehensive`. Runtime: ~1s.
- **Finding — routines by role signal** (from the join):
  - Backs ≥1 RPC: **1,446** (matches RF-017 ∩ MANIFEST)
  - Backs ≥1 TYPE=R option: **4,816** (matches RF-018 ∩ MANIFEST)
  - Backs **both** RPC and option: **49** — dual-surface routines
    serving both CPRS (via RPC Broker) and legacy terminal menus.
    Named set dominated by DSIROIU (Release of Information),
    DSIVIC* (Insurance Capture Buffer), DVBA*/DVBC* (Automated
    Medical Information Exchange — heavy dual-surface legacy),
    IBC*/IBO* (Integrated Billing). These are strong modernization
    candidates — their role duplication signals migration-in-flight
    or legacy coverage.
  - In File 9.8: **29,102** (matches RF-016 intersection)
- **Finding — call graph shape**:
  - **out_degree = 0** (leaves, no outbound calls): **7,041**
    routines. Pure-function utilities and terminal actions.
  - **in_degree = 0** (sinks, no caller in our data): **18,828**
    routines (47.9%). Decomposes further into:
    - 824 back RPCs (legitimately invoked via RPC Broker, not `.m`
      source)
    - 3,020 back TYPE=R options (invoked via menu system)
    - **15,010 truly unreferenced** — no RPC, no option, no `.m`
      caller found by Phase 5. Candidate categories:
      (a) invoked from File 101 protocol ENTRY ACTION (MUMPS text
      Phase 5 doesn't parse), (b) called via indirection, (c)
      missed by comma-continuation or line-offset limitations, or
      (d) genuinely dead.
  - **Truly unreferenced by package** (top): AICS (2,856),
    Integrated Billing (849), Registration (753), AMIE (721),
    Nursing Service (709), "Uncategorized" (476 — worth noting
    as a distinct package in its own right), Scheduling (464),
    IFCAP (409), Kernel (396), Lab (353). AICS's share is
    striking — suggests either substantial dead code or heavy
    reliance on invocation mechanisms outside `.m` source.
- **Finding — library hubs (top in_degree)**:
  All in VA FileMan and Kernel, all with rpc_count=0 and
  option_count=0 — internal libraries, not user-facing:
  - DIC (7,511 callers), DIE (7,509), DIR (7,219), XLFDT (6,643),
    DIQ (6,464), XPDUTL (3,866), DIK (3,325), DICN (2,781),
    VADPT (1,860).
  - **XLFSTR (2,571 callers, 0 outbound calls)** — a pure leaf
    utility. Every caller, no callees. The cleanest node in the
    graph.
- **Finding — dispatch hubs (top out_degree)**:
  - SDEC (65 callees, 14 callers, 124 RPCs) — Scheduling
    orchestrator, already identified in RF-017 and RF-020.
    Cross-validated across three phases.
  - MCARP (50 out, 19 options) — Medicine/Cardiology front-end.
  - SDES (44 out, 20 RPCs, 0 callers) — Scheduling event entry.
  - PSSJXR (42 out, 0 callers, 0 RPCs, 0 options) — interesting
    cases: heavy outbound coupling but no detected caller. Likely
    invoked via protocol ENTRY ACTION.
- **Evidence**: `vista/export/normalized/routines-comprehensive.tsv`
  — 39,330 rows × 19 columns.
- **Implications**:
  - **Direct human-sortable view of the whole routine corpus.**
    "Which routines are RPCs with >5 callers and touch Patient
    data?" becomes a two-line awk.
  - **Library vs dispatch vs leaf vs dual-role** are now
    first-class computed attributes per routine. These are the
    natural clustering axes for decomposition/modernization.
  - The **15,010 truly-unreferenced** cohort is the next
    high-value investigation — partitioning it into "invoked via
    protocol" vs "invoked via indirection" vs "truly dead" needs
    File 101 ENTRY ACTION parsing (deferred Phase 5 refinement).
    Worth a TODO.
  - **The 49 dual-role routines** are a well-defined
    modernization-candidate set worth naming for follow-up.
- **Status**: verified

### RF-021: Package manifest — code↔data bridge in full form

- **Date**: 2026-04-19
- **Scope**: All 175 packages with either routines or shipped data.
  One row per package joining every prior phase into a single
  analytical artifact. Phase 6a of ADR-045.
- **Method**: `host/scripts/build_package_manifest.py` loads seven
  normalized TSVs and emits `package-manifest.tsv`:
  - packages.tsv          → routine_count, total_lines
  - package-piks-summary  → files_shipped + P/I/K/S per-package
  - rpcs.tsv              → rpc_routines (joined via routines.tsv)
  - options.tsv (TYPE=R)  → option_routines
  - routine-globals.tsv   → distinct_globals_touched per package
  - routine-calls.tsv     → outbound_edges, outbound_cross_pkg
  Canonical "package" = filesystem directory name (title case).
  For rpcs/options whose own PACKAGE field is uppercase
  (RF-018 mismatch), we join through the ROUTINE field via
  `routines.tsv` to get the canonical name.
- **Finding**:
  - **175 packages** total (174 with routines + 1 data-only
    participant from package-piks-summary: VA-DOD Sharing).
  - **Cross-validation vs prior RFs** (all match exactly):
    - PIKS totals: P=1,287, I=822, K=393, S=377 (RF-014)
    - RPC-routines total: 1,446 (RF-017)
    - Outbound edges: 241,309 (RF-020)
  - **43.8% of all call edges cross package boundaries** — VistA
    is not package-encapsulated. Large packages regularly call
    into Kernel, FileMan, List Manager, MailMan, and each other.
    This is the dominant architectural characteristic.
- **Architectural observations surfaced by the manifest**:
  - **Lexicon Utility is 63.3% cross-package outbound** — a
    terminology service with heavy outbound coupling to its
    consumers. Highest external-coupling ratio in the top-N.
  - **Integrated Billing (51.1%)** and **Registration (53.4%)**
    are the most broadly interconnected core clinical-admin
    packages.
  - **Scheduling tops RPC exposure** (261 RPCs, 218 options) —
    the largest CPRS surface of any package. Confirmed by SDEC
    being both the top RPC routine (124 RPCs, RF-017) and the top
    call-graph out-degree routine (65 distinct callees, RF-020).
  - **Lab Service has 0 RPCs, 366 options, 45 K-files** — purely
    terminal-menu driven with heavy terminology ownership. Uses
    protocols (1,354 — RF-019) rather than options as its
    primary workflow mechanism.
  - **IFCAP: 4 RPCs, 318 options, 134 I-files** — classic
    back-office. Menu-driven, Institution-scoped data, minimal
    CPRS surface.
  - **Kernel**: 19 RPCs, 143 options, 44 S-files, touches 70
    distinct globals — VistA's plumbing with the expected System
    profile.
  - **Integrated Billing** is 91% P-files but only 16 RPCs —
    billing holds enormous patient data volume but exposes little
    to CPRS directly; external systems consume it via other
    integration paths.
- **Evidence**: `vista/export/normalized/package-manifest.tsv` —
  175 rows × 13 columns.
- **The ADR-045 bridge is now concrete**. A question like "which
  packages would need to travel together in a migration wave?" is
  now a direct query over the manifest joined with the call graph.
  The package-level view is the primary unit of VistA analysis going
  forward.
- **Implications**:
  - Phase 6a answers per-package questions directly (shape, mix,
    roles, coupling). Phase 6b (per-routine comprehensive view)
    and Phase 6c (cross-package edge matrix) are natural
    extensions if the user wants drill-down.
  - Cross-package coupling ratios are the primary candidate metric
    for identifying decomposition/modernization candidates. A
    package with >60% outbound cross-package is an integration
    surface; a package with <30% is self-contained.
  - The 175-row manifest is the right size for human review — a
    page or two. This is the "package card" ADR-045 § 1.3
    described.
- **Status**: verified

### RF-020: Routine → routine call graph — 241,309 edges

- **Date**: 2026-04-19
- **Scope**: All 39,330 routines in the inventory. Static regex scan
  for DO/GOTO/JOB commands and $$ function calls referencing another
  routine. Phase 5 of ADR-045.
- **Method**: `host/scripts/build_routine_calls.py` reads MANIFEST,
  strips strings and comments from each line, matches two patterns:
  - `\b(D|DO|G|GOTO|J|JOB)\b(?::\S+)? +([A-Z%][A-Z0-9]*)?\^(%?[A-Z][A-Z0-9]*)`
  - `\$\$([A-Z%][A-Z0-9]*)?\^(%?[A-Z][A-Z0-9]*)`
  One row per (caller, callee_tag, callee_routine, kind) tuple with
  ref_count. Run via `make routine-calls`. Runtime: ~10s for 39,330
  routines.
- **Finding**:
  - **241,309 edges** across **32,289 callers** (82.1% of routines
    make at least one call). 444,802 total call instances summed
    across ref_counts.
  - **20,974 distinct callees**. **Cross-reference against MANIFEST:
    20,502 (97.7%) are in MANIFEST** — very high validity rate. The
    472 not in MANIFEST are T-002 cohort names (A1A-prefix Albany
    OIFO, %A1*, A7R*, %AAH* percent routines — File 9.8-registered
    but not shipped under `Packages/`).
  - **By call kind**:
    - do   — 155,402 (64.4%)
    - func — 74,986 (31.1%) — $$ extrinsic function calls
    - goto — 10,880 (4.5%)
    - job  — 41 (<0.1%) — background JOB is rare in this corpus
  - **Top callees by in-degree (unique caller count)** are exactly
    the VistA utility-library "bones" — precisely the names that
    Phase 3a's initial (buggy) regex misidentified as globals
    before the lookbehind fix:
    - DIC — 7,511 (FileMan lookup)
    - DIE — 7,509 (FileMan data editor)
    - DIR — 7,219 (terminal reader)
    - XLFDT — 6,643 (date/time library)
    - DIQ — 6,464 (FileMan retrieval)
    - %DTC — 4,143 (date conversion)
    - XPDUTL — 3,866 (KIDS utilities)
    - %ZTLOAD — 3,784 (TaskMan scheduler)
    - %ZIS — 3,647 (device/IO handler)
    - %DT — 3,459 (date input)
    - DIK — 3,325 (FileMan kill)
    - DICN — 2,781 (FileMan add-new)
    - XLFSTR — 2,571 (string library)
    - VADPT — 1,860 (Patient API)
    - VALM1 — 1,586 (List Manager)
    - XMD — 1,538 (MailMan delivery)
  - **Top callers by out-degree (unique callee count)** are
    dispatch/controller routines:
    - SDEC (65) — Scheduling hub. Also topped RPC counts (124
      RPCs in Phase 4b) — the scheduling orchestrator.
    - MCARP (50) — Medicine/Cardiology
    - SDES (44), PSSJXR (42), IBAMTC (40), PSGOEE (39),
      PRCFFMOM (39), PSJOE (37), IBXS11 (37), DGREG (37).
- **Iteration and validation logic**:
  - The 20,974-callee result on first run was surprising (expected
    lower). Cross-ref check against MANIFEST revealed 97.7% hit rate,
    which reframed it as legitimate (VistA really is that
    interconnected). The 472 not-in-MANIFEST callees map cleanly to
    the T-002 File-9.8-only cohort — consistent signal across
    phases.
  - Top-callee list equals the Phase 3a false-positive list from the
    initial regex: DIQ, XLFDT, XPDUTL, XLFSTR, DIE. These are
    routines, not globals — Phase 3a's lookbehind fix was correct.
    Phase 5's data is the validation that those identifications
    were right.
- **Evidence**: `vista/export/normalized/routine-calls.tsv` — 241,309
  rows, 6 columns (caller_name, caller_package, callee_tag,
  callee_routine, kind, ref_count).
- **Known MVP limitations (documented)**:
  - Comma-continuation (`D A^R1,B^R2`) catches only the first call.
  - Line-offset calls (`D TAG+3^ROU`) are skipped.
  - Indirection (`D @X`, `D @^ROU`) is undecidable statically.
  - Strings and comments are stripped before matching.
- **Implications**:
  - Combined with Phase 4 (roles) and Phase 3a (globals), we now
    have the three edge types needed for a complete routine-level
    view: routine→routine (Phase 5), routine→global (Phase 3a),
    and routine→role-tables (Phase 4).
  - Phase 6 (package manifest unification) can now measure
    cross-package call coupling by joining `routine-calls.tsv` with
    `routines.tsv` on caller_package vs callee's package (looked up
    via routines.tsv).
  - Library routines (high in-degree, low out-degree) and dispatch
    routines (high out-degree) are now identifiable quantitatively.
    These are the natural clustering axes for any modernization /
    decomposition plan.
- **Status**: verified (within MVP limits)

### RF-019: VistA File 101 (PROTOCOL) extraction — 6,556 protocols

- **Date**: 2026-04-19
- **Scope**: Every entry in VEHU's File 101 (PROTOCOL) — VistA's
  event/protocol system used by CPRS, Order Entry, HL7, and
  ScreenMan. Phase 4d of ADR-045.
- **Method**: New MUMPS routine `vista/dev-r/VMDUMP101.m` walks
  `^ORD(101,IEN,...)`. Extracts NAME, ITEM TEXT, TYPE, and PACKAGE
  from the 0-node (pieces 1/2/4/12), resolves PACKAGE through
  `^DIC(9.4)`, and reads ENTRY ACTION + EXIT ACTION from sub-nodes
  20 and 15 (MUMPS-code strings, 245 char max). Same `/tmp` +
  `docker cp` pattern. Run via `make dump-file-101`.
- **Finding**:
  - **6,556 protocols** total (max IEN 7,053 — 497 gaps from
    deletions).
  - **TYPE distribution** — File 101's type codes differ from
    File 19's:
    - A (action) — **3,409** (52%)
    - L (limited protocol) — **1,208**
    - M (menu) — **800** (CPRS right-click menus, OE/RR context)
    - S (subscriber) — **363** — HL7 event subscribers
    - E (event driver) — **321** — HL7/OE/RR event sources
    - O (protocol) — 252
    - X (extended action) — 145
    - Q (protocol menu) — 48
    - D (dialog) — 6, empty — 4
  - **684 event-driven pairs** (321 drivers + 363 subscribers)
    constitute VistA's event integration fabric — this is how HL7
    messages, order events, and consult notifications propagate.
  - **4,976 protocols have ENTRY ACTION** populated (76%) — the
    MUMPS code that runs when the protocol fires. **4,861 have a
    PACKAGE** (74%).
  - **Top packages by protocol count**: LAB SERVICE (**1,354** —
    every lab test is configured as a protocol), INTEGRATED BILLING
    (787), TIU (261), REGISTRATION (230), SCHEDULING (197),
    OUTPATIENT PHARMACY (194), CLINICAL REMINDERS (184), AR (176),
    CONSULT/REQUEST TRACKING (148), AICS (144).
- **Evidence**: `vista/export/normalized/protocols.tsv` — 6,556
  rows, 7 columns (ien, name, item_text, type, package,
  entry_action, exit_action).
- **Implications**:
  - Third authoritative role signal, and the one with the richest
    semantics because File 101's TYPE codes distinguish event
    drivers from subscribers — letting us map the pub/sub fabric
    directly.
  - Unlike File 19, File 101 has NO dedicated ROUTINE field —
    routines are invoked via MUMPS code embedded in ENTRY ACTION.
    Extracting those routine references (e.g., parsing `D EN^LRXO0`
    out of ENTRY ACTION text) is deferred to Phase 5 (call graph)
    where it belongs with the general MUMPS-code-parsing work.
  - Quick exploratory scan (not stored) suggests ~1,155 distinct
    routines are invoked from protocol ENTRY ACTIONs, with LRXO0
    (Lab protocol handler) alone referenced in ~1,195 protocols —
    a single routine driving the bulk of Lab's protocol-defined
    workflows. Concrete figure to be produced in Phase 5.
  - LAB SERVICE protocol count (1,354) is 2.2× larger than File 19
    option count for Lab (627). Labs are far more
    protocol-configured than menu-configured — a meaningful
    architectural observation about how that domain is built.
- **Status**: verified

### RF-018: VistA File 19 (OPTION) extraction — 13,163 menu options

- **Date**: 2026-04-19
- **Scope**: Every entry in VEHU's File 19 (OPTION) — VistA's menu
  system, including menus, actions, broker endpoints, server
  listeners, print templates, etc. Phase 4c of ADR-045.
- **Method**: New MUMPS routine `vista/dev-r/VMDUMP19.m` walks
  `^DIC(19,IEN,...)`. Extracts NAME, MENU TEXT, TYPE, and PACKAGE
  from the 0-node (pieces 1/2/4/12), resolves the PACKAGE IEN through
  `^DIC(9.4,ien,0)` to a name, and reads the ROUTINE spec from the
  `25` sub-node (a string that may be `TAG^ROUTINE` or `ROUTINE`).
  Splits the routine spec on `^` into `tag` + `routine` columns.
  Same `/tmp` + `docker cp` pattern. Run via `make dump-file-19`.
- **Finding**:
  - **13,163 options** total (max IEN 17,050 — 3,887 gaps from
    deletions). 8,296 have a routine set (25-subnode populated).
  - **TYPE distribution** — the primary role signal this extraction
    gives us:
    - R (run routine) — **8,184** (62%) — the dominant type;
      options that directly invoke a routine
    - M (menu) — **2,111** — container options grouping children
    - A (action) — **1,780** — inline MUMPS action
    - P (print) — 480 — print-template options
    - E (edit) — 268
    - B (broker/client-server) — **138** — Broker entry-point
      options for setting up RPC contexts
    - S (server) — 96 — incoming server/mail messages
    - I (inquire) — 72, C (ScreenMan) — 12, X (extended) — 6,
      O (protocol) — 5, Q (protocol menu) — 2, empty — 9
  - **Routine cross-reference**: 5,105 distinct routines referenced
    across all options; **4,910 (96.2%) are in MANIFEST**. Same
    pattern as File 8994 — 195 in File 9.8-only cohort (T-002).
  - **Package coverage**: 7,032 of 13,163 options (53.4%) have a
    PACKAGE (File 9.4) pointer. The other 6,131 are core Kernel or
    site-local options.
  - **Top packages by option count**: LAB SERVICE (627),
    REGISTRATION (360), INTEGRATED BILLING (345), CLINICAL
    REMINDERS (305), OE/RR (292), SCHEDULING (261), OUTPATIENT
    PHARMACY (242), IFCAP (231), TEXT INTEGRATION UTILITIES (230),
    KERNEL (228). Expected shape — these are the core VistA
    domains with the most user-facing functionality.
- **Evidence**: `vista/export/normalized/options.tsv` — 13,163 rows,
  8 columns (ien, name, menu_text, type, package, routine_raw, tag,
  routine).
- **Join-issue noted for Phase 6**: File 19's PACKAGE field
  resolves to **uppercase** names (`LAB SERVICE`, `OUTPATIENT
  PHARMACY`), while `packages.tsv` uses **title case** from the
  filesystem (`Lab Service`, `Outpatient Pharmacy`). Phase 6 will
  need either case-insensitive joining or a name-normalization step.
  Worth documenting separately once more join sources are in hand.
- **Implications**:
  - Second authoritative role signal. A routine listed in
    `options.tsv.routine` with TYPE=R is a **menu-invokable entry
    point** — distinct from (but may overlap with) an RPC entry
    point.
  - Comparison to be done in Phase 6: how many routines serve both
    as RPC and as option entry point? And how many are neither
    (pure utility/library/task)?
  - TYPE=B (138 Broker options) are specifically CPRS RPC context
    entry points — they configure the broker environment before
    RPCs fire. Worth examining the 138 names against CPRS context
    conventions.
  - 6,131 options without a PACKAGE assignment is a data-quality
    observation but not surprising — core Kernel options predate
    the File 9.4 registry model.
- **Status**: verified

### RF-017: VistA File 8994 (REMOTE PROCEDURE) extraction — 4,501 RPCs

- **Date**: 2026-04-19
- **Scope**: Every entry in VEHU's File 8994 (REMOTE PROCEDURE) — the
  RPC Broker's authoritative registry of callable procedures.
  Phase 4b of ADR-045.
- **Method**: New MUMPS routine `vista/dev-r/VMDUMP8994.m` walks
  `^XWB(8994,IEN,0)` via `$ORDER`. Extracts .01 NAME, .02 TAG,
  .03 ROUTINE, .04 RETURN VALUE TYPE, .05 AVAILABILITY,
  .06 INACTIVE, .09 VERSION — all in the 0-node, pieces 1-9.
  Same `/tmp` + `docker cp` pattern as Phase 4a. Run via
  `make dump-file-8994`.
- **Finding**:
  - **4,501 RPCs registered** (max IEN 4,689 — 188 gaps from
    deletions). 4,467 active, 34 inactive.
  - **1,526 distinct routines** back those 4,501 RPCs (average ~3
    RPCs per routine; biggest hubs are SDEC with 124 RPCs, ORWTPP
    with 46, OREVNTX1 with 39 — typical VistA dispatch-routine
    pattern where one routine exposes many tag entry points).
  - **Cross-reference against MANIFEST**: 1,446 of 1,526
    (**94.8%**) of RPC-referenced routines are in MANIFEST. The
    80 (5.2%) not in MANIFEST include DENTVRF (Dental), DSIFBAT*
    (Document Storage Systems — third-party commercial), which
    appear in File 9.8 but not the shipped `Packages/*/Routines/`
    tree (T-002 cohort).
  - **Top packages by RPC exposure** (joined via MANIFEST):
    Scheduling (261 distinct RPC-routines), Imaging (209),
    Order Entry Results Reporting (185 — CPRS), Vendor - Document
    Storage Systems (62), Automated Medical Information Exchange
    (57), Mental Health (43), Prosthetics (38), VA Certified
    Components - DSSI (31), Clinical Case Registries (31), Dental
    (30). All expected — these are the CPRS/client-facing packages.
  - **Availability distribution**: Public=395, Subscription=606,
    Agreement=456, Restricted=1,608, empty/other=1,436. Empty
    availability is most common on older RPCs that predate the
    classification.
  - **5 RPCs have no ROUTINE value** — presumably malformed or
    in-progress entries. Ignorable minority.
- **Evidence**: `vista/export/normalized/rpcs.tsv` — 4,501 rows, 8
  columns.
- **Implications**:
  - **Authoritative role signal**: a routine in `rpcs.tsv`.`routine`
    IS definitively an RPC entry point. This is the authoritative
    data that Phase 2b would have guessed at badly from source
    alone. ADR-045's decision to defer role classification until
    Phase 4 is vindicated.
  - The 1,526 RPC-backing routines are the CPRS/client-facing API
    surface of VistA. Cross-referencing against PIKS of data
    touched (Phase 3 + package-piks-summary) will give the true
    "what data does the RPC surface expose" picture — a key
    security/exchange consideration.
  - Big-dispatch-routines (SDEC 124, ORWTPP 46) are hotspots —
    many entry points in one file. Natural candidates for
    decomposition/refactoring in any modernization plan.
- **Status**: verified

### RF-016: VistA File 9.8 (ROUTINE) extraction — 30,665 entries, compared to MANIFEST

- **Date**: 2026-04-19
- **Scope**: Every entry in VEHU's File 9.8 (ROUTINE) — VistA's own
  self-inventory of routines. Phase 4a of ADR-045.
- **Method**: New MUMPS routine `vista/dev-r/VMDUMP98.m` walks
  `^DIC(9.8,IEN,0)` via `$ORDER`, extracts `.01 NAME`, `1 TYPE`,
  `1.2 SIZE (BYTES)`, `1.5 RSUM VALUE`, plus `7.2 CHECKSUM VALUE` from
  sub-node 4. Output piped to `/tmp/vista-file-9-8.tsv` inside the
  container (vehu cannot write to the ubuntu-owned export bind mount),
  then `docker cp`-ed out to `vista/export/normalized/`. Run via
  `make dump-file-9-8`.
- **Finding**:
  - **File 9.8 contains 30,665 entries**: 30,255 typed as R (routine),
    0 as P (package — DD allows it but VEHU has none), 410 with an
    empty TYPE field.
  - **Cross-reference against MANIFEST.tsv (39,330 shipped routines)**:
    - Intersection: **29,102** — known to both, core routines
    - **MANIFEST-only: 10,228** — shipped as .m files under
      `Packages/*/Routines/` but NOT registered in File 9.8
    - **File 9.8-only: 1,563** — registered in Kernel's ROUTINE file
      but not found as shipped `.m` source
  - **File 9.8-only prefix distribution** shows the "registered but
    not shipped" cohort is dominated by specific package namespaces:
    PSN (304 — Pharmacy National), MAG (149 — Imaging), PRA (126),
    LBR (75), ABS (74 — IHS namespace), DSI (59), QAC (58), ONC (57),
    QAN (53), SOW (52). These suggest routines installed directly
    into the routine namespace by some path outside the FOIA
    `Packages/` tree.
  - **Optional fields are essentially empty in VEHU**: 34/30,665
    rows have SIZE (BYTES), 24 have CHECKSUM VALUE, 0 have RSUM
    VALUE. These fields are populated by KIDS during patch install
    cycles and VEHU is a fresh-build snapshot — expected.
- **Evidence**: `vista/export/normalized/vista-file-9-8.tsv` (30,665
  rows, 6 columns).
- **Interpretation — MANIFEST and File 9.8 measure different things**:
  MANIFEST answers "what .m files ship in the FOIA distribution?"
  File 9.8 answers "what routines does VistA's Kernel know about at
  runtime?" Neither is wrong; the 10,228/1,563 diffs are legitimate.
  This finding does NOT resolve T-001 (which is about the +1 symlink
  / +8 compiled `.o` in the Dockerfile build artifacts — a different
  dimension entirely). T-001 remains open.
- **Implications**:
  - The intersection (29,102 routines known to both) is the "solid
    core" for any analysis that needs VistA to acknowledge the
    routine exists.
  - The 10,228 MANIFEST-only cohort is a well-defined set worth
    investigating — likely includes routines shipped but never
    registered, test/sample code, or dev-only utilities.
  - The 1,563 File 9.8-only cohort suggests additional routine
    sources beyond `Packages/*/Routines/`. Candidate sources:
    `$ydb_dist` system routines, directly-loaded routine globals,
    patch routines from alternative install paths. Worth a separate
    TODO.
  - Authoritative role classification (deferred in Phase 2b) now has
    its baseline dataset ready. Phase 4b (File 8994 RPCs) and 4c
    (File 19 options) will layer on top.
- **Status**: verified

### RF-015: Routine → global edges — 77,838 subscripted references

- **Date**: 2026-04-19
- **Scope**: All 39,330 routines in the inventory. Static regex scan
  for subscripted global references (`^IDENT(`). Phase 3a of ADR-045.
- **Method**: `host/scripts/build_routine_globals.py` reads MANIFEST.tsv,
  strips strings (`"..."` with `""` escape) and `;`-comments from each
  line, then regex-matches `(?<![A-Z0-9$])\^(%?[A-Z][A-Z0-9]*)\(`. The
  lookbehind excludes routine-call patterns like `$$TAG^ROU(args)` and
  `$$^ROU(args)` — the `^` there is preceded by an alpha tag or `$`.
  Run via `make routine-globals`. Runtime: ~8s for 39,330 routines.
- **Finding**:
  - **77,838 edges** across 30,205 routines (76.8% of routines reference
    at least one subscripted global). 490,094 total references counted.
  - **618 distinct globals** referenced — on the low end of expected
    VistA global count (~300-500 unique across a full system), but
    consistent with a wider surface that includes many subset globals.
  - **Top globals by routine-count** match well-known VistA structure:
    - `^TMP` (12,002 routines — scratch)
    - `^DD` (4,820 — FileMan data dictionary)
    - `^DIC` (4,434 — FileMan file header / lookup)
    - `^DPT` (3,643 — PATIENT file)
    - `^VA` (2,840 — VA-specific global)
    - `^UTILITY` (2,314 — FileMan scratch)
    - `^%ZOSF` (2,012 — OS-specific system functions)
    - `^XTMP` (1,843 — 90-day temp scratch)
    - package-namespace clinical globals: `^PS` (Pharmacy, 1,562),
      `^SC` (Scheduling, 1,426), `^IBE` (Billing, 1,317),
      `^LAB` (1,149), `^PRC` (IFCAP, 1,134), `^ORD` (Order Entry,
      1,059), `^DG` (Registration, 1,040), `^XMB` (MailMan, 889)
- **Iteration during validation**: initial naive regex `\^IDENT\(`
  produced **10,316 "globals"** across **164,736 edges** — false
  positives from `$$TAG^ROU(args)` patterns where routines were
  misidentified as globals (DIQ, XLFDT, XPDUTL, XLFSTR all ranked
  top-10). The negative lookbehind for alphanumeric-or-`$` cut the
  edge count in half and brought the distinct-global count down to
  realistic scale before commit.
- **Known limitations (MVP, documented):**
  - Bare globals without subscripts (`K ^FOO`, `S X=^FOO`) are not
    captured.
  - `D ^ROU(args)` / `J ^ROU(args)` DO/JOB with args are still
    counted as globals (lookbehind only catches single-char context,
    not the preceding command). The residual 207 "DIE" references
    are believed to be mostly of this form; DIE is primarily a
    FileMan routine, not a global.
  - Indirection (`^@X`, naked `^(subscripts)`) is undecidable statically
    and skipped entirely.
  - Extended references (`^|pkg|NAME`, `^$JOB`) are skipped.
- **Evidence**: `vista/export/normalized/routine-globals.tsv` — 77,838
  rows, 4 columns (routine_name, package, global_name, ref_count).
- **Implications**:
  - Foundation for Phase 6 — joining routine-globals.tsv against
    package-data.tsv on `global_name` answers "which routines touch
    which package's data?" Cross-package edges (routine in pkg A
    touches global owned by pkg B) are the cross-boundary coupling
    we want to measure.
  - 618 distinct globals is tractable for human review. Candidates
    for clustering: per-namespace prefix (DG*, PS*), per-package,
    per-PIKS-of-owning-file.
  - Joining on file_number (via global_root → file_number mapping
    from files.tsv) will give routine→FileMan-file edges, and thus
    routine→PIKS edges — the final piece for per-routine PIKS mix.
- **Status**: verified (within documented MVP limits)

### RF-014: Per-package PIKS distribution — code↔data bridge realized

- **Date**: 2026-04-19
- **Scope**: 2,899 distinct FileMan file numbers shipped by 120
  packages (from `package-data.tsv`, kind=file rows), joined on
  `file_number` against `piks.tsv` + `piks-triage.tsv` (manual triage
  overrides automated). Phase 2d of ADR-045.
- **Method**: `host/scripts/build_package_piks_summary.py`. Deduplicates
  sharded chunks by collapsing to distinct file_numbers per package,
  then buckets by PIKS letter. Run via `make package-piks`.
- **Finding**:
  - **Distribution across 2,899 shipped files**:
    P=1,287 (44.4%), I=822 (28.4%), K=393 (13.6%), S=377 (13.0%),
    unclassified=20 (0.7%).
  - P is **over-represented among shipped files** vs the whole-corpus
    distribution (P=37.2% of all 8,261 files, RF-006). Clinical
    packages ship their own files; I-files are concentrated in a
    few large structural anchors (File 200, 44, etc.) that aren't
    shipped by many packages.
  - **Top shippers line up with known VistA domains** — the
    mechanical join produces domain profiles without any
    interpretation:
    - **P-dominant**: Integrated Billing (203 P / 224 total = 91%),
      Imaging (79%), Mental Health (79%), Scheduling (68%),
      Registration (45%, mixed with I and S for enrollment plumbing).
    - **K-dominant**: Oncology (94%), Lexicon Utility (97%),
      DRG Grouper (96%), Lab Service (57%), OE/RR (56%).
    - **I-dominant**: IFCAP (98%, Fund Control Point / procurement),
      PAID (100%, payroll), Engineering (82%), Imaging I-slice (21%).
    - **S-dominant**: Kernel (57%), Health Level Seven (85%),
      VA FileMan (56%), Toolkit (80%).
  - **5 packages ship data but not FileMan files** — they ship only
    non-FileMan globals (125 with Globals/ per RF-013 minus 120 with
    kind=file rows here). Examples from package-data.tsv include
    VA-DOD Sharing, which ships one file plus globals only, and
    Altoona VA, which is globals-only.
- **Evidence**: `vista/export/normalized/package-piks-summary.tsv`
  (120 rows, 7 columns). Sum of P+I+K+S+unclassified across all
  rows = 2,899, matches distinct FileMan files shipped from RF-013.
- **Implications**:
  - The **code↔data bridge at the package level (ADR-045 Phase 4) is
    partially delivered** — via filename extraction + a simple join,
    no routine-side MUMPS parsing required. We now know each
    package's PIKS profile for the data it owns.
  - Packages' PIKS profile can drive management decisions: which
    teams own which packages, which packages need HIPAA/PHI
    controls (P-heavy), which are candidates for centralization
    (K-heavy — terminology is inherently shared), which are
    site-specific (I-heavy).
  - The 5 globals-only shippers are a well-defined cohort — they
    carry operational or site-specific state without a corresponding
    FileMan DD. Worth investigating in Phase 3 when we know which
    routines touch those globals.
- **Status**: verified

### RF-013: Package-shipped data inventory — 3,138 ZWR exports

- **Date**: 2026-04-19
- **Scope**: All `Globals/*.zwr` files across the 125 packages with
  `Globals/` subdirectories in the VEHU image.
- **Method**: `host/scripts/build_package_data_inventory.py` walks
  `vista/vista-m-host/Packages/*/Globals/*.zwr` and classifies each
  filename by one of three strict patterns. No ZWR parsing — filename
  and byte size only. Run via `make package-data`.
- **Finding**: VistA FOIA ZWR filenames follow three shapes, all
  mechanically recognizable:
  - **`<file_number>+<name>.zwr`** — whole FileMan file export
    (2,878 rows). Example: `340+AR DEBTOR.zwr` → FileMan file 340.
  - **`<file_number>-<chunk>+<name>.zwr`** — sharded FileMan file
    (98 chunk rows across 21 distinct files). Big reference tables
    are split across multiple ~67 MB ZWRs. Examples: ICD DIAGNOSIS
    (file 80) in 5 chunks; EXPRESSIONS (Lexicon, file 757.01) in
    20 chunks; DRUG INTERACTION (file 56) in 11 chunks; RXNORM
    RELATED CONCEPTS (file 129.22) in 6 chunks.
  - **`<name>.zwr`** — non-FileMan global export
    (162 rows). Filename IS the global name. Examples: `PRCA.zwr`
    (^PRCA), `RC.zwr` (^RC), `PXRMINDX.zwr` (^PXRMINDX — Clinical
    Reminders index global).
  - **Totals**: 3,138 ZWR files, 2,899 distinct FileMan file numbers
    shipped with data, 125 packages shipping data, ~7.3 GB of ZWR
    content on disk.
  - **Anomaly**: `0-1+ICDLD82.zwr` and `0-2+ICDLD82.zwr` ship under
    DRG Grouper with `file_number=0`. FileMan doesn't have a "file 0"
    in the normal sense — this is a legacy bulk-load convention for
    `^ICDLD82` (a direct global load, not a DD-described file).
    Mechanical extraction captures it as-is.
- **Evidence**: `vista/export/normalized/package-data.tsv` (3,138
  rows, 7 columns). Reconciles exactly with `find` count of
  `Globals/*.zwr`.
- **Implications**:
  - Delivers the **code↔data join at the package level** described in
    ADR-045 Phase 4 — via filename extraction only, no ZWR parsing or
    globals-touched scan required. Each row links a package to a
    FileMan file number or a non-FileMan global.
  - `routines.tsv` + `package-data.tsv` together form a complete
    package manifest. Joining on `package` answers "what code and
    what data does this package ship?" directly.
  - Joining `package-data.tsv` on `file_number` against `files.tsv`
    (from PIKS work) will give each package a PIKS distribution of
    the data it owns. Candidate for a future RF once we do the join.
  - The 162 non-FileMan global exports correspond to the non-FM
    globals RF-002 identified (67 unique in the database). The 162
    here is package-ships-of-globals, not unique global count —
    some globals are shipped by multiple packages, and some packages
    ship multiple globals. Reconciling the two counts is a candidate
    follow-up.
- **Status**: verified

### RF-012: VistA package distribution shape — code+data bundles

- **Date**: 2026-04-19
- **Scope**: All 176 package directories under
  `/opt/VistA-M/Packages/` in the VEHU image.
- **Method**: `find -mindepth 2 -maxdepth 2 -type d` to enumerate the
  subdirectories each package ships, then cross-classify by presence
  of `Routines/` and `Globals/`.
- **Finding**: VistA's FOIA distribution ships each package as a
  code-plus-data bundle. Across the 176 package directories:
  - **123 ship both Routines/ and Globals/** — the normal shape.
    Code (MUMPS `.m`) plus ZWR exports of the FileMan files the
    package owns. Example: Clinical Procedures ships MD-namespace
    routines under `Routines/` and ZWR exports like
    `702+CP TRANSACTION.zwr`, `702.01+CP DEFINITION.zwr` under
    `Globals/`, which KIDS replays at install time to create the
    DD and load seed records for File 702, 702.01, etc.
  - **51 ship Routines only** — code-only packages that operate on
    data owned by other packages (utilities, add-ons).
  - **2 ship Globals only** — "Altoona VA" and "VA-DOD Sharing"
    (previously noted in RF-010). DD/seed data with no routines.
  - Only two subdirectory types exist across the entire distribution:
    `Routines/` and `Globals/`. No `Docs/`, `Init/`, or other
    top-level subdirs in this VEHU.
- **Evidence**: `find` enumeration over `vista/vista-m-host/Packages/`
  reproducibly yields the 123/51/2 split.
- **Implications**:
  - Directly validates the ADR-045 choice of package as the unifying
    bridge between data and code. The package is already the native
    code+data shipping unit in VistA's own conventions — we aren't
    imposing a synthetic grouping on top.
  - The "files-per-package" inventory is the natural counterpart to
    the "routines-per-package" inventory in RF-010. Cataloging the
    `Globals/*.zwr` filenames (which encode FileMan file numbers)
    would give the code↔data join at the package level described in
    ADR-045's Phase 4, without needing to parse routine globals-
    touched (Phase 3).
  - 51 code-only packages will have interesting cross-package global
    access patterns when Phase 3 lands — they necessarily read/write
    data owned by other packages.
- **Status**: verified

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
