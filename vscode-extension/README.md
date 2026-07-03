# VistA Compass

**A compass for VistA's code — point it at any `.m` routine to get
your bearings, then click any reference, call-in, call-out, global,
or XINDEX finding to navigate through *all* of VistA's rich,
interconnected web of routines, FileMan files, pointers, RPCs,
options, protocols, and globals.**

VistA is huge: ~39,000 routines across 130+ packages, tied together
by tag-level calls between routines, FileMan field-level pointers
between files, RPC bindings, option menus, protocol events, and
~9,800 shared globals — all accreted over forty years of clinical
software. Reading one routine in isolation tells you almost nothing.

VistA Compass turns the [vista-meta](https://github.com/rafael5/vista-meta)
code-model TSVs — roughly 1M rows of pre-extracted facts across 19
tables covering every routine, call edge, FileMan pointer, RPC,
option, protocol, global reference, and lint finding — into an
always-on sidebar (plus an in-editor hover surface) where **every row
is a clickable jump**. Click a caller and you're in the caller. Click
a callee and you're in the callee. Click an XINDEX finding and you're
on the offending line. Click a `^GLOBAL` reference in the source and
the hover card tells you which routines write it. Reading VistA stops
being a search-and-scroll exercise; it becomes a graph walk.

## What you see when you open a routine

Drop into any `.m` file and the **VistA Routine** panel under the
Explorer view fills in immediately:

| Section | What it tells you |
|---|---|
| **Header** | Package, source path, line count, in-degree, out-degree |
| **Tags** | Every entry point in this routine — click to reveal the line |
| **Callers** | Who calls in, aggregated per caller routine, with ref counts — click to jump |
| **Callees** | Who this routine calls out to, with ref counts — click to open the target |
| **Globals** | Which `^GLOBALS` it reads or writes, ranked by ref count |
| **XINDEX** | Lint findings, severity-icon-coded — click to reveal the offending line |

Everything is clickable. Switching between routines is instant — the
sidebar redraws from cached TSVs, no parser, no container call, no
network.

## Hover, too

Hover over a `TAG^ROUTINE`, `$$FUNC^ROUTINE`, or `^GLOBAL` reference
anywhere in a `.m` file and you get a card showing the target's
package, callers, callees, and globals — without leaving the line.
Same data, same TSVs, same zero-cost lookup.

## What it isn't

- **Not a language server.** Writing a full MUMPS LSP is months of
  work; VistA Compass gets you the 90% case (navigation, caller
  graph, XINDEX, global usage) from already-computed data.
- **Not a parser.** It never reads or interprets `.m` source for
  semantics — all facts come from the vista-meta extraction pipeline.
- **Not a runtime dependency.** No MCP server, no container shell-out,
  no internet. Pure Node + TSV reads against files already on disk.

## Install (local `.vsix`, no marketplace)

```bash
cd vscode-extension
npm install --ignore-scripts
npx tsc -p .
npx vsce package --no-dependencies --skip-license
code --install-extension vista-compass-*.vsix
```

Reload VSCode. Open any `.m` file in the vista-meta workspace; the
**VistA Routine** panel appears under Explorer.

## Refresh after regenerating TSVs

TSVs are cached in memory for the VSCode session. After running
`make sync-routines && make routines-comprehensive` (etc.) in the
parent vista-meta repo, run the command palette action:

```
VistA Compass: Reload Code-Model TSVs
```

The sidebar will redraw from fresh data on the next routine switch.

## Settings

- `vistaCompass.codeModelPath` — default `vista/export/code-model`.
  Workspace-relative path to the code-model TSV directory. Absolute
  or `~/`-prefixed values are honored as-is.
- `vistaCompass.vistaMHostPath` — default `vista/vista-m-host`.
  Workspace-relative path to the host-synced VistA-M source tree —
  used to jump to source lines.
- `vistaCompass.topN` — default `15`. Caps the per-section entry
  count (callers, callees, globals) so dense routines don't blow the
  tree wide open.

## How it fits in

VistA Compass is the **interactive read surface** for the vista-meta
project. vista-meta extracts and reduces the entire VistA corpus into
machine-readable TSVs covering inventory, relationships, code quality,
and authoritative metadata (RPCs, options, protocols, FileMan files).
That work happens offline, in batch, in a container. VistA Compass is
the live, in-editor consumer of those TSVs — the part you actually
look at while writing or reading M code.

The compass needle always points at the routine you're in. Everything
else is bearings — and one click away.
