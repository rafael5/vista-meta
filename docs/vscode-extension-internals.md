# vista-meta VSCode Extension — Internals & Roadmap

Architecture reference and extension roadmap for the
[vscode-extension/](../vscode-extension/) source tree. Read
[vista-vscode-guide.md § 2](vista-vscode-guide.md#2-the-vscode-extension)
first for the user-facing surface; this document covers the inside of
the box and what to add next.

> Audience: anyone modifying the extension. The current code is ~500
> lines across 4 TypeScript files — keep additions in that spirit.

---

## Table of contents

- [1. Scope and design constraints](#1-scope-and-design-constraints)
- [2. Architecture at a glance](#2-architecture-at-a-glance)
- [3. The four source files](#3-the-four-source-files)
- [4. Data flow on routine open](#4-data-flow-on-routine-open)
- [5. Current feature inventory](#5-current-feature-inventory)
- [6. Code-model data not yet surfaced](#6-code-model-data-not-yet-surfaced)
- [7. Recommended extensions, by tier](#7-recommended-extensions-by-tier)
  - [7.1 Tier A — HoverProvider (highest leverage)](#71-tier-a--hoverprovider-highest-leverage)
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
3. **TSVs are the single source of truth.** If the data isn't in
   `vista/export/code-model/*.tsv`, the extension does not invent
   it. Add it to the bake first, surface it in the UI second.

If a feature can't be implemented within those constraints, it goes
into the CLI or stays out.

---

## 2. Architecture at a glance

```
                     ┌──────────────────────────────────┐
  active editor ───► │  extension.ts (activation)       │
  (.m file path)     │  - wires onDidChangeActiveEditor │
                     │  - registers commands            │
                     └──────────────┬───────────────────┘
                                    │ setActiveFile(path)
                                    ▼
                     ┌──────────────────────────────────┐
                     │  treeProvider.ts                 │
                     │  - maps RoutineInfo → Tree nodes │
                     │  - HeaderNode / SectionNode /    │
                     │    TagNode / CallerNode /        │
                     │    CalleeNode / GlobalNode /     │
                     │    XindexNode                    │
                     └──────────────┬───────────────────┘
                                    │ analyze(routineName)
                                    ▼
                     ┌──────────────────────────────────┐
                     │  routine.ts                      │
                     │  - parseTags(filePath)           │
                     │  - resolveSourcePath(row)        │
                     │  - cross-joins 4 TSVs into one   │
                     │    RoutineInfo                   │
                     └──────────────┬───────────────────┘
                                    │ load(name) / byColumn(...)
                                    ▼
                     ┌──────────────────────────────────┐
                     │  tsv.ts                          │
                     │  - lazy file load + cache        │
                     │  - per-(file, column) index cache│
                     │  - workspace path resolution     │
                     └──────────────────────────────────┘
```

The flow is one-directional: editor event → tree refresh → routine
analysis → TSV reads. There is no async work; the largest TSV
(`routine-calls.tsv`, ~20 MB) reads in ~200 ms on first access and
stays warm.

---

## 3. The four source files

### [extension.ts](../vscode-extension/src/extension.ts)

Activation only. Creates the tree view, wires
`onDidChangeActiveTextEditor` so the sidebar reacts to editor focus,
and registers two commands (`vistaMeta.refresh`,
`vistaMeta.reloadTsvs`). 51 lines.

The activation predicate is `workspaceContains:**/*.m` — the
extension activates the moment any `.m` file exists in the workspace.

### [tsv.ts](../vscode-extension/src/tsv.ts)

The TSV layer. Two caches:

- `cache: Map<filename, Row[]>` — parsed rows per file
- `indexCache: Map<"file::col", Map<value, Row[]>>` — per-(file,column)
  multi-value index

Both cleared by `reloadAll()` / `clearIndexes()` (the `Reload TSVs`
command). Cells are split on `\t`; no quoting, no escapes — the bake
guarantees clean TSVs.

Workspace path resolution: paths are read from the
`vistaMeta.codeModelPath` and `vistaMeta.vistaMHostPath` settings,
joined to the first workspace folder. There is no support for
multi-root workspaces — see [§10 of vista-vscode-guide.md](vista-vscode-guide.md#10-troubleshooting).

### [routine.ts](../vscode-extension/src/routine.ts)

The cross-join. `analyze(routineName)` produces a `RoutineInfo` by
reading from four TSVs:

| Source | Purpose |
|---|---|
| `routines-comprehensive.tsv` | header (package, line count, in/out-degree, RPC/Option counts, `source_path`) |
| `routine-calls.tsv` (× 2 indexes) | callees (caller_name → rows) and callers (callee_routine → rows) |
| `routine-globals.tsv` | globals touched by this routine |
| `xindex-errors.tsv` | static-analyzer findings |

Tags come from a regex scan of the on-disk file (`parseTags`), not
from a TSV — `xindex-tags.tsv` has the same data but isn't read yet
([§6](#6-code-model-data-not-yet-surfaced)).

`resolveSourcePath` rewrites the container-side path
(`/opt/VistA-M/...`) to the host-visible path under
`vista/vista-m-host/`. The bake never sees the host filesystem; this
mapping is what bridges the two.

### [treeProvider.ts](../vscode-extension/src/treeProvider.ts)

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

---

## 5. Current feature inventory

| Feature | Implementation | Source |
|---|---|---|
| Sidebar tree view (`VISTA ROUTINE`) | `RoutineTreeProvider` in Explorer container | `treeProvider.ts` |
| Routine header (package, lines, in/out, RPC×, OPT×) | `HeaderNode` from `routines-comprehensive.tsv` | `treeProvider.ts:119` |
| Tags section (file TOC) | Regex scan of column-0 labels | `routine.ts:67` |
| Callers section (with package, ref-count) | Aggregated from `routine-calls.tsv` indexed on `callee_routine` | `routine.ts:119` |
| Callees section (with kind, ref-count) | `routine-calls.tsv` indexed on `caller_name` | `routine.ts:108` |
| Globals section (with ref-count) | `routine-globals.tsv` indexed on `routine_name` | `routine.ts:140` |
| XINDEX section (severity icons, line jump) | `xindex-errors.tsv` indexed on `routine` | `routine.ts:149` |
| Click-to-open (tags / callers / callees / XINDEX line) | `vscode.open` command with selection range | `treeProvider.ts` |
| MUMPS language id (`.m`) + bracket / comment config | `language-configuration.json` | `package.json:16` |
| Refresh + Reload TSVs commands | Command palette entries | `extension.ts:38` |
| Configurable code-model / vista-m-host paths + topN | `vistaMeta.*` settings | `package.json:52` |
| Empty-state messaging | `MessageNode` distinguishing "no .m open" vs "not in TSVs" | `treeProvider.ts:48` |

That is the complete current surface. Everything below is **not yet
implemented**.

---

## 6. Code-model data not yet surfaced

The bake produces 19 TSVs. The extension reads 4. Unused payload:

| TSV | Carries | Useful for |
|---|---|---|
| `xindex-tags.tsv` | per-tag metadata: kind, line, parameters, formal-list, doc-comment summary | Hover for tag entrypoints; outline; signature help |
| `xindex-routines.tsv` | per-routine roll-up: line counts, MUMPS-vs-comment ratio, complexity | Status bar; hover header |
| `xindex-xrefs.tsv` | every variable / global / tag reference with line + offset | Reference provider; hover for any identifier under cursor |
| `xindex-validation.tsv` | secondary lint findings | Diagnostics |
| `rpcs.tsv` | RPC name, tag, routine, return type, doc | Hover when cursor is on an RPC entrypoint |
| `options.tsv` | option name, type, description, entry routine | Hover on option entrypoints |
| `protocols.tsv`, `protocol-calls.tsv` | protocol type (event / menu / extended), invokers | Hover; callers section enrichment |
| `vista-file-9-8.tsv` | File 9.8 (Routine) — VistA's own description, package owner, compile flag | Hover header |
| `package-manifest.tsv`, `package-edge-matrix.tsv` | per-package roll-up + cross-package edges | Workspace-level views |
| `package-piks-summary.tsv` + data-model TSVs | global → FileMan file → PIKS classification | Hover for `^GLOBAL` references — "this is Patient data" |

Most recommendations below are "read TSV X, render in surface Y."

---

## 7. Recommended extensions, by tier

Ordered by leverage-to-effort ratio. Each tier is independent — pick
any subset.

### 7.1 Tier A — HoverProvider (highest leverage)

**The headline addition.** When the cursor is over an identifier in
a `.m` file, show a markdown popup pulled from the code model. Six
hover targets, one provider:

| Cursor on | Hover shows | Source TSV |
|---|---|---|
| Routine name (file header, or `^ROUTINE` reference) | Package, line count, in/out-degree, RPC×/OPT×, File 9.8 description, top callers/callees | `routines-comprehensive.tsv`, `vista-file-9-8.tsv` |
| Tag at column 0 (the entrypoint) | Tag kind, line, formal parameters, ref-count from callers, doc-comment summary | `xindex-tags.tsv`, `routine-calls.tsv` |
| `TAG^ROUTINE` call site | Same as routine + tag, shown as a single card | `xindex-tags.tsv`, `routine-calls.tsv` |
| `^GLOBAL` reference | Global root, FileMan file (if any) + file number + name, **PIKS class** (P/I/K/S), record count, top routines that touch it | `routine-globals.tsv`, `vista-file-9-8.tsv`, data-model `files.tsv` + `piks.tsv` |
| RPC name in code | RPC display name, return type, doc, broker entrypoint | `rpcs.tsv` |
| Option / protocol name | Type, description, entry routine | `options.tsv`, `protocols.tsv` |

Why this is highest-value: every other surface in VSCode is
navigation. Hover is **comprehension** — the developer's eyes never
leave the code. For VistA specifically, the global → FileMan file →
PIKS class chain is what newcomers can't reconstruct from the source
alone, and what makes vista-meta uniquely useful.

Implementation lives in a new `src/hoverProvider.ts`. Wire from
`extension.ts`:

```ts
ctx.subscriptions.push(
  vscode.languages.registerHoverProvider(
    { language: 'mumps', scheme: 'file' },
    new VistaMetaHoverProvider(),
  ),
);
```

The provider takes a `Position`, runs a small lexer to classify the
token (routine name vs tag vs global vs call ref), then calls into
existing TSV indexes. Total add: ~250 lines, zero new dependencies.

Sketch in [§8.1](#81-hoverprovider-sketch).

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
Add a setting `vistaMeta.xindexAsDiagnostics: boolean` — default off
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
to the user. Click → command palette for `vista-meta:` commands.

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

### 8.1 HoverProvider sketch

`src/hoverProvider.ts`:

```ts
import * as vscode from 'vscode';
import { byColumn } from './tsv';

const ROUTINE_RE = /[A-Z%][A-Z0-9]{0,7}/;
const TAG_AT_ROUTINE_RE = /([A-Z%][A-Z0-9]*)\^([A-Z%][A-Z0-9]{0,7})/;
const GLOBAL_RE = /\^([A-Z%][A-Z0-9]*)/;

export class VistaMetaHoverProvider implements vscode.HoverProvider {
  provideHover(
    doc: vscode.TextDocument,
    pos: vscode.Position,
  ): vscode.ProviderResult<vscode.Hover> {
    const line = doc.lineAt(pos.line).text;
    const wordRange = doc.getWordRangeAtPosition(pos, /[A-Z%][A-Z0-9]*/);
    if (!wordRange) return null;
    const word = doc.getText(wordRange);

    // Classify by surrounding context
    const before = line.slice(0, wordRange.start.character);
    const after  = line.slice(wordRange.end.character);

    if (after.startsWith('^')) {
      // TAG^ROUTINE — left side is a tag
      const routineMatch = after.match(/^\^([A-Z%][A-Z0-9]{0,7})/);
      if (routineMatch) {
        return this.hoverTagInRoutine(word, routineMatch[1]);
      }
    }
    if (before.endsWith('^')) {
      // ^ROUTINE or ^GLOBAL — disambiguate by uppercase + length
      // (globals tend to be ≤4 chars; routines ≤8). Fall back to
      // checking routines.tsv membership.
      return this.hoverRoutineOrGlobal(word);
    }
    if (pos.character < 8 && wordRange.start.character === 0) {
      // Column-0 — this is a tag definition in the current routine
      const routineName = routineNameFromDoc(doc);
      if (routineName) return this.hoverTagInRoutine(word, routineName);
    }
    // Bare identifier — try as a routine
    return this.hoverRoutineOrGlobal(word);
  }

  private hoverTagInRoutine(tag: string, routine: string): vscode.Hover | null {
    const tagRows = byColumn('xindex-tags.tsv', 'routine').get(routine) ?? [];
    const tagRow = tagRows.find(r => r['tag'] === tag);
    if (!tagRow) return null;

    const callers = byColumn('routine-calls.tsv', 'callee_routine').get(routine) ?? [];
    const tagCallers = callers.filter(r => r['callee_tag'] === tag);
    const totalRefs = tagCallers.reduce(
      (n, r) => n + parseInt(r['ref_count'] || '0', 10), 0);

    const md = new vscode.MarkdownString();
    md.appendMarkdown(`**${tag}^${routine}**  \n`);
    md.appendMarkdown(`kind: \`${tagRow['kind'] || '?'}\`  \n`);
    if (tagRow['formal_list']) {
      md.appendCodeblock(`${tag}(${tagRow['formal_list']})`, 'mumps');
    }
    if (tagRow['summary']) {
      md.appendMarkdown(`\n${tagRow['summary']}\n`);
    }
    md.appendMarkdown(`\n${tagCallers.length} callers · ${totalRefs} refs`);
    return new vscode.Hover(md);
  }

  private hoverRoutineOrGlobal(name: string): vscode.Hover | null {
    // Try routine first
    const rRow = byColumn('routines-comprehensive.tsv', 'routine_name').get(name)?.[0];
    if (rRow) {
      const md = new vscode.MarkdownString();
      md.appendMarkdown(`**${name}** \`[${rRow['package']}]\`  \n`);
      md.appendMarkdown(
        `${rRow['line_count']} lines · in=${rRow['in_degree']} · ` +
        `out=${rRow['out_degree']}  \n`,
      );
      const desc = rRow['description_98'];
      if (desc) md.appendMarkdown(`\n${desc}\n`);
      return new vscode.Hover(md);
    }

    // Fall back to global lookup — needs data-model TSVs
    // (left as exercise; pattern identical to routine lookup)
    return null;
  }
}
```

The disambiguation between routine references and globals is the
fiddly part. A cheap rule: if the token appears in
`routines-comprehensive.tsv`, treat it as a routine; otherwise as a
global. The lookup is O(1) on the cached index.

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
const collection = vscode.languages.createDiagnosticCollection('vista-meta-xindex');
ctx.subscriptions.push(collection);

function refreshDiagnostics(doc: vscode.TextDocument) {
  if (!doc.fileName.endsWith('.m')) return;
  const routine = routineNameFromPath(doc.fileName);
  if (!routine) return;
  const errs = byColumn('xindex-errors.tsv', 'routine').get(routine) ?? [];
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
  ([build-log BL-007](build-log.md)) and any in-editor formatter
  must agree byte-for-byte with `mfmt`.
- **Live container introspection** (running `D ^XINDEX` from the
  extension, querying globals over a broker). Violates constraint
  #1; the CLI does this when needed.
- **Multi-root workspace support.** The bake assumes one workspace
  root; supporting more is a non-trivial path-resolution refactor.
  Document the limitation, don't paper over it.
- **Telemetry.** The extension is a single-user dev tool; no usage
  collection.

If a feature request implies any of the above, push it to the CLI or
a sibling tool. Keep the extension small.

---

## 10. Reference

- [vista-vscode-guide.md § 2](vista-vscode-guide.md#2-the-vscode-extension) — user-facing surface
- [code-model-guide.md](code-model-guide.md) — every TSV the extension reads
- [piks-analysis-guide.md](piks-analysis-guide.md) — the global → file → PIKS chain hover would expose
- [VSCode extension API](https://code.visualstudio.com/api/references/vscode-api) — provider interfaces
- [vscode-extension/src/](../vscode-extension/src/) — the current 4-file source tree
