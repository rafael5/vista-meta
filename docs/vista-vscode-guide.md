# VistA VSCode & CLI Developer Tools Guide

Technical reference for every developer-productivity tool this repo
ships. Covers installation, the full CLI surface, the pre-commit
hook, the VSCode extension, the patch workflow, CI, and the
recommended daily loop.

For the architectural "why VistA is hard and how to approach it"
background, see [vista-developers-guide.md](vista-developers-guide.md).

---

## 0. Quick reference

```
bin/vista-meta doctor                   Environment health
bin/vista-meta pkg NAME                 Package overview
bin/vista-meta context NAME [--with-source]   AI context pack
bin/vista-meta where TAG^ROUTINE        Jump to source
bin/vista-meta callers TAG^ROUTINE      Caller graph
bin/vista-meta search PATTERN           Annotated corpus grep
bin/vista-meta file N                   FileMan file overview
bin/vista-meta new-test ROUTINE         M-Unit test skeleton
bin/vista-meta lint FILES...            Doc-comment lint
bin/vista-meta xindex FILE              Run XINDEX on one .m (live)

bin/mfmt FILES...                       Canonical .m formatter
bin/mfmt --check FILES...               Dry-run formatter

make install-hooks                      Install pre-commit hook
make patch-new NAME=...                 Scaffold a new on-disk patch
make patch-decompose KID=...            .KID -> on-disk form
make patch-assemble DIR=...             on-disk form -> .KID
make patch-roundtrip KID=...            decompose + re-assemble + diff
```

---

## 1. Installation

### 1.1 Prerequisites

- Python 3.10+ at `/usr/bin/python3`
- Node 18+ (for the VSCode extension build only)
- Docker with the `vista-meta` container built (`make build && make run`)
- bash 5.x

The CLI tools have zero external Python dependencies — standard
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

This creates a symlink `.git/hooks/pre-commit ->
../../hooks/pre-commit`. Every future `git commit` runs the hook.
Bypass with `git commit --no-verify` (rare; the hook is usually
right).

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
the "VistA Routine" panel appears under the Explorer view.

### 1.5 Verify

```bash
bin/vista-meta doctor
```

Expect every line to end `[ok]`. Any `[!!]` has a suggested fix
after the `—` marker.

---

## 2. The CLI — `vista-meta`

A single Python CLI with subcommands, implemented in
[host/scripts/vista_meta_cli.py](../host/scripts/vista_meta_cli.py).

### 2.1 `doctor` — environment health

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

### 2.2 `pkg NAME` — package overview

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

### 2.3 `context NAME` — AI context pack

```bash
vista-meta context PSO                                    # headers only
vista-meta context PSO --with-source --bytes 200000       # include source, capped
vista-meta context PSO --routines PSOVCC1,PSOVCC0         # specific source only
```

Emits a single markdown document suitable for pasting into an AI
prompt: package summary, FM files, RPCs, top edges, routines
inventory, and optionally full source. `--with-source` budgets the
source section at `--bytes` (default 200 KB).

### 2.4 `where TAG^ROUTINE` — jump to source

```bash
vista-meta where BYE^XUSCLEAN
vista-meta where PSOVCC1         # no tag -> routine header
vista-meta where ^XUSCLEAN       # same
```

Emits `path:line` with a 6-line source snippet, using a host-relative
path so VSCode can make it clickable in terminals that support OSC 8
or editor integrations.

### 2.5 `callers TAG^ROUTINE` — caller graph

```bash
vista-meta callers BYE^XUSCLEAN
vista-meta callers EN^ORWPT --limit 50
vista-meta callers XUSCLEAN            # all tags of this routine
```

Aggregates callers by `caller_routine`, sums `ref_count`, sorts
descending. Each line shows caller + caller package + per-tag
breakdown.

### 2.6 `search PATTERN` — annotated corpus grep

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

### 2.7 `file N` — FileMan file overview

```bash
vista-meta file 2                   # PATIENT
vista-meta file 52.41 --fields 20   # show first 20 fields
vista-meta file 200                 # NEW PERSON
```

The data-model counterpart to `pkg`. Prints global root, record
count, field count, DINUM flag, pointer-in / pointer-out counts,
PIKS (joined from `piks.tsv`), properties (volatility/sensitivity/
portability/volume/subdomain), top 15 "points out to" target files,
top 15 "pointed to by" source files, and optionally a field preview.

### 2.8 `new-test ROUTINE` — M-Unit test skeleton

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

### 2.9 `lint FILES...` — doc-comment lint

```bash
vista-meta lint vista/dev-r/VMPIKS.m
vista-meta lint vista/dev-r                      # directory = recursive
```

Checks that every public tag (column-0 alphabetic label except the
routine header) has an `@summary` or `@test` doc block. Legacy code
won't pass; this is intended for new code. The pre-commit hook
applies it automatically to newly-added files.

Exit 0 if clean, 1 if issues found.

### 2.10 `xindex FILE` — live XINDEX via the container

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

## 3. `mfmt` — canonical formatter

Deterministic, idempotent, minimal MUMPS formatter.
[host/scripts/mfmt.py](../host/scripts/mfmt.py).

```bash
bin/mfmt vista/dev-r/MYNEW.m              # rewrite in place
bin/mfmt --check vista/dev-r/MYNEW.m      # dry run, exit 1 if changes needed
bin/mfmt vista/dev-r                      # recurse into a directory
```

Rules applied:

| Rule | Transformation |
|---|---|
| R1  | Strip trailing whitespace |
| R2  | Leading tabs → spaces (1 tab = 1 space) |
| R3  | File ends with exactly one LF |
| R4  | Normalize `\r\n` / `\r` → `\n` |

