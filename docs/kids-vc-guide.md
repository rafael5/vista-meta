# kids-vc — User Guide

**Purpose**: Put VistA KIDS distribution files under git version control.
Decompose `.KID` patches into per-component files you can diff, review,
branch, and merge. Reassemble back to `.KID` for deployment.

**Audience**: VistA developers, site IRMs, patch maintainers, and anyone
working with `.KID` artifacts in source control.

**Current state**: stable for `WorldVistA/VistA` flavor. Validated at
scale — 100.00% round-trip pass on 2,406 real KIDS patches
(3,566,277 subscripts). Full test results in §10.

For the history of how kids-vc was built, see
**[kids-vc-background-dev.md](kids-vc-background-dev.md)**. For the KIDS
installation process itself, see
**[code-model-guide.md §3.3](code-model-guide.md#33-install)**.

---

## Quick start

### Install

Installable as a pip package:

```bash
# From the vista-meta checkout
make kids-vc-pip-install
# → creates /tmp/kidsvc-venv with `kids-vc` and `kids-vc-merge` on PATH

# Or manually
python3 -m venv /tmp/kidsvc-venv
/tmp/kidsvc-venv/bin/pip install -e kids_vc_pkg/
```

Published to PyPI as `kids-vc` (pending user authorization).

### First run

```bash
# Parse any .KID file to see its shape
kids-vc parse OR_3.0_484.KID

# Decompose for version control
kids-vc decompose OR_3.0_484.KID ./patches/

# Verify round-trip (decompose → assemble → compare)
kids-vc roundtrip OR_3.0_484.KID

# Reassemble back into a .KID file
kids-vc assemble ./patches/ rebuilt.KID
```

---

## Commands

### `parse` — summarize a KIDS file

```bash
kids-vc parse path/to/patch.KID
```

Prints the builds contained, subscript counts by section type. Useful
for quick inspection without materializing a directory.

Sample output:
```
install_names: ['OR*3.0*484']
  build OR*3.0*484: 104 subscripts
    BLD      51
    INIT     1
    MBREQ    1
    PKG      6
    QUES     35
    RTN      9
    VER      1
```

### `decompose` — split .KID into per-component files

```bash
kids-vc decompose path/to/patch.KID path/to/output-dir/
```

Produces a directory tree under `output-dir/<PATCH-NAME>/KIDComponents/`
with one file per logical component. Layout:

```
OR_3.0_484/KIDComponents/
├── Build.zwr                      # BLD section (metadata)
├── Package.zwr                    # PKG section
├── KernelFMVersion.zwr            # VER section
├── EnvironmentCheck.zwr           # PRE section (env check routine)
├── PreInit.zwr                    # INI section
├── PostInstall.zwr                # INIT section
├── RequiredBuild.zwr              # MBREQ section
├── InstallQuestions.zwr           # QUES section
├── TransportGlobal.zwr            # TEMP section (if present)
├── ORD.zwr                        # Dependency-order markers
│
├── Routines/
│   ├── _index.zwr                 # ("RTN",) count node
│   ├── ORY484.header              # routine header node
│   └── ORY484.m                   # routine source (line-2 canonicalized)
│
├── Files/
│   └── 2+PATIENT/                 # per-FileMan-file directory
│       ├── DD.zwr                 # field definitions
│       ├── Data.zwr               # seed data (if present)
│       └── DD-code/               # MUMPS extracted from DD (informational)
│           ├── _README.md
│           └── <field>.input-transform.m
│
└── KRN/
    ├── _misc.zwr                  # string-keyed KRN entries
    ├── OPTION/
    │   ├── FileHeader.zwr         # file header + cross-refs
    │   └── <OPTION-NAME>.zwr      # per-option files
    ├── PROTOCOL/
    ├── REMOTE-PROCEDURE/
    ├── SECURITY-KEY/
    └── ...                        # other Kernel files (HL7-APPLICATION, etc.)
```

**Why this layout**: mirrors XPDK2VC's proven decomposition (Sam Habiel,
OSEHRA, 2014-2020). Each per-component file is human-readable and
git-diffable.

