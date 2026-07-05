# Machine-friendly exports — vdocs-parity for AI consumers

**Status:** COMPLETE — all workstreams shipped 2026-07-05 (filed same day). W4c was
built on explicit direction ahead of vdocs `serve-mcp` (its original wait-for-parity
deferral was overridden); when vdocs' front door ships, align tool naming then.
**Owner:** rafael
**Children:** [`ai-card.md`](ai-card.md) (Workstream 1's artifact spec — filed 2026-07-05, `56a07e6`)
**Benchmark:** the vdocs gold corpus AI surface (`~/data/vdocs/documents/gold/`)

## 1. Problem

vista-meta's exports are deterministic, verifiable, and *query-able* — but not
*self-describing*. An AI landing cold must reverse-engineer 24 TSVs, guess join keys,
and has no citation contract or freshness signal. Its sibling project **vdocs** solved
exactly this for the documentation corpus, and the two releases are already mutually
pinned (Gate R), so the asymmetry is now the bottleneck: grounded dual-source answers
("what the docs say" × "what the code measurably is") work only as well as the weaker
surface.

What vdocs ships that vista-meta lacks:

| vdocs artifact | Purpose | vista-meta today |
|---|---|---|
| `CORPUS.md` | human/AI orientation card, regenerated every run | none (hand-drafted draft only) |
| `ai-manifest.json` | machine-readable catalog + query recipe + `index_fingerprint` | none |
| `discovery.json` | lightweight front door (vocab + capabilities) | none |
| stable IDs (`doc_key`/`section_id`/`entity_id`) | citation contract | implicit (TSV + key column) |
| pre-cited one-command query (`vdocs search/section`) | grounded answer path | CLI exists, but no citation output |
| skill (`vdocs-corpus`) | harness wiring | `vista-meta` skill (installed 2026-07-05) |

## 2. Goal

An AI (Claude Code session, subagent, or any MCP-capable model) can answer measured
questions about VistA from vista-meta **without prior orientation**, with row-level
citations pinned to a release fingerprint, and can join those answers to vdocs
documentation — with every orientation artifact **generated and drift-gated**, never
hand-maintained (same discipline as the org's `source-tag → generate → registry →
red-gate` rule).

## 3. Workstreams

### W1 — Generated AI card (phase 1, the core) — ✅ shipped 2026-07-05

> Implemented as `host/scripts/build_ai_card.py` (TDD,
> `tests/test_build_ai_card.py`): `make ai-card` emits both artifacts;
> `make card-check` (in `make check`) is the drift gate; `emit-all` ends with it.

Emit `vista/export/AI-CARD.md` + `vista/export/ai-manifest.json` from the export
pipeline, replacing the hand-drafted draft ([`ai-card.md`](ai-card.md), which is the
content spec). Generator inputs: the TSVs themselves (headers, row counts), the release
manifest (hashes), and a small static fragment for prose (caveats, PIKS one-liners,
recipes).

- The card lands **beside the TSVs**, written by the pipeline — `vista/export/`
  ownership (container-side writes) makes hand-editing structurally impossible, which
  is the correct failure mode.
- `ai-manifest.json` mirrors vdocs' shape where it maps: header
  (`schema_version`, `generated_at`, `content_hash`), `capabilities`, `citation`
  contract, `query` recipes, per-TSV catalog (path, rows, columns, key, sha256), join-key
  registry.
- **Gate:** `make docs-check` (or a sibling `make card-check`) regenerates the card
  in a temp dir and diffs — a stale committed card is RED. The card's `content_hash`
  must equal the release manifest's.

### W2 — Join surface

Answering real questions needs joins (RPC → routine → package → PIKS). Two tiers:

- **W2a (now, zero-build):** the documented `sqlite3 :memory:` `.import` recipe — already
  in the card spec; the generated card carries it. No new artifact.
- **W2b (done 2026-07-05 — unblocked by W4b shipping, per this clause):** generated
  `meta.db` as a dist artifact. Implemented as `host/scripts/build_meta_db.py`
  (TDD, `tests/test_build_meta_db.py`): `make meta-db` →
  `dist/vista-meta-data-v1.db` — 24 typed tables + `entity_bridge` + `meta` pins
  + 6 join views (`v_rpc_impl`, `v_option_impl`, `v_global_file_piks`,
  `v_routine_global_piks`, `v_rpc_data_piks`, `v_package_overview`); `--check`
  verifies contents ≡ TSVs + pin ≡ release record. First consumer: the W4b
  dual-source agent (one attachable file). Its sha256 joins the release manifest
  at the next data tag (data-v1 assets are immutable); the TSVs stay the
  canonical format. Natural backing store for W4c when it comes.

### W3 — vdocs entity bridge — ✅ shipped 2026-07-05

> Implemented as `host/scripts/build_entity_bridge.py` (TDD,
> `tests/test_build_entity_bridge.py`): `make peer-fetch` downloads +
> sha256-verifies the pinned vdocs bundle into `dist/peers/`; `make bridge`
> emits `vista/export/bridge/entity-bridge.tsv` + `entity-bridge.meta.json`
> (dual pins — the Gate R extension); `make bridge-check` (in `make check`)
> gates pins, recounted rates and floors even without the peer bundle.
> Measured on the published pin (`54a26e07…`, option type quarantined there):
> 1,914/6,494 joined — fileman_file 0.8526, rpc 0.7296, routine 0.5791
> (reproducing vdocs' D2.5 rates exactly), package_namespace 0.9474,
> global 0.076 (positive-only), build/hl7_segment/mail_group no-vocabulary.

A generated `entity-bridge.tsv`: vdocs `entity_id` ↔ vista-meta `(tsv, key)` rows, with
a `join_method` + `join_confidence` column, produced deterministically from the two
mutually-pinned releases (vdocs `data-v1` entity index × vista-meta `data-v1` keys).

- Anchor joins: `package-namespace.tsv` `app_code`/`vdl_id` ↔ vdocs `app_code`
  (already exact); routine/file/RPC/option names ↔ vdocs entities (fuzzy tier).
- **Floors, not aspirations** (per the 2026-07-03 hardening review): routine join
  measured at 57.7% (census has ~no `%`-routines), option entities in vdocs measured
  as noise (1.6%). The bridge must make `undetermined` legal and *report* rates, not
  fake coverage; a floor gate red-lines only on regression, not on the known ceiling.
- Ownership: built in **vista-meta** (it owns the keys; vdocs' entity index is a
  published, pinned input). Ships with the data release; consumers include the
  planned Vista Compass surfaces.

### W4 — Harness + agent wiring

- **W4a (done 2026-07-05):** `~/.claude/skills/vista-meta/SKILL.md` — measured-model
  protocol, citation contract, measured-vs-documented rule, pairs with `vdocs-corpus`.
  The skill's orientation path now points at the generated `vista/export/AI-CARD.md`
  (re-pointed same day W1 landed).
- **W4b (done 2026-07-05):** `~/.claude/agents/corpus-researcher.md` extended to
  dual-source — queries vdocs *and* vista-meta, labels `documented:`/`measured:`,
  never reconciles silently, crosses via `entity-bridge.tsv`/`app_code`. Verified
  live on a PSO docs-vs-measured question (labeled, per-source citations).
- **W4c (done 2026-07-05 — deferral overridden by explicit direction):** MCP stdio
  server over `meta.db`, stdlib-only (`host/scripts/mcp_server.py`, TDD
  `tests/test_mcp_server.py`; wired by the repo's `.mcp.json`). Tools: `query`
  (SELECT/WITH-only over a read-only connection, row-capped), `lookup` (keyed, emits
  the citation line), `bridge` (vdocs entity → vista-meta row), `orientation` (pins +
  surface + contract). Self-building: startup regenerates a missing/stale meta.db.
  When vdocs' `serve-mcp` ships, align the two front doors' tool naming.

### W5 — Fingerprint-pinned answers

Every AI answer cites the release (`vista-meta data-v1 · <tsv> · <key>=<value>`).
Carried by the card + skill (done in draft form); W1's gate makes the pin trustworthy
(card hash ≡ manifest hash). No separate artifact — this is a contract clause, listed
as a workstream so the acceptance test below names it.

## 4. Sequencing & acceptance

| Phase | Work | Accept when |
|---|---|---|
| P1 ✅ | W1 card+manifest emitter + drift gate; W4a skill re-point (shipped 2026-07-05) | fresh clone → `make <export>` → card present, gate green, hash ≡ manifest; a cold AI session answers a measured question citing `AI-CARD.md` recipes only |
| P2 ✅ | W3 entity bridge + rate report + regression floor (shipped 2026-07-05; release inclusion lands with the next data tag — data-v1 assets are immutable) | bridge TSV in release; measured join rates reported; dual-source question ("docs vs measured for package X") answers via one bridge hop |
| P3 ✅ | W4b agent dual-source (shipped 2026-07-05) | corpus-researcher returns labeled `documented:`/`measured:` findings |
| W2b ✅ | `meta.db` projection (shipped 2026-07-05 — W4b's shipping met its unblock clause; consumer = the dual-source agent) | `make meta-db` green; join views answer the four canonical paths |
| W4c ✅ | MCP server (shipped 2026-07-05 on explicit direction, ahead of vdocs `serve-mcp`) | cold MCP client answers a measured question with a pinned citation via `orientation`+`lookup` |

## 5. Non-goals

- **Semantic search** — stays vdocs-side (its Phase-6 `embed`); vista-meta queries are
  exact/structural by nature.
- **Changing the canonical format** — TSVs remain the model of record; everything here
  is a generated projection (one fact, one owner, projections).
- **Production/site data** — the scope is the shipped code base + VEHU demo structure;
  nothing here changes extraction scope.
- **A new query CLI** — `bin/vista-meta` verbs are sufficient; gaps are closed with
  card recipes, not new commands (revisit only if W4c happens).

## 6. Risks / open questions

- **Generator drift vs vdocs' shape** — don't chase byte-parity with vdocs'
  `ai-manifest.json`; mirror the *concepts* (catalog, recipe, fingerprint, citation)
  and keep schemas independent. The bridge (W3) is the only artifact that must parse
  vdocs' output, and it reads a *pinned release*, not the live lake.
- **In-container vs host-side emission** — schema_v1 normalization already runs
  host-side; the card emitter should run in the same place as whatever writes the
  final TSVs, so ownership of `vista/export/AI-CARD.md` matches its siblings.
- **Bridge staleness** — the bridge is valid only for its input pin pair; its header
  must carry both fingerprints, and Gate R's mutual-pin check should extend to it.
