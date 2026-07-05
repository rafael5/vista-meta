# Vista Atlas + Vista Compass — de-novo twin editor extensions over the published releases

**Status:** Draft · 2026-07-05
**Owner:** rafael
**Scope:** two repos' human surfaces — vdocs-web (superseded by **Vista Atlas**) and
`vscode-extension/` here (superseded by **Vista Compass v2**)
**Benchmark:** the two MCP front doors (`vdocs serve-mcp` · `host/scripts/mcp_server.py`) —
the machine interfaces already expose the full published scope; the human interfaces do not.
**Grounding:** 2026-07-05 three-way survey (vdocs-web consumption · vdocs gold human
surface · Compass extension consumption); measured facts below cite it.

## 1. Problem

Both human consumers use slivers of what the producers publish, and each sliver was
grown incrementally against formats that have since matured into pinned, contracted,
release-fetched artifacts:

- **Vista Compass 0.2.0** reads **7 of 24 TSVs** (5 code-model + 2 data-model). RPCs,
  options, protocols, the package topology set (`package-edge-matrix`,
  `package-manifest`, `package-piks-summary`), `xindex-xrefs`, `field-piks`, the
  entity bridge, `package-namespace`'s vdocs keys (`app_code`/`vdl_id`), `meta.db`,
  and the AI card are all shipped and all unread. Its own internals guide defers the
  whole Tier B–D roadmap on shapes the current whole-file-TSV-parse model can't
  serve (per-keystroke symbol search over ~292k tags; signatures).
- **vdocs-web** reconstructs bodies from `v_chunks` and hydrates tables/figures, but
  the **entity graph is dark** (queryable in its vendored library, no API/UI),
  **relations are not in the read contract** (cross-doc navigation impossible),
  boilerplate links and revision history dead-end, version lineage is unmodeled, and
  a release-download install is **text-only** (rich assets/tables excluded).
- The two surfaces don't know about each other. The dual-source discipline
  (`documented:` × `measured:`) exists for AI (skills, agents, MCP orientations,
  the entity bridge) — a human in the editor gets none of it.

**The parity principle:** anything the machine front doors can answer, a human in
the editor should be able to see and navigate. Both MCP servers reach the full
published scope; the rewrite makes the human surfaces do the same.

## 2. Goal

Two sibling VSCode extensions, designed as a pair:

- **Vista Atlas** — *what the documentation says.* The de-novo successor of
  vdocs-web as an in-editor navigator over the vdocs data release (index.db +
  gold reading surface + rich bundles).
- **Vista Compass v2** — *what the system measurably is.* The de-novo successor of
  the current extension, over the vista-meta data release (meta.db as the store,
  TSVs as the model of record).
- **One bridge between them.** Entity-level deep links both ways (the W3 bridge +
  `app_code`), so "open the docs for this RPC" and "show me the measured routine
  behind this doc mention" are single clicks — the human twin of the
  `documented:`/`measured:` MCP contract.

## 3. Design principles

1. **Consumers of releases, not repo internals.** Both extensions acquire data by
   fetch-and-verify of the published release artifacts (both standalone manifests
   already carry per-file sha256 + schema/read version; vdocs-web's `dbfetch`
   proves the pattern) — or point at a local lake/checkout for dev. Neither
   extension requires its producer repo.
2. **Contract-first reads.** Atlas binds only to the `read_schema_version`'d `v_*`
   views + `chunks_fts` (the vendored-contract seam vdocs-web proved, ported to
   TS). Compass binds to `meta.db`'s tables/views + `ai-manifest.json` as its
   self-describing catalog (columns, pks, join keys — no hardcoded schemas).
