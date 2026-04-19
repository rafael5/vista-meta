# XINDEX reference — metrics, parameters, output surfaces

Catalog of everything XINDEX (VistA's own static analyzer, Toolkit
patch XT*7.3*158, Enhanced flavor via OSEHRA/WorldVistA) produces.
Written 2026-04-19 during Phase 6 closure of ADR-045.

Purpose: document what a future Phase 7+ could extract from XINDEX
instead of our regex-based Phase 3a / 5 / 5b scans. XINDEX is a real
MUMPS parser, not a regex; its output is richer and more accurate
than anything we've produced so far, but it requires running XINDEX
across the corpus first.

## 1. What XINDEX is

- **Name**: INDEX & CROSS-REFERENCE (Toolkit namespace XT)
- **Primary routine**: `XINDEX` → `G ^XINDX6` (goto XINDX6 which
  handles interactive setup)
- **Supporting routines**: `XINDX1` through `XINDX13`, plus satellites
  `XINDX52`, `XINDX53`
- **Source**:
  `/opt/VistA-M/Packages/Toolkit/Routines/XIND*.m` (17 routines)
- **Symlinked into**: `/opt/VistA-M/r/XIND*.m`
- **Patch lineage in VEHU**: XT*7.3*{20,27,48,61,66,68,110,121,128,
  132,133,148,151,153,155,158}. The 155/158 patches bring Enhanced
  XINDEX extensions to cover FileMan Sort Templates, Input Transforms,
  Screens. ADR-017 documents our reliance on this.
- **Runtime model**: interactive via terminal device, prompts user
  for routine list and options; also callable non-interactively by
  seeding `^UTILITY($J,"RTN",...)` and entering at `ALIVE^XINDEX`.

## 2. Runtime parameters (INP array)

All prompts set `INP(N)` values:

| INP | Prompt | Values |
|---|---|---|
| INP(1) | Print more than compiled errors and warnings? | Y/N |
| INP(2) | Print routines? | Y/N — print source with errors |
| INP(3) | Print errors and warnings with each routine? | Y/N |
| INP(4) | Print DDs/Functions/Options/other package code? | Y/N |
| INP(5) | Print (R)egular, (S)tructured, (B)oth, control (F)low? | R/S/B/F |
| INP(6) | Print summary only? | Y/N |
| INP(7) | **Save parameters in ROUTINE file?** | **Y/N** (writes File 9.8 subfiles) |
| INP(8) | Index all called routines? | Y/N |
| INP(9) | Include compiled template routines? | Y/N |
| INP(10) | Build/Package file DA | 9.4/9.6/9.7 or NAMESPACE |
| INP(11) | Execute-check for version number on line 2 | M code string |
| INP(12) | Patch number check executable | M code string |

The parameter of interest for analytical use is **INP(7)**. With
INP(7)=Y and DUZ defined, XINDEX writes its findings into File 9.8
(ROUTINE) subfiles — the persistent output the rest of VistA can
later read.

## 3. Error/warning codes — the full catalog

XINDEX classifies 66 distinct issues across four severity levels:

**Severity legend**: F = Fatal, S = Standard (SAC violation), W = Warning, I = Info.

Source: `ERROR` label in `XINDX1`, patches through p153.

