# VistA Compass (vista-meta VSCode Extension) — Internals & Roadmap

Architecture reference and extension roadmap for the
[vscode-extension/](../../vscode-extension/) source tree — shipped as
**VistA Compass 0.2.0** (`vista-compass-0.2.0.vsix`). Read
[vista-vscode-guide.md § 2](vista-vscode-guide.md#2-the-vscode-extension)
first for the user-facing surface; this document covers the inside of
the box and what to add next.

> Audience: anyone modifying the extension. The current code is
> ~1,200 lines across 6 TypeScript files — keep additions in that
> spirit.

---

## Table of contents

- [1. Scope and design constraints](#1-scope-and-design-constraints)
- [2. Architecture at a glance](#2-architecture-at-a-glance)
- [3. The six source files](#3-the-six-source-files)
- [4. Data flow on routine open](#4-data-flow-on-routine-open)
- [5. Current feature inventory](#5-current-feature-inventory)
- [6. Code-model data not yet surfaced](#6-code-model-data-not-yet-surfaced)
- [7. Recommended extensions, by tier](#7-recommended-extensions-by-tier)
  - [7.1 Tier A — HoverProvider (SHIPPED in 0.2.0)](#71-tier-a--hoverprovider-shipped-in-020)
  - [7.2 Tier B — DocumentSymbolProvider + DefinitionProvider](#72-tier-b--documentsymbolprovider--definitionprovider)
  - [7.3 Tier C — Diagnostics, workspace symbols, CodeLens](#73-tier-c--diagnostics-workspace-symbols-codelens)
  - [7.4 Tier D — Completion, status bar, semantic tokens](#74-tier-d--completion-status-bar-semantic-tokens)
  - [7.5 Tier E — Optional LSP migration](#75-tier-e--optional-lsp-migration)
- [8. Implementation sketches](#8-implementation-sketches)
- [9. Non-goals](#9-non-goals)

---

## 1. Scope and design constraints

The extension exists to make per-routine code-model data visible
without leaving the editor. Three constraints, in priority order:

1. **No runtime dependency on the container.** The extension reads
   TSVs and source files off disk; it must work offline, on a laptop,
   without YottaDB running.
2. **No MUMPS parser.** Tag detection is a regex scan of column-0
   labels. Anything that requires real parsing (expression types,
   variable scope, control flow) belongs in a separate tool.
3. **TSVs are the single source of truth.** If the data isn't in the
   schema_v1 data root (`code-model/*.tsv` + `data-model/*.tsv`), the
   extension does not invent it. Add it to the bake first, surface it
   in the UI second.

If a feature can't be implemented within those constraints, it goes
into the CLI or stays out.

---

## 2. Architecture at a glance

```
                     ┌──────────────────────────────────┐
  active editor ───► │  extension.ts (activation)       │
  (.m file path)     │  - wires onDidChangeActiveEditor │
                     │  - registers commands            │
                     │  - registers HoverProvider       │
                     │  - shows data vintage / warning  │
                     └───────┬───────────────┬──────────┘
                             │ setActiveFile │ provideHover(doc, pos)
                             ▼               ▼
     ┌──────────────────────────────┐  ┌──────────────────────────────┐
     │  treeProvider.ts             │  │  hover.ts                    │
     │  - maps RoutineInfo →        │  │  - VistaCompassHoverProvider │
     │    Tree nodes                │  │  - token parse + classify    │
     │  - HeaderNode / SectionNode /│  │    (routine / TAG^RTN / tag  │
     │    TagNode / CallerNode /    │  │    at col 0 / ^GLOBAL)       │
     │    CalleeNode / GlobalNode / │  │  - global → files.tsv →      │
     │    XindexNode                │  │    piks.tsv join             │
     └──────────────┬───────────────┘  └──────┬──────────────┬────────┘
                    │ analyze(routineName)    │              │
                    ▼                         │              │ globalBase()
     ┌──────────────────────────────┐         │              ▼
     │  routine.ts                  │         │  ┌────────────────────────┐
     │  - parseTags(filePath)       │         │  │  model.ts (pure)       │
     │  - resolveSourcePath(row)    │         │  │  - globalBase()        │
     │  - cross-joins 4 TSVs into   │         │  │  - vintageFrom…()      │
     │    one RoutineInfo           │         │  │  no vscode imports —   │
     └──────────────┬───────────────┘         │  │  node-testable         │
                    │ load / byColumn         │  └───────────▲────────────┘
                    ▼                         │              │ vintage parse
     ┌────────────────────────────────────────▼──────────────┴───────────┐
     │  tsv.ts                                                           │
     │  - data-root resolution (dataPath → auto-discover → legacy)       │
     │  - lazy file load + cache; per-(file, column) index cache         │
     │  - loadModel()/byColumnIn() for code-model AND data-model         │
     │  - dataVintage() from manifest.json / meta/column-manifest.json   │
     └───────────────────────────────────────────────────────────────────┘
```

The flow is one-directional: editor event (focus change or hover) →
routine/token analysis → TSV reads. `model.ts` is deliberately pure
(no `vscode` imports) so the schema_v1 contract helpers — `globalBase`
and the vintage parsers — are node-testable against the real
artifacts. There is no async work; the largest TSV
(`routine-calls.tsv`, ~20 MB) reads in ~200 ms on first access and
stays warm.

---

## 3. The six source files

### [extension.ts](../../vscode-extension/src/extension.ts)

Activation and wiring only. Creates the tree view
(`vistaCompassRoutine`, shown as **VistA Routine**), registers the
`VistaCompassHoverProvider` for `mumps`/`**/*.m` files, wires
`onDidChangeActiveTextEditor` so the sidebar reacts to editor focus,
and registers two commands (`vistaCompass.refresh`,
`vistaCompass.reloadTsvs`). On activation (and again on every
`Reload TSVs`) it reads `dataVintage()` and:

- sets the tree view's **description** to the vintage label —
  `data-v1 · 23d037f1` (release bundle) or `dev tree · schema v1`
  (repo tree);
- pops a warning if the data root declares a `schema_version` ≠ 1
  ("columns may not line up").

`vistaCompass.reloadTsvs` clears all three caches (row cache, column
indexes, the hover's global-base index), refreshes the tree, and
re-reads the vintage.

The activation predicate is `workspaceContains:**/*.m` — the
extension activates the moment any `.m` file exists in the workspace.

### [tsv.ts](../../vscode-extension/src/tsv.ts)

The TSV layer. Two caches:

- `cache: Map<filename, Row[]>` — parsed rows per file
- `indexCache: Map<"file::col", Map<value, Row[]>>` — per-(file,column)
  multi-value index

Both cleared by `reloadAll()` / `clearIndexes()` (the `Reload TSVs`
command). Caches are keyed by **absolute file path**, not bare
filename — the data root can change as the active file moves across
projects. Cells are split on `\t`; no quoting, no escapes — the bake
guarantees clean TSVs.

**Data-root resolution (0.2.0).** The extension resolves a **data
root** — a directory holding `code-model/` + `data-model/` — in this
order (`dataRoot()`):

1. `vistaCompass.dataPath`, if set. Absolute / `~`-prefixed values
   are used as-is; workspace-relative values are resolved by walking
   **up** from the active file, then from each workspace folder, then
   `workspaceFolders[0]/<rel>` (the walk-up is what makes the sidebar
   work when vista-meta is opened from a parent workspace like
   `~/projects`).
2. Auto-discovery, same walk-up rules: `vista/export` (the repo's dev
   tree) first, then `vista-meta-data-v1` (an unpacked release
   bundle).
3. Legacy fallback: the parent of `vistaCompass.codeModelPath`
   (deprecated, kept for pre-0.2.0 configs).

A candidate counts as a data root only if
`<root>/code-model/routines.tsv` exists (`isDataRoot()`).

`loadModel(model, name)` / `byColumnIn(model, …)` read either model
(`code-model` | `data-model`); the legacy `load`/`byColumn` are
code-model wrappers.

**Data vintage.** `dataVintage()` reads the bundle's `manifest.json`
(`tag`, `schema_version`, `content_hash`, `engine` — the V7 producer
contract) or, failing that, the dev tree's
`meta/column-manifest.json` (V3 — pins `schema_version` only, no data
identity). The result is cached with the TSVs, surfaced as the tree
view's description, and drives the schema_version ≠ 1 warning. A
broken manifest reads as "unknown", never a crash.

### [routine.ts](../../vscode-extension/src/routine.ts)

The cross-join. `analyze(routineName)` produces a `RoutineInfo` by
reading from four TSVs:

| Source | Purpose |
|---|---|
| `routines-comprehensive.tsv` | header (package, line count, in/out-degree, RPC/Option counts, `source_path`) |
| `routine-calls.tsv` (× 2 indexes) | callees (`caller_routine` → rows) and callers (`callee_routine` → rows) |
| `routine-globals.tsv` | globals touched by this routine |
| `xindex-errors.tsv` | static-analyzer findings |

Sidebar tags come from a regex scan of the on-disk file
(`parseTags`), not from a TSV — the hover provider does read
`xindex-tags.tsv`, but only to confirm a tag exists
([§7.1](#71-tier-a--hoverprovider-shipped-in-020)).

`resolveSourcePath` rewrites the container-side path
(`/opt/VistA-M/...`) to the host-visible path under
`vista/vista-m-host/`. The bake never sees the host filesystem; this
mapping is what bridges the two.

### [treeProvider.ts](../../vscode-extension/src/treeProvider.ts)

`RoutineTreeProvider` implements `vscode.TreeDataProvider`. State is
two fields: `activeFile: string | null` and `info: RoutineInfo | null`.
Editor focus changes call `setActiveFile`, which re-runs `analyze`
and fires the change event. All node types are local classes
(`HeaderNode`, `SectionNode`, `TagNode`, `CallerNode`, `CalleeNode`,
`GlobalNode`, `XindexNode`, `MessageNode`); each owns its
`toTreeItem()` and click command.

Click commands all use `vscode.open` with an optional `selection`
range — there is no custom command for navigation, just the built-in
opener.

### [model.ts](../../vscode-extension/src/model.ts)

Pure helpers over the schema_version 1 data contract — **no `vscode`
imports**, so everything here is node-testable against the real
artifacts. Two responsibilities:

- **Vintage parsing.** `vintageFromManifest()` (the bundle's
  `manifest.json`: tag, schema_version, content_hash, engine,
  extraction timestamp) and `vintageFromColumnManifest()` (the dev
  tree's `meta/column-manifest.json`: schema_version only) both
  return a `DataVintage` — a short UI label plus a tooltip-sized
  provenance line.
- **`globalBase(globalRoot)`.** `files.tsv` `global_root` is a
  storage root like `^DPT(` or `^DD("IX",`; `routine-globals.tsv`
  `global_name` is the bare name (`DPT`). `globalBase` strips the
  caret and everything from the first `(` — the join key between the
  two models.

### [hover.ts](../../vscode-extension/src/hover.ts)

`VistaCompassHoverProvider` — the Tier A hover, shipped in 0.2.0.
Registered for `{ language: 'mumps' }` and `**/*.m`. All facts come
from the same TSVs the sidebar uses; no parsing, no container. See
[§7.1](#71-tier-a--hoverprovider-shipped-in-020) for token
classification, hover cards, and the global → FileMan → PIKS join.
Owns one extra cache — the `files.tsv` global-base index
(`filesByGlobalBase()`), cleared by `clearGlobalBaseIndex()` on
`Reload TSVs`.

---

## 4. Data flow on routine open

```
1. User focuses PRCA45PT.m.
2. onDidChangeActiveTextEditor fires.
3. extension.ts checks doc.fileName.endsWith('.m'),
   calls provider.setActiveFile(path).
4. treeProvider.recomputeInfo:
     name = routineNameFromPath(path)        // "PRCA45PT"
     info = analyze(name)
5. analyze() pulls one row from routines-comprehensive.tsv,
   four indexed lookups from routine-calls/globals/xindex-errors.tsv,
   parses tags off disk.
6. _onDidChange.fire() — VSCode re-requests getChildren().
7. rootNodes() builds the tree from RoutineInfo,
   skipping zero-count sections.
```

Worst-case first-open cost (cold caches): ~250 ms dominated by the
`routine-calls.tsv` read. Every subsequent open is < 5 ms.

And on hover (the 0.2.0 path):

```
1. User hovers a token in a .m file.
2. VistaCompassHoverProvider matches TOKEN_RE at the cursor,
   parseToken() splits it ($$ prefix, ^ position).
3. Classification:
     TAG^RTN / $$TAG^RTN → routine card + tag badge
     ^X                  → routine if X is in
                           routines-comprehensive.tsv AND not
                           followed by '(' ; else global card
     bare ident at col 0 → tag-in-this-routine card
     bare ident after D/DO/G/GOTO/J/JOB, or a known routine
                         → routine card
4. Card builders read the already-cached column indexes; the global
   card additionally joins files.tsv (global_root base) → piks.tsv.
5. Return a vscode.Hover (markdown), or null → no popup.
```

---

## 5. Current feature inventory

| Feature | Implementation | Source |
|---|---|---|
| Sidebar tree view (`vistaCompassRoutine`, shown as **VistA Routine**) | `RoutineTreeProvider` in Explorer container | `treeProvider.ts` |
| Routine header (package, lines, in/out, RPC×, OPT×) | `HeaderNode` from `routines-comprehensive.tsv` | `treeProvider.ts` |
| Tags section (file TOC) | Regex scan of column-0 labels | `routine.ts` |
| Callers section (with package, ref-count) | Aggregated from `routine-calls.tsv` indexed on `callee_routine` | `routine.ts` |
| Callees section (with kind, ref-count) | `routine-calls.tsv` indexed on `caller_routine` | `routine.ts` |
| Globals section (with ref-count) | `routine-globals.tsv` indexed on `routine_name` | `routine.ts` |
| XINDEX section (severity icons, line jump) | `xindex-errors.tsv` indexed on `routine_name` | `routine.ts` |
| Click-to-open (tags / callers / callees / XINDEX line) | `vscode.open` command with selection range | `treeProvider.ts` |
| **Hover: routine card** (`RTN`, `^RTN`, bare name, `D RTN`) | package, size, in/out-degree, top callers/callees/globals | `hover.ts` |
| **Hover: `TAG^RTN` / `$$TAG^RTN`** | routine card + tag-exists badge from `xindex-tags.tsv` | `hover.ts` |
| **Hover: tag at column 0** | tag location + external callers of `TAG^RTN` | `hover.ts` |
| **Hover: `^GLOBAL` with FileMan + PIKS** | who-references summary + `files.tsv` (global_root base) → `piks.tsv` join — e.g. `^DPT` → File 2 PATIENT — PIKS **P** (Patient, auto) | `hover.ts`, `model.ts` |
| Data-root resolution (`dataPath` → auto-discover → legacy fallback) | walk-up search for `vista/export` / `vista-meta-data-v1` | `tsv.ts` |
| Data-vintage badge (sidebar description) + schema warning | `manifest.json` / `meta/column-manifest.json` → `DataVintage`; warns if schema_version ≠ 1 | `extension.ts`, `tsv.ts`, `model.ts` |
| MUMPS language id (`.m`) + bracket / comment config | `language-configuration.json` | `package.json` |
| Refresh + Reload TSVs commands (`vistaCompass.refresh`, `vistaCompass.reloadTsvs`) | Command palette entries | `extension.ts` |
| Configurable data root / vista-m-host path + topN | `vistaCompass.{dataPath, codeModelPath (deprecated), vistaMHostPath, topN}` | `package.json` |
| Empty-state messaging | `MessageNode` distinguishing "no .m open" vs "not in TSVs" | `treeProvider.ts` |

That is the complete current surface as of 0.2.0. Everything below is
**not yet implemented**.

---

## 6. Code-model data not yet surfaced

The bake produces 20 code-model TSVs plus the data-model TSVs. As of
0.2.0 the extension reads five of the code-model TSVs
(`routines-comprehensive`, `routine-calls`, `routine-globals`,
`xindex-errors`, `xindex-tags`) and two data-model TSVs (`files.tsv`,
`piks.tsv` — the hover's PIKS join). Unused payload:

| TSV | Carries | Useful for |
|---|---|---|
| `xindex-tags.tsv` (partially used) | per-tag rows: `routine_name`, `tag`, `data` — the hover only checks tag *existence* | Outline / DocumentSymbol backing; workspace symbols |
| `xindex-routines.tsv` | per-routine roll-up: line counts, MUMPS-vs-comment ratio, complexity | Status bar; hover header |
| `xindex-xrefs.tsv` | every variable / global / tag reference with line + offset | Reference provider; hover for any identifier under cursor |
| `xindex-validation.tsv` | secondary lint findings | Diagnostics |
| `rpcs.tsv` | RPC name, tag, routine, return type, availability, package | Hover when cursor is on an RPC entrypoint |
| `options.tsv` | option name, menu text, type, entry routine, package | Hover on option entrypoints |
| `protocols.tsv`, `protocol-calls.tsv` | protocol type (event / menu / extended), invokers | Hover; callers section enrichment |
| `vista-file-9-8.tsv` | File 9.8 (Routine) — VistA's own description, package owner, compile flag | Hover header |
| `package-manifest.tsv`, `package-edge-matrix.tsv` | per-package roll-up + cross-package edges | Workspace-level views |
| `package-piks-summary.tsv` | per-package PIKS distribution (the per-*global* PIKS join shipped in the 0.2.0 hover) | Package-level views |

Most recommendations below are "read TSV X, render in surface Y."

---

## 7. Recommended extensions, by tier

Ordered by leverage-to-effort ratio. Each tier is independent — pick
any subset.

### 7.1 Tier A — HoverProvider (SHIPPED in 0.2.0)

**Shipped** as [src/hover.ts](../../vscode-extension/src/hover.ts)
(`VistaCompassHoverProvider`), registered from `extension.ts` for
`{ language: 'mumps' }` and `**/*.m`. Zero new dependencies. Four
hover targets are live:

| Cursor on | Hover shows | Source TSV |
|---|---|---|
| Routine name (`RTN`, `^RTN`, bare name after a `D`/`DO`/`G`/`GOTO`/`J`/`JOB` verb, or any bare identifier that resolves to a routine) | Package, lines, tags, in/out-degree, RPC×/OPT×, globals count, top callers / callees / globals, source basename | `routines-comprehensive.tsv`, `routine-calls.tsv`, `routine-globals.tsv` |
| `TAG^ROUTINE` / `$$TAG^ROUTINE` call site | Routine card + a tag badge (found / not found in `xindex-tags.tsv`) | above + `xindex-tags.tsv` |
| Tag at column 0 (the entrypoint) | External callers of `TAG^ROUTINE` with ref-counts, or "no external callers — likely private" | `xindex-tags.tsv`, `routine-calls.tsv` |
| `^GLOBAL` reference | Who-references summary (routine count, total refs, top consumers) **plus the two-models join**: `files.tsv` rows whose `global_root` base matches → `piks.tsv` PIKS class — e.g. `^DPT` → File **2** PATIENT — PIKS **P** (Patient, auto) | `routine-globals.tsv`, data-model `files.tsv` + `piks.tsv` |

Mechanics worth knowing before touching it:

- **`^X` disambiguation:** if `X` exists in
  `routines-comprehensive.tsv` it's a routine — *unless* the very
  next character is `(`, which forces the global reading. Routines
  and FileMan globals don't collide in practice (`^DPT` is a global;
  `^DGRP` is a routine).
- **The bare-name join fix.** schema_v1 stores **bare** global names
  in `routine-globals.tsv` (`DPT`, not `^DPT`); the caret is
  display-only. The original lookup matched on the caret-prefixed
  form, which silently returned zero rows after the V1.7
  normalization — the global hover was dead until 0.2.0 fixed the
  lookup to strip the caret.
- **The PIKS join** (`appendPiksBlock`): top-level `files.tsv` rows
  (`parent_file` empty) are indexed by `globalBase(global_root)` —
  `^DD("IX",` → `DD` — then `file_number` → `piks.tsv` (B1: one
  authoritative row per file). Capped at 5 files per global, with a
  "… N more" overflow line. The index is a module-level cache cleared
  on `Reload TSVs`.
- **Noise control:** a bare identifier that is neither at column 0,
  nor after a call verb, nor a known routine name gets **no** hover —
  local variables stay quiet.

Why this was the headline 0.2.0 addition: every other surface in
VSCode is navigation. Hover is **comprehension** — the developer's
eyes never leave the code. For VistA specifically, the global →
FileMan file → PIKS class chain is what newcomers can't reconstruct
from the source alone, and what makes vista-meta uniquely useful.

**Still open from the original Tier A list** (genuinely unshipped):

| Cursor on | Hover would show | Source TSV |
|---|---|---|
| RPC name in code | RPC display name, return type, availability, broker entrypoint | `rpcs.tsv` |
| Option / protocol name | Type, menu text, entry routine | `options.tsv`, `protocols.tsv` |
| (enrichment) routine card | File 9.8 description / package owner | `vista-file-9-8.tsv` |
| (enrichment) global card | record count from `files.tsv` | data-model `files.tsv` |

### 7.2 Tier B — DocumentSymbolProvider + DefinitionProvider

**DocumentSymbolProvider** populates VSCode's built-in **Outline**
view and the breadcrumb bar with this routine's tags. Tags already
live in `RoutineInfo.tags` — wiring them through is ~30 lines. Side
benefits: `Ctrl+Shift+O` (Go to Symbol in Editor) starts working,
and the sticky-scroll header shows the current tag.

**DefinitionProvider** makes `Ctrl+Click` on a `TAG^ROUTINE` token
in `.m` source jump to the target. Currently the user has to find
the token in the Callees section first. Resolution path:

1. Tokenize the cursor word.
2. Match `^([A-Z%][A-Z0-9]*)\^([A-Z%][A-Z0-9]*)` etc.
3. Look up routine in `routines-comprehensive.tsv`, find its
   `source_path`, map to host.
4. If a tag is named, look it up in `xindex-tags.tsv` for the line.
5. Return a `vscode.Location`.

This is the same lookup the sidebar's CalleeNode does — extract once,
reuse for both.

### 7.3 Tier C — Diagnostics, workspace symbols, CodeLens

**Diagnostics from XINDEX.** `xindex-errors.tsv` already has
file-line-severity-message tuples. Push them through
`vscode.languages.createDiagnosticCollection('vista-meta-xindex')`
and findings light up in the Problems panel and inline in the gutter.
Add a setting `vistaCompass.xindexAsDiagnostics: boolean` — default off
until the bake is stable enough to avoid noise.

**WorkspaceSymbolProvider.** Powers `Ctrl+T` ("Go to Symbol in
Workspace"). Backed by `xindex-tags.tsv` — every public tag becomes a
workspace symbol named `TAG^ROUTINE`. With ~200k tags in a real
VistA, return only top-N matches and lean on VSCode's filter; do not
scan the full TSV per keystroke (build a sorted index once, binary-
search by prefix).

**CodeLens above each tag.** `N callers · N callees · N globals`
clickable to the sidebar sections. Visually noisy if always on — gate
behind a setting and ship it off-by-default.

### 7.4 Tier D — Completion, status bar, semantic tokens

**CompletionProvider for `TAG^ROUTINE` and `^GLOBAL`.** When the user
types `^`, suggest routine names from `routines.tsv`; when they type
`TAG^`, suggest tag names from `xindex-tags.tsv` filtered to that
routine. Useful, but lower priority — the sidebar + hover already
cover most of the navigation need.

**Status bar item.** Right-aligned segment showing
`PRCA45PT · AR · 74L · in=0 out=5`. One line of code, constant value
to the user. Click → command palette for `VistA Compass:` commands.

**Semantic tokens.** Custom highlighting for global references
colored by PIKS class (Patient = red, Institution = blue, Knowledge
= green, System = grey). Striking, but pragmatically: we don't have
a real MUMPS tokenizer, and naive regex coloring will misfire inside
string literals. Defer until a parser exists, or scope to global
references only with a conservative regex.

### 7.5 Tier E — Optional LSP migration

Currently the extension is in-process. If Tiers A–D land and the
combined provider count grows past ~6, consider extracting them into
a language server (`vscode-languageclient`) so the same logic can be
reused by Neovim, JetBrains MUMPS plugins, etc. Not a near-term
priority — the data layer is small enough that running it in-process
is fine, and an LSP adds installation complexity.

---

## 8. Implementation sketches

Concrete enough to start coding from. None of these are committed
yet — they are recommendations.

### 8.1 HoverProvider — shipped; sketch retired

The Tier A hover shipped in 0.2.0 as
[src/hover.ts](../../vscode-extension/src/hover.ts) — see
[§7.1](#71-tier-a--hoverprovider-shipped-in-020). The old sketch here
predates the implementation; the real code differs in two ways worth
noting if you extend it:

- `xindex-tags.tsv` carries only `routine_name` / `tag` / `data` —
  there is no `kind`, `formal_list`, or `summary` column, so the
  shipped tag card shows callers, not signatures. Signature help
  needs the bake to extract formals first.
- Routine-vs-global disambiguation is membership in
  `routines-comprehensive.tsv` (O(1) on the cached index), with one
  refinement: a `(` immediately after the token forces the global
  reading even when a same-named routine exists.

### 8.2 DocumentSymbolProvider sketch

```ts
export class TagSymbolProvider implements vscode.DocumentSymbolProvider {
  provideDocumentSymbols(doc: vscode.TextDocument): vscode.DocumentSymbol[] {
    const symbols: vscode.DocumentSymbol[] = [];
    for (let i = 0; i < doc.lineCount; i++) {
      const text = doc.lineAt(i).text;
      if (!text || text[0] === ' ' || text[0] === '\t' || text[0] === ';') continue;
      const m = text.match(/^([A-Z%][A-Z0-9]*|[0-9]+)/);
      if (!m) continue;
      const range = new vscode.Range(i, 0, i, m[1].length);
      symbols.push(new vscode.DocumentSymbol(
        m[1], '', vscode.SymbolKind.Function, range, range,
      ));
    }
    return symbols;
  }
}
```

Register with `vscode.languages.registerDocumentSymbolProvider`. The
parsing logic is identical to `parseTags()` in `routine.ts` — extract
to a shared helper to avoid duplication.

### 8.3 Diagnostics from XINDEX sketch

```ts
const collection = vscode.languages.createDiagnosticCollection('vista-compass-xindex');
ctx.subscriptions.push(collection);

function refreshDiagnostics(doc: vscode.TextDocument) {
  if (!doc.fileName.endsWith('.m')) return;
  const routine = routineNameFromPath(doc.fileName);
  if (!routine) return;
  const errs = byColumn('xindex-errors.tsv', 'routine_name').get(routine) ?? [];
  const diags = errs
    .filter(e => /^\d+$/.test(e['line_text'] || ''))
    .map(e => {
      const ln = parseInt(e['line_text'], 10) - 1;
      const sev = sevToVscode(e['error_text']);
      return new vscode.Diagnostic(
        new vscode.Range(ln, 0, ln, 999),
        e['error_text'],
        sev,
      );
    });
  collection.set(doc.uri, diags);
}
```

Wire to `onDidOpenTextDocument` and `onDidChangeTextDocument` (debounced).

---

## 9. Non-goals

The following are deliberately **out of scope**, even though VSCode
extensions in adjacent ecosystems often ship them:

- **Real-time MUMPS evaluation / debugging.** Belongs to a YDB
  debugger, not us.
- **Refactoring (rename tag, extract function).** Requires a real
  parser. Out of scope until one exists.
- **Auto-formatting on save.** `mfmt` is the canonical formatter,
  invoked by hook and CI. The extension should not format on save —
  we already had one false-positive incident
  ([build-log BL-007](../build-log.md)) and any in-editor formatter
  must agree byte-for-byte with `mfmt`.
- **Live container introspection** (running `D ^XINDEX` from the
  extension, querying globals over a broker). Violates constraint
  #1; the CLI does this when needed.
- **Multiple simultaneous data roots.** 0.2.0's walk-up resolution
  (from the active file, then each workspace folder) already makes
  multi-root workspaces *work* — but only one data root is resolved
  at a time, following the active file. Merging several data roots
  into one view is out of scope; document the semantics, don't paper
  over them.
- **Telemetry.** The extension is a single-user dev tool; no usage
  collection.

If a feature request implies any of the above, push it to the CLI or
a sibling tool. Keep the extension small.

---

## 10. Reference

- [vista-vscode-guide.md § 2](vista-vscode-guide.md#2-the-vscode-extension) — user-facing surface
- [code-model-guide.md](code-model-guide.md) — every TSV the extension reads
- [piks-analysis-guide.md](piks-analysis-guide.md) — the global → file → PIKS chain the 0.2.0 hover exposes
- [VSCode extension API](https://code.visualstudio.com/api/references/vscode-api) — provider interfaces
- [vscode-extension/src/](../../vscode-extension/src/) — the current 6-file source tree