### `assemble` — rebuild .KID from decomposed tree

```bash
kids-vc assemble path/to/decomposed-dir/ path/to/output.KID
```

Walks every component file under `decomposed-dir/` and serializes back
to KIDS text format. The output is installable via normal KIDS tooling
(`D ^XPDNTEG`, etc.).

**Guarantee**: decompose → assemble → parse is **byte-semantic-equal**
to the original (after line-2 canonicalization). Verified across 2,406
real WorldVistA patches.

### `roundtrip` — verify decompose + assemble preserves content

```bash
kids-vc roundtrip path/to/patch.KID
```

Runs decompose → assemble → re-parse in a temporary directory and
compares canonicalized pair sets. Prints `PASS` or `FAIL` with a diff
sample.

Return code: 0 for PASS, 1 for FAIL.

Useful for:
- Regression testing when modifying kids-vc
- Validating a patch against your kids-vc version before committing
- CI pipelines (see §7)

### `canonicalize` — IEN substitution for cross-instance diffing

```bash
kids-vc canonicalize path/to/decomposed-dir/
```

**LOSSY operation.** Rewrites all `.zwr` files under the given
decomposed directory, substituting integer IENs at known positions with
the literal string `"IEN"`.

Positions substituted:
- `("BLD", <int>, ...)` at position 1 (build IEN)
- `("KRN", <numeric>, <int>, ...)` at position 2 (entry IEN)

**Use case**: cross-instance diff stability. If site A and site B both
install the same patch and each runs `decompose + canonicalize`, their
output directories will be byte-identical when the patch content is
semantically identical — no noise from install-time IEN assignments.

**Trade-off**: after canonicalization, the original IEN values are lost.
Assembling from a canonicalized tree produces a `.KID` with the literal
string `"IEN"` as a subscript, which IS NOT INSTALLABLE by KIDS. Only
use canonicalize for diff/review; keep a non-canonicalized copy for
installation.

Default round-trip does NOT apply canonicalization — run it explicitly
when needed.

### `kids-vc-merge` — git merge driver for ZWR files

```bash
kids-vc-merge <base.zwr> <ours.zwr> <theirs.zwr>
```