| Code | Severity | Description |
|---|---|---|
| 1 | F | UNDEFINED COMMAND (rest of line not checked) |
| 2 | F | Non-standard (Undefined) 'Z' command |
| 3 | F | Undefined Function |
| 4 | F | Undefined Special Variable |
| 5 | F | Unmatched Parenthesis |
| 6 | F | Unmatched Quotation Marks |
| 7 | F | ELSE Command followed by only one space |
| 8 | F | FOR Command did not contain '=' |
| 9 | I | QUIT Command followed by only one space |
| 10 | F | Unrecognized argument in SET command |
| 11 | W | Invalid local variable name |
| 12 | W | Invalid global variable name |
| 13 | W | Blank(s) at end of line |
| 14 | F | Call to missing label 'X' in this routine |
| 15 | W | Duplicate label (M57) |
| 16 | F | Error in pattern code |
| 17 | W | First line label NOT routine name |
| 18 | W | Line contains a CONTROL (non-graphic) character |
| 19 | S | Line is longer than 245 bytes |
| 20 | S | View command used |
| 21 | F | General Syntax Error |
| 22 | S | Exclusive Kill |
| 23 | S | Unargumented Kill |
| 24 | S | Kill of an unsubscripted global |
| 25 | S | Break command used |
| 26 | S | Exclusive or Unargumented NEW command |
| 27 | S | $View function used |
| 28 | S | Non-standard $Z special variable used |
| 29 | S | 'Close' command should be invoked through 'D ^%ZISC' |
| 30 | S | LABEL+OFFSET syntax |
| 31 | S | Non-standard $Z function used |
| 32 | S | 'HALT' command should be invoked through 'G ^XUSCLEAN' |
| 33 | S | Read command doesn't have a timeout |
| 34 | S | 'OPEN' command should be invoked through ^%ZIS |
| 35 | S | Routine exceeds SACC maximum size of 20000 |
| 36 | S | Should use 'TASKMAN' instead of 'JOB' command |
| 37 | F | Label is not valid |
| 38 | F | Call to this label is broken |
| 39 | S | Kill of a protected variable |
| 40 | S | Space where a command should be |
| 41 | I | Star or pound READ used |
| 42 | W | Null line (no commands or comment) |
| 43 | F | Invalid or wrong number of arguments to a function |
| 44 | S | 2nd line of routine violates the SAC |
| 45 | S | Set to a '%' global |
| 46 | F | Quoted string not followed by a separator |
| 47 | S | Lowercase command(s) used in line |
| 48 | F | Missing argument to a command post-conditional |
| 49 | F | Command missing an argument |
| 50 | S | Extended reference |
| 51 | F | Block structure mismatch |
| 52 | F | Reference to routine that isn't in this UCI |
| 53 | F | Bad Number |
| 54 | S | Access to SSVN's or $SYSTEM restricted to Kernel |
| 55 | S | Violates VA programming standards |
| 56 | S | Patch number missing from second line |
| 57 | S | Lower/Mixed case Variable name used |
| 58 | S | Routine code exceeds SACC maximum size of 15000 |
| 59 | F | Bad WRITE syntax |
| 60 | S | Lock missing Timeout |
| 61 | S | Non-Incremental Lock |
| 62 | S | First line of routine violates the SAC |
| 63 | F | GO or DO mismatch from block structure (M45) |
| 64 | F | Cache Object doesn't exist |
| 65 | W | Vendor specific code is restricted |
| 66 | S | Incorrect format for ICR Reference |

Some codes have exclude lists (e.g., `X,Z,DI,DD,KMP` — errors don't
fire against these namespace prefixes). Stored as the 3rd `;`-piece
of each error-text line.

## 4. Scratch-global output (`^UTILITY($J,...)`)

During an XINDEX run, per-routine intermediate data is stored in the
process-scoped scratch global. This is the richest, most direct
output surface — everything XINDEX computes passes through here.

| Path | Content |
|---|---|
| `^UTILITY($J,1,RTN,0,0)` | Line count of routine RTN |
| `^UTILITY($J,1,RTN,0,N,0)` | Source line N (raw text) |
| `^UTILITY($J,1,RTN,"RSUM")` | RSUM checksum (format `B<hash>` from `$$SUMB^XPDRSUM`) |
| `^UTILITY($J,1,RTN,"E",0)` | Error count for RTN |
| `^UTILITY($J,1,RTN,"E",N)` | Error N — text block: `line_text<TAB>LAB+offset<TAB>severity-and-text` |
| `^UTILITY($J,1,RTN,"T",LAB)` | Tag/label LAB — definition metadata |
| `^UTILITY($J,1,RTN,"L",LAB)` | Label LAB — line number location |
| `^UTILITY($J,1,RTN,"P",LAB)` | Label's properties (entry-point info, p158) |
| `^UTILITY($J,1,RTN,"X",REF)` | External cross-reference — routine/tag RTN calls |
| `^UTILITY($J,1,RTN,"I",T)` | Invoked items at label T |
| `^UTILITY($J,1,RTN,"COM",N)` | Line N's command breakdown (command, args) |
| `^UTILITY($J,1,"***",LOC,S)` | Consolidated cross-refs across ALL routines in the run. `LOC` ∈ {G=global, L=local, T=tag, X=external}; S = referenced name. |

Keys to notice:
- The `"X"` subtree is the **real call graph** with MUMPS-parser
  accuracy — catches comma-continuation, indirection, `D @X`
  patterns that our Phase 5 regex misses (T-003 relevance).
- `"COM"` holds per-line command/argument tokenization — much
  richer than anything regex can produce.
- `"T"/"L"/"P"` together give the complete label/tag inventory
  per routine — entry points, line offsets, exit types.
- `"***"` is the cross-corpus rollup. Reading it after a bulk
  XINDEX run gives the full inverse call graph in one structure.

## 5. Persistent File 9.8 writes (when INP(7)=Y)

When the user answers "save parameters in ROUTINE file" with Y and
DUZ is defined, `XINDX53` propagates the scratch-global data into
persistent File 9.8 records. The fields updated:

Top-level fields (0-node):
- `1.2 SIZE (BYTES)` — byte size of the routine
- `1.4 DATE OF %INDEX RUN` — timestamp of the XINDEX run
- `1.5 RSUM VALUE` — routine checksum (hash)
- `1.6 RSUM DATE` — when the RSUM was computed
- `2 DESCRIPTION` (word-processing) — free-text comments
- `2.1 BRIEF DESCRIPTION` (multiple) — short summaries
- `4 PARAMETERS (IN/OUT)` — routine parameter metadata
- `7.1 CHECKSUM DATE` / `7.2 CHECKSUM VALUE` / `7.3 PATCH LIST AT
  CHECKSUM TIME` — KIDS-grade checksums

Multiples (subfiles):

| Field | Subfile | Fields in subfile | Purpose |
|---|---|---|---|
| 5 TAG | 9.801 | `.01 TAG`, `1 EXPLANATION`, `2 SUPPORTED ENTRY POINT`, `3 FOUND BY %INDEX` | Every label in the routine, with support classification. |
| 8 PATCH | 9.818 | (patch metadata) | KIDS-assigned patches |
| 19 ROUTINE INVOKED | 9.803 | `.01 ROUTINE INVOKED`, `3 FOUND BY %INDEX` | Routines this routine calls — the outbound call list. |
| 20 INVOKED BY | 9.804 | `.01 INVOKED BY`, `3 FOUND BY %INDEX` | Routines that call this routine — the inbound call list. |
| 21 VARIABLES | 9.805 | `.01 VARIABLES`, `2 CHANGED OR KILLED`, `3 FOUND BY %INDEX` | Local variables referenced, with SET/KILL flag. |
| 22 GLOBALS | 9.806 | `.01 GLOBALS`, `1 EXPLANATION`, `3 FOUND BY %INDEX` | Globals referenced by the routine. |
| 2.1 BRIEF DESCRIPTION | 9.808 | (brief-desc fields) | Short text summaries |
| 9 DEV PATCH | 9.819 | `.01 Dev Patch`, `2 Dev Checksum`, `3 Dev Patch List` | Developer patch metadata |

The `3 FOUND BY %INDEX` flag on each subfile row records whether the
entry was auto-generated by XINDEX (vs. manually entered). This is
the key provenance marker.

## 6. VEHU File 9.8 population state (2026-04-19)

Current VEHU instance has File 9.8 largely empty of XINDEX-generated
data:
- 30,665 top-level entries (names known)
- 34/30,665 rows with `1.2 SIZE (BYTES)`
- 24/30,665 rows with `7.2 CHECKSUM VALUE`
- 0 rows with `1.5 RSUM VALUE`
- **27 routines with ≥1 ROUTINE INVOKED (19) subfile entry**
- **21 routines with ≥1 INVOKED BY (20) subfile entry**
- **0 routines with ≥1 TAG (5) subfile entry**
- **0 routines with ≥1 VARIABLES (21) subfile entry** (not verified
  but expected empty)
- **0 routines with ≥1 GLOBALS (22) subfile entry** (expected)

The bake sentinel confirms: the `xindex` phase is still `"status":
"pending"` (see `vista/export/.vista-meta-initialized`). XINDEX has
not been run batch-wide with `INP(7)=Y` against this VEHU. ADR-018
says the first-run bake should trigger it, but it hasn't.

## 7. How DOX (vivian.worldvista.org/dox/) uses XINDEX

ADR-043 dropped DOX from the project, but it's worth documenting
what DOX surfaces so we know what's comparable.

DOX is **generated from XINDEX output + FileMan DD extraction**, but
uses only a subset:

What DOX surfaces per routine:
- First-line header comment (from routine source, not XINDEX)
- Caller Graph PNG (Graphviz, from XINDEX `"X"` rollup data)
- Entry Points table with comments and DBIA/ICR references
- Interaction Calls (WRITE/READ prompt locations)
- Used in RPC table (from File 8994)
- FileMan Files Accessed via FileMan Db Call

What DOX **discards** from XINDEX's actual output:
- All 66 error/warning codes and severity breakdowns
- Per-line error diagnostics
- Line counts, byte sizes, checksums, RSUM values
- File 9.8 subfile data (ROUTINE INVOKED, INVOKED BY, VARIABLES,
  GLOBALS) — at least in the per-page view
- TAG classification (Supported Entry Point flag)
- Any aggregate "routines by error count" or "most Fatal errors"
  index page

DOX uses XINDEX primarily as a **call-graph data source**. The
diagnostic surface that XINDEX is actually designed for is not
exposed by DOX.

## 8. Comparison vs. our ADR-045 regex extractions

