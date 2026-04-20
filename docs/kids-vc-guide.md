# KIDS Version-Control Methodology Guide

Investigation of the two known historical attempts to bring VistA's KIDS
(Kernel Installation and Distribution System) build process under native
version control: **SKIDS** (WorldVistA, 2011–2013) and **XPDK2VC**
(Sam Habiel / OSEHRA, 2014–2020). Documents what each tool does, where
each falls short, and concrete remediations for a successor.

Written 2026-04-19 as follow-up to RF-028. Based on source-level review
of both codebases — SKIDS cloned from github.com/WorldVistA/SKIDS and
XPDK2VC inspected in the VEHU corpus at
`vista/vista-m-host/Packages/Kernel/Routines/XPDK2V*.m`.

Companion to [code-model-guide.md §3.1](code-model-guide.md#31-develop) which frames the
broader VistA-on-git landscape.

---

## 1. Why this matters

KIDS is VistA's package manager + release pipeline. A `.KID` file bundles
routines, FileMan DD changes, seed data, options, protocols, RPCs,
pre/post-install routines, environment checks, and install prompts.
KIDS install is additive: once applied, patches are forward-only — there
is no uninstall beyond restoring from backup (see [code-model-guide.md §3.4](code-model-guide.md#34-uninstall)).

The fundamental mismatch with git: **KIDS bundles are the shipping unit
and the change unit simultaneously**. A patch might touch 40 routines,
3 FileMan files, and 12 options as one indivisible unit. Git wants
fine-grained commits that can be diffed, branched, reverted, and
bisected. Bridging the two requires either:

- **Parsing `.KID` files into per-component source tree** (so git can
  diff individual routines/options/etc.), and
- **Re-assembling per-component source back into `.KID` files** (for
  install and deployment), while keeping the round-trip lossless.

That's the architectural problem both SKIDS and XPDK2VC attempted.

---

## 2. SKIDS (Source KIDS) — WorldVistA, 2011–2013

### 2.1 What it is

Repository: [github.com/WorldVistA/SKIDS](https://github.com/WorldVistA/SKIDS).
Apache 2.0 licensed. 16 commits on master. Silently abandoned after
September 2013. Three disjoint spikes by three contributors, never
integrated into a coherent pipeline.

### 2.2 The three pieces

**(A) `ParseKIDS.py`** — Christopher Edwards (KRM), 2012-02 to 2012-05.
- 115 lines of Python 2 (uses `f.next()`, `xrange`).
- Two functions: `unpack(kid, routineDir)` and `checksum(routine)`.
- `unpack` walks the `.KID` text line-by-line looking for the `"RTN"`
  section. Handles three RTN line shapes: count header, per-routine
  header `"RTN","NAME")`, and per-line records `"RTN","NAME",N,0)`.
- **Output**: flat directory of `<NAME>.m` files.
- **Everything else in the KIDS format is ignored**: `BLD`, `KRN`,
  `FIA`/DD, `RPC`, `OPT`, `PRO`, `SEC`, `MBREQ`, `INIT`, `PRE`, `POST`,
  `ENV`, `QUES`, transport global — none handled.
- `main()` is commented out except for a checksum call; `unpack()` is
  dead code as shipped.
- `checksum()` is a Python port of `$$EN^XPDRSUM` routine checksum.

**(B) `ZDIOUT1.m`** — Brad King (Kitware), 2011-10 to 2011-11.
- 172 lines of MUMPS.
- Reads directly from **live `^DIC`/`^DD`** — NOT from KIDS transport
  globals. So it's not a KIDS tool at all.
- Emits a custom tab-separated text format with `ENTITY`/`KA`/`F<num>`/
  `SUBS` tags. Not ZWR, not `.KID`, not JSON — a bespoke serialization.
- Entry points: `SAVEFILE(FILE,DIR)`, `PRNFILE(FILE,IO)`,
  `PRNENTRY(FILE,I,IO)`, `PRNDD(FILE,IO)`.
- No reader for the custom format exists anywhere in the repo — not
  round-trippable.
- Contains explicit TODOs: sort entries, handle non-entry subscripts
  like `"B"` cross-refs, preserve word-processing timestamps, escape
  values containing `" $ ;`, handle indentation.

**(C) `KIDSAssembler/` (Java, unmerged branch)** — Jason Li (Kitware),
2013-09.
- 48 Java files imported verbatim from VA Imaging team's
  `KidsAssembler` (Maven, JAXB, commons-cli, log4j).
- Covers a much wider surface than ParseKIDS:
  `Bulletin`, `DataDictionary`, `Dialog`, `Form`, `HelpFrame`,
  `Hl7Application`, `Hl7LogicalLink`, `InputTemplate`, `MailGroup`,
  `MenuOption`, `ParameterDefinition`, `ParameterTemplate`,
  `PrintTemplate`, `Protocol`, `RemoteProcedureCall`, `SecurityKey`,
  `SortTemplate`, etc.
- XML-manifest-driven (reads a manifest + per-component files, builds
  a `.KID`).
- **The opposite direction** from ParseKIDS: filesystem → KIDS.
- Marked "Class II medical device, do not modify" in its header — VA
  IP that SKIDS adopted rather than authored.
- **Never merged to master.** Never integrated with ParseKIDS or
  ZDIOUT1. No wire-up between the XML manifest format and the routine
  files ParseKIDS produces.

### 2.3 What SKIDS does NOT handle

- **~95% of the KIDS format** via ParseKIDS (routines only)
- **Round-trip**: filesystem → KIDS was attempted in the unmerged Java
  branch but never wired up
- **Diff-stability**: no build-number stripping, no IEN substitution,
  no entry sorting, no value escaping — every re-export produces
  gratuitous diffs
- **ZWR global data seeds** (never emits ZWR)
- **Merge strategy** for parallel edits to the same file
- **Patch-list-append diff noise** (the central problem KIDS install
  creates for git) — never addressed
- **FileMan-embedded MUMPS** (cross-refs, input transforms, computed
  fields) — ZDIOUT1 dumps the MUMPS-typed field as an opaque string
  with no parsing

### 2.4 Why SKIDS was abandoned

No commit ever states "abandoned" or "deprecated" — the end was silent.
Reading the commit history and structure:

- Three contributors never collaborated. Commit author streams are
  disjoint (Kitware 2011, KRM 2012, Kitware again 2013) with no
  cross-references or integration commits.
- Each spike solved a different slice of the problem in a different
  language for a different runtime. No one stitched them together.
- The Java branch was a code-dump of external work (VA Imaging's
  KidsAssembler) not written for SKIDS integration.
- OSEHRA's 2011 "VistA version control" effort shifted focus: by late
  2013, [github.com/WorldVistA/VistA-M](https://github.com/WorldVistA/VistA-M)
  had emerged as a simpler answer — just store `.m` files in git and
  keep KIDS for deployment, sidestepping the per-component
  decomposition problem entirely.

The unstated lesson: **decomposition-then-reassembly was over-engineered
for the need**. The community adopted "put the existing source tree in
git, no transformation" and it was enough.

### 2.5 What SKIDS got right (despite abandonment)

- **The architectural instinct was correct**: KIDS bundles need to be
  decomposed for git diffs to be meaningful.
- **Apache 2.0 license** — usable for reference or fork.
- **The Java `KIDSAssembler`** concept (XML manifest + per-component
  files → `.KID`) is structurally the right approach for the reverse
  direction, even though SKIDS didn't wire it up.
- **Multi-language** (Python + MUMPS + Java) is defensible: each layer
  suits its runtime, provided they integrate.

---

## 3. XPDK2VC — Sam Habiel / OSEHRA, 2014–2020

### 3.1 What it is

Four MUMPS routines (~870 total lines) shipped as KERNEL patch
8.0\*11310 in March 2014, last-modified through April 2020. Apache 2.0.
Author: Sam Habiel ("VEN/SMH" → "OSE/SMH"), [github.com/shabiel](https://github.com/shabiel).

Present in our VEHU at `/opt/VistA-M/Packages/Kernel/Routines/XPDK2V*.m`,
indexed in [code-model/routines.tsv](../vista/export/code-model/routines.tsv) at line 37028.

### 3.2 Architecture

Four routines, each with a distinct responsibility:

| Routine | Lines | Purpose |
|---|---|---|
| `XPDK2VC.m` | 406 | Main entry + dispatcher. Component-by-component export. Public entry points. |
| `XPDK2V0.m` | 245 | Routine exporter, FileMan file exporter, DATA exporter, custom ZWRITE with IEN substitution, reverse LOAD path. |
| `XPDK2V1.m` | 157 | KIDS text-format state-machine parser. Handles FORUM-mail, straight-KIDS, multi-build, and `$KID`-wrapped variants. |
| `XPDK2VG.m` | 65 | Global-type build exporter (when KIDS ships whole globals, not just FileMan seed data). |

### 3.3 Flow

**Forward (KIDS → filesystem)**:

1. User invokes `D EXPKIDIN^XPDK2VC` (interactive) or
   `D F^XPDK2VC(path)` (non-interactive), or
   `D EXPKID96^XPDK2VC(.XPDFAIL,BUILD_IEN)` (by File 9.6 Build IEN).
2. If given a `.KID` text file, `ANALYZE^XPDK2V1` parses it with a
   5-state machine (`BEGIN` → `KIDSSS` → `INSTLNM` → `ZERO` →
   `CONTENT`) into `^XTMP("K2VC","EXPORT",...)`.
3. If given a Build IEN, KIDS's own `D PCK^XPDT` builds the transport
   global directly — no text parsing needed.
4. `EXPORT^XPDK2VC` dispatches to per-component handlers. Directory
   layout: `<root>/<PATCH_DESCRIPTOR>/KIDComponents/`.

**Per-component output files**:

| KIDS section | Output file | Handler |
|---|---|---|
| `BLD` (build metadata) | `Build.zwr` | GENOUT |
| `GLO` (if global-type build) | `Globals/<global>.zwr` | XPDK2VG |
| `FIA` + `^DD` + `^DIC` + `SEC` + `UP` + `IX` + `KEY` + `KEYPTR` + `PGL` | `Files/<num>+<name>.DD.zwr` | XPDK2V0 FIA |
| `DATA` + `FRV1*` | `Files/<num>+<name>.Data.zwr` | XPDK2V0 DATA |
| `PKG` (package) | `Package.zwr` | GENOUT |
| `VER` (Kernel/FM version) | `KernelFMVersion.zwr` | GENOUT |
| `PRE` (env check) | `EnvironmentCheck.zwr` | GENOUT |
| `INI` (pre-init) | `PreInit.zwr` | GENOUT |
| `INIT` (post-install) | `PostInstall.zwr` | GENOUT |
| `MBREQ` (required builds) | `RequiredBuild.zwr` | GENOUT |
| `QUES` (install questions) | `InstallQuestions.zwr` | GENOUT |
| `RTN` (routines) | `Routines/<NAME>.header` + `Routines/<NAME>.m` | XPDK2V0 RTN |
| `KRN` (options/protocols/RPCs/forms/…) + `ORD` | `<file-name>/ORD.zwr` + `<file-name>/<entry-name>.zwr` | XPDK2VC KRN |
| `TEMP` (transport global remains) | `TransportGlobal.zwr` | GENOUT |

**Reverse (filesystem → KIDS)**:
`LOAD^XPDK2V0` / `LOAD1` / `PROCESS` — recursive directory walk, opens
each file, executes lines as MUMPS `SET` statements against
`^XTMP`. **Incomplete** — code contains `TODO: Document and clean` and
`TO CONTINUE HERE!!! -- MAKE SPECIAL PROCESSING FOR ROUTINES` markers.

### 3.4 Diff-stability techniques — XPDK2VC's best ideas

Two specific engineering moves make XPDK2VC git-friendly where SKIDS is
not:

**(1) Build-number stripping in routine line 2.**
`XPDK2V0.m` line 33:
```mumps
I LN=2 W $P(^(LN,0),";",1,6),!  ; **** DO NOT INCLUDE BUILD NUMBER YOU STUPID IDIOT! **** SCREWS UP DIFF ****
```
KIDS increments the build number on every install. Without this strip,
every install of the same content produces a different line 2, polluting
every git diff. Keeping only pieces 1-6 drops the volatile build-number
trailer.

**(2) IEN-subscript substitution in ZWRITE.**
`XPDK2V0.m` `ZWRITE0`/`SUBNAME` functions substitute a named subscript
position with a literal string:
```
^DIC(9.8,123,0) → ^DIC(9.8,IEN,0)   # when subscript 2 replaced with "IEN"
```
IENs are assigned sequentially at install time and vary between
VistA instances. Without substitution, the same option defined in
two VistAs produces different subscripts → different git diffs.
Replacing the IEN with a stable literal makes the ZWR dump content-
addressable across instances.

These two techniques are precisely what SKIDS lacks and why SKIDS
outputs aren't usefully diff-able.

### 3.5 What XPDK2VC does NOT handle

Observable limitations in the source:

1. **Multi-builds are partially unsupported.** `EXPKID96` line 344:
   ```
   I 12[$P(Z,U,3) QUIT  ; Multi or Global package; can't do!!! I am fricking primitive.
   ```
   Main path refuses multi-build KIDS. The text-parser (XPDK2V1) DOES
   handle multi-build format; the dispatcher doesn't follow through.
2. **Reverse direction (LOAD) is incomplete.** Comments flag it:
   `TODO: Document and clean`, `TO CONTINUE HERE!!! -- MAKE SPECIAL
   PROCESSING FOR ROUTINES`.
3. **Caché-specific dependency.** `D CLRCX^XPDOS` in the cleanup path
   specifically addresses a Caché bug where Windows file handles
   prevent directory deletion. Irrelevant on YDB but unnecessary.
4. **Depends on KIDS being loaded**. Operates on the transport global
   `^XTMP("XPDT",...)`. You can't reverse-engineer an already-installed
   patch from live VistA state — only a KIDS build that's been loaded
   but not yet installed.
5. **No git integration.** Writes files to disk; you run `git add`
   manually. No commit automation, no pre-commit hook, no manifest.
6. **No built-in test harness beyond T4/T5.** Two test entries
   (`T4` TIU, `T5` MAG) exist but aren't a proper CI test suite.
7. **Entry names stripped of punctuation.** `$TR(ENTRYNAME,"\/!@#$%^&*()?<>","---------------")`
   — option names with special chars get mangled in filenames. Not
   round-trippable without reference back to the original entry.
8. **Single author.** Bus factor 1. No active contributors since 2020.
9. **Not bundled with KIDS itself.** Is a patch (`8.0*11310`) that must
   be installed; not part of base Kernel. Few sites have it.

### 3.6 What XPDK2VC got right

- **Coherent design by one author with a clear mental model** — unlike
  SKIDS's disjoint spikes.
- **Comprehensive component coverage** — 13 distinct KIDS sections
  handled.
- **Diff-stability engineering** (build-number strip + IEN
  substitution) — the correct solutions to the correct problems.
- **Both text-`.KID`-file and Build-IEN entry points** — flexible
  input.
- **Multi-build-aware text parser** even if the dispatcher punts.
- **Named-entry-point filenames** — `Routines/DIC.m` rather than
  `routines/123.txt`.

---

## 4. Side-by-side comparison

| Dimension | SKIDS (2011–2013) | XPDK2VC (2014–2020) |
|---|---|---|
| **Language** | Python 2 + MUMPS + Java (3 stacks, not integrated) | MUMPS only |
| **Runtime** | External tool (offline) + in-VistA (live DD read) + Java (unmerged) | In-VistA, operates on transport global |
| **Input** | `.KID` text file (ParseKIDS); live `^DIC`/`^DD` (ZDIOUT1) | `.KID` text OR Build IEN OR existing ^XTMP transport global |
| **KIDS-format awareness** | Routines only (ParseKIDS) | 13 component types |
| **Output format** | `.m` files (ParseKIDS); bespoke tab-separated (ZDIOUT1) | ZWR (per-component) + `.m` + `.header` for routines |
| **Directory structure** | Flat (ParseKIDS) | Hierarchical, mirrors KIDS component tree |
| **Diff-stability — build-number strip** | Accidental (line 2 skipped) | Explicit (pieces 1-6 kept, build number cut) |
| **Diff-stability — IEN substitution** | None | Explicit subscript replacement (`ZWRITE0`/`SUBNAME`) |
| **Diff-stability — entry sort** | None | Not explicit (relies on `$O` ordering) |
| **Diff-stability — value escaping** | None (TODO in ZDIOUT1) | Explicit (`FORMAT`/`CCC`/`RCC` functions) |
| **Multi-build** | Not handled | Parser handles; dispatcher refuses |
| **FileMan DD export** | Not handled (ZDIOUT1 dumps live DD in bespoke format) | Full `^DD` + `^DIC` + SEC + IX + KEY + KEYPTR |
| **Routine header** | Preserved in ParseKIDS (minus line 2) | `.header` + `.m` pair |
| **Special components (Forms, Parameters, Param Templates)** | Not handled | Special processing (FORM, PARM, PARM2 for files .403, 8989.51, 8989.52) |
| **Reverse direction (FS → KIDS)** | Java branch only, unmerged, never wired to forward side | `LOAD^XPDK2V0` — incomplete with TODO markers |
| **Git integration** | None | None |
| **Test suite** | None | Two test entry points (T4, T5) |
| **Documentation** | 9-line README | In-routine comments only |
| **Maintenance status** | Abandoned silently 2013-09 | Last commit 2020-04; effectively dormant |
| **Adoption** | Reference/experimental | Shipped as KERNEL patch; low visibility |
| **License** | Apache 2.0 | Apache 2.0 |
| **Bus factor** | 3 (never collaborated) | 1 (Sam Habiel) |
| **Lines of code** | ~290 (ParseKIDS + ZDIOUT1); ~5000+ Java unmerged | ~870 (all 4 routines) |
| **Round-trip integrity** | Never tested | Partial, untested |

---

## 5. What's missing from BOTH

Neither tool addresses these — they are the genuine open problems for a
KIDS-vc successor:

### 5.1 The patch-list-append problem

KIDS install appends the patch number to line 2 of every touched
routine. XPDK2VC correctly strips the build number from the current
line, but the **patch list itself** (`**20,27,48**`) still gets longer
on every install. If site A installs patch 100 and site B installs
patches 100 and 101, their line 2 diverges:
```
Site A: ;;8.0;KERNEL;**20,27,48,100**;
Site B: ;;8.0;KERNEL;**20,27,48,100,101**;
```
A git repo tracking either site sees legitimate drift. A git repo
tracking the **source** (pre-install) should not include the patch
list at all — the source has no patch list until KIDS applies one.

**Neither tool canonicalizes the patch list for source storage.**

### 5.2 Round-trip integrity verification

Both tools export KIDS → files. Neither proves the round-trip:
- Export KIDS build X to files
- Import files back to a transport global
- Re-export to verify the same bytes come out

Without this, a silent divergence is possible. Every diff-stability
choice needs to be reversible.

### 5.3 FileMan-embedded MUMPS

Many KIDS components contain MUMPS code as *data*:
- Input transforms (stored as MUMPS strings in `^DD(file,field,...)`)
- Computed fields (MUMPS expressions)
- Cross-references (SET + KILL logic as MUMPS)
- Screen expressions, identifier logic
- Option ENTRY ACTION / EXIT ACTION (File 19)
- Protocol ENTRY ACTION / EXIT ACTION (File 101)

XPDK2VC dumps these verbatim inside ZWR nodes — they end up as
escaped strings inside the `.zwr` file. A developer reading the git
diff sees `S ^DD(19,15,0)="EXIT ACTION^K^^15;E1,245^K:$L(X)>245 X D:$D(X) ^DIM"`
rather than readable MUMPS code.

**Neither tool extracts DD-embedded MUMPS to separate `.m`-like files**
for meaningful diffs.

### 5.4 Binary / ZWR merge strategy

`Data.zwr` and `Build.zwr` files are large serialized global trees.
When two branches modify the same file's seed data, git's line-based
3-way merge cannot reliably merge them. The ZWR format is:
```
^DIC(9.8,IEN,0)="XUSER^R^^^^"
^DIC(9.8,IEN,2,0)="^^0^0^3221009"
^DIC(9.8,IEN+1,0)="ZIS^R^^^^"
```
Ordering matters; subscripts can overlap; inline edits of the same key
are the common conflict case. A git merge driver that understands ZWR
subscript keying could merge by entry instead of by text line.

**Neither tool ships a git merge driver for ZWR.**

### 5.5 Parallel development / branch semantics

KIDS patches are serially numbered by VA's patch coordinator. Git
encourages parallel branches. A successor needs to handle:
- Two developers each working on "the next patch" to the same package
  — who gets patch 101?
- Merge conflicts when both touch the same routine
- Semantic versioning beyond patch-list append

Both tools ignore this dimension entirely.

### 5.6 Commit-per-patch mapping

After XPDK2VC exports a patch's components, you get a directory of
files. There's no automation to:
- `git add` the changed files
- Commit with the patch descriptor as subject
- Tag the commit with the patch identifier
- Push to origin

Every site runs XPDK2VC and then manually handles git. No repeatable
workflow.

### 5.7 CI / test integration

A modern KIDS-vc workflow would:
- On git push, build `.KID` from the committed source
- Install into an ephemeral VistA (vista-meta's Docker setup proves
  this is feasible)
- Run XINDEX static analysis on touched routines
- Run M-Unit tests
- Report pass/fail on the PR

Neither SKIDS nor XPDK2VC includes any of this. Both stop at "produce
files on disk."

### 5.8 Live-installed → source-of-truth reconciliation

If a site locally-modifies a routine (`LOCALLY MODIFIED` flag in File
9.8), neither tool detects this vs. the upstream source-of-truth git
repo. Site customizations drift silently from the community branch.

### 5.9 Semantic deduplication

A patch that ships file X with only a `;;` line 2 change (patch-list
append, no content change) should ideally produce an empty commit,
or be omitted entirely. Neither tool detects this.

### 5.10 Attribution

Neither tool carries per-line authorship. The `;;` patch list gives
patch-level attribution; git provides line-level blame. Neither tool
bridges them — after round-trip, the original commit author/timestamp
for each line is lost.

---

## 6. Remediation — what a successor should look like

Building on what XPDK2VC got right and addressing the gaps above:

### 6.1 Build on XPDK2VC's decomposition, not SKIDS's

SKIDS's fragmented design is not salvageable as-is. XPDK2VC's
component-dispatch architecture is the right starting point.

### 6.2 Concrete remediations per gap

| Gap | Remediation |
|---|---|
| **Patch-list noise** (§5.1) | Extend XPDK2V0 line 33 technique — strip pieces 3 (patch list), 4 (build date) from line 2 when emitting to source; preserve only `;;VERSION;PACKAGE;;` (with empty patch list). Document this as the "source canonical form." Regenerate on each install from Kernel. |
| **Round-trip integrity** (§5.2) | Build a test harness: for each production KIDS build, export to files, import via LOAD, re-export, hash-compare. Fail if mismatched. Finish XPDK2V0 LOAD — complete the `TO CONTINUE HERE!!!` path. |
| **DD-embedded MUMPS** (§5.3) | Extract every DD code node (input transforms, xrefs, computed fields) into a dedicated `Files/<num>/<field>.<kind>.m` file. These become first-class .m files in git. On reassembly, embed them back into the `.DD.zwr`. |
| **ZWR merge driver** (§5.4) | Ship a `.gitattributes`-installable custom merge driver that parses ZWR by subscript key and merges entry-by-entry. Conflict only when the same key's value diverges. |
| **Parallel development** (§5.5) | Adopt WorldVistA's `10001+` patch-number convention as the community namespace. Document the coordination protocol (patch number reservation) outside git. |
| **Commit-per-patch mapping** (§5.6) | Wrap XPDK2VC with a shell/Python driver: export → `git add` → commit with patch descriptor subject → tag with patch identifier → push. |
| **CI/CD** (§5.7) | Reuse vista-meta's Docker infrastructure. On PR: build `.KID` from source, install to ephemeral VEHU, run XINDEX + M-Unit, post result. |
| **Local modification drift** (§5.8) | Periodic XPDK2VC export against live VistA; diff against committed source; surface drift as a report. |
| **Empty commits on no-op patches** (§5.9) | After export, compare against last commit; if no meaningful diff (content + stable fields), skip commit. Still tag the patch-list bump separately for history. |
| **Attribution** (§5.10) | On round-trip, preserve git blame information as sidecar `.blame` files in the source tree. Load back into a supplementary global during install so history survives. |

### 6.3 A minimum viable KIDS-vc successor

Scope for a successor project ("KIDS-vc v2"):

**Required**:
1. **Decomposition** — based on XPDK2VC's component dispatch
2. **Diff-stable output** — adopt line-2 strip + IEN substitution from
   XPDK2VC, extend with patch-list canonicalization
3. **Round-trip verified** — automated test that every decomposition is
   losslessly reversible
4. **DD-embedded MUMPS extraction** — new, not in either predecessor
5. **ZWR merge driver** — new
6. **Git wrapper** — export → commit → tag → push as one command

**Nice to have**:
7. CI pipeline (vista-meta Docker hookup)
8. Per-line blame preservation
9. Drift detection (live VistA vs committed source)
10. Multi-build support (finish XPDK2VC's partial handling)

**Deliberately out of scope**:
- Replacing KIDS as deployment mechanism (keep it; version-control the inputs)
- Full semantic versioning (not needed — patch list works)
- Distributed patch-number coordination (existing WorldVistA convention suffices)

### 6.4 Leverage XPDK2VC in our project

This project (vista-meta) has a working VEHU Docker setup — the minimum
infrastructure a KIDS-vc successor needs for CI/CD. XPDK2VC itself is
already in our routine corpus (see [code-model/routines.tsv:37028](../vista/export/code-model/routines.tsv)).
Candidate Phase 8 trajectory:

1. Exercise XPDK2VC on a sample KIDS build (one VA patch) inside
   our container — prove the export works.
2. Set up a git repo for the per-component output.
3. Build the round-trip test harness (export → LOAD → re-export).
4. Identify and fix XPDK2V0's `LOAD` TODO markers.
5. Prototype the DD-embedded MUMPS extractor.
6. Document the workflow in a new guide (`kids-vc-workflow.md`).

This is substantial work — not a single session. But the infrastructure
and prior art are both in hand.

---

## 7. Architectural verdict

**SKIDS failed because it never integrated.** Three contributors wrote
three spikes in three languages for three runtimes and called it a
project. No common data model, no common output format, no tests, no
round-trip. Even if every spike had been finished, there was no
architecture to finish it into.

**XPDK2VC half-succeeded.** One author, one coherent design, running
inside VistA where the data lives, with thoughtful diff-stability
engineering. The two things it's missing are polish (complete round-
trip, DD-embedded MUMPS) and ecosystem (git wrapper, CI integration,
community adoption).

**WorldVistA/VistA-M did succeed** by sidestepping the problem: just
store `.m` files in git, don't try to decompose KIDS bundles. For the
routine slice, this works. It doesn't give you git-native diffing of
FileMan DD changes, seed data, options, or protocols — which is
precisely the surface XPDK2VC covers and VistA-M doesn't.

**The real opportunity** is not "replace KIDS with git" — it's "make
KIDS builds git-native at the source level, keep KIDS for deployment."
XPDK2VC is two-thirds of the way there. Finishing it, not restarting
from SKIDS, is the right move.

---

## 8. References

- [github.com/WorldVistA/SKIDS](https://github.com/WorldVistA/SKIDS) — the abandoned prototype
- [github.com/WorldVistA/VistA-M](https://github.com/WorldVistA/VistA-M) — the simpler approach that won
- [github.com/shabiel](https://github.com/shabiel) — Sam Habiel (XPDK2VC author)
- `vista/vista-m-host/Packages/Kernel/Routines/XPDK2V{C,0,1,G}.m` — XPDK2VC source in VEHU
- [code-model/routines.tsv:37028](../vista/export/code-model/routines.tsv) — XPDK2VC indexed
- [RF-028](../vista/export/RESEARCH.md) — SKIDS investigation findings
- [code-model-guide.md §3](code-model-guide.md#3-code-development-lifecycle-in-vista) — VistA development lifecycle context
- [OSEHRA's first challenge: VistA version control (O'Reilly Radar, 2011)](http://radar.oreilly.com/2011/10/osehra-vista-version-control.html)
- [Cracking VistA Version Control — Nikolay Topalov (2014)](https://nikolaytopalov.wordpress.com/2014/01/30/cracking-vista-version-control/)
