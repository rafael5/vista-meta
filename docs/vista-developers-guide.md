# VistA Developer's Guide

**Who this is for**: a competent programmer of a mainstream modern language
(Python, JavaScript, Go, Rust) who has been asked to "work on a VistA package"
and is staring at a codebase that looks like nothing they've seen.

**The thesis of this guide**: the MUMPS language itself is small enough to
learn in a weekend — Kevin O'Kane's 100-page *Introduction to the Mumps
Language* covers it adequately. The real difficulty of VistA is
**architectural**. Packages, FileMan data dictionaries, cross-references,
the Kernel, KIDS, TaskMan, MailMan, RPC Broker, options, protocols — these
form a web of conventions and interactions that took 40+ years to grow and
has never been flattened into a coherent programmer's model.

This guide is that model, written explicitly from the perspective of
"intelligent programmer meeting VistA for the first time". It tells you what
to look at, what tools exist, what tools should exist but don't, what
conventions to follow, how to develop/test/validate new functionality, and
where AI-assisted development fits in.

Where possible this guide cites code and data already in the vista-meta
project. You can produce most of the referenced artifacts yourself by
running `make` targets in this repo.

---

## 1. The first 24 hours — orientation for Python programmers

### 1.1 What VistA is

VistA (Veterans Health Information Systems and Technology Architecture) is
the electronic health record system the US Department of Veterans Affairs
has used since the 1980s. It runs ~170 hospitals and ~1,100 clinics.
Written in MUMPS (now typically called "M"). Data lives in MUMPS **globals**
— persistent hierarchical key-value structures — managed by a MUMPS engine
(VA production uses InterSystems IRIS/Caché; open-source installs use
YottaDB or older GT.M).

Multiple distributions exist:
- VA production (closed, internal)
- **VistA-M** — WorldVistA's GitHub mirror — the canonical community source
- **OSEHRA FOIA VistA** — the open-source baseline
- **VEHU** — VistA Enterprise Health University — a synthetic test instance
  this project uses
- **RPMS** — Indian Health Service's fork
- **vxVistA**, **VistA-Office EHR** — smaller derivatives

Any of these installs has roughly the same core: **~200 packages**,
**~40,000 routines**, **~8,000 FileMan files**, **~500 globals**,
**~13,000 menu options**, **~4,500 RPCs**, **~6,500 protocols**.

### 1.2 What's weird from a Python perspective

Every dimension of the Python ecosystem you rely on either doesn't exist or
has a weaker VistA equivalent. This is the actual gap:

