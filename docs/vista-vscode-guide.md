# VistA VSCode & CLI Developer Tools Guide

Technical reference for every developer-productivity tool this repo
ships. Opens with the **VSCode extension** you'll use constantly,
then covers the **CLI** that powers the rest of the workflow: the
formatter, the pre-commit hook, patch assembly, CI, and the
recommended daily loop.

> For the architectural "why VistA is hard and how to approach it"
> background, see [vista-developers-guide.md](vista-developers-guide.md).

---

## Table of contents

- [Quick reference](#quick-reference)
- [1. Installation](#1-installation)
- [2. The VSCode extension](#2-the-vscode-extension)
  - [2.1 Where the sidebar lives on screen](#21-where-the-sidebar-lives-on-screen)
  - [2.2 Reading the sidebar — VistA terminology primer](#22-reading-the-sidebar--vista-terminology-primer)
  - [2.3 Click behaviors](#23-click-behaviors)
  - [2.4 Commands](#24-commands)
  - [2.5 Settings](#25-settings)
  - [2.6 When the sidebar is empty](#26-when-the-sidebar-is-empty)
  - [2.7 Rebuilding the extension](#27-rebuilding-the-extension)
- [3. The CLI — `vista-meta`](#3-the-cli--vista-meta)
- [4. `mfmt` — canonical formatter](#4-mfmt--canonical-formatter)
- [5. The pre-commit hook](#5-the-pre-commit-hook)
- [6. Patch workflow (decomposed-on-disk)](#6-patch-workflow-decomposed-on-disk)
- [7. CI — enforce the same checks on PRs](#7-ci--enforce-the-same-checks-on-prs)
- [8. Recommended daily loop](#8-recommended-daily-loop)
- [9. Optimizing productivity](#9-optimizing-productivity)
- [10. Troubleshooting](#10-troubleshooting)
- [11. Reference](#11-reference)

---

## Quick reference

```
vista-meta doctor                   Environment health
vista-meta pkg NAME                 Package overview
vista-meta context NAME [--with-source]   AI context pack
vista-meta where TAG^ROUTINE        Jump to source
vista-meta callers TAG^ROUTINE      Caller graph
vista-meta search PATTERN           Annotated corpus grep
vista-meta file N                   FileMan file overview
vista-meta new-test ROUTINE         M-Unit test skeleton
vista-meta lint FILES...            Doc-comment lint
vista-meta xindex FILE              Run XINDEX on one .m (live)

mfmt FILES...                       Canonical .m formatter
mfmt --check FILES...               Dry-run formatter

make install-hooks                      Install pre-commit hook
make patch-new NAME=...                 Scaffold a new on-disk patch
make patch-decompose KID=...            .KID → on-disk form
make patch-assemble DIR=...             on-disk form → .KID
make patch-roundtrip KID=...            decompose + re-assemble + diff
```

---

## 1. Installation

### 1.1 Prerequisites

- Python 3.10+ at `/usr/bin/python3`
- Node 18+ (for the VSCode extension build only)
- Docker with the `vista-meta` container built (`make build && make run`)
- bash 5.x

The CLI tools have **zero external Python dependencies** — standard
library only.

### 1.2 Put `bin/` on your PATH

Add to `~/.bashrc` (or wherever you keep PATH edits):

```bash
export PATH="$HOME/vista-meta/bin:$PATH"
```

Now `vista-meta pkg PSO` works from any directory inside the
workspace.

### 1.3 Install the pre-commit hook

```bash
cd ~/vista-meta
make install-hooks
```

Creates a symlink `.git/hooks/pre-commit → ../../hooks/pre-commit`.
Every future `git commit` runs the hook. Bypass with
`git commit --no-verify` (rare; the hook is usually right).

### 1.4 Build and install the VSCode extension

```bash
cd vscode-extension
npm install --ignore-scripts
npx tsc -p .
npx vsce package --no-dependencies --skip-license \
                 --allow-missing-repository
code --install-extension vista-meta-0.1.0.vsix
```

Reload VSCode. Open any `.m` file in the `vista-meta` workspace —
the **VISTA ROUTINE** panel appears in the Explorer sidebar.

### 1.5 Verify

```bash
bin/vista-meta doctor
```

Expect every line to end `[ok]`. Any `[!!]` has a suggested fix
after the `—` marker.

---

## 2. The VSCode extension

[vscode-extension/](../vscode-extension/). No language server, no
MCP, no container calls — pure reads of the code-model TSVs. That
means the extension is instant, works offline, and has no way to
break your workspace.

### 2.1 Where the sidebar lives on screen

When any `.m` file is the active editor, a **VISTA ROUTINE** panel
appears in the **Explorer** view. To reach it: click the Explorer
icon at the top of the Activity Bar (the two-documents glyph, or
press `Ctrl+Shift+E`). VISTA ROUTINE is the last collapsible panel
in the Explorer, below Open Editors, the workspace file tree,
Outline, and Timeline.

Opening
[vista/vista-m-host/Packages/Accounts Receivable/Routines/PRCA45PT.m](../vista/vista-m-host/Packages/Accounts%20Receivable/Routines/PRCA45PT.m)
renders this, with every section expanded:

```
# wireframe
 Activity Bar   Explorer sidebar  (Ctrl+Shift+E)
 ┌─────┐        ┌────────────────────────────────────────────────────┐
 │     │        │ EXPLORER                                     · · · │
 │  ≡  │        ├────────────────────────────────────────────────────┤
 │     │        │ ▸ OPEN EDITORS                                     │
 │ [▭] │❶       │                                                    │
 │     │        ├────────────────────────────────────────────────────┤
 │  ⌕  │        │ ▾ VISTA-META                                       │
 │     │        │    ▸ bin/                                          │
 │  ⎇  │        │    ▸ docs/                                         │
 │     │        │    ▸ vista/                                        │
 │  ▶  │        │    …                                               │
 │     │        ├────────────────────────────────────────────────────┤
 │  ▦  │        │ ▸ OUTLINE                                          │
 │     │        ├────────────────────────────────────────────────────┤
 └─────┘        │ ▸ TIMELINE                                         │
                ├────────────────────────────────────────────────────┤
                │ ▾ VISTA ROUTINE                              ⟳     │❷
                │                                                    │
                │   ▣ PRCA45PT  [Accounts Receivable]                │❸
                │     74 lines · in=0 · out=5                        │
                │                                                    │
                │   ▾ Tags (5)                                       │❹
                │      ƒ V          line 2                           │
                │      ƒ EN         line 24                          │
                │      ƒ 430        line 36                          │
                │      ƒ 433        line 48                          │
                │      ƒ XCLN       line 59                          │
                │                                                    │
                │   ▾ Callees (5)                                    │❺
                │      ← BMES^XPDUTL      do  ×7                     │
                │      ← MES^XPDUTL       do  ×6                     │
                │      ← HOME^%ZIS        do  ×1                     │
                │      ← ^%ZTLOAD         do  ×1                     │
                │      ← ^DIK             do  ×1                     │
                │                                                    │
                │   ▾ Globals (1)                                    │❻
                │      ⊡ ^PRCA            ×18                        │
                │                                                    │
                │   ▾ XINDEX (2)                                     │❼
                │      ⓘ [S] Lock missing Timeout.                   │
                │           430+5   line 41                          │
                │      ⓘ [S] Lock missing Timeout.                   │
                │           433+5   line 53                          │
                └────────────────────────────────────────────────────┘
```

**Key**

| | Pointing to | What it is |
|---|---|---|
| **❶** | Activity Bar Explorer icon | Click to open the file sidebar. Keyboard: `Ctrl+Shift+E`. |
| **❷** | VISTA ROUTINE panel title | Contributed by the vista-meta extension; the `⟳` icon runs `vista-meta: Refresh Routine Sidebar` (use after regenerating TSVs or switching branches). |
| **❸** | Header node | Routine name, package in brackets, stats pulled from `routines-comprehensive.tsv` (line count, in-degree, out-degree, plus `RPC×N` / `OPT×N` when nonzero). |
| **❹** | Tags (N) | Labels parsed from the file on disk. Click a tag → reveal its line. |
| **❺** | Callees (N) | Routines this one calls, aggregated from `routine-calls.tsv`, sorted by ref-count. Click → open the target routine. |
| **❻** | Globals (N) | Distinct globals touched, with ref-counts. Read-only — no click target. |
| **❼** | XINDEX (N) | Findings from `xindex-errors.tsv`. **Auto-expanded** so Fatals can't be missed; severity `F` → error icon, `W` → warning, rest → info. Numeric-line findings click → reveal that line. |

Sections with zero entries are hidden entirely. PRCA45PT has
`in_degree=0`, so no **Callers** section renders — it's not a bug.
All sections except XINDEX start collapsed; click the `▸` twisty to
open. Top-N per section is 15 (configurable via `vistaMeta.topN`).

### 2.2 Reading the sidebar — VistA terminology primer

VistA carries 40 years of medical-informatics jargon that can feel
opaque if you're coming from modern web or enterprise stacks. Here's
what the sidebar actually shows, in terms you already know.

#### 2.2.1 The core concepts (translation table)

| VistA term | Mainstream equivalent | Where it appears in the sidebar |
|---|---|---|
| **Routine** | Source file / module | The `.m` file you opened; rows in Callers/Callees |
| **Tag** | Function / method entry point | Rows in the **Tags** section |
| **Package** | Module / subsystem | Bracketed `[Accounts Receivable]` next to the routine name |
| **Global** | Database table / persistent key-value store | `^PRCA` in the **Globals** section — the data this code reads or writes |
| **FileMan file** | SQL table (with soft schema) | Not in the sidebar — see `vista-meta file N` |
| **RPC** | Remote procedure / API endpoint | `RPC×N` badge in the routine header |
| **Option** | Menu item (roll-and-scroll UI) | `OPT×N` badge in the routine header |
| **Protocol** | Event handler / menu action | Shown on package pages |
| **XINDEX** | Static analyzer / linter | The **XINDEX** section |
| **KIDS** | Package installer / patch system | `.KID` files — see §6 |
| **SAC** | Style / coding standard | Enforced by the pre-commit hook (§5) |
| **IEN** | Primary key (auto-increment integer) | `Internal Entry Number` — embedded in global subscripts |
| **Cross-reference** / **X-ref** | Index | Secondary indexes on global fields |
| **Namespace prefix** | Package identifier | First 2–4 chars of a routine name (e.g. `PRCA*` = Accounts Receivable) |

#### 2.2.2 The mental model

**Globals = data.** The native MUMPS persistent array. Every byte of
VistA data — patients, medications, appointments — is stored in a
tree-shaped global like `^DPT(patient_id, 0)="SMITH,JOHN^M^..."`.
Think "a filesystem of typed key-value pairs, with built-in indexes."

**Routines = code.** A `.m` file with callable **tags** at column
zero. Think "a Python module of functions, but the module name is
8 chars max and functions live in a flat namespace."

**Packages = subsystems.** Logical groupings — Pharmacy, Lab,
Accounts Receivable — identified by a 2–4 char namespace prefix.
The `PRCA45PT` routine is in the Accounts Receivable package because
`PRCA*` routines are conventionally that package's namespace.

**FileMan = the relational layer.** FileMan sits *on top of* globals
and imposes a schema: **files** (tables), **fields** (columns),
**records** (rows), and **cross-references** (indexes). Mental
shorthand: "ORM invented in 1982, still running."

**Three UI surfaces:**

- **RPCs** — modern clients (CPRS, JLV, FHIR gateways) call these.
- **Options** — the roll-and-scroll terminal menus that VA clerks use.
- **Protocols** — event hooks and menu actions.

#### 2.2.3 What each sidebar section answers

| Section | Question it answers |
|---|---|
| **Tags** | "What are this file's functions?" (file TOC) |
| **Callers** | "Who calls into this file?" (reverse call graph) |
| **Callees** | "What does this file call?" (forward call graph) |
| **Globals** | "What data does this file touch?" |
| **XINDEX** | "What does the VA's official linter say about this file?" |

When you open a routine, your first three questions are usually
**"what does it do?"**, **"who depends on it?"**, and **"what data
is involved?"** — the sidebar puts all three one click away without
leaving the editor.

### 2.3 Click behaviors

Every clickable sidebar item acts as go-to-definition:

- **Tags** → reveal the tag's line in the current editor.
- **Callers** → open the caller routine at its header.
- **Callees** → open the target routine.
- **XINDEX** findings with a numeric line → reveal that line.
  Severity maps to icon: `F` → error, `W` → warning, `S`/`I` → info.

### 2.4 Commands

Run from the command palette (`Ctrl+Shift+P`):

- **`vista-meta: Refresh Routine Sidebar`** — re-analyze the active
  file. Use after regenerating TSVs or switching branches.
- **`vista-meta: Reload Code-Model TSVs`** — invalidate the
  in-memory TSV cache. Run after `make sync-routines && make
  routines-comprehensive`.

### 2.5 Settings

`Preferences → Settings → Extensions → vista-meta`:

| Key | Default | Purpose |
|---|---|---|
| `vistaMeta.codeModelPath` | `vista/export/code-model` | Workspace-relative TSV dir |
| `vistaMeta.vistaMHostPath` | `vista/vista-m-host` | Synced VistA-M source tree |
| `vistaMeta.topN` | `15` | Max entries per section |

All paths resolve relative to the first workspace folder.

### 2.6 When the sidebar is empty

The extension surfaces a message instead of silently showing nothing:

- *"Open a VistA .m file to see its context."* — active editor isn't
  a `.m` file.
- *"Routine not found in code-model TSVs. Run `make sync-routines &&
  make routines-comprehensive`."* — the active file isn't in the
  synced corpus (e.g., a brand-new dev-r file).

### 2.7 Rebuilding the extension

```bash
cd vscode-extension
npx tsc -p .
npx vsce package --no-dependencies --skip-license \
                 --allow-missing-repository
code --install-extension vista-meta-0.1.0.vsix --force
```

Reload VSCode to pick up the new version.

---

## 3. The CLI — `vista-meta`

A single Python CLI with subcommands, implemented in
[host/scripts/vista_meta_cli.py](../host/scripts/vista_meta_cli.py).

### 3.1 `doctor` — environment health

```bash
vista-meta doctor
```

Reports:

- `python3` on PATH
- `bin/vista-meta` + `bin/mfmt` executable
- pre-commit hook installed
- `routines-comprehensive.tsv` not older than the last
  `make sync-routines` run
- 9 critical code-model TSVs present
- 3 data-model TSVs present
- kids-vc fixture round-trips cleanly
- container `vista-meta` running

Exit 0 if every hard check passes, 1 otherwise. Run this any time
something feels off.

### 3.2 `pkg NAME` — package overview

```bash
vista-meta pkg PSO
vista-meta pkg "Outpatient Pharmacy"
vista-meta pkg kernel
```

Resolves `NAME` in this cascade: exact match → case-insensitive
exact → case-insensitive substring → namespace-prefix inference
(most routines starting with `NAME` wins). Ambiguous matches list
candidates.

Prints:

- Routines + total lines
- PIKS file breakdown (P/I/K/S counts)
- RPCs, options, protocols exposed
- Distinct globals touched
- Top 20 FileMan files owned
- Top 10 globals by ref count
- Top 10 RPCs exposed
- Top 10 inbound/outbound package edges
- Top 10 entry-point candidates (by in-degree)

### 3.3 `context NAME` — AI context pack

```bash
vista-meta context PSO                                    # headers only
vista-meta context PSO --with-source --bytes 200000       # include source, capped
vista-meta context PSO --routines PSOVCC1,PSOVCC0         # specific source only
```

Emits a single markdown document suitable for pasting into an AI
prompt: package summary, FM files, RPCs, top edges, routines
inventory, and optionally full source. `--with-source` budgets the
source section at `--bytes` (default 200 KB).

### 3.4 `where TAG^ROUTINE` — jump to source

```bash
vista-meta where BYE^XUSCLEAN
vista-meta where PSOVCC1         # no tag → routine header
vista-meta where ^XUSCLEAN       # same
```

Emits `path:line` with a 6-line source snippet, using a host-relative
path so VSCode can make it clickable in terminals that support OSC 8
or editor integrations.

### 3.5 `callers TAG^ROUTINE` — caller graph

```bash
vista-meta callers BYE^XUSCLEAN
vista-meta callers EN^ORWPT --limit 50
vista-meta callers XUSCLEAN            # all tags of this routine
```

Aggregates callers by `caller_routine`, sums `ref_count`, sorts
descending. Each line shows caller + caller package + per-tag
breakdown.

### 3.6 `search PATTERN` — annotated corpus grep

```bash
vista-meta search "HALT"                           # everywhere
vista-meta search "HALT" --package Kernel          # scoped
vista-meta search "^BAD" --tags-only               # label rows only
vista-meta search "filterfoo" -i                   # case-insensitive
vista-meta search "XUSCLEAN" --limit 500
```

Walks `vista/vista-m-host/Packages/`, applies the regex, annotates
each match with the owning package. `--tags-only` restricts to
column-0 label lines — useful when you want definitions rather than
every textual mention.

### 3.7 `file N` — FileMan file overview

```bash
vista-meta file 2                   # PATIENT
vista-meta file 52.41 --fields 20   # show first 20 fields
vista-meta file 200                 # NEW PERSON
```

The data-model counterpart to `pkg`. Prints global root, record
count, field count, DINUM flag, pointer-in / pointer-out counts,
PIKS (joined from `piks.tsv`), properties (volatility / sensitivity /
portability / volume / subdomain), top 15 "points out to" target
files, top 15 "pointed to by" source files, and optionally a field
preview.

### 3.8 `new-test ROUTINE` — M-Unit test skeleton

```bash
vista-meta new-test PSOVCC1                      # stdout
vista-meta new-test PSOVCC1 -o TPSOVCC1.m        # write to file
```

Reads the target's source, enumerates public tags, emits a
`T<ROUTINE>.m` (truncated to 8 chars) with:

- Conventional header + line 2 with the right package
- Empty `STARTUP` / `SHUTDOWN` stubs
- One `T<N>` stub per public tag, each containing
  `; @TEST exercise <TAG>^<ROUTINE>` plus a `D SUCCEED^%ut` placeholder

You fill in the fixture setup and assertions.

### 3.9 `lint FILES...` — doc-comment lint

```bash
vista-meta lint vista/dev-r/VMPIKS.m
vista-meta lint vista/dev-r                      # directory = recursive
```

Checks that every public tag (column-0 alphabetic label except the
routine header) has an `@summary` or `@test` doc block. Legacy code
won't pass; this is intended for new code. The pre-commit hook
applies it automatically to newly-added files.

Exit 0 if clean, 1 if issues found.

### 3.10 `xindex FILE` — live XINDEX via the container

```bash
vista-meta xindex /tmp/MYNEW.m
vista-meta xindex vista/dev-r/VMPIKS.m
```

Requires container `vista-meta` running. Copies the file into
`/home/vehu/dev/r/<name>.m`, drives the existing VMXIDX routine
(`SETUP + PROC + EXTRACT`), reads `/tmp/xindex-errors.tsv`, and
emits one line per finding:

```
path:LINE  [TAG+OFFSET]  F - Block structure mismatch.

1 issue(s) (F=1, W=0, I=0, S=0)
```

Exit 1 if any Fatal. Container identity is overridable via
`VISTA_META_CONTAINER`.

---

## 4. `mfmt` — canonical formatter

Deterministic, idempotent, minimal MUMPS formatter.
[host/scripts/mfmt.py](../host/scripts/mfmt.py).

```bash
bin/mfmt vista/dev-r/MYNEW.m              # rewrite in place
bin/mfmt --check vista/dev-r/MYNEW.m      # dry run; exit 1 if changes needed
bin/mfmt vista/dev-r                      # recurse into a directory
```

Rules applied:

| Rule | Transformation |
|---|---|
| R1 | Strip trailing whitespace |
| R2 | Leading tabs → spaces (1 tab = 1 space) |
| R3 | File ends with exactly one LF |
| R4 | Normalize `\r\n` / `\r` → `\n` |

Rules deliberately **not** applied (would require parsing MUMPS —
string literals, DO-block `.` depth, command case in user code):

- Command-case normalization
- Body indent normalization
- Line-2 reshape
- Trailing-comment spacing

Running `mfmt` twice is guaranteed to produce the same output as
running it once. Clean corpus routines are a noop.

---

## 5. The pre-commit hook

[hooks/pre-commit](../hooks/pre-commit). Installed via
`make install-hooks` → symlink `.git/hooks/pre-commit`.

### 5.1 What it checks, per staged file type

**`.m` files — newly added** (all rules apply to every line):

- Line 1 must start at column 0 and contain `;`
- Line 2 must start with `;;` (optional single-space leading indent)
- Every column-0 content must be a valid MUMPS label
  (`[%A-Za-z][A-Za-z0-9]*` or `[0-9]+`, optionally followed by
  `(...)` and then whitespace or `;`)
- Line length ≤ 245 (SAC)
- No tab characters
- No trailing whitespace
- No bare `HALT` (route through `$$EN^XUSCLEAN`)
- Doc-comment discipline: every public tag has `@summary` or `@test`

**`.m` files — modified** (per-line rules on added diff lines only):

- Length ≤ 245
- No tabs
- No trailing whitespace
- No bare `HALT`

This distinction matters: legacy VistA code doesn't follow every SAC
rule, and the hook must not block edits to existing files just
because a pre-existing line somewhere has a tab. It only cares about
lines **you** added.

**`.kid` / `.KID` files:**

- `kids_vc.py roundtrip` must pass (parse + re-assemble must be
  byte-semantically identical)

### 5.2 Opt-in XINDEX gating

Off by default because it needs the container. Enable per session:

```bash
export VISTA_META_XINDEX=1
git commit -m "..."
```

Every staged `.m` is piped through the live XINDEX. Any Fatal blocks
the commit. Container name overridable via
`VISTA_META_CONTAINER=<name>`.

### 5.3 Bypass (rare)

```bash
git commit --no-verify -m "emergency fix, pre-merge cleanup follows"
```

Use sparingly. The hook is usually right.

### 5.4 Verification

Smoke-tested against a random 200-routine sample of the real
WorldVistA corpus: zero false positives on modified files. Newly
added malformed files correctly flagged.

---

## 6. Patch workflow (decomposed-on-disk)

Edit patches as trees of files, not `.KID` bundles. Assembly happens
at build time via [host/scripts/kids_vc.py](../host/scripts/kids_vc.py).

### 6.1 Start a new patch

```bash
make patch-new NAME=MYPKG_1_0_1001
```

Creates:

```
patches/MYPKG_1_0_1001/
├── README.md
├── routines/
├── files/
├── options/
├── protocols/
├── rpcs/
├── keys/
└── hooks/
```

### 6.2 Work on an existing upstream patch

```bash
make patch-decompose KID=downloaded/XU_8_0_1234.KID
# → patches/XU_8_0_1234/ tree you can git-add and edit
```

### 6.3 Assemble

```bash
make patch-assemble DIR=patches/MYPKG_1_0_1001
# → patches/MYPKG_1_0_1001.KID
```

### 6.4 Validate round-trip

```bash
make patch-roundtrip KID=some.KID
# decompose + re-assemble + diff; should be byte-identical
```

The full kids-vc toolchain is documented in
[kids-vc-guide.md](kids-vc-guide.md).

---

## 7. CI — enforce the same checks on PRs

Two workflows under `.github/workflows/`:

### 7.1 `dev-tools-ci.yml`

Triggers on any PR (and push to `main`) that touches `.m` files or
the dev tool scripts:

| Job | What it runs |
|---|---|
| `fmt-check` | `mfmt --check` on `.m` files changed in the PR diff |
| `lint` | `vista-meta lint` on `.m` files newly added in the PR diff |
| `syntax` | `py_compile` on `vista_meta_cli.py` + `mfmt.py` |

### 7.2 `kids-vc-ci.yml`

Triggers on changes to kids-vc sources or fixtures:

| Job | What it runs |
|---|---|
| `roundtrip` | Round-trips every fixture in `host/scripts/kids_vc_fixtures/` |
| `zwr-merge` | `test_zwr_merge.py` (7 merge scenarios) |
| `xpdk2vc-compat` | `test_xpdk2vc_compat.py` (6 structural contracts) |
| `lint-check` | `py_compile` + import-safety on kids-vc scripts |

### 7.3 Running the same checks locally

```bash
# What fmt-check does:
bin/mfmt --check $(git diff --name-only origin/main...HEAD -- '*.m')

# What lint does:
bin/vista-meta lint $(git diff --name-only --diff-filter=A origin/main...HEAD -- '*.m')

# kids-vc:
make kids-vc-test
make zwr-merge-test
make kids-vc-xpdk2vc-compat
```

---

## 8. Recommended daily loop

Assumes you've installed the hook and the extension.

### 8.1 Start of session

```bash
bin/vista-meta doctor                     # 2 seconds
```

Green → you're fine. Any `[!!]` → fix before coding.

### 8.2 Before editing a package

```bash
bin/vista-meta pkg <package>              # orient
bin/vista-meta context <package> \
      --with-source --bytes 200000 \
      > /tmp/ctx.md                       # paste into AI chat
```

### 8.3 While editing

- Open the relevant `.m` in VSCode — sidebar shows callers/callees/
  globals/XINDEX inline.
- Use the Tags section as a file TOC; click to jump.
- When you name a callee you aren't sure of, use `vista-meta where
  TAG^ROUTINE` in the terminal or let the sidebar's Callees section
  resolve it.

### 8.4 Before committing

```bash
git add <files>
# The hook runs automatically on `git commit`. For an explicit
# pre-flight:
bin/mfmt --check <files>
bin/vista-meta lint <new-files>

# Optional — catch XINDEX issues locally before committing:
bin/vista-meta xindex <file.m>

# Or have the hook do it:
VISTA_META_XINDEX=1 git commit -m "..."
```

### 8.5 Writing tests

```bash
bin/vista-meta new-test <ROUTINE> -o vista/dev-r/T<ROUTINE>.m
```

Fill in fixtures. Run the generated tests inside the container
(`make mumps` → `D EN^TROUTINE`).

### 8.6 Shipping a patch

```bash
make patch-new NAME=MYPKG_1_0_1001
# edit under patches/MYPKG_1_0_1001/
make patch-assemble DIR=patches/MYPKG_1_0_1001
# patches/MYPKG_1_0_1001.KID ready to install / transmit
```

---

## 9. Optimizing productivity

### 9.1 Put the terminal one keystroke away

Bind a VSCode keybinding for `workbench.action.terminal.toggleTerminal`
if you don't already have one. Half of the tools are fastest in a
shell; the extension's job is to make the other half (navigation)
one click.

### 9.2 Use `context` for every AI conversation

An AI assistant is ~10× more useful with the code-model baked into
its prompt. Before asking "how do I add a field to File 2", paste
the output of:

```bash
vista-meta file 2 --fields 200
vista-meta context "Registration" > /tmp/reg_ctx.md
```

The AI now has specifics, not generalities.

### 9.3 Treat `doctor` as the first diagnostic

Before "why is my change not taking effect?" — run `doctor`. Most
unexpected behavior has a root cause in "TSVs are stale" or
"container is down".

### 9.4 Turn XINDEX on once the container is stable

```bash
echo 'export VISTA_META_XINDEX=1' >> ~/.bashrc
```

Every commit then runs XINDEX on every staged `.m`. You stop
shipping SAC-violating code by accident.

### 9.5 Keep patches on-disk, not in `.KID`

Never hand-edit a `.KID` file. The line-2 rules, patch-list format,
and ZWR escaping are fiddly. Let `kids-vc` assemble; you edit the
tree.

### 9.6 Use `search` for "does this convention exist already"

Before inventing a new naming pattern:

```bash
vista-meta search "REFILL" --tags-only
```

If existing code uses a tag name, follow suit. VistA conventions
are learned by imitation (§6.1 of the developer's guide).

---

## 10. Troubleshooting

### Sidebar is empty after opening a `.m` file

Run `vista-meta: Reload Code-Model TSVs` from the command palette.
If still empty, `bin/vista-meta doctor` — you likely need to sync.

### `vista-meta pkg` says "No package matching"

Try a narrower query. `vista-meta pkg foo` does substring matches;
if nothing matches, it falls back to namespace-prefix inference. If
that also fails, check
`awk -F'\t' '{print $1}' vista/export/code-model/packages.tsv` for
the exact list.

### `vista-meta xindex` errors with "container is not running"

```bash
make run
bin/vista-meta doctor            # confirm "container vista-meta running"
bin/vista-meta xindex <file>
```

Or override the container name: `VISTA_META_CONTAINER=my-box
vista-meta xindex <file>`.

### Pre-commit hook rejects what looks like valid code

Read the exact complaint. Usually:

- Line 2 doesn't match `;;` — make sure it's `;;version;package;...`
- Column-0 content isn't a label — you accidentally started a body
  line at column 0; indent it with a single space
- Line length — either shorten the line or break it into continuations

If you're genuinely blocked: `git commit --no-verify` once and fix
in the next commit.

### `mfmt` won't idempotent

It does. If `mfmt FILE` then `mfmt --check FILE` reports changes,
that's a bug — open a bug report with the exact input file.

### CI `fmt-check` fails but local `mfmt --check` passes

You probably ran `mfmt` after the commit. The staged content matters
to the hook; the working tree matters to CI. Re-stage after
formatting:

```bash
bin/mfmt <files>
git add <files>
```

### Extension not finding the workspace TSVs

Extension reads from the first workspace folder only. If you have a
multi-folder workspace, set `vistaMeta.codeModelPath` absolutely
(though the option isn't designed for that — easier to open
`vista-meta` as the sole folder).

---

## 11. Reference

- [host/scripts/vista_meta_cli.py](../host/scripts/vista_meta_cli.py) — every CLI subcommand
- [host/scripts/mfmt.py](../host/scripts/mfmt.py) — formatter
- [hooks/pre-commit](../hooks/pre-commit) — the pre-commit hook
- [vscode-extension/](../vscode-extension/) — extension source
- [.github/workflows/](../.github/workflows/) — CI
- [Makefile](../Makefile) — all Makefile targets (`make help` lists them)
- [vista-developers-guide.md](vista-developers-guide.md) — architectural context
- [kids-vc-guide.md](kids-vc-guide.md) — `.KID` decompose / assemble
- [code-model-guide.md](code-model-guide.md) — the TSVs these tools read
- [piks-analysis-guide.md](piks-analysis-guide.md) — the data-model side
