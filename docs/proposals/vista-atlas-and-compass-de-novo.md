# Vista Atlas + Vista Compass — de-novo twin editor extensions over the published releases

**Status:** Draft · 2026-07-05
**Owner:** rafael
**Scope:** two repos' human surfaces — vdocs-web (superseded by **Vista Atlas**) and
`vscode-extension/` here (superseded by **Vista Compass v2**). The twins also
officially supersede **vista-info-hub** (the Go joined-CLI/TUI/MCP over vista-meta
TSVs + the retired v1 `frontmatter.db`) — deleted with the VistA-Copilot org,
2026-07-05, by owner direction.
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
- **Richer data → richer UX (the point of the rewrite).** Parity with the
  predecessors is the **floor** (P2/P3), never the ceiling: the twins exist to
  exploit, to the full extent, the newly published registry-gated data tiers —
  search and display possibilities the old consumers structurally could not
  offer because the data didn't ship or wasn't queryable. Concretely:
  - **Compass** searches and displays the *whole* measured model, not 7 of 24
    TSVs: workspace-wide symbol/call-graph search over indexed `meta.db`,
    one-query transitive joins via the shipped views ("which RPCs reach
    Patient-class globals" — `v_rpc_data_piks`), RPC/option/protocol pickers,
    package dashboards (PIKS mix, cross-package coupling), field-level PIKS
    drill-downs, XINDEX diagnostics with agreement-ratio context, and
    bridge-ranked "documented in N docs" on every hover.
  - **Atlas** searches and displays the *whole* gold corpus, not just chunks:
    FTS5 ranked search side-by-side with **entity search** ("every doc
    mentioning `^DIC`"), relations-graph cross-doc navigation, version-lineage
    browsing, rendered revision histories, and reading views with hydrated
    tables, figures, and boilerplate — the tiers vdocs-web left dark.
  - **Cross-source search** spans both releases through the entity bridge: one
    query surface answering `documented:` × `measured:` questions in the
    editor, with copyable citations matching the MCP contracts.
  P4/P5 are where this richness lands; §4–§5 enumerate the surfaces per side.

## 3. Design principles

1. **Consumers of releases, not repo internals — and consumers never re-derive.**
   Both extensions acquire data by fetch-and-verify of the published release
   artifacts (both standalone manifests carry per-file sha256 + schema/read
   version; vdocs-web's `dbfetch` proves the pattern) — or point at a local
   lake/checkout for dev. Neither extension requires its producer repo, and
   neither builds a summary, index, or projection the producer publishes:
   vdocs ships `index.db`; vista-meta ships `meta.db` + the entity bridge as
   data-v1 assets (`docs/releases/data-v1-derived.json`). A shape a consumer
   needs is added to the producer's bake first, surfaced second. This extends
   to **algorithms as well as data** (owner directive, 2026-07-05): all
   indexing and cross-referencing lands producer-side, published as data —
   including the token **canonicalization spec** (`entity-bridge.meta.json`
   `canonicalization`: per-type transform steps + target vocabulary, emitted
   from the same declaration the bridge builder itself interprets, so spec
   and implementation cannot drift). The payoff is answer identity: the MCP
   servers, the extensions, and any agent resolve the same token through the
   same published spec against the same published stores — human and machine
   clients get **identical answers**.
2. **Contract-first reads.** Atlas binds only to the `read_schema_version`'d `v_*`
   views + `chunks_fts` (the vendored-contract seam vdocs-web proved, ported to
   TS). Compass binds to `meta.db`'s tables/views + `ai-manifest.json` as its
   self-describing catalog (columns, pks, join keys — no hardcoded schemas).
3. **One storage engine — DECIDED at P0 (2026-07-05): `node:sqlite`.** VSCode
   1.125's extension host runs Node 24.15 (Electron 42) with `node:sqlite`
   available unflagged, FTS5 compiled in — zero native dependencies, one
   universal VSIX. The spike record (§11) has the measurements; `better-sqlite3`
   was verified *failing* in the extension host without an Electron-ABI rebuild,
   which is exactly the complexity `node:sqlite` eliminates. Because the Node API
   is still marked experimental, `vista-store` wraps it behind a thin interface
   with `better-sqlite3` (+ platform VSIX) as the documented swap-in fallback.
   SQLite in-process dissolves Compass's "pre-sorted symbol index" format
   problem (an index on `xindex_tags(tag)` *is* the symbol index — and even the
   unindexed prefix scan measured 13 ms over 292k rows).
4. **Stable-ID deep links.** A documented command-URI contract:
   `vistaAtlas.open(doc_key|section_id|entity_id)` ·
   `vistaCompass.lookup(kind, key)`. Same IDs as the MCP citations
   (`vdocs://section/<id>`; `vista-meta data-v1 · tsv · key=value`), so AI
   citations, MCP answers, and human clicks all resolve through one scheme.
   Full spec: the twin-link contract, §6.1.
5. **Citation discipline for humans.** Every Atlas section and Compass row has
   "copy citation" producing the exact contract line the skills/agents use —
   humans and AI cite identically.
6. **Read-only, no live engine.** Both are navigators over static releases —
   homed in **vista-forge** as non-waterline repos (VistA-Copilot retired;
   see §6).
7. **Producer-side shapes, consumer-side rendering.** Anything a consumer would
   re-derive or regex away (nav chrome, table titles, flattened-chunk detection)
   moves upstream into the published format (Track P below) — the vdocs-web
   workaround list is the requirements list.
8. **Clean-room de novo (owner directive, 2026-07-05).** The predecessors —
   `vscode-extension/` 0.2.0, vdocs-web, vista-info-hub — are **behavioral
   references, never code sources**: no file, module, or snippet is ported into
   the twins. Their ad-hoc/iterative design (and any orphaned code) stays
   behind. What DOES carry over, deliberately: (a) the **UX to replicate as a
   floor** (§2 — the full published scope is the target, parity is never the
   ceiling), specified from their docs and guides (for Compass: the
   extension-internals / situational-awareness guides; the guide walkthrough is
   P3's acceptance), and
   (b) their **known bug classes, re-encoded as new TDD test cases first**
   (bare-vs-caret global join, `global_root` normalization, XINDEX
   line-number-as-text, the mis-nested table placeholder) so the rewrite can't
   re-learn them the hard way. Everything in the twins is written test-first
   against the published data contracts, version-pinned (`.node-version`,
   `engines.vscode`, pinned release tags), and gated by `ts-ci`.

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

- **Home — DECIDED 2026-07-05 (owner): the vista-forge org.** The VistA-Copilot
  org is retired (name too close to Microsoft Copilot). Repos created and
  published same day: `github.com/vista-forge/vista-atlas` +
  `github.com/vista-forge/vista-compass` (house node template scaffolds,
  Node 24 pinned, gates green). Both are **non-waterline** repos — read-only
  navigators over published releases that never touch an engine, so they
  declare no `m`/`v` layer artifact and sit outside the waterline gates (the
  `clikit` precedent). The shared lib (`vista-store`: sqlite engine wrapper +
  contract check + release fetch/verify + deep-link registry) starts inside
  `vista-compass` at P1 and extracts to a sibling repo when Atlas consumes it.
  Compass moving out of vista-meta is deliberate: it becomes a *consumer of
  the release* like every other downstream; vista-meta keeps a pointer and
  stays the producer.
- **Toolchain:** house node template (npm, Biome, `node:test`, tsx, c8) +
  the VSCode extension harness (esbuild bundle, `@vscode/test-electron`, vsce
  platform builds). TDD as always.
- **Distribution:** GitHub Releases (`.vsix` per platform if better-sqlite3);
  data fetched on first run into `globalStorage` with sha256 verification against
  the in-repo release records.

### 6.1 The twin-link contract (docs↔code synergy spec)

Both extensions are installed side-by-side; each is fully standalone, and the
synergy is a thin, versioned seam — designed 2026-07-05 by owner direction.

**Mechanism — commands + URI handlers, soft-dependency.** VSCode's sanctioned
inter-extension seam is registered commands: each twin exposes a small
versioned command surface; the other calls `executeCommand` only after a
`getExtension()` presence check. No shared runtime, storage, or activation
dependency; every cross-feature degrades gracefully (twin absent → affordance
hides, or a one-time "install the twin" hint). Each twin also registers a
**URI handler** (`vscode://vista-forge.vista-atlas/…`,
`vscode://vista-forge.vista-compass/…`) so deep links work from terminals,
markdown, MCP answers, and AI chat — the citation contracts become clickable.

**Keystone rule — the ID crosses the boundary, never the data.** Both sides
already speak the same stable IDs (`entity_id` = `<type>:<canonical_name>`,
`doc_key`/`section_id`, `(tsv, key)`). Atlas hands Compass an `entity_id` and
Compass resolves it in its own meta.db (`entity_bridge`); Compass hands Atlas
an `entity_id`/`section_id` and Atlas resolves it in its own index.db. Neither
queries the other's store — standalone is preserved structurally.

**Command surface (contract v1, sketch — frozen at P1):**
- `vistaCompass.lookup {kind, key}` · `vistaCompass.openEntity {entity_id}` ·
  `vistaCompass.search {query}` · `vistaCompass.pins → {tag, content_hash, …}`
- `vistaAtlas.openDoc {doc_key}` · `vistaAtlas.openSection {section_id}` ·
  `vistaAtlas.openEntity {entity_id}` · `vistaAtlas.search {query, filters?}` ·
  `vistaAtlas.pins → {tag, corpus_content_hash, …}`
- `vista.openCitation {text}` — accepts either citation format
  (`vdocs://section/<id>` or `vista-meta data-vN · <tsv> · <key>=<value>`)
  and routes to the right twin.

**The synergy features (land at P5):**
1. **Cross-jumps everywhere** — Compass hovers/rows show *"documented: N
   mentions → Atlas"* (`entity_bridge.mention_count`, no docs query needed);
   Atlas entity chips show *"measured → Compass"*.
2. **Seeded search handoff** — the searches are complementary (Atlas
   lexical FTS5/BM25; Compass exact/structural): each search UI adds one
   footer row forwarding the query to the twin, with tokens normalized by
   applying the **published canonicalization spec**
   (`entity-bridge.meta.json` `canonicalization` — declared steps per entity
   type, interpreted, never re-implemented) so they land in the other side's
   native form.
3. **Editor-context entries** — right-click a token in an `.m` file →
   "find in docs" (Compass canonicalizes, forwards); entity mentions in
   Atlas's reading pane link to Compass.
4. **Citation routing** — `vista.openCitation` + the URI handlers make any
   citation an agent or MCP server emits navigable.
5. **Mutual-pin handshake** — on activation each twin checks the other's
   `pins` against the Gate R pair and warns on a mismatched release pair —
   release-drift surfaced to the human the way the gates surface it to CI.

**Contract as data (registry discipline).** The command IDs, payload schemas,
and URI scheme live as a versioned contract artifact in `vista-store`; both
extensions implement handlers against it and test against it, so the two
command surfaces cannot drift apart — the same reason the two MCP front doors
share conventions. Contract v1 is a P1 deliverable; the features are P5.

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
1. ~~**meta.db as a release asset**~~ — **done 2026-07-05, ahead of schedule and
   as a hard principle: consumers never re-derive summaries/indexes** (owner
   direction). `make derived-publish` uploads meta.db + the entity bridge as
   supplementary data-v1 assets (gate-verified against the pinned TSVs before
   upload; existing assets untouched) and records their shas in
   `docs/releases/data-v1-derived.json` (the peers-sidecar pattern). Compass
   fetch-verifies the published meta.db; it never builds one.
2. Bake-side tag enrichment for signature help: `kind` / `formal_list` /
   `summary` columns (new TSV or xindex-tags widening; spec change → data-v2).
3. Indexes tuned for the extension's query shapes (prefix search on tags,
   callee lookups) — additive `build_meta_db.py` changes, no schema impact.
4. ~~**Canonicalization as published data**~~ — **done 2026-07-05**:
   `entity-bridge.meta.json` now carries a `canonicalization` block (per-type
   steps + vocabulary + the namespace-then-prefix resolution rule), emitted
   from the declaration `build_entity_bridge.py` itself interprets
   (`canonicalize()`), TDD'd, and re-published to the data-v1 derived assets.
   Consumers apply the spec; they never re-implement the algorithm.

## 8. Sequencing & acceptance

| Phase | Work | Accept when |
|---|---|---|
| P0 ✅ | Engine spike (done 2026-07-05): `node:sqlite` vs better-sqlite3 vs Go sidecar on the real dbs | **met** — decision recorded (§11); a toy extension inside the installed VSCode 1.125 host queried both real dbs (FTS5 hits from index.db, rpc+bridge rows from meta.db) |
| P1 | `vista-store` shared lib: engine + contract checks + release fetch/verify + **twin-link contract v1 (§6.1)** | unit-tested lib; both real releases fetched, verified, opened; contract artifact frozen |
| P2 | **Atlas MVP** = vdocs-web parity in-editor (facets, search, reading pane with table/figure hydration) | side-by-side parity on 10 benchmark docs; vdocs-web frozen |
| P3 | **Compass v2 MVP** = 0.2.0 parity on meta.db (sidebar, hovers, PIKS) | current extension's guide walkthrough passes on v2 |
| P4 | Full-scope surfaces: Atlas entities/relations/lineage/history *(needs P-vdocs 1)*; Compass RPC/option/protocol/package dashboard/symbols/diagnostics | each MCP tool's answer has a visible human counterpart (spot-check list) |
| P5 | The twin-link features (§6.1): cross-jumps, seeded search handoff, citation routing, mutual-pin handshake, copy-citation everywhere | "docs for this RPC" and "measured row for this mention" are single clicks; a query forwards to the twin's native search; `vista.openCitation` routes both citation formats; a mismatched release pair warns on activation |

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
- ~~**Two orgs, one pair**~~ — resolved 2026-07-05: both repos live in
  vista-forge (VistA-Copilot retired); vista-meta's `exposes:` gets the pointer
  when Compass v2 reaches parity (P3).
- **Webview duplication**: Atlas's reading pane re-implements vdocs-web's
  hydration behavior in TS — clean-room per principle 8 (no code ported); the
  behaviors are re-specified as pure TDD'd transforms, and the
  mis-nested-placeholder bug class is encoded as a regression test first.
- **Naming**: "Vista Atlas" (map of the documentation) / "Vista Compass"
  (orientation in the measured code) — pairs cleanly; Compass keeps its
  marketplace identity and bumps major.

## 11. P0 spike record (2026-07-05)

**Decision: `node:sqlite`** (Node's built-in SQLite), wrapped behind a thin
`vista-store` interface; `better-sqlite3` + platform VSIX is the documented
fallback if the experimental API regresses. The Go-sidecar option is retired.

**Environment measured:** VSCode 1.125.1 on Linux; its extension host is
Electron 42.2.0 / **Node 24.15.0**, where `node:sqlite` loads unflagged with
**FTS5 compiled in** (sqlite 3.51.3). `better-sqlite3`'s node-24 prebuild fails
to load in that host (Electron ABI 146 mismatch) — usable only with
electron-rebuild + per-platform VSIX. `engines.vscode` floor: `^1.125.0`
(the verified host; probe an earlier floor only if it ever matters).

**Measurements** (real published artifacts: index.db 322 MB, meta.db 85 MB;
identical shape in plain node 24 and in the extension-host runtime):

| Probe | node:sqlite | notes |
|---|---|---|
| FTS5 `MATCH 'kaajee'` count / ranked top-5 | 2.6 ms / 0.4 ms | bm25 ordering works |
| cold doc body reconstruct (481 chunks, 850 KB) | ~20 ms | reading pane path |
| rpc lookup / callers lookup (indexed) | 0.3 ms / 0.2 ms | |
| tag prefix scan, 292k rows, **no index** | 13 ms | symbol search viable even pre-index |
| whole-model transitive agg (`v_rpc_data_piks`) | ~1.7 s | dashboard-only; precompute/cache (or add a covering index at Track P-vista-meta 3) |
| RSS after everything, both dbs open | **84 MB** | mmap — the 322 MB fear is dead |

**Acceptance run:** a toy extension (`activate()` + `@vscode/test-electron`
against the *installed* VSCode binary) queried both dbs from inside the real
extension host — FTS5 ranked hits from index.db, `SELECT^ORWPT` + the
`global:^DPT` bridge row from meta.db — PASS. Spike sources live in the session
scratchpad (`spike-p0/`); they are throwaway, this record is the artifact.