Rules deliberately NOT applied (would require parsing MUMPS — string
literals, DO-block `.` depth, command case in user code):

- Command-case normalization
- Body indent normalization
- Line-2 reshape
- Trailing-comment spacing

Running `mfmt` twice is guaranteed to produce the same output as
running it once. Clean corpus routines are a noop.

---

## 4. The pre-commit hook

[hooks/pre-commit](../hooks/pre-commit). Installed via
`make install-hooks` → symlink `.git/hooks/pre-commit`.

### 4.1 What it checks, per staged file type

**`.m` files — newly added** (all rules apply to every line):

- Line 1 must start at column 0 and contain `;`
- Line 2 must start with `;;` (with optional single-space leading indent)
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
lines *you* added.

**`.kid` / `.KID` files:**

- `kids_vc.py roundtrip` must pass (parse + re-assemble must be
  byte-semantically identical)

### 4.2 Opt-in XINDEX gating

Off by default because it needs the container. Enable per session:

```bash
export VISTA_META_XINDEX=1
git commit -m "..."
```

Every staged `.m` is piped through the live XINDEX. Any Fatal blocks
the commit. Container name overridable via
`VISTA_META_CONTAINER=<name>`.

### 4.3 Bypass (rare)

```bash
git commit --no-verify -m "emergency fix, pre-merge cleanup follows"
```

Use sparingly. The hook is usually right.

### 4.4 Verification

Smoke-tested against a random 200-routine sample of the real
WorldVistA corpus: zero false positives on modified files. Newly
added malformed files correctly flagged.

---

## 5. The VSCode extension

[vscode-extension/](../vscode-extension/). No language server, no
MCP, no container calls — pure reads of the code-model TSVs.

### 5.1 The sidebar

When any `.m` file is the active editor, a "VistA Routine" panel
appears under the Explorer view. Hierarchy:

```
<ROUTINE>  [<Package>]           in=… out=… RPC×… OPT×… · N lines
├─ Tags (N)
│   ├─ TAG1  (line X)
│   └─ …
├─ Callers (N)
│   ├─ CALLER1  [package]  ×refcount
│   └─ …
├─ Callees (N)
│   ├─ TAG^ROUTINE  kind  ×refcount
│   └─ …
├─ Globals (N)
│   ├─ ^GLB  ×refcount
│   └─ …
└─ XINDEX (N)             # auto-expanded
    ├─ [F] error text  (tag+offset  line N)
    └─ …
```

Every clickable child acts as go-to-definition:

- **Tags** reveal the tag's line in the open file
- **Callers** open the caller routine at top (resolved via
  `routines-comprehensive.tsv`)
- **Callees** open the target routine
- **XINDEX** findings reveal the offending line

### 5.2 Commands

Run from the command palette:

- `vista-meta: Refresh Routine Sidebar` — re-analyze the active file.
  Useful if you regenerated TSVs after starting VSCode.
- `vista-meta: Reload Code-Model TSVs` — invalidate the in-memory
  TSV cache. Run this after `make sync-routines && make
  routines-comprehensive`.

### 5.3 Settings

`Preferences → Settings → Extensions → vista-meta`:

| Key | Default | Purpose |
|---|---|---|
| `vistaMeta.codeModelPath` | `vista/export/code-model` | Workspace-relative TSV dir |
| `vistaMeta.vistaMHostPath` | `vista/vista-m-host` | Synced VistA-M source tree |
| `vistaMeta.topN` | 15 | Max entries per section |

All paths are resolved relative to the first workspace folder.

### 5.4 When the sidebar is empty

The extension surfaces a message instead of silently showing nothing:

- *"Open a VistA .m file to see its context."* — active editor isn't
  a `.m` file
- *"Routine not found in code-model TSVs. Run `make sync-routines &&
  make routines-comprehensive`."* — the active file isn't in the
  synced corpus (e.g., brand-new dev-r file)

### 5.5 Rebuilding the extension after a source change

```bash
cd vscode-extension
npx tsc -p .
npx vsce package --no-dependencies --skip-license \
                 --allow-missing-repository
code --install-extension vista-meta-0.1.0.vsix --force
```

Reload VSCode to pick up the new version.

---

## 6. Decomposed-on-disk patch workflow

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
# -> patches/XU_8_0_1234/ tree you can git-add and edit
```

### 6.3 Assemble

```bash
make patch-assemble DIR=patches/MYPKG_1_0_1001
# -> patches/MYPKG_1_0_1001.KID
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

### 9.4 Turn XINDEX on once you're confident the container is stable

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
that also fails, check `awk -F'\t' '{print $1}' vista/export/
code-model/packages.tsv` for the exact list.

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

If you're genuinely blocked: `git commit --no-verify` once and
fix in the next commit.

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

- [host/scripts/vista_meta_cli.py](../host/scripts/vista_meta_cli.py) — every subcommand
- [host/scripts/mfmt.py](../host/scripts/mfmt.py) — formatter
- [hooks/pre-commit](../hooks/pre-commit) — the pre-commit hook
- [vscode-extension/](../vscode-extension/) — extension source
- [.github/workflows/](../.github/workflows/) — CI
- [Makefile](../Makefile) — all Makefile targets (`make help` lists them)
- [vista-developers-guide.md](vista-developers-guide.md) — architectural context
- [kids-vc-guide.md](kids-vc-guide.md) — `.KID` decompose / assemble
- [code-model-guide.md](code-model-guide.md) — the TSVs these tools read
- [piks-analysis-guide.md](piks-analysis-guide.md) — the data-model side