| Our artifact | Phase | XINDEX equivalent | Accuracy gap |
|---|---|---|---|
| routine-calls.tsv | 5 | `^UTILITY($J,1,RTN,"X",…)` + File 9.8 subfiles 19/20 | XINDEX catches comma-continuation, `D @X` indirection, `D TAG+N^ROU` offsets our regex misses. 14,658 "truly unreferenced" (T-003) would shrink. |
| routine-globals.tsv | 3a | `^UTILITY($J,1,RTN,"X",…)` with LOC="G" + File 9.8 subfile 22 | XINDEX catches bare globals (`K ^FOO`), naked references `^(N)`, and extended references `^|pkg|NAME` — all missed by our regex MVP. |
| protocol-calls.tsv | 5b | Not directly — XINDEX doesn't natively scan File 101 ENTRY ACTION, only `.m` source | Our regex-based extraction remains the approach here. |
| routines-comprehensive.tsv | 6b | Much of it derivable from File 9.8 + subfiles once populated | Would gain: severity-graded error counts per routine, SACC violation counts, checksum change detection. |

**Bottom line**: XINDEX is a strict upgrade to Phase 3a and Phase 5's
data accuracy. Phase 4 (FileMan metadata) and Phase 5b (protocol
parsing) stand on their own — XINDEX doesn't help there.

## 9. How to run XINDEX for analytical capture

Two paths documented in the VEHU source:

**Path A — interactive, full parameters, save to File 9.8**:
```
D ^XINDEX
  → answer the ~12 prompts
  → answer "Save parameters in ROUTINE file? Y"
  → choose "A" (all routines) or "P" (package) at ASKRTN
```
Result: File 9.8 subfiles populated, can be queried afterwards via
our existing VMDUMP98.m pattern + new VMDUMP98-subfiles.

**Path B — non-interactive, scratch-global capture**:
```
; Seed the routine list
S ^UTILITY($J,"RTN","MYROUTINE")=""
; Set minimal INP parameters
S INP(1)=0,INP(2)=0,INP(3)=0,INP(4)=0,INP(5)="R",INP(6)=1
S INP(7)=0,INP(8)=0,INP(9)=0,INP(10)=0
; Enter the indexer
D ALIVE^XINDEX
; Then read ^UTILITY($J,1,…) to extract findings
K ^UTILITY($J)   ; cleanup
```
Result: `^UTILITY($J,...)` populated with per-routine findings; must
read and emit to TSV before the job ends (scratch is job-scoped).

Path A is simpler for a one-time bake; Path B is better for
automated extraction we can re-run.

**ADR-018's bake phase** is designed to be Path A via TaskMan —
launches XINDEX in a TM job that runs to completion in the
background. Re-running `make bake-xindex` would trigger that.

## 10. Why this hasn't happened yet in our project

Three reasons, in order:

1. **Bake is first-run-only** — the sentinel logic skips re-bake if
   the file exists, even with phases=pending. The first-run bake
   launched XINDEX and apparently completed or crashed before
   reaching save-to-File-9.8 (INP(7) defaults to N in non-interactive
   flow). ADR-023 says "continue on error" so errors don't abort.
2. **`make bake-xindex` hasn't been manually run** — per ADR-018
   this is the refresh path, and we haven't exercised it.
3. **The existing Phase 4a VMDUMP98 extraction already got us the
   NAME + TYPE columns** which was sufficient for RF-016's cross-
   reference against MANIFEST. The enriched subfile data wasn't
   needed for any ADR-045 phase as scoped.

## 11. Candidate next steps (if the user wants to pursue)

**Short path — make bake-xindex + VMDUMP98 extensions**:
1. `make bake-xindex` to populate File 9.8 across 30k+ routines
2. Extend VMDUMP98 to emit additional TSVs for subfiles:
   - `vista-file-9-8-invoked.tsv` (field 19, subfile 9.803)
   - `vista-file-9-8-invoked-by.tsv` (field 20, subfile 9.804)
   - `vista-file-9-8-variables.tsv` (field 21, subfile 9.805)
   - `vista-file-9-8-globals.tsv` (field 22, subfile 9.806)
3. Cross-check these against routine-calls.tsv and
   routine-globals.tsv to quantify T-003's "truly unreferenced"
   cohort reduction.

**Longer path — errors extract**:
Error-by-error extraction per routine (via scratch global `"E"`
subtree) would give a code-quality heatmap across all 39,330
routines: which routines have the most Fatal/Standard violations,
SACC size-limit breaches, missing-timeout risks, etc. Useful for any
cleanup prioritization — per ADR-045's "code-side classification"
intent.

**Reference for either path**: this document. Subfile structure is
stable across VistA patches since XT*7.3 baseline.
