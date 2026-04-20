# vista-meta — VistA Sidebar for VSCode

When you open a `.m` file inside the vista-meta workspace, a sidebar
panel under the Explorer view appears showing everything the
`vista/export/code-model/` TSVs know about the routine:

- Package + source path
- Line count, in-degree, out-degree
- Tags in this routine (clickable — reveals the line)
- Callers (aggregated per caller routine, with ref counts — click to jump)
- Callees (with ref counts — click to open the target routine)
- Global usage, ranked by ref count
- XINDEX findings, severity-icon-coded (click to reveal line)

No language server. No MCP. No container calls. Pure file-reading
over data you already generated with `make routines-comprehensive`
and friends. Updates immediately when you switch files.

## Install (local .vsix, no marketplace)

```bash
cd vscode-extension
npm install --ignore-scripts
npx tsc -p .
npx vsce package --no-dependencies --skip-license
code --install-extension vista-meta-*.vsix
```

Reload VSCode. Open any `.m` file in the vista-meta workspace; the
"VistA Routine" panel appears in the Explorer view.

## Refresh after regenerating TSVs

TSVs are cached in memory for the VSCode session. After running
`make sync-routines && make routines-comprehensive` (etc.), run the
command palette action:

```
vista-meta: Reload Code-Model TSVs
```

## Settings

- `vistaMeta.codeModelPath` — default `vista/export/code-model`
- `vistaMeta.vistaMHostPath` — default `vista/vista-m-host`
- `vistaMeta.topN` — default 15, caps per-section entries

## Why not a language server?

A full MUMPS LSP would be months of work. The sidebar gets you the
90%-case benefit (symbol navigation, caller graph, XINDEX findings,
globals touched) using the already-computed code-model TSVs, with
zero runtime dependencies beyond Node.
