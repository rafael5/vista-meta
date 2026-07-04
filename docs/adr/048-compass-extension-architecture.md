# ADR-048: VistA Compass — offline TSV-reading extension over the schema_v1 data root

Date: 2026-07-04 (backfill — architecture shipped incrementally, 0.1.0 → 0.2.0 commit 5b7811f)
Status: Accepted

## Context

Per-routine situational awareness (tags, callers, callees, globals, XINDEX,
PIKS) needed an editor surface. The models already exist as flat TSVs; a
running VEHU container must not be a prerequisite for reading code.

## Decision

The VSCode extension (**VistA Compass**, `vscode-extension/`) is a **Level-1
offline reader of the schema_v1 data root** — no runtime dependency on the
container, no server, no reimplemented analysis:

1. **Data interface = the schema_v1 DATA ROOT** (`code-model/` + `data-model/`
   siblings), resolved by `vistaCompass.dataPath` → auto-discovery (walk up
   from the active file for the repo's `vista/export` tree, else an unpacked
   `vista-meta-data-v1` release bundle) → deprecated `codeModelPath` fallback.
   The same binary data contract serves the dev tree and the public release.
2. **Vintage is surfaced, not assumed** — the sidebar shows the data's identity
   (release `tag · content_hash` from the bundle manifest, or
   "dev tree · schema v1" from `meta/column-manifest.json`) and warns when
   `schema_version ≠ 1`.
3. **Six-file architecture** with pure logic separated from VSCode plumbing:
   `extension.ts` (activation/commands), `tsv.ts` (data-root resolution +
   TSV loading), `routine.ts`, `treeProvider.ts` (sidebar), and the 0.2.0
   additions `model.ts` (pure, no vscode imports — global-base + vintage
   parsing, node-testable) and `hover.ts` (global/PIKS hovers via the
   two-model join: global → `files.tsv` global_root → `piks.tsv`).
4. **Namespace `vistaCompass.*`** for commands/config/views (the earlier
   `vistaMeta.*` names are retired).

## Consequences

- Positive: works on any machine with the data (release bundle or repo);
  hovers/joins stay consistent with the CLI because both read the same TSVs;
  pure `model.ts` gets real unit tests.
- Negative: no live-container features (record counts, runtime state) — by
  design; TSV loads are memory-resident (fine at ~1M rows, revisit if the
  model grows an order of magnitude).
- Neutral: packaged per-platform as `vista-compass-<version>.vsix`; not on the
  marketplace (private distribution).

## Alternatives considered

- **LSP/daemon architecture** — rejected (spec §"engineering non-goals"): a
  static TSV read at activation is simpler and sufficient.
- **Querying the container (RPC/Octo)** — rejected: reintroduces the runtime
  dependency the flat-TSV design exists to avoid.
- **SQLite instead of TSVs** — unnecessary at current scale; TSVs keep the
  data git-diffable and awk-queryable.