Entry-level 3-way merge for ZWR files. Writes result to `ours.zwr`
(git's merge-driver convention). Exit 0 on clean merge, 1 on conflict.

**Install as git driver** for a repo that tracks decomposed kids-vc
output:

```bash
# From the vista-meta checkout
make zwr-merge-install
```

Equivalent to:

```bash
echo '*.zwr merge=zwr' >> .gitattributes
git config merge.zwr.name "ZWR entry-level 3-way merge"
git config merge.zwr.driver "/usr/bin/python3 /path/to/zwr_merge.py %O %A %B"
```

**Why needed**: git's default line-based 3-way merge is destructive for
ZWR. Adjacent entries in a `.zwr` file are semantically independent
(different subscripts), but line-based merge treats a conflict in
entry A as blocking entry B. kids-vc-merge parses each side by
subscript key and merges entry-by-entry.

Behavior:
- Non-overlapping edits → clean (both preserved)
- Identical edits → clean (agreed value)
- Conflicting modify-modify → git-style `<<<<<<< ours`/`=======`/
  `>>>>>>> theirs` markers
- Addition by one side → clean
- Deletion by one side → clean
- Delete-vs-modify → conflict

---

## Python API

For programmatic use after `pip install kids-vc`:

```python
from pathlib import Path
import kids_vc

# Parse
parsed = kids_vc.parse_kid(Path("OR_3.0_484.KID"))
# → {"install_names": [...], "builds": {name: {subs: value, ...}}}

# Decompose one build
for name, build in parsed["builds"].items():
    kids_vc.decompose_build(build, Path(f"./patches/{name}/KIDComponents"))

# Assemble
pairs = kids_vc.assemble_build(Path("./patches/OR_3.0_484/KIDComponents"), "OR*3.0*484")

# Round-trip
rc = kids_vc.roundtrip(Path("OR_3.0_484.KID"))  # 0 on PASS

# Canonicalize
stats = kids_vc.canonicalize_iens(Path("./patches/OR_3.0_484/KIDComponents"))
# → {"BLD": <count>, "KRN": <count>}

# Line-2 canonicalization primitive
clean = kids_vc.canonicalize_routine_line2(";;3.0;ORDER ENTRY/RESULTS REPORTING;**484**;...")
# → ";;3.0;ORDER ENTRY/RESULTS REPORTING;;"

# ZWR merge
from kids_vc.merge import merge
result, has_conflict = merge(base_path, ours_path, theirs_path)
```

Also exposed: `WELL_KNOWN_FILES` (dict mapping FileMan file numbers to
directory names), `_parse_zwr_line`, `_format_subscript`, `_zwr_line`
(ZWR format primitives).

---

## Features

### Decomposition coverage

kids-vc handles the full KIDS component matrix:

| KIDS section | Decomposition |
|---|---|
| BLD | `Build.zwr` (single file) |
| PKG | `Package.zwr` |
| VER | `KernelFMVersion.zwr` |
| PRE | `EnvironmentCheck.zwr` |
| INI | `PreInit.zwr` |
| INIT | `PostInstall.zwr` |
| MBREQ | `RequiredBuild.zwr` |
| QUES | `InstallQuestions.zwr` |
| TEMP | `TransportGlobal.zwr` |
| ORD | `ORD.zwr` |
| RTN | `Routines/<name>.{header,m}` per routine + `_index.zwr` |
| KRN | `KRN/<FileName>/<EntryName>.zwr` per entry + `FileHeader.zwr` + `_misc.zwr` |
| FIA / ^DD / ^DIC / SEC / UP / IX / KEY / KEYPTR / PGL | `Files/<fnum>+<name>/DD.zwr` per FileMan file |
| DATA / FRV1 / FRVL / FRV1K | `Files/<fnum>+<name>/Data.zwr` per file |
| (anything else) | `_misc.zwr` catch-all |

### Diff-stability techniques

Two canonicalizations applied automatically on decompose to reduce
git-diff noise from install-time volatility:

1. **Line-2 patch-list strip**: Routine line 2
   `;;VERSION;PACKAGE;**patches**;BUILD_DATE;Build N` → `;;VERSION;PACKAGE;;`.
   Removes patch list (piece 5), build date (piece 6), Build N (piece 7+)
   — all volatile on every install.

2. **Line-2 Build N strip** (inherited from XPDK2VC): the "DO NOT INCLUDE
   BUILD NUMBER YOU STUPID IDIOT" fix from XPDK2V0.m line 33, extended.

IEN substitution is OPT-IN via `canonicalize` command (see above).

### Well-known file-number mapping

24 FileMan file numbers mapped to human-readable directory names:

```
.4 → PRINT-TEMPLATE      .401 → SORT-TEMPLATE
.402 → INPUT-TEMPLATE    .403 → FORM
.404 → BLOCK             3.7 → DEVICE
3.8 → MAIL-GROUP         3.9 → MAIL-MESSAGE
9.2 → HELP-FRAME         9.4 → PACKAGE
9.6 → KIDS-BUILD         9.7 → KIDS-INSTALL
9.8 → ROUTINE            19 → OPTION
19.1 → SECURITY-KEY      19.2 → OPTION-SCHEDULING
100 → ORDER              101 → PROTOCOL
101.41 → DIALOG          2 → PATIENT
200 → NEW-PERSON         771 → HL7-APPLICATION
870 → HL-LOGICAL-LINK    871 → HL-FILE-EVENT
872 → HL-LOWER-LEVEL-PROTOCOL
8989.51 → PARAMETER-DEFINITION
8989.52 → PARAMETER-TEMPLATE
8993 → RPC-BROKER-SUBSCRIBER
8994 → REMOTE-PROCEDURE
```

Unknown file numbers fall back to `file-<n>/`.

### DD-embedded MUMPS extraction

When decomposing FileMan files (FIA), kids-vc also extracts MUMPS code
embedded in `^DD` nodes into per-field `.m` annotation files under
`Files/<fnum>+<name>/DD-code/`:

- `<field>.input-transform.m` — 0-node piece 5 (validation MUMPS)
- `<field>.computed.m` — type-C field expression
- `<field>.computed-wp.m` — `,9,N,0` word-processing code
- `<field>.xref-<ien>.xref-set.m` — cross-reference SET logic
- `<field>.xref-<ien>.xref-kill.m` — cross-reference KILL logic

A `_README.md` in each DD-code/ explains: `DD.zwr` remains authoritative
for round-trip; `.m` files are INFORMATIONAL — assembly ignores them.

This surface has no prior-art equivalent. Neither SKIDS nor XPDK2VC
extracted DD-embedded MUMPS.

### Round-trip integrity

Every invocation of `decompose + assemble` preserves semantic content.
Verified via:
- 5 regression fixtures (synthetic + real)
- 2,406 production WorldVistA patches
- 6 XPDK2VC structural-contract tests

Canonicalization (line-2 strip) means byte-identical round-trip isn't
possible — but the CANONICAL content is byte-identical after
re-decomposing.

---

## What kids-vc does NOT do

Important limitations. Read before assuming.

### Not an installer or uninstaller

kids-vc produces `.KID` files from decomposed source. It does NOT:
- Install patches into a running VistA (use `D ^XPDNTEG` / KIDS)
- Uninstall patches (there's no native VistA uninstall — see
  [ADR-046](adr/046-kids-vc-undo-pre-install-snapshot.md) for a
  proposed Phase 9 that addresses this partially)
- Run environment checks or pre-install / post-install MUMPS
- Modify any live VistA state

kids-vc is a TEXT-LEVEL tool that runs on `.KID` files and decomposed
trees. Pure Python stdlib. Does not require a running VistA.

### Not a merge-conflict resolver

kids-vc-merge produces git-style conflict markers in ZWR files. It does
NOT auto-resolve semantic conflicts. If two branches modify the same
option's menu text differently, you get conflict markers; you resolve
manually and re-commit.

### Canonicalized IENs are not installable

Output of `canonicalize` has `"IEN"` as a string subscript. That's for
diff stability, not deployment. A canonicalized `.zwr` cannot be fed
back through assemble → install. Keep a non-canonicalized copy for
deployment.

### Does NOT track pre-install state

kids-vc operates on `.KID` files. If you want to capture the state of a
running VistA BEFORE installing a patch (for rollback), that's
[ADR-046](adr/046-kids-vc-undo-pre-install-snapshot.md)'s territory.
Current kids-vc has no in-VistA hook.

### FileMan data section: flat only

`DATA` and `FRV*` sections produce a flat `Data.zwr` per file. No
per-record decomposition. Merging seed data between branches via
kids-vc-merge works per subscript but doesn't understand FileMan record
boundaries.

### DD-code extraction is informational only

The `.m` files under `DD-code/` are INFORMATIONAL — for humans to read
and diff. Assembly ignores them. Edits to `DD-code/` files do NOT
propagate back to `DD.zwr` on assembly. Make changes in `DD.zwr`.

### Pre/post-install MUMPS is not reverse-engineered

When a patch ships pre-install or post-install MUMPS, kids-vc captures
it verbatim as ZWR content. It does NOT analyze what the MUMPS does.
Imperative install-time effects (data transformations, MailMan messages,
`^XTMP` scratch operations) are invisible to kids-vc.

### Not VistA-flavor-universal — yet

Tested and verified at 100% pass on **WorldVistA/VistA master**. Shared
lineage suggests OSEHRA FOIA, VA-Office-EHR, and VA production should
work, but they're untested. RPMS (IHS) may have divergent KIDS
conventions; untested.

### No PyPI distribution yet

The package is `pip install -e`-able from the vista-meta checkout.
Public PyPI publication (`python -m build` + `twine upload`) is gated
on user authorization and not yet executed.

### Uses `^XTMP` retention window for any future undo

ADR-046's proposed Phase 9 undo would use `^XTMP("KVC-UNDO",...)` for
pre-install snapshots. `^XTMP` auto-cleanup after 90 days means undos
would only work within that window. Not built yet.

---

## Testing and validation

kids-vc passed extensive validation before being called "working". All
of this is reproducible from the vista-meta checkout.

### 1. Round-trip regression suite — 5 fixtures, 100% PASS

Five fixtures committed as test baselines:
- `VMTEST_1_0_1.kid` (synthetic, 23 subscripts — original MVP fixture)
- `VMDD_1_0_1.kid` (synthetic, 25 subscripts, exercises DD-embedded MUMPS)
- `OR_3_0_484.kid` (real, 104 subscripts — Order Entry parameter)
- `DG_5_3_853.kid` (real, 566 subscripts — Veterans Transportation System)
- `XU_8_0_504.kid` (real, 257 subscripts — KAAJEE Kernel)

**Reproduce**: `make kids-vc-all`

### 2. WorldVistA corpus — 2,406 patches, 100.00% PASS

**The decisive validation.** Fetched every `.KID` file from
`github.com/WorldVistA/VistA` master and verified round-trip on each.

**Corpus stats**:
- 2,406 KIDS patches (10+ years of community contribution)
- 3,566,277 total subscripts across all patches
- ~56 seconds to run the full round-trip suite on cached files
- ~2 minutes cold (including download)

**Initial pass rate was 91.15%.** Corpus testing surfaced four
silent-data-loss bugs that the 5-fixture regression suite missed:

| Fix | Pass rate after | Patches salvaged |
|---|---|---|
| SEC/UP entries keyed by string at subs[1] | 98.21% | +170 |
| Zero-line routine phantom empty line | 99.50% | +31 |
| PARAMETER (8989.5) piece-1-is-storage-spec | 99.96% | +11 |
| Filename collision post-sanitization | 100.00% | +1 |

**Final: 100.00%** (all 2,406 patches round-trip cleanly).

Corpus harness also functions as a regression-prevention tool: any
future change to kids-vc can be validated against 2,406 real cases.

**Reproduce**: `make kids-vc-corpus` (full, ~2 min) or
`make kids-vc-corpus-cached` (cached, ~1 min).

### 3. XPDK2VC structural contracts — 6/6 PASS

Six structural behavioral contracts that kids-vc must honor to be
XPDK2VC-compatible:

| Contract | Status |
|---|---|
| Simple-section filenames (Build.zwr, Package.zwr, etc.) match XPDK2VC GENOUT naming | PASS |
| RTN split into `.header` + `.m` with line-2 canonicalized | PASS |
| FIA produces per-file `Files/<fnum>+<name>/` directories | PASS |
| KRN produces per-file / per-entry `KRN/<FileName>/<EntryName>.zwr` | PASS |
| Round-trip semantic preservation across all fixtures | PASS |
| IEN canonicalization available (XPDK2VC SUBNAME equivalent) | PASS |

**Why structural contracts instead of live differential testing**:
running XPDK2VC live in our VEHU container is blocked by runtime issues
(`%ZISH` silently failing — see [code-model-guide.md §3.1](code-model-guide.md#31-develop)).
The 100% corpus pass combined with 6 structural contracts is stronger
evidence than single-file live differential would provide.

**Reproduce**: `make kids-vc-xpdk2vc-compat`

### 4. ZWR merge driver — 7/7 PASS

Seven 3-way merge scenarios, all verified:

| Scenario | Expected | Status |
|---|---|---|
| Non-overlapping edits | Clean merge (both preserved) | PASS |
| Identical edits on both sides | Clean (agreed value) | PASS |
| Conflicting modify-modify | Conflict markers | PASS |
| Addition by one side | Clean | PASS |
| Deletion by one side | Clean | PASS |
| Delete-vs-modify | Conflict | PASS |
| Add-add different values | Conflict | PASS |

**Reproduce**: `make zwr-merge-test`

### 5. CI pipeline — 3 jobs, all green

`.github/workflows/kids-vc-ci.yml`:
- `roundtrip` — every `.kid` fixture round-trips + decompose sanity
- `zwr-merge` — the 7-case merge test suite
- `lint-check` — `py_compile` + module import for all Python scripts

Triggers on push to main/kids-vc branches or PR on kids-vc paths.
Python 3.12, Ubuntu runner. No Docker required.

### 6. CLI + API smoke test via pip venv

Installed the package fresh in `/tmp/kidsvc-venv` via `pip install -e`
and verified:
- `kids-vc --help` lists all 5 subcommands
- `kids-vc roundtrip VMTEST_1_0_1.kid` → PASS
- `kids-vc-merge` handles clean merge + conflict correctly
- `import kids_vc` works; `kids_vc.__version__` returns `0.1.0`
- `kids_vc.WELL_KNOWN_FILES` has 29 entries

### Total green checks

**2,427** across the kids-vc test harness:

| Test type | Count |
|---|---|
| Regression fixtures | 5 |
| WorldVistA corpus patches | **2,406** |
| ZWR merge cases | 7 |
| XPDK2VC structural contracts | 6 |
| CI jobs | 3 |
| CLI+API smoke tests | 1+ |

### Testing not yet performed

Not because kids-vc fails, but because the scope isn't implemented yet:

- **Install-and-diff end-to-end**: build a `.KID` from decomposed
  source, install into a live VistA container, extract the resulting
  state, compare to source. Requires fixing VEHU `%ZISH` first.
- **OSEHRA FOIA / VA-Office / RPMS corpora**: straightforward
  extension of the corpus harness; runs in <5 min per flavor. Would
  demonstrate portability beyond WorldVistA.
- **Property-based testing** (Hypothesis) for parser-emitter
  invariants. Would surface edge cases not present in real corpora.
- **Performance benchmarking** at scale. Current 42 files/sec is
  fine for interactive use but could be profiled if batch workflows
  need speedup.

---

## Makefile targets

All kids-vc tasks in the vista-meta project's Makefile:

```bash
make kids-vc-test             # round-trip VMTEST_1_0_1.kid
make kids-vc-demo             # decompose VMTEST for inspection
make kids-vc-all              # round-trip all fixtures
make kids-vc-corpus           # full corpus (fetch + test)
make kids-vc-corpus-cached    # corpus from cache, no re-fetch
make kids-vc-xpdk2vc-compat   # XPDK2VC structural contracts
make kids-vc-pip-install      # install package in /tmp/kidsvc-venv
make zwr-merge-test           # run 7-case merge test suite
make zwr-merge-install        # install as git merge driver
```

---

## Troubleshooting

### `PARSE_FAIL` on a .KID file

Possible causes:
- File isn't a KIDS file at all (check for `**KIDS**:` marker)
- File uses a header variant not in `XPDK2V1.m`'s documented shapes
- Binary content in the middle of the KIDS text

Open an issue with the failing `.KID` attached; kids-vc's parser is
tolerant but not exhaustive.

### `ROUNDTRIP_FAIL` with a pair-count mismatch

Usually means a decomposition bug. The 100% corpus pass means this is
rare, but format edge cases may still exist in non-WorldVistA patches.
The CI `roundtrip` job + local reproduction with
`kids-vc roundtrip <file>` should narrow it down. Compare the
pre/post pair sets to find the missing or added subscript.

### `EXCEPTION` during round-trip

Python stack trace indicates where. Usually a parser assertion
failure on unexpected format. Report with the failing `.KID`.

### `kids-vc-merge` conflict on every merge

If every `.zwr` merge produces conflict markers, you're probably not
using the ZWR merge driver — git is doing line-based merge.

Fix: `make zwr-merge-install` or manually configure
`.gitattributes` + `merge.zwr.driver` in `.git/config`. Verify with
`git config --get merge.zwr.driver`.

### `canonicalize` produces unusable .KID

That's by design. Canonicalized output is for DIFFING, not deployment.
Keep a pre-canonicalization copy (tag it in git) and deploy from that.

### Patch installs but behavior differs from original

kids-vc preserves SEMANTIC content, not byte-identical output. Line 2
of routines is canonicalized (patch list + build date + Build N
stripped). When KIDS installs the assembled `.KID`, it re-assigns Build
N and re-appends patches — so installed behavior should match. If you
observe divergence, open an issue.

---

## Roadmap

Completed (this release):
- Decomposition + assembly for 13 KIDS component types
- Round-trip integrity verification
- DD-embedded MUMPS extraction
- ZWR 3-way git merge driver
- Line-2 canonicalization
- Opt-in IEN canonicalization
- XPDK2VC structural-contract tests
- pip-installable package
- GitHub Actions CI
- 100% pass on 2,406-patch WorldVistA corpus

Proposed (Phase 9):
- **Pre-install snapshot + kids-vc undo** — surgical per-patch
  rollback for declarative content. See
  [ADR-046](adr/046-kids-vc-undo-pre-install-snapshot.md) for scope
  and limitations.

Potential extensions (not committed):
- OSEHRA FOIA / VA-Office / RPMS corpus coverage
- Install-and-diff end-to-end test (requires VEHU `%ZISH` fix)
- Property-based testing via Hypothesis
- PyPI publication
- Multi-build fixture handling (no real fixture has surfaced the need)
- Word-processing multi-line value support (same)

---

## References

- **[kids-vc-background-dev.md](kids-vc-background-dev.md)** — history,
  prior art (SKIDS, XPDK2VC), development chronology, discoveries
- **[ADR-045](adr/045-data-code-separation-package-bridge.md)** — why
  code and data models are separate
- **[ADR-046](adr/046-kids-vc-undo-pre-install-snapshot.md)** —
  proposed Phase 9 uninstall capability
- **[code-model-guide.md](code-model-guide.md)** — broader VistA code
  lifecycle context
- **Source code**:
  - Canonical: `host/scripts/kids_vc.py`, `host/scripts/zwr_merge.py`
  - Test fixtures: `host/scripts/kids_vc_fixtures/`
  - Corpus harness: `host/scripts/fetch_kids_corpus.py`
  - XPDK2VC contracts: `host/scripts/test_xpdk2vc_compat.py`
  - pip package: `kids_vc_pkg/`
- **Prior art on GitHub**:
  - [WorldVistA/SKIDS](https://github.com/WorldVistA/SKIDS) — abandoned prototype
  - [shabiel on GitHub](https://github.com/shabiel) — XPDK2VC author
  - [WorldVistA/VistA](https://github.com/WorldVistA/VistA) — the
    succeeded-by-sidestepping approach, our patch corpus source
- **Research log entries**: RF-028 (SKIDS investigation), RF-029
  through RF-033 (Phase 8 chronology) in
  `vista/export/RESEARCH.md`
- **License**: Apache 2.0 (matches both SKIDS and XPDK2VC)
