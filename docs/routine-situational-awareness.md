# Reading a VistA Routine — Situational-Awareness Guide

VistA has ~40,000 routines. You're looking at one. This guide is a
prioritized sweep — what to look at first, what to ignore until later
— that turns "I have no idea what this does" into "I know what this
does, who depends on it, and what data it touches" in under five
minutes, without leaving VSCode.

> Audience: anyone reading or modifying an unfamiliar `.m` file.
> Companion to [vista-vscode-guide.md](vista-vscode-guide.md) (tool
> reference) and [vista-developers-guide.md](vista-developers-guide.md)
> (architectural background). For the next zoom-out — **scanning the
> whole package folder** the routine lives in — see
> [package-situational-awareness.md](package-situational-awareness.md).

---

## Table of contents

- [1. The cognitive problem](#1-the-cognitive-problem)
- [2. The 30-second fingerprint](#2-the-30-second-fingerprint)
- [3. The layered sweep — priority order](#3-the-layered-sweep--priority-order)
  - [L0 · Decode the path and name (5 s)](#l0--decode-the-path-and-name-5-s)
  - [L1 · Read the header (15 s)](#l1--read-the-header-15-s)
  - [L2 · Map the surface — tags as TOC (30 s)](#l2--map-the-surface--tags-as-toc-30-s)
  - [L3 · Read the topology — callers, callees, globals (1–2 min)](#l3--read-the-topology--callers-callees-globals-12-min)
  - [L4 · External exposure — RPC, Option, Protocol (1 min)](#l4--external-exposure--rpc-option-protocol-1-min)
  - [L5 · Risk and quality — XINDEX, PIKS, history (variable)](#l5--risk-and-quality--xindex-piks-history-variable)
- [4. VSCode surfaces, mapped to layers](#4-vscode-surfaces-mapped-to-layers)
- [5. vista-meta CLI as terminal companion](#5-vista-meta-cli-as-terminal-companion)
- [6. Worked example — cold-open PRCA45PT](#6-worked-example--cold-open-prca45pt)
- [7. Worked example — cold-open a hub (XUSCLEAN)](#7-worked-example--cold-open-a-hub-xusclean)
- [8. AI handoff — when to give up and ask](#8-ai-handoff--when-to-give-up-and-ask)
- [9. Cognitive traps (don't fall in)](#9-cognitive-traps-dont-fall-in)
- [10. Setup checklist — keybindings and settings](#10-setup-checklist--keybindings-and-settings)
- [11. Reference card](#11-reference-card)

---

## 1. The cognitive problem

Three properties of VistA conspire to flood a newcomer's working
memory:

1. **Names are eight characters max.** `PSOVCC1`, `XUSCLEAN`,
   `PRCA45PT` carry no semantics beyond a 2–4 char namespace
   prefix. You cannot guess what a routine does from its name.
2. **Globals look like routines.** `^XUS` is data, `^XUSCLEAN` is
   code, `^DPT` is patient data, `^%ZIS` is the device-handler
   global *or* the routine, depending on context. Same syntax,
   different worlds.
3. **The control flow is flat.** A "function" is a column-0 label
   (a tag); calls are bare `D EN^XUSCLEAN`; there are no modules,
   no imports, no types. The boundary between "this routine" and
   "everything reachable" is invisible without tooling.

The fix is **not** to read the file top-to-bottom. The fix is to
get five facts about the routine before reading any of its lines,
then narrow in. The sidebar + a small terminal habit give you those
five facts in under a minute.

---

## 2. The 30-second fingerprint

Open the file. Look at the **VISTA ROUTINE** sidebar header. Five
fields:

```
PRCA45PT  [Accounts Receivable]
74 lines · in=0 · out=5 · RPC×0 · OPT×1
```

| Field | What it tells you | Mental model |
|---|---|---|
| **Name** | Namespace prefix (`PRCA*` → Accounts Receivable) | Which subsystem owns this |
| **Package** | Subsystem in plain English | Which mental map applies |
| **Lines** | Size class | < 100 = utility; 100–500 = workhorse; 500+ = god-routine, treat with care |
| **in-degree** | Reverse popularity | 0 = entrypoint or dead; 1–5 = focused dependency; 100+ = framework |
| **out-degree** | Forward fan-out | 0 = leaf; 1–10 = normal; 50+ = orchestrator |
| **RPC× / OPT×** | UI exposure | Nonzero → user-facing; zero → internal |

The combination places the routine on a 2×2:

```
                 high in-degree
                       │
       hub utility ────┼──── framework / library
                       │
  ────────────────────┼─────────────────── high out-degree
                       │
       leaf ───────────┼──── orchestrator / entrypoint
                       │
                 low in-degree
```

Calibrate your reading effort by quadrant. A leaf with
`in=0 · out=2` deserves 30 seconds; an orchestrator with
`in=200 · out=80` deserves the rest of your morning.

---

## 3. The layered sweep — priority order

Six layers, each cheaper than the next, in the order to spend
attention. Stop at the layer that answers your question.

### L0 · Decode the path and name (5 s)

The host file path encodes the package:

```
vista/vista-m-host/Packages/Accounts Receivable/Routines/PRCA45PT.m
                            └────────┬────────┘            └──┬──┘
                            authoritative package        namespace prefix
```

The directory name is the **authoritative** package. The 2–4 char
prefix on the routine name is the **conventional** prefix — almost
always agrees, but the directory wins on conflict.

Common prefixes worth memorizing:

| Prefix | Package | Prefix | Package |
|---|---|---|---|
| `XU*` | Kernel (auth, sessions, jobs) | `PSO*` | Outpatient Pharmacy |
| `XW*` | Kernel toolkit | `PSI*` | Inpatient Pharmacy |
| `DI*` | FileMan core | `LR*` | Lab |
| `DIC*` | FileMan dictionary | `RA*` | Radiology |
| `DG*` | Registration | `OR*` | Order Entry / CPRS |
| `PRCA*` | Accounts Receivable | `GMRA*` | Allergy / Adverse Reaction |
| `IB*` | Integrated Billing | `MAG*` | Imaging |
| `FH*` | Dietetics | `TIU*` | Text Integration Utilities |
| `%*` | System / VistA-internal | `Z*` (varies) | Local site customizations |

Don't trust the prefix in isolation — but if the name starts with
`PSO`, your default is "this lives in the Pharmacy mental world."

### L1 · Read the header (15 s)

Two sources, same time:

**A. The first 3 lines of the file** (VistA convention):

```
PRCA45PT ;ALB/CMS - PURGE EXEMPT BILL FILES ;6/30/97  09:13
 ;;4.5;Accounts Receivable;**14,79,153,302,409**;Mar 20, 1995;Build 78
 ;Per VHA Directive 2004-038, this routine should not be modified.
```

| Line | Format | Carries |
|------|--------|---------|
| 1    | `NAME ;site/author - title ;date` | Author site (`ALB` = Albany), one-line title |
| 2    | `;;version;package;**patches**;date;build` | Patch list — the audit trail |
| 3    | Free-form `;` comments | Often a directive or warning — read it |

The patch list (`**14,79,153,...**`) is the most underrated metadata
in VistA: each number is a `.KID` patch that touched this routine.
Long patch list → mature, much-modified code. Short list → either
new or untouched-since-1995.

**B. The sidebar header** (the fingerprint from §2). Confirms the
package, gives you size class and topology in one glance.

### L2 · Map the surface — tags as TOC (30 s)

Tags are the file's entrypoints. Treat the **Tags (N)** sidebar
section (or the **Outline** view, once
[DocumentSymbolProvider lands](vscode-extension-internals.md#72-tier-b--documentsymbolprovider--definitionprovider))
as the file's table of contents.

What to read off the tag list:

- **First tag (often `EN`, `START`, `MAIN`)** — the conventional
  entrypoint. If callers exist, this is usually what they call.
- **`EN1`, `EN2`, …** — alternate entrypoints with different
  argument shapes. Look for them in pairs.
- **`STARTUP` / `SHUTDOWN`** — M-Unit test markers (the routine has
  tests).
- **`KILL`, `EXIT`, `BYE`** — teardown.
- **Numeric tags (`430`, `433`)** — historic state-machine entries
  or computed-`GOTO` targets. Treat with care; they're rarely
  modified safely.
- **`%`-prefixed tags** — system-level utilities, likely called from
  many places.

Click any tag to jump. Your goal here is **not** to read each tag's
body — it's to learn that the file has, say, 5 entrypoints and 12
internal helpers, so you know which 5 to focus on.

### L3 · Read the topology — callers, callees, globals (1–2 min)

This is the most expensive layer of the cheap layers, and the most
information-dense. Three sections, each answering a distinct
question:

**Callers — "who depends on me?"** (blast radius)

- `in=0` → either an entrypoint (RPC/Option/Protocol) or dead code.
  Check L4 to disambiguate.
- `in=1–5` → focused dependency. Read the callers' packages — if
  they're in the same package, this is internal; if cross-package,
  it's an interface.
- `in=20+` → utility or framework. Changes here cascade. Check the
  caller-package distribution: 20 callers all in one package is
  different from 20 callers across 12 packages.

The **caller package distribution** is the single most useful signal
for "how risky is editing this." Same-package callers are cheap;
cross-package callers are expensive.

**Callees — "who do I depend on?"** (forward graph)

- `out=0` → leaf. Self-contained.
- `out=1–10` → normal. Scan callees for surprises (a Pharmacy
  routine calling Lab is a coupling worth knowing about).
- `out=50+` → orchestrator. Probably a menu driver, a build script,
  or an integration point.

The `kind` column on callees (`do`, `goto`, `extrinsic`, `xecute`)
matters: `xecute` callees are dynamic and may not even exist on
the system; `extrinsic` callees return values and are usually
purer; `goto` callees never return.

**Globals — "what data do I touch?"** (data surface)

This is the layer that **lies the least**. Names obscure intent;
globals don't. A routine that touches `^DPT` reads or writes
patient data, full stop. A routine that touches only `^DIC` and
`^%ZIS` is a system utility.

Read the globals top-down by ref-count:

| Global | Owner package | Implies |
|---|---|---|
| `^DPT` | Registration | Patient data — protected |
| `^PS(...)` | Pharmacy | Drug / order data |
| `^OR(...)` | CPRS / Order Entry | Clinical orders |
| `^LAB(...)` | Lab | Lab results |
| `^DIC` | FileMan | Reading the data dictionary itself |
| `^DD` | FileMan | Reading field definitions |
| `^DIZ` | FileMan | Local site customization tables |
| `^%ZIS` | Kernel | Device / printer handling |
| `^XUSEC` | Kernel | Security keys |
| `^TMP` | (per-job) | Scratch space — ephemeral |
| `^XTMP` | (system-temp) | Cross-job scratch with expiration |

Two heuristics:

- **`^TMP` / `^XTMP` heavy = scratch worker.** Doing computation,
  not persistence.
- **One real global with high ref-count = a domain operator.** That
  global is what the routine is *about*.

Once a hover provider lands ([Tier A in extension internals](vscode-extension-internals.md#71-tier-a--hoverprovider-highest-leverage)),
hovering a global will surface its FileMan file number, file name,
and **PIKS class** (P/I/K/S). Until then, look up by hand:

```bash
vista-meta file 2          # ^DPT → File 2 (PATIENT)
vista-meta file 200        # ^VA(200) → NEW PERSON
```

The PIKS class is the call-to-attention you can't get anywhere else:
**P = Patient data** (protected, longitudinal, audit-relevant) means
edits trigger compliance review.

### L4 · External exposure — RPC, Option, Protocol (1 min)

The header badges (`RPC×N`, `OPT×N`) tell you a routine is exposed.
The CLI tells you *how*:

```bash
vista-meta where EN^PSOVCC1     # is this tag an RPC entrypoint?
vista-meta search "PSOVCC1" --tags-only
```

(A future
[hover provider](vscode-extension-internals.md#71-tier-a--hoverprovider-highest-leverage)
will do this inline — for now use the terminal.)

The three exposure surfaces:

| Surface | TSV | What it means |
|---|---|---|
| **RPC** | `rpcs.tsv` | A modern client (CPRS, JLV, FHIR gateway) calls this. Changes affect external software. |
| **Option** | `options.tsv` | The roll-and-scroll terminal menus. VA clerks invoke this through the keyboard menu. |
| **Protocol** | `protocols.tsv` | An event hook or extended-action menu. May fire automatically on patient events. |

A routine with `in=0` but `RPC×3` is **not** dead — the in-degree
counts only routine-to-routine calls. RPCs are invoked from
outside the M space; the call graph stops at the broker.

### L5 · Risk and quality — XINDEX, PIKS, history (variable)

This layer is where you decide whether to trust what you've read.

**XINDEX section** in the sidebar (auto-expanded when present).
Severity icons:

- `F` (Fatal) → block-structure mismatches, syntax issues. Real bugs.
- `W` (Warning) → SAC violations, structural smell.
- `S` (Style) → e.g. "Lock missing Timeout." Often tolerated in
  legacy code; required for new.
- `I` (Info) → noise.

If the sidebar shows a Fatal, **stop and read it before changing
anything else**. Fatals are rare and almost always real.

**PIKS classification of touched globals** — once hover lands. Until
then, the rule of thumb: any routine that touches `^DPT`, `^PS(...)`
clinical, `^OR(...)`, or any patient-keyed global needs more care
than one that touches only system globals. The data-model TSVs
(`vista/export/data-model/files.tsv`, `piks.tsv`) have the full
classification.

**Git history** — VSCode's source control panel and inline blame
(enable `git.blame.editorDecoration.enabled`):

- Last modified date — is this code under active maintenance?
- Author distribution — one author = bus factor 1; many authors =
  shared.
- Patch list on line 2 of the file complements this with the VistA
  perspective: how many KIDS patches have hit it?

---

## 4. VSCode surfaces, mapped to layers

Every VSCode surface that helps build situational awareness, mapped
to which layer it serves and whether it's available today.

| Surface | Layer | Status | How to invoke |
|---|---|---|---|
| **File path in title bar** | L0 | available | already on screen |
| **Breadcrumb bar** (with DocumentSymbol) | L0, L2 | proposed (Tier B) | top of editor; `Ctrl+Shift+.` to navigate |
| **Sticky scroll header** | L2 | available | settings: `editor.stickyScroll.enabled` |
| **First 3 lines of the file** | L1 | available | scroll to top |
| **VISTA ROUTINE sidebar header** | L1 | available | Explorer (`Ctrl+Shift+E`) |
| **VISTA ROUTINE Tags section** | L2 | available | Explorer sidebar |
| **Outline view** | L2 | proposed (Tier B) | `Ctrl+Shift+E` → Outline; or `Ctrl+Shift+O` |
| **Workspace symbol search** | L2 cross-routine | proposed (Tier C) | `Ctrl+T` |
| **VISTA ROUTINE Callers / Callees / Globals** | L3 | available | Explorer sidebar |
| **Hover (routine, tag, ^GLOBAL with PIKS)** | L1, L3, L4 | proposed (Tier A) | hover the cursor over an identifier |
| **Go to Definition (`Ctrl+Click`)** | L3 | proposed (Tier B) | `Ctrl+Click` on `TAG^ROUTINE` |
| **References / Find All** | L3 | partly: workspace search works today | `Ctrl+Shift+F` for now |
| **VISTA ROUTINE XINDEX section** | L5 | available | Explorer sidebar (auto-expanded) |
| **Problems panel (XINDEX as diagnostics)** | L5 | proposed (Tier C) | `Ctrl+Shift+M` once wired |
| **Status bar item** | L1 | proposed (Tier D) | bottom-right, always visible |
| **Source Control panel + inline blame** | L5 | available (built-in) | `Ctrl+Shift+G`; enable `git.blame.editorDecoration.enabled` |
| **Integrated terminal** | L4, L5 | available | `` Ctrl+` `` |
| **Diff editor (compare with sibling)** | L3 (delta) | available | right-click → "Select for Compare" |
| **Open Recent / Pinned tabs** | meta — keep context | available | `Ctrl+P` for files; right-click tab → Pin |
| **Multi-cursor (`Ctrl+D`, `Alt+Click`)** | reading helpers | available | when scanning callees inline |
| **Word highlight on cursor** | reading helpers | available (built-in) | hover any identifier; same-name occurrences light up |
| **Workspace search with regex** | layer-agnostic | available | `Ctrl+Shift+F`, regex on |
| **File search (`Ctrl+P`)** | navigation | available | type partial routine name |

The sidebar covers L1–L3 + L5 today. The proposed
[hover provider](vscode-extension-internals.md#71-tier-a--hoverprovider-highest-leverage)
brings that information **into the editor itself** — the
single highest-leverage addition for cognitive-load reduction.

### 4.1 Built-in features worth turning on for VistA reading

These are stock VSCode but pay off disproportionately for VistA
work:

```jsonc
// .vscode/settings.json (workspace) or User settings
{
  // Sticky scroll keeps the current tag visible at the top of
  // the editor — essential when reading 500-line god-routines
  "editor.stickyScroll.enabled": true,
  "editor.stickyScroll.maxLineCount": 5,

  // Inline blame: see who last touched this line, when, and why
  "git.blame.editorDecoration.enabled": true,

  // Word highlight: when cursor is on a tag or global, every
  // occurrence in the file lights up
  "editor.occurrencesHighlight": "singleFile",

  // Show file path in window title — disambiguate when 5 PSO*
  // routines are open
  "window.title": "${activeEditorMedium}${separator}${rootName}",

  // Wrap long XINDEX/comment lines so you don't have to scroll
  "editor.wordWrap": "on",
  "editor.wordWrapColumn": 132,

  // Show ref counts inline once CodeLens lands (Tier C)
  "editor.codeLens": true
}
```

---

## 5. vista-meta CLI as terminal companion

Open the integrated terminal with `` Ctrl+` `` and keep it docked
right. Every CLI command is a one-liner that complements the sidebar:

| Question | Command | Layer |
|---|---|---|
| What's this package's overall shape? | `vista-meta pkg "Accounts Receivable"` | L0 |
| Where does `EN^PSOVCC1` live? | `vista-meta where EN^PSOVCC1` | L2 |
| Who calls this tag specifically? | `vista-meta callers EN^PSOVCC1` | L3 |
| What FileMan file is `^DPT`? | `vista-meta file 2` | L3 / L5 |
| Is the convention `EN` or `MAIN`? | `vista-meta search "^MAIN" --tags-only --package PSO` | L2 |
| Is XINDEX clean on this file right now? | `vista-meta xindex vista/dev-r/MYNEW.m` | L5 |
| Hand the AI the whole package | `vista-meta context PSO --with-source > /tmp/ctx.md` | L8 |
| Is anything stale? | `vista-meta doctor` | L0 (env) |

The CLI is fastest when you've already narrowed in: sidebar tells
you "there are 12 callers"; CLI tells you who, in what package, with
how many refs each.

### 5.1 The "bind one keystroke" trick

VSCode keybindings (`Ctrl+K Ctrl+S` → search command):

| Action | Suggested keybinding | What it does |
|---|---|---|
| Toggle terminal | `Ctrl+\`` | (default) gets the CLI in front of you in 1 keystroke |
| Reveal active file in Explorer | `Ctrl+K R` | lets you eyeball the package directory |
| Go to Symbol | `Ctrl+Shift+O` | once Outline lands (Tier B) |
| Reload TSVs | bind `vistaMeta.reloadTsvs` | useful right after `make routines-comprehensive` |

Half of VistA reading is shell work. Make the shell one keystroke
away.

---

## 6. Worked example — cold-open PRCA45PT

You've never seen this routine. Stopwatch.

**0:05 — L0.** Path:
`vista/vista-m-host/Packages/Accounts Receivable/Routines/PRCA45PT.m`.
Package = Accounts Receivable. Prefix `PRCA*` matches.

**0:20 — L1.** Sidebar header: `PRCA45PT [Accounts Receivable] · 74
lines · in=0 · out=5 · OPT×1`. Small file. No callers — entrypoint
or dead. One Option exposure → menu-invokable, not dead.

File line 1: `PRCA45PT ;ALB/CMS - PURGE EXEMPT BILL FILES ;6/30/97`.
"Purge exempt bill files." Now you know what it does in plain
English, without reading any code.

File line 2: `;;4.5;Accounts Receivable;**14,79,153,302,409**;Mar 20,
1995;Build 78`. Five patches over ~25 years — moderate maintenance.

**0:50 — L2.** Tags: `V`, `EN`, `430`, `433`, `XCLN`. `EN` is the
conventional entrypoint; `430`/`433` are numeric (probably file
numbers, given the package); `XCLN` looks like the cleanup. Five
tags in 74 lines = dense.

**2:00 — L3.** Callees:
`BMES^XPDUTL ×7`, `MES^XPDUTL ×6` — these are KIDS-installer message
helpers, so this routine is wired into a patch installer.
`HOME^%ZIS ×1`, `^%ZTLOAD ×1`, `^DIK ×1` — device, taskman, FileMan
delete. Globals: `^PRCA ×18`. The whole routine operates on the
Accounts Receivable global.

**2:30 — L5.** XINDEX: 2 Style findings ("Lock missing Timeout") at
lines 41 and 53. Legacy code; not fatal.

**Synthesis (2:30):** "PRCA45PT is a 74-line cleanup utility that's
invoked from a KIDS patch install. It iterates the AR global and
deletes exempt bill records via FileMan. It's menu-exposed but
mostly fires from the installer. Two old style violations, no
fatals. Editing is low-risk if you preserve the patch-install
contract."

You haven't read the actual MUMPS yet. You don't need to, unless
your task requires it.

---

## 7. Worked example — cold-open a hub (XUSCLEAN)

Same exercise, different quadrant.

**0:05 — L0.** Path: `Packages/Kernel/Routines/XUSCLEAN.m`. Kernel.
Prefix `XU*`.

**0:30 — L1.** Sidebar header: `XUSCLEAN [Kernel] · 180 lines ·
in=400+ · out=20 · RPC×0 · OPT×0`. **Stop.** in=400+ means this is a
framework routine. Editing it changes behavior across every package.

Line 1: `XUSCLEAN ;SF-IRMFO/MVB - SIGN-ON CLEANUP ROUTINE`.
Line 2: many patches. Line 3+: comments warning against modification.

**1:00 — L2.** Tags include `BYE`, `MAIN`, `EXIT`, plus a host of
internal helpers. The `BYE` tag is the conventional sign-off
entrypoint — you've probably seen `D BYE^XUSCLEAN` everywhere in
VistA. That's why the in-degree is huge.

**3:00 — L3.** Top callers span every package. Globals:
`^XUSEC` (security), `^XTMP` (cross-job scratch), `^%ZIS` (devices).
This is genuinely framework code.

**3:30 — L5.** XINDEX clean. Pre-commit hook will reject any new
`HALT` you add — and you'd want it to.

**Synthesis:** "XUSCLEAN is the canonical sign-off routine. Every
package's logout flow goes through `BYE^XUSCLEAN`. Don't edit it
unless you have a Kernel-level mandate; treat it as read-only
infrastructure."

The shape of the sweep is the same; the **decision** is the
opposite. That's the point — your reading effort calibrates to the
fingerprint, not to the line count.

---

## 8. AI handoff — when to give up and ask

If after L1–L3 you still don't know what the routine does, hand the
problem to an AI assistant — but with context, not raw source.

```bash
# Per-package context pack (cheapest — covers a whole subsystem)
vista-meta context "Accounts Receivable" \
  --with-source --bytes 200000 \
  > /tmp/ar_ctx.md

# Per-file FM context (when the routine touches a specific file)
vista-meta file 430 --fields 50 >> /tmp/ar_ctx.md
vista-meta file 433 --fields 50 >> /tmp/ar_ctx.md

# Caller graph for the specific tag you're confused about
vista-meta callers EN^PRCA45PT >> /tmp/ar_ctx.md
```

Paste `/tmp/ar_ctx.md` into the AI chat. The model now has package
shape, file definitions, and call graph — a 10× better starting
point than the routine source alone. See
[vista-vscode-guide.md § 9.2](vista-vscode-guide.md#92-use-context-for-every-ai-conversation).

**Rule of thumb:** if you've spent more than 10 minutes on layers
L1–L3 without convergence, the source is not the bottleneck — the
context is. Switch tools.

---

## 9. Cognitive traps (don't fall in)

VistA has specific gotchas that burn time if you don't know them.

| Trap | Symptom | Defense |
|---|---|---|
| **Reading top-to-bottom** | You spend 20 minutes on a 500-line routine and still don't know what it does | Always do the fingerprint (§2) first. The body is the last thing to read, not the first. |
| **Trusting names** | "PSOZZZ — must be a placeholder?" Actually a real Pharmacy utility. | Names are 8 chars and historically encoded. Treat them as opaque tokens until L1–L3 give them meaning. |
| **Confusing `^GLOBAL` and `^ROUTINE`** | `^XUSCLEAN` could be either | The lookup is unambiguous: if it's in `routines.tsv`, it's a routine; otherwise it's a global. The proposed [hover](vscode-extension-internals.md#71-tier-a--hoverprovider-highest-leverage) decides for you. |
| **Ignoring `in=0`** | "Dead code, skip" | Check L4 first. RPCs, Options, and Protocols invoke from outside the M call graph — `in=0` plus `RPC×N` or `OPT×N` is a live entrypoint. |
| **Treating numeric tags as line numbers** | `D 430` looks like a typo for line 430 | Numeric tags are real label names, often historic state-machine entries. They're rarely safe to rename. |
| **Editing line 2** | Adding a patch reference, hand-editing the version | Line 2 is parsed by the KIDS installer. Never hand-edit; use the patch tooling ([kids-vc-guide.md](kids-vc-guide.md)). |
| **Skipping the patch list** | Missing the "this routine has been touched 47 times" signal | The `**14,79,153,...**` on line 2 is the audit trail. Long list = mature, much-tested; short list = brittle or unmaintained. |
| **Treating XINDEX `S` (Style) as "noise"** | Shipping `LOCK ^X` without timeout because legacy does it | Legacy is grandfathered. New code must pass — the [pre-commit hook](vista-vscode-guide.md#5-the-pre-commit-hook) enforces it. |
| **`xecute` callees in the sidebar** | Treating `XECUTE` targets as real callees | They're dynamic — string assembled at runtime. May not exist on this system. The `kind` column flags them. |
| **Ignoring the `^TMP` / `^XTMP` distinction** | Worrying about state in scratch globals | `^TMP` is per-job, dies with the process; `^XTMP` is system-temp with explicit expiration. Neither is "real" data. |
| **Multi-root workspace** | Sidebar inexplicably empty | Extension reads from the first workspace folder only. Open `vista-meta` as the sole folder. |

---

## 10. Setup checklist — keybindings and settings

Run-once checklist to make the rest of this guide fast.

**Once per machine:**

```bash
# 1. Tools on PATH
echo 'export PATH="$HOME/vista-meta/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc

# 2. Pre-commit hook
cd ~/vista-meta && make install-hooks

# 3. Extension built and installed
cd vscode-extension
npm install --ignore-scripts
npx tsc -p .
npx vsce package --no-dependencies --skip-license --allow-missing-repository
code --install-extension vista-meta-0.1.0.vsix

# 4. Sanity
vista-meta doctor          # all [ok]
```

**Workspace settings** (`.vscode/settings.json`):

```jsonc
{
  "editor.stickyScroll.enabled": true,
  "git.blame.editorDecoration.enabled": true,
  "editor.occurrencesHighlight": "singleFile",
  "editor.wordWrap": "on",
  "editor.wordWrapColumn": 132,
  "vistaMeta.topN": 25,
  "files.associations": { "*.m": "mumps" }
}
```

**Keybindings** (`Ctrl+K Ctrl+S`):

| Command | Suggested key | Earns |
|---|---|---|
| `workbench.action.terminal.toggleTerminal` | `Ctrl+\`` (default) | one-keystroke shell |
| `workbench.action.gotoSymbol` | `Ctrl+Shift+O` (default) | tag jump (Tier B) |
| `workbench.action.showAllSymbols` | `Ctrl+T` (default) | workspace tag search (Tier C) |
| `vistaMeta.reloadTsvs` | unbound — bind to `Ctrl+Alt+R` | after a TSV regen |
| `vistaMeta.refresh` | unbound — bind to `Ctrl+Alt+F5` | after switching branches |

**Optional but high-payoff extensions** from the marketplace
(orthogonal to vista-meta — none required):

- **GitLens** — beefs up the inline blame layer (L5).
- **Bookmarks** — useful when reading hubs > 500 lines and you want
  to mark "the actual logic" inside a sea of error handling.
- **Project Manager** — only matters if you work across multiple
  VistA forks.

---

## 11. Reference card

Print this and tape it next to the monitor.

```
┌────────────────────────────────────────────────────────────────┐
│ VISTA ROUTINE SITUATIONAL AWARENESS — SWEEP IN ORDER           │
├────────────────────────────────────────────────────────────────┤
│ L0 (5s)    Path → package; namespace prefix → confirm          │
│ L1 (15s)   Sidebar header + file lines 1–3 (title, version,    │
│            patches)                                            │
│ L2 (30s)   Tags section = TOC; spot EN, EN1, numeric tags,     │
│            STARTUP/SHUTDOWN                                    │
│ L3 (1–2m)  Callers (in-degree, package distribution)           │
│            Callees (out-degree, surprises)                     │
│            Globals (the truth — what data this touches)        │
│ L4 (1m)    RPC×N / OPT×N badges; vista-meta where TAG^RTN      │
│ L5 (var)   XINDEX findings; PIKS class of globals; git blame   │
├────────────────────────────────────────────────────────────────┤
│ FINGERPRINT: name [pkg] · NL · in=I · out=O · RPC×R · OPT×Op   │
│   I=0,RPC=0,OPT=0 → entrypoint or dead → CHECK L4              │
│   I=0, RPC>0 OR OPT>0 → live external entrypoint               │
│   I high, O low → utility / library                            │
│   I low,  O high → orchestrator                                │
│   I high, O high → framework — read with care                  │
├────────────────────────────────────────────────────────────────┤
│ TERMINAL ONE-LINERS:                                           │
│   vista-meta pkg <PKG>                  package overview       │
│   vista-meta where TAG^RTN              jump                   │
│   vista-meta callers TAG^RTN            who depends            │
│   vista-meta file N                     FileMan / PIKS         │
│   vista-meta context PKG --with-source  AI handoff             │
│   vista-meta xindex FILE                live SAC check         │
│   vista-meta doctor                     env health             │
└────────────────────────────────────────────────────────────────┘
```

---

## 12. Reference

- [vista-vscode-guide.md](vista-vscode-guide.md) — every tool this repo ships
- [vista-developers-guide.md](vista-developers-guide.md) — VistA architectural background
- [vscode-extension-internals.md](vscode-extension-internals.md) — internals + roadmap (HoverProvider, etc.)
- [code-model-guide.md](code-model-guide.md) — the 19 TSVs the sidebar reads
- [piks-analysis-guide.md](piks-analysis-guide.md) — what P/I/K/S means
- [xindex-reference.md](xindex-reference.md) — what the XINDEX section is showing you
- [kids-vc-guide.md](kids-vc-guide.md) — KIDS patch workflow (line-2 patch list)