3. **One storage engine, chosen once (P0 spike).** index.db is **322 MB**, meta.db
   **85 MB** — `sql.js` (whole-db-in-WASM-heap) is out. Recommended:
   **`better-sqlite3`** with platform-specific VSIX builds (CI matrix; standard
   practice), which memory-maps both files and gives FTS5 + indexes for free —
   this dissolves Compass's "pre-sorted symbol index" format problem (an index on
   `xindex_tags(tag)` *is* the symbol index). Fallbacks, in order: Node ≥22
   built-in `node:sqlite` (VSCode's Electron permitting); a spawned Go sidecar
   reusing vdocs-web's `internal/index` read-contract library behind localhost.
4. **Stable-ID deep links.** A documented command-URI contract:
   `vistaAtlas.open(doc_key|section_id|entity_id)` ·
   `vistaCompass.lookup(kind, key)`. Same IDs as the MCP citations
   (`vdocs://section/<id>`; `vista-meta data-v1 · tsv · key=value`), so AI
   citations, MCP answers, and human clicks all resolve through one scheme.
5. **Citation discipline for humans.** Every Atlas section and Compass row has
   "copy citation" producing the exact contract line the skills/agents use —
   humans and AI cite identically.
6. **Read-only, no live engine.** Both are navigators over static releases —
   squarely **VistA-Copilot org** material by the actuate/navigate ADR.
7. **Producer-side shapes, consumer-side rendering.** Anything a consumer would
   re-derive or regex away (nav chrome, table titles, flattened-chunk detection)
   moves upstream into the published format (Track P below) — the vdocs-web
   workaround list is the requirements list.

## 4. Vista Atlas (successor of vdocs-web)

**Data (full published scope):** `v_documents` / `v_sections` / `v_chunks` /
`chunks_fts` / `v_vocab` (as today) **plus** the currently-dark tier: entities +
mentions, relations (contract addition, P-vdocs), version lineage
(`group_key`/`is_latest`/`patch_id`), glossary, `_shared` boilerplate, revision
history, tables CSV sidecars, rich-assets figures, `discovery.json`/manifests for
about/pins.

**Surfaces:**
- **Library view** (tree): faceted browse (app / section / doc_type / persona /
  year) with counts — vdocs-web's facet browser as a native tree.
- **Search view**: FTS5 with scopes (name/headings/all) + structured filters;
  ranked pre-cited results.
- **Reading pane** (webview): section-at-a-time rendering (marked+DOMPurify
  pattern), TOC outline wired to VSCode's outline/breadcrumbs, extracted-table
  hydration (CSV → grid, real captions per Track P), figure hydration from the
  rich-assets bundle, **boilerplate hydration** (no more dead `_shared/` links),
  **revision-history panel** (the change log humans currently never see).
- **Entity pages**: "every doc mentioning X" + per-doc entity chips — the dark
  graph, lit.
- **Version lineage**: "this manual across patches" with is_latest badging.
- **Measured jump**: entity chip → `vistaCompass.lookup` via the bridge.

**Predecessor fate:** vdocs-web freezes at Atlas parity (end of P2) and is retired
unless a non-VSCode audience materializes; its `internal/index` contract library
remains the reference semantics (and the sidecar fallback if P0 rejects in-process
sqlite).

## 5. Vista Compass v2 (successor of vscode-extension/)

**Data (full published scope):** all 24 TSVs via **meta.db** (tables + the 6 join
views), `entity-bridge.tsv` (in meta.db as `entity_bridge`), `ai-manifest.json`
(catalog + join-key registry), AI-CARD (rendered "about this data" page),
release manifest (pins/vintage badge, as today).

**Surfaces:**
- **Keep** (parity first): routine sidebar (tags/callers/callees/globals/XINDEX),
  the hover set incl. the `^GLOBAL` → file → PIKS card.
- **RPCs / Options / Protocols first-class**: sidebar sections on the active
  routine; workspace-wide "find RPC/option" pickers; protocol-call edges.
- **Package dashboard** (webview): namespace/prefixes/`app_code`/`vdl_id`, PIKS
  distribution, top cross-package couplings (edge matrix), routine leaderboard —
  the per-package situational-awareness guide, materialized.
- **Language features unblocked by sqlite**: workspace symbols (indexed prefix
  query over `xindex_tags`), go-to-definition / find-references from
  `routine_calls`, diagnostics from `xindex-errors` (with the
  `callees_agreement_ratio` caveat surfaced). Signature help remains gated on the
  bake extracting formals (Track P).
- **Documented jump**: routine/RPC/option/file hover and sidebar rows show
  "documented in N docs" (bridge `mention_count`) → `vistaAtlas.open`.
- **Field-level PIKS**: `field-piks` drill-down under the file hover (cross-PIKS
  pointer flags — today's data-model sliver widened to the whole model).

## 6. Shared infrastructure

- **Home:** new sibling repos under the VistA-Copilot org (`~/vista-copilot/`):
  `vista-atlas`, `vista-compass`, and a small shared lib (`vista-store`: sqlite
  engine wrapper + contract check + release fetch/verify + deep-link registry).
  Compass moving out of vista-meta is deliberate: it becomes a *consumer of the
  release* like every other downstream; vista-meta keeps a pointer and stays the
  producer. (Decision for owner: keeping Compass in-repo is workable but couples
  the extension's cadence to the data repo and leaves the twin split across orgs.)
- **Toolchain:** house node template (npm, Biome, `node:test`, tsx, c8) +
  the VSCode extension harness (esbuild bundle, `@vscode/test-electron`, vsce
  platform builds). TDD as always.
- **Distribution:** GitHub Releases (`.vsix` per platform if better-sqlite3);
  data fetched on first run into `globalStorage` with sha256 verification against
  the in-repo release records.

## 7. Producer prerequisites (Track P — land alongside, gate the marked phases)

**P-vdocs** (in ~/projects/vdocs):
1. Read-contract additions (additive, 1.5 → 1.6): **relations view**, **entities
   formally in-contract** (they exist; make them normative), **boilerplate**
   (id → markdown), **revision history** (per-doc revisions view or exported
   sidecar in the bundle). *(gates Atlas P4)*
2. Reading-surface hygiene at the producer: nav chrome excluded from `v_chunks`
   text; flattened search-only table chunks flagged by column, not filename
   convention; real table titles carried in the placeholder/sidecar. *(gates P2
   polish; consumer workarounds exist meanwhile)*
3. Release completeness: rich-assets + rich-tables bundles as release assets +
   the **unified producer manifest** (one manifest naming db/assets/tables);
   already-flagged data gaps (4 empty `app_name`s, heading-less docs, toc drift).
   *(gates "figures work from a clean install")*

**P-vista-meta** (here):
1. **meta.db as a release asset** at the next data tag (sha in the manifest —
   already the W2b plan); until then Compass builds it from the TSV checkout.
2. Bake-side tag enrichment for signature help: `kind` / `formal_list` /
   `summary` columns (new TSV or xindex-tags widening; spec change → data-v2).
3. Indexes tuned for the extension's query shapes (prefix search on tags,
   callee lookups) — additive `build_meta_db.py` changes, no schema impact.

## 8. Sequencing & acceptance

| Phase | Work | Accept when |
|---|---|---|
| P0 | Engine spike: better-sqlite3 in extension host vs node:sqlite vs Go sidecar — FTS5 on the real 322 MB index.db, memory profile, platform-vsix build | decision recorded; both dbs queried from a toy extension on Linux |
| P1 | `vista-store` shared lib: engine + contract checks + release fetch/verify + deep-link registry | unit-tested lib; both real releases fetched, verified, opened |
| P2 | **Atlas MVP** = vdocs-web parity in-editor (facets, search, reading pane with table/figure hydration) | side-by-side parity on 10 benchmark docs; vdocs-web frozen |
| P3 | **Compass v2 MVP** = 0.2.0 parity on meta.db (sidebar, hovers, PIKS) | current extension's guide walkthrough passes on v2 |
| P4 | Full-scope surfaces: Atlas entities/relations/lineage/history *(needs P-vdocs 1)*; Compass RPC/option/protocol/package dashboard/symbols/diagnostics | each MCP tool's answer has a visible human counterpart (spot-check list) |
| P5 | The bridge, both directions + copy-citation everywhere | "docs for this RPC" and "measured row for this mention" are single clicks; citations byte-match the MCP contracts |

## 9. Non-goals

- **Editing anything** — both are read-only navigators; no formatting, refactoring,
  or live-engine features (that's vista-forge's `m`/`v` world).
- **Semantic search** — stays parked with vdocs §14-vNext.
- **Replacing the MCP servers or vdocs `ask`** — those remain the machine front
  doors; the extensions are the human ones over the same contracts.
- **A web audience** — if one appears, revive vdocs-web from its freeze rather
  than making Atlas dual-target.
- **The docs-as-code GitHub materialized publication** — orthogonal; deprioritized
  while the editor is the reading surface.

## 10. Risks / open questions

- **Native module distribution** (better-sqlite3): platform-specific VSIX is
  well-trodden but adds CI complexity; P0 exists to kill this risk early, and the
  Go-sidecar fallback reuses proven code at the cost of process management.
- **index.db in extension memory**: mmap should make 322 MB a non-issue; verify
  in P0 on the real file (and confirm FTS5 is compiled into whatever engine wins).
- **Two orgs, one pair**: moving Compass to VistA-Copilot is the recommendation
  but changes vista-meta's `exposes:`; owner call before P3.
- **Webview duplication**: Atlas's reading pane re-implements vdocs-web's
  hydration logic in TS; keep the transforms pure + ported with their tests
  (the mis-nested-placeholder bug class must not regress).
- **Naming**: "Vista Atlas" (map of the documentation) / "Vista Compass"
  (orientation in the measured code) — pairs cleanly; Compass keeps its
  marketplace identity and bumps major.