| Python habit | VistA reality |
|---|---|
| `pip install` | **KIDS** — monolithic patch bundles, interactive install, VA-coordinated registry |
| `virtualenv` / project isolation | One global namespace. `^DPT` in package A is the same `^DPT` in package B. |
| `pytest` | **M-Unit** (sparse adoption — most packages have zero tests) |
| `black` / `ruff` — format/lint on save | None. **XINDEX** is manual, runs ad-hoc, no IDE integration |
| Type hints, autocomplete, refactoring | None. Everything is a string. Identifier is known at runtime. |
| `git` | Patch lists `;;**20,27,48**` — flat linear accumulation. Community overlays use git on top of the MUMPS source tree. |
| Package dependency declaration (`pyproject.toml`) | Implicit. KIDS "environment check" routine probes for prerequisites manually. |
| `git revert` / rollback | **None.** Install is destructive, no uninstall. See [code-model-guide.md §3.4](code-model-guide.md#34-uninstall). |
| IDE with go-to-definition | Terminal editor (ZED, `%ZEDIT`). VSCode MUMPS extensions exist but are shallow. |
| Debugger with breakpoints | `ZBREAK` gets you partway. Line-level. No variable inspector beyond `W` statements. |
| Structured logs | `^ERROR`. Unstructured. Stays on-box. |
| Semantic versioning | Patch numbers. `;;**158**;` means "158 patches applied"; says nothing about breaking changes. |
| Deprecation warnings | "Deleted by patch" marker (File 9.8 field 6.2) — forward-delete, not deprecation. |
| Cross-reference / call graph in IDE | Had to build one (see §3). |

When you hit friction, check the table. The friction is usually structural,
not your misunderstanding.

### 1.3 MUMPS itself is small

In case you haven't touched MUMPS yet:

- Dynamically typed. Every value is a string. Numeric context coerces.
- One-letter commands: `S` (SET), `D` (DO), `Q` (QUIT), `K` (KILL),
  `W` (WRITE), `I` (IF), `F` (FOR), `X` (XECUTE), `G` (GOTO), `J` (JOB).
- **Globals** are persistent data structures, syntactically identical to
  local variables except they're prefixed with `^`:
  ```
  SET ^DPT(1,0)="SMITH,JOHN^M^1980..."
  ```
  `^DPT` is the patient file global. `(1,0)` is the subscript path. The
  value is caret-delimited pieces.
- Column 1 is meaningful: a line starting in column 1 is a **label** (tag);
  a line starting with whitespace is a body line.
- Post-conditionals: `DO:$D(X) WORK` means "DO WORK if X is defined".
- Indirection: `@X` evaluates to whatever X names. `DO @X` calls the
  routine whose name is in X.
- Argumentless commands: `QUIT` without arg quits the current scope; with
  arg returns a value.

That's essentially it. The language fits on a few pages. What takes months
is the ECOSYSTEM.

### 1.4 Your first mental model

Pin this:

```
VistA
├── MUMPS engine (YottaDB or IRIS) — runs the code, stores globals
├── Globals namespace — one flat tree shared by everyone
│     ^DPT (patients), ^DIC (file list), ^DD (data dict), ^OPT (options), …
├── Kernel — Login, Security, TaskMan, MailMan, KIDS, Parameters
│     (written in MUMPS, provides OS-like services)
├── FileMan — the database layer
│     Adds schemas (Data Dictionary), forms (ScreenMan), search (FileMan Lookup)
│     to the bare globals
├── Packages — logical groupings
│     Pharmacy (PS*), Lab (LR*), Radiology (RA*), etc.
│     Each has: namespace prefix, routines, FileMan files, options, protocols, RPCs
├── Options — menu entries (File 19) — user-facing surface
├── Protocols — event-driven hooks (File 101) — HL7, OE/RR
├── RPCs — File 8994 — CPRS-facing API surface
└── KIDS — the package manager + installer
```

Everything else is detail. Come back to this diagram when confused.

---

## 2. Understanding a single package

### 2.1 What a "package" actually is

A package in VistA is a **convention**, not an enforced boundary. It's the
union of:

- A **namespace prefix** — 2-4 letters (e.g., `DG` for Registration,
  `PSO` for Outpatient Pharmacy, `LR` for Laboratory). All the package's
  routines and globals should start with this.
- A **set of routines** — `.m` files under
  `Packages/<PackageName>/Routines/` in the VistA-M repo.
- A **set of FileMan files** — data-dictionary entries (in File 1) that
  live under a `^`-prefixed global. E.g., Outpatient Pharmacy owns file 52
  (`^PSRX`), file 55 (`^PS(55`), etc.
- **KIDS components** — options (File 19), protocols (File 101), RPCs
  (File 8994), security keys (File 19.1), parameters (File 8989.51),
  dialogs, templates, forms, etc. — all namespaced.
- An **entry in File 9.4** — the PACKAGE file, listing the package's
  namespace, version, patches applied, and dependencies.

**Nothing in VistA enforces package boundaries.** A Pharmacy routine can
freely touch a Registration global. Package boundaries are code-review
norms, not module-system guarantees.

### 2.2 Where to start reading

When you're assigned to work on package `FOO`:

**Step 1 — find the source.** In this repo:
```bash
ls vista/vista-m-host/Packages/<Name>/Routines/
```
or in WorldVistA's mirror: `github.com/WorldVistA/VistA` →
`Packages/<Name>/Routines/<FOO>*.m`

**Step 2 — read File 9.4.** The PACKAGE entry tells you the namespace,
version, install history. In our code-model:
```bash
grep -i "^<fnum>\t" vista/export/code-model/vista-file-9-8.tsv
```

**Step 3 — read the namespace's entry points.** Look for routines named
like `<PREFIX>MAIN`, `<PREFIX>ENV`, `<PREFIX>POST` — these are often
install entry points or menu dispatchers.

**Step 4 — read one real routine top-to-bottom.** Most routines have a
1-line header: `ROUTINE ;SITE/AUTHOR - description ;DATE` followed by a
2nd line with version info. Then typically several tags (labels) with
`;` comments.

**Step 5 — query the code-model.** You've already generated
`routines-comprehensive.tsv` and `package-manifest.tsv`. These answer
questions like:

```bash
# What RPCs does my package expose?
awk -F'\t' -v P="Outpatient Pharmacy" '$2==P && $12>0 {print $1}' \
  vista/export/code-model/routines-comprehensive.tsv

# What globals do my package's routines touch?
awk -F'\t' -v P="Outpatient Pharmacy" '$2==P {print $3}' \
  vista/export/code-model/routine-globals.tsv | sort -u

# Who calls into my package from outside?
awk -F'\t' -v P="Outpatient Pharmacy" '$1!=P && $callee_pkg==P' \
  vista/export/code-model/routine-calls.tsv
```

**Step 6 — check external documentation.** The VA Documentation Library
at `https://www.va.gov/vdl/` has package-level manuals for VA-authored
packages. Usually hundreds of pages per package. Often out of date, but
still more than the code gives you.

### 2.3 Key questions to answer before editing

You have not understood a package well enough to modify it until you can
answer:

- [ ] What namespace prefix does it own?
- [ ] What FileMan files does it own? (check File 9.4 entry)
- [ ] What globals does it own (vs. read from other packages)?
- [ ] What options / protocols / RPCs does it expose?
- [ ] Who calls INTO this package (inbound dependency)?
- [ ] What does this package call OUT to (outbound dependency)?
- [ ] What's the install history? (patch list in routine line 2)
- [ ] Is there existing M-Unit test coverage? (usually: no)
- [ ] What's the recent change history? (git log on the `.m` files, if mirrored)
- [ ] Who maintains it? (WorldVistA mailing list / OSEHRA)

The vista-meta code-model gives you most of this mechanically. See
[code-model-guide.md](code-model-guide.md) for the query vocabulary.

---

## 3. How packages affect each other — the coupling reality

### 3.1 Explicit vs implicit dependencies

**Explicit** (declared in File 9.4):
- **Required Builds** (`MBREQ`) — "this patch requires Kernel 8.0*256 first"
- **Package requires** — a package can list upstream packages it needs

**Implicit** (the majority):
- **Routine calls** — `D ^DIC`, `$$GET1^DIQ(...)`, `D EN^XMD` — never declared
- **Global reads/writes** — Billing routines that read `^DPT` (Patient)
- **Pointer fields** — File 52 (Prescription) field .02 points to File 2
  (Patient). You can't delete a Patient that a Prescription points to.
- **Option menu nesting** — Package A's option can have a child option
  belonging to Package B
- **Protocol subscribers** — HL7 subscriber in package C fires when an
  event driver in package D publishes
- **MailMan bulletins** — routine X in package A sends to mail group Y
  owned by package B

### 3.2 Where to look for dependencies

The vista-meta code-model makes implicit dependencies explicit:

| Artifact | Answers |
|---|---|
| `routine-calls.tsv` | "What routines does my package call?" |
| `routine-globals.tsv` | "What globals does my package touch?" |
| `package-manifest.tsv` | "Per-package summary: counts, PIKS, fan-in/out" |
| `package-edge-matrix.tsv` | "Cross-package call volumes — who depends on whom?" |
| `xindex-xrefs.tsv` | "Authoritative MUMPS-parser call graph (supersedes regex where available)" |
| `rpcs.tsv` / `options.tsv` / `protocols.tsv` | "What surfaces does my package expose?" |
| `package-data.tsv` | "What FileMan files does my package ship?" |

When you're about to change something, run the relevant query. The answer
is usually "more than you thought".

### 3.3 The "shared substrate" problem

Per [RF-023](../vista/export/RESEARCH.md), **VA FileMan and Kernel together
receive 75.4% of all cross-package calls.** They're VistA's shared library,
equivalent to Python's stdlib. You will call into them from every package.

Practical consequence: changes to FileMan or Kernel APIs ripple across
everything. That's why those packages get the most patch-review scrutiny.
As a new developer, assume you are a consumer of FileMan/Kernel, not a
modifier.

### 3.4 What breaks what — the cascades

| Change | What cascades |
|---|---|
| Change a field's type in DD (F→P) | Every routine that reads that field with a specific type expectation |
| Delete a FileMan field | Cross-references break; pointer-in targets lose data; historical reports fail |
| Rename an RPC | CPRS client code breaks (separately deployed) |
| Remove a routine | Any `D ^X` or `$$Y^X` call hits "Routine does not exist" at runtime |
| Rename an option menu | Menu trees that include it break; user workflows fail |
| Modify a global's subscript structure | Every routine that reads that global by subscript breaks |
| Change a KIDS pre-install | Silently — routines that rely on pre-install side effects might not detect |

**Critical**: there's no "compile time" to catch these. Everything is
runtime. A broken `D ^OLDROUTINE` call fails only when the execution path
that calls it actually runs.

---

## 4. The tooling landscape

### 4.1 What exists

| Tool | Purpose | Location | State |
|---|---|---|---|
| **XINDEX** | Static analysis — 66 error codes | Toolkit (XT*7.3*158) | Functional but manual; VEHU's version has runtime issues ([RF-026](../vista/export/RESEARCH.md)) |
| **M-Unit** | Unit testing framework | `github.com/ChristopherEdwards/M-Unit` | Works; adoption sparse |
| **KIDS** | Package manager + installer | Kernel | Production-stable, forward-only |
| **FileMan** | Database layer + schema | Core | Production-stable |
| **TaskMan** | Background job scheduler | Kernel | Production-stable |
| **MailMan** | User messaging + bulletins | Kernel | Production-stable |
| **RPC Broker** | CPRS network API | Kernel | Production-stable |
| **VistA-M** | Source on GitHub | [github.com/WorldVistA/VistA](https://github.com/WorldVistA/VistA) | The canonical community mirror |
| **kids-vc** | Git integration for KIDS | This project | See [kids-vc-guide.md](kids-vc-guide.md) |
| **XPDK2VC** | In-VistA KIDS→VCS | Kernel 8.0*11310 | Shipped but rarely run |
| **ViViaN/DOX** | Web cross-ref browser | `vivian.worldvista.org/dox/` | Call-graph subset only ([RF-025](../vista/export/RESEARCH.md)) |

### 4.2 What doesn't exist (modern Python ecosystem equivalents missing)

| Python tool | VistA equivalent | Gap |
|---|---|---|
| `ruff`, `black` | — | No format-on-save. XINDEX is the closest analogue; it's not a formatter. |
| `pytest`, `unittest` | M-Unit | Exists, rarely used |
| `mypy`, TypeScript | — | No type system. Everything is a string at runtime. |
| `pip` | KIDS | Exists but operationally different — monolithic patches, no versioned packages |
| `venv` | — | Impossible. Global namespace. |
| `git hooks` / pre-commit | — | No standard pre-commit infrastructure |
| `coverage.py` | — | No code coverage tool for MUMPS |
| `pdb` breakpoint debugger | `ZBREAK` | Line-level, primitive |
| `Sphinx` / doc generation | VDL | Manual, out-of-band |
| LSP / IDE refactoring | — | No language server. No rename-symbol across a project. |
| `Dependabot` / security scanning | — | None |
| Python Package Index / search | — | No searchable registry of packages |

### 4.3 What's emerging (worth knowing about)

- **kids-vc** (this project) — fills the git-native KIDS slot
- **YottaDB Python API** — lets you script VistA from Python (see §7)
- **IRIS Python gateway** — same idea on the closed-source side
- **OSEHRA's test infrastructure** — growing, container-based
- **VEHU** — synthetic VistA-in-a-box for test development

### 4.4 What you, as a new developer, should install

Minimum:
1. A **VistA container** — this project's Docker setup (VEHU on YottaDB)
2. **kids-vc** — `make kids-vc-pip-install`
3. A **MUMPS syntax highlighter** — VSCode's `mumps` extensions
4. **XINDEX** in your container — ships with Toolkit
5. **M-Unit** — clone Christopher Edwards's fork and install via KIDS
6. **Git** — obviously
7. **A notebook** — you'll accumulate tribal knowledge that isn't
   documented anywhere

Recommended:
8. **Python 3.10+** — for running kids-vc, corpus harness, and writing
   analytical scripts
9. **YottaDB Python bindings** — `pip install yottadb` — if you plan to
   script against live VistA
10. **Claude / Copilot / similar** — AI assistant that can read MUMPS; see §9

---

## 5. The Standards and Conventions (SAC) — why it's aspirational

### 5.1 What SAC says

The VA **Standards and Conventions** document is a style guide covering:
- Naming (namespace prefixes, routine names, variable casing)
- Line length (245 bytes max)
- `NEW` scoping discipline
- Device I/O via `^%ZIS` (not direct `OPEN`)
- `HALT` only via `^XUSCLEAN` (not bare `HALT`)
- `OPEN` only via `^%ZIS`
- Required line-2 format (`;;version;package;**patches**;date;build`)
- Comment conventions
- Error handling via `$ETRAP`
- Cross-reference naming
- DD-embedded MUMPS restrictions

It's about 30-40 pages depending on version.

### 5.2 Why it's insufficient

**Zero automated enforcement.** SAC is document-only. XINDEX catches some
violations (the 66 error codes — see [xindex-reference.md §3](xindex-reference.md#3--errorwarning-codes--the-full-catalog))
— notably:
- Exclusive kill (code 22)
- Unargumented NEW (code 26)
- Missing READ timeout (code 33)
- Direct `HALT` instead of `^XUSCLEAN` (code 32)
- Lowercase commands (code 47)
- SACC size violations (codes 35, 58)

XINDEX's coverage IS a subset of SAC. But XINDEX is not wired into:
- Commit hooks
- CI pipelines
- IDE warnings
- Code review gates

So SAC compliance is enforced by **manual code review at patch-submission
time**, which is slow and inconsistent.

**Doesn't cover modern concerns** at all:
- Testing practices (no guidance on M-Unit usage)
- Git hygiene (doesn't mention git)
- Commit/merge workflow
- Documentation-as-code (JSDoc/docstring equivalent)
- Dependency declarations
- Configuration management
- Secrets management
- Observability (logging, metrics, tracing)
- Security review checklist

### 5.3 A proposed modern successor — sketch

If someone sat down to write **SAC v2** as "what a 2026 Python/Go/Rust dev
would want", it would cover:

**Style** (unchanged from SAC where still relevant):
- Namespace prefix per package
- Line length cap (increase to 510 or let the runtime decide)
- Column-0 labels, column-1+ body
- `NEW` discipline for locals

**Modern additions**:
- **Automated enforcement** — every rule is checkable by a linter at
  commit time. No "aspirational" rules.
- **Testing minimum** — each new routine ships with an M-Unit test file
  (`T<routinename>.m`) exercising public tags. CI rejects patches
  without tests.
- **Doc-comment convention** — doc block before each public tag:
  ```
  ; @summary   Validate a patient IEN
  ; @param DFN — patient file IEN
  ; @returns   1 if valid, 0 otherwise
  ; @example   I $$VALIDATE^XUSVAL(123) W "ok"
  VALIDATE(DFN) ;
   ...
  ```
- **Error handling** — every routine sets `$ETRAP` on entry; errors log
  structured records (not just `^ERROR`).
- **Explicit dependencies** — a `<pkg>.deps` file declaring upstream
  packages by namespace. Parsed by KIDS env-check.
- **Semantic versioning** — each patch declares `major.minor.patch`
  impact alongside the patch number.
- **Deprecation markers** — standard `; @deprecated use X instead`
  comment, caught by linter.
- **No global namespace collisions** — linter rejects any routine that
  writes to a global not in its namespace without explicit cross-package
  annotation.
- **Commit discipline** — one patch = one semantic change. Mass
  refactors are separate patches.
- **Pre-commit hook** — runs XINDEX + kids-vc roundtrip + M-Unit before
  allowing a commit. Rejection with machine-readable output.
- **Security checklist** — PHI access logged; no site-local secrets in
  source; parameters stored via `^XTV(8989.3)`, not hardcoded.

None of this exists today as a single document. But every bullet could be
implemented with small tooling additions — and several (M-Unit, XINDEX
checks, kids-vc) already exist; they just aren't mandatory.

**Opportunity for the community**: write SAC v2 as a live linter
(`msac`), not a PDF. Rules expressed as Python check functions that run
over decomposed kids-vc output. Patch-level pass/fail. If the community
would accept it.

---

## 6. Development lifecycle — what you actually do

A concrete recipe for adding new functionality to an existing package.
Let's say you're adding a new option to Package `PSO` (Outpatient Pharmacy)
that prints a prescription refill history report.

### 6.1 Step 1 — scope and research

1. Read the relevant routines:
   ```bash
   ls vista/vista-m-host/Packages/Outpatient\ Pharmacy/Routines/PSO*.m
   ```
2. Understand the FileMan files involved:
   ```bash
   awk -F'\t' '$1=="Outpatient Pharmacy"' \
     vista/export/code-model/package-data.tsv
   ```
3. Check what options already exist (to see the naming patterns):
   ```bash
   awk -F'\t' '$5=="OUTPATIENT PHARMACY"' \
     vista/export/code-model/options.tsv | cut -f1,2,4
   ```
4. Read a similar existing routine end-to-end. **This is essential.**
   VistA conventions are learned by imitation, not by reading a style
   guide.

### 6.2 Step 2 — design

- **Pick a routine name** — `PSOREFHX` for "PSO REFILL HISTORY"
- **Pick an option name** — `PSO REFILL HISTORY` (File 19 entries are
  space-separated, uppercase, namespaced)
- **Decide the option type** — `R` (run routine) if it invokes code,
  `M` (menu) if it groups sub-options
- **Design the workflow** — what prompts does the user see? What data
  is shown? Output device?
- **Error handling** — what if no refills? What if patient IEN invalid?

### 6.3 Step 3 — develop

**Write the routine.** In `vista/dev-r/PSOREFHX.m`:
```mumps
PSOREFHX ;SITE/YOU - Outpatient Rx Refill History Report ;2026-04-20
 ;;1.0;OUTPATIENT PHARMACY;;
 ;
EN ; @summary Main entry — prompt for patient + print refill history
 N DFN,RXIEN,REFCNT,DATA
 S DFN=$$ASKPAT() Q:'DFN
 D HEAD(DFN)
 D REFILLS(DFN,.REFCNT)
 W !,"Total refills: ",REFCNT
 Q
 ;
ASKPAT() ; @returns DFN of selected patient, or 0 if cancelled
 ...
 ;
HEAD(DFN) ; @param DFN patient IEN — print report header
 ...
 ;
REFILLS(DFN,REFCNT) ; @param DFN patient IEN ; @returns REFCNT count
 ...
```

Conventions you're following:
- Namespace prefix `PSO` (matches Outpatient Pharmacy)
- First-line format `ROUTINE ;SITE/AUTHOR - description ;DATE`
- Second-line format `;;version;PACKAGE;patches;date;build`
  (for source, canonical empty — KIDS will fill)
- Tags (labels) at column 0
- Body lines indented (typically 1 space)
- `NEW` discipline — explicit list at routine top
- Doc comments using the proposed `@summary`/`@param`/`@returns`
  convention (new; not yet enforced)

### 6.4 Step 4 — register the option

Create the option in File 19 (OPTION). Interactive way via FileMan, but
for a packaged patch you'd add to your KIDS build. A draft option entry:

```
File 19, IEN auto-assigned:
  .01 NAME          : PSO REFILL HISTORY
  1   MENU TEXT     : Refill History Report
  4   TYPE          : R
  12  PACKAGE       : OUTPATIENT PHARMACY
  25  ROUTINE       : EN^PSOREFHX
```

### 6.5 Step 5 — test

**Static** — run XINDEX:
```
D ^XINDEX
  → pick PSOREFHX
```
Fix any reported errors before proceeding. Errors 1-66; critical ones
(Fatal) must be zero.

**Unit** — write an M-Unit test `TPSOREFH.m`:
```mumps
TPSOREFH ;SITE/YOU - M-Unit tests for PSOREFHX ;2026-04-20
 ;;1.0;OUTPATIENT PHARMACY;;
 Q
 ;
EN D EN^%ut($T(+0),1,1) Q
 ;
T1 ; @TEST REFILLS with known patient returns expected count
 N DFN S DFN=1  ; known test patient
 N REFCNT
 D REFILLS^PSOREFHX(DFN,.REFCNT)
 D CHKEQ^XTMUNIT(REFCNT,3,"expected 3 refills for patient 1")
 Q
 ;
T2 ; @TEST REFILLS with invalid IEN returns 0
 N DFN S DFN=99999999
 N REFCNT
 D REFILLS^PSOREFHX(DFN,.REFCNT)
 D CHKEQ^XTMUNIT(REFCNT,0,"expected 0 for invalid patient")
 Q
```

Run: `D EN^TPSOREFH`. Check all tests pass.

**Integration** — actually run the option from the menu:
```
D ^XUP  (user dispatcher)
  → pick PSO REFILL HISTORY
```
Walk through the workflow manually.

### 6.6 Step 6 — package via KIDS

**Option A** — in-VistA KIDS build:
```
D ^XPDB   (Build Edit Menu)
  → create new build "PSO*1.0*1001"
  → add routine PSOREFHX
  → add option PSO REFILL HISTORY
  → run environment check, pre-install, post-install if needed
  → export .KID file via D ^XPDTS
```

**Option B** — decompose-first via kids-vc (newer workflow):
1. Develop in a git repo with kids-vc layout
2. `kids-vc assemble patches/PSO_1_0_1001/ PSO_1_0_1001.KID`
3. Install the `.KID` into VEHU

Verify installation produces expected result.

### 6.7 Step 7 — deploy

For a real patch, this involves:
- **Pre-install backup** of globals volume (SOP)
- **Install on TEST account** first
- **User acceptance** — let an end-user walk through
- **Production install** during a maintenance window
- **Post-install monitoring** — watch `^ERROR` and user reports
- **Document** — VDL update, patch description

If something breaks: there is no uninstall (see [ADR-046](adr/046-kids-vc-undo-pre-install-snapshot.md)
for a proposed partial remedy). Restore backup.

---

## 7. The Python-via-C-API path — alternative for new work

### 7.1 What's possible

Both major MUMPS engines now expose Python APIs:

- **YottaDB** — `pip install yottadb`. Calls YDB C API. Full global
  read/write, routine invocation, lock management.
  [docs.yottadb.com](https://docs.yottadb.com/MultiLangProgGuide/pythonprogman.html)
- **InterSystems IRIS** — `pip install intersystems-iris`. Native Python
  SDK with global/class/SQL access.

Example YottaDB:
```python
import yottadb as ydb

# Read a patient's 0-node
node = ydb.Key("^DPT")[1][0]
print(node.value)   # "SMITH,JOHN^M^1980..."

# Iterate patients
for ien in ydb.Key("^DPT")[::1]:
    pass

# Call a MUMPS routine
ydb.ci("EN^PSOREFHX", args=("1",))
```

### 7.2 When to use Python-via-C-API

**Good fit**:
- **Analytics / reporting** — read-only analytical workloads (this whole
  vista-meta project is that)
- **External integrations** — FHIR adapters, REST endpoints, HL7
  receivers, file imports/exports
- **Batch data transformation** — ETL pipelines, data migration
- **AI / ML** — model training or inference over VistA data
- **Dashboards** — Prometheus exporters, Grafana datasources
- **Glue code** — orchestration that calls MUMPS routines but lives
  in Python

**Bad fit**:
- **Modifying FileMan file behavior** — cross-refs, input transforms,
  computed fields — these MUST be MUMPS (they're called by FileMan's
  own execution engine)
- **Pre-install / post-install routines** — KIDS runs these in MUMPS
  context
- **Options / protocols / RPCs** — the entry point is a MUMPS tag
- **Performance-critical inner loops** — Python↔MUMPS boundary has
  overhead

### 7.3 What you still have to understand

Python access doesn't let you avoid VistA fundamentals. You still need:

- **Global structure** — `^DPT(ien,0)` means "patient with IEN=ien, zero
  node, which contains name^sex^DOB^..." You have to know this to read
  anything.
- **Piece conventions** — caret-delimited values, positional semantics
- **FileMan DD** — which files have which fields, pointer relationships
- **Cross-references** — how to query (`$O(^DPT("B","SMITH"))`)
- **MUMPS semantics at the boundary** — `$D`, `$O`, NAKED references, `KILL`
- **Locking** — `LOCK ^DPT(ien)` before writing, or risk races

### 7.4 Hybrid pattern — recommended

Do new development in Python when you can; drop into MUMPS for the
pieces that must be MUMPS. Use YottaDB's `ci()` (call-in) to invoke
MUMPS tags from Python. Use Python's richer ecosystem (pytest, logging,
HTTP clients, SQLAlchemy) for everything else.

The vista-meta project itself uses this pattern:
- Python host/scripts/ for analytical tools
- MUMPS vista/dev-r/ for things that must run in the database (VMFILES,
  VMPIKS, VMDUMP98, etc.)

---

## 8. Tooling gaps and how to work around them

Practical workarounds for the missing Python ecosystem pieces:

### 8.1 No linter-on-save

**Workaround**: pre-commit git hook that runs XINDEX on changed routines.
If XINDEX reports any Fatal (F) errors, reject the commit.

```bash
#!/bin/bash
# .git/hooks/pre-commit
changed_m=$(git diff --cached --name-only | grep '\.m$')
for m in $changed_m; do
    # Extract routine name, run XINDEX via docker exec, parse output
    ...
done
```

Not built here yet but straightforward to add.

### 8.2 No formatter

**Workaround**: accept whatever formatting upstream uses and match it.
When writing new code, use spaces (not tabs), one space after commands,
column-0 labels. Eventually someone should write an `mfmt`.

### 8.3 No type checking

**Workaround**: docstring-style parameter annotations in doc comments.
Convention (proposed):
```
EN(DFN) ; @param DFN number ; @returns number ; main entry
```
Today this is informational only; a future `msac`-type linter could
parse it.

### 8.4 No autocomplete

**Workaround**: vista-meta's `routines-comprehensive.tsv` +
`routine-calls.tsv` is a **queryable symbol database** for a single
VistA snapshot. Grep for a tag name to find every caller:
```bash
grep -P "\tX\^DIC\t|\tDIC\t" vista/export/code-model/routine-calls.tsv
```

### 8.5 No rename-symbol

**Workaround**: `grep -rl 'OLDNAME' vista/vista-m-host/Packages/` and
sed — with all the caveats of textual rename (strings, comments, etc.).
XINDEX after the rename to catch broken references.

### 8.6 No coverage tool

**Workaround**: none, really. M-Unit doesn't track coverage. You know
a routine is tested iff you wrote a test for it; there's no automated
"72% covered" metric.

### 8.7 No package registry

**Workaround**: WorldVistA's master + OSEHRA's website. Package
discovery is by reputation.

### 8.8 No IDE

**Workaround**: VSCode + a MUMPS syntax highlighter + our code-model
TSVs side-by-side. Or use Claude / Copilot to do the navigation for
you (see §9).

---

## 9. AI-assisted development — a real option

### 9.1 What AI tools can do for VistA today

Large language models (Claude, GPT-4, etc.) are already capable of:

- **Reading MUMPS code** and explaining what it does — the language is
  small enough that they understand it natively
- **Writing new MUMPS routines** to specification, following VistA
  conventions you demonstrate
- **Finding bugs** — "what's wrong with this routine?" works
- **Navigating FileMan DD structures** — they can read `^DD(file,field,0)`
  format
- **Porting patterns** from Python/other-language code to MUMPS
  (and vice versa)
- **Following XINDEX conventions** — if you tell them the 66 error
  codes to avoid, they'll generate compliant code
- **Building KIDS patches** via kids-vc
- **Generating M-Unit test suites**
- **Writing doc comments** in the proposed modern convention
- **Explaining cross-references and calling conventions**

The vista-meta project itself is an existence proof: **kids-vc was built
primarily with AI assistance**. 2,406-patch corpus validation achieved in
a single session. ~3,000 lines of Python + MUMPS written with AI pairing.
See [kids-vc-background-dev.md Part IV](kids-vc-background-dev.md) for
the development chronology.

### 9.2 What AI can't (yet) do

- **Access a running VistA** without you providing the tooling (VEHU
  container, `kids-vc`, YottaDB Python bindings)
- **Deploy patches** — they can write KIDS builds, not install them
- **Replace understanding VistA fundamentals** — if you ask "how do I
  add a field to File 2", you still need to know what a field is, what
  File 2 is, and the FileMan conventions
- **Know your site-local customizations** — national AI trained on
  general VistA may not know that your site renamed option `X` to
  `X-LOCAL`
- **Debug live production issues** without the logs and state exposed
  to it

### 9.3 Effective AI-assisted patterns

**Pattern 1 — context-first.** Before asking for code, ask for
understanding:
```
"Read routine PSOREFHX and explain what each tag does. What globals
does it touch? What does it assume about its input?"
```
Give the AI the source. It'll read it. Now it has context.

**Pattern 2 — iterate with XINDEX.** Ask the AI to generate code,
run XINDEX, feed the errors back:
```
"Here's the XINDEX output for your proposed routine: <paste>.
Fix the errors and regenerate."
```

**Pattern 3 — round-trip via kids-vc.** When building a KIDS patch:
```
"Decompose the existing patch via kids-vc, then modify the Routines/
dir to add my new routine, then assemble. Verify round-trip."
```

**Pattern 4 — test-first.** Ask for tests before the implementation:
```
"Write an M-Unit test file for a routine that validates a patient
IEN. Then write the implementation that passes those tests."
```

**Pattern 5 — query the code-model.** AI can't scan 40,000 routines
from scratch each conversation, but it can use the code-model TSVs:
```
"Query routines-comprehensive.tsv for Outpatient Pharmacy routines
that back both an RPC and an option, then propose a design for
extending them."
```

### 9.4 The onramp multiplier

Historically, becoming productive in VistA took 6-18 months for a
smart programmer. The tribal knowledge — FileMan conventions, Kernel
APIs, namespace rules, SAC — wasn't in any one place.

With AI assistance + the vista-meta code-model, this timeline is
compressible to **weeks** — probably **days** for narrow tasks.
The AI reads conventions off existing routines. The code-model TSVs
provide the machine-queryable symbol database. kids-vc provides a
modern workflow.

This is not hypothetical. The vista-meta project itself took one
session to produce: a full Python port of XPDK2VC, 100% corpus pass,
structural XPDK2VC contract tests, pip package, CI. Numbers of
human-work-weeks saved are significant.

### 9.5 Honest risks

- **AI hallucinates** routine names and tags that don't exist. The
  "~24,000 routines" error corrected in RF-024 is an in-this-session
  example. Always verify against real state.
- **AI doesn't know your site's customizations.** Treat AI-generated
  code as a starting point, not a final product.
- **AI can produce plausible-looking but broken MUMPS.** XINDEX and
  round-trip testing catch most of this; manual review catches the
  rest.
- **Overreliance** risks letting the AI handle what you should be
  learning. AI is a force multiplier for understanding, not a
  substitute.

---

## 10. Practical onramp — your first two weeks

A concrete checklist.

### Week 1 — orientation

- [ ] **Day 1**: Clone vista-meta. Run `make build && make run`. SSH
      into the container (`make shell`). You have a running VistA.
- [ ] **Day 2**: Skim `docs/code-model-guide.md` end-to-end. Don't
      memorize; just get the landscape.
- [ ] **Day 3**: Produce the code-model artifacts:
      ```bash
      make sync-routines && make inventory
      make package-data && make package-piks
      make package-manifest && make routines-comprehensive
      ```
      Open each TSV and look at the data. Grep for your target package.
- [ ] **Day 4**: Read Kevin O'Kane's MUMPS book (100 pages, one sitting).
      You now know the language.
- [ ] **Day 5**: Read one real package's routines top-to-bottom. Pick a
      small one (Dental / DENT is ~150 routines; Mental Health is
      manageable). Don't try to read Pharmacy or Lab on week 1.

### Week 2 — a real task

Pick a small task: add an option to display some existing data.

- [ ] **Day 6**: Scope and design (§6.1, §6.2). Use AI to help
      read the existing package.
- [ ] **Day 7**: Develop (§6.3). Use AI to generate initial draft; edit
      to fix what the AI got wrong.
- [ ] **Day 8**: Test (§6.5). Write M-Unit tests. Run XINDEX. Fix every
      Fatal error.
- [ ] **Day 9**: Package via kids-vc (§6.6). `kids-vc assemble` → .KID.
- [ ] **Day 10**: Install into VEHU, run your option end-to-end, verify
      output. Iterate.

By end of week 2 you've shipped a working patch into a clean VistA
instance. You understand, concretely, the full lifecycle.

### What not to do

- **Don't start with Pharmacy, Lab, OE/RR, Billing, or Scheduling.**
  These are the most complex packages. You'll bounce off.
- **Don't try to refactor something "just to clean it up".** VistA
  code is interconnected in ways you won't see until you break it.
- **Don't assume documentation is current.** VDL, package READMEs,
  and even source comments drift.
- **Don't skip XINDEX.** It catches things you'll miss.
- **Don't skip M-Unit tests** "because there aren't any for this
  package already". Be the first.

---

## 11. Community and resources

Where to get help.

- **[github.com/WorldVistA/VistA](https://github.com/WorldVistA/VistA)** —
  the canonical community source tree
- **[github.com/OSEHRA](https://github.com/OSEHRA)** — organization with
  test tooling, community VistA instances, documentation
- **[github.com/shabiel](https://github.com/shabiel)** — Sam Habiel; authored
  XPDK2VC, actively maintains community tooling
- **[github.com/ChristopherEdwards/M-Unit](https://github.com/ChristopherEdwards/M-Unit)** —
  M-Unit testing framework fork (most active)
- **[WorldVistA Hardhats mailing list](https://groups.google.com/g/Hardhats)** —
  community Q&A
- **[OSEHRA forum](https://www.osehra.org/)** — community hub
- **[VA Documentation Library (VDL)](https://www.va.gov/vdl/)** — per-package
  manuals (VA-authored)
- **[vivian.worldvista.org/dox/](https://vivian.worldvista.org/dox/)** —
  auto-generated cross-reference docs (XINDEX-based)
- **[docs.yottadb.com](https://docs.yottadb.com/)** — YottaDB reference
  including Python bindings
- **[intersystems-iris](https://docs.intersystems.com/)** — IRIS docs
- **Kevin O'Kane, *Introduction to the Mumps Language*** — the book the
  user mentions; widely available; learns the language in a weekend
- **vista-meta** (this project) — contains all cross-references used in
  this guide; run `make help` for available tooling

---

## 12. The single-paragraph summary

**VistA is not hard because MUMPS is hard. It's hard because the
architecture has grown for 40+ years without the ecosystem that modern
languages take for granted — no automated linter, no type system, no
package manager in the modern sense, no IDE refactoring, no test-first
culture, no rollback. The way in is (a) understand packages as shared
namespaces rather than isolated modules, (b) use the code-model artifacts
from vista-meta to answer cross-package questions mechanically, (c) write
new code in a small package you understand, using AI assistance plus
XINDEX plus M-Unit, (d) ship via kids-vc rather than hand-crafted KIDS
builds. A competent Python programmer can be productive on a small VistA
task within two weeks and substantially productive within three months,
provided they accept that most of the Python ecosystem has no equivalent
and learn to work around the gaps rather than mourn them.**

---

## References

- [code-model-guide.md](code-model-guide.md) — the VistA code-model
  artifacts this guide references
- [kids-vc-guide.md](kids-vc-guide.md) — using kids-vc
- [kids-vc-background-dev.md](kids-vc-background-dev.md) — history,
  SKIDS/XPDK2VC prior art, development chronology
- [xindex-reference.md](xindex-reference.md) — XINDEX catalog
- [piks-analysis-guide.md](piks-analysis-guide.md) — data-model side
  (FileMan file PIKS classification)
- [vista-meta-spec-v0.4.md](vista-meta-spec-v0.4.md) §11 — research
  methodology
- [ADR-045](adr/045-data-code-separation-package-bridge.md) — why code and
  data are classified separately
- [ADR-046](adr/046-kids-vc-undo-pre-install-snapshot.md) — proposed
  Phase 9 KIDS undo
- [RESEARCH.md](../vista/export/RESEARCH.md) — research findings log
  (RF-001 through RF-033+)
