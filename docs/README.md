# docs/ — index and filing rules

## The lifecycle rule

Documentation here is classified by **lifecycle state, not topic**:

1. A workstream is born as a **committed** proposal (+ implementation-plan/tracker) in
   [`proposals/`](proposals/). Never leave a proposal untracked on disk.
2. Session kickoff prompts move to `historical/prompts/` **in the commit that lands their work**.
3. When the last phase ships — or the workstream is formally dropped — the proposal/tracker moves
   to [`historical/`](historical/) in the closing commit, *after* promoting anything still
   load-bearing into [`reference/`](reference/) or [`guides/`](guides/).
4. Decisions that must outlive their workstream become ADRs in [`adr/`](adr/).
5. **Path-stability rule:** anything cited from code (`# Spec:` / `# Plan:` / `; Spec:` headers)
   lives in `reference/` or `historical/` and never moves without a same-commit citation sweep.
   `make docs-check` (host/scripts/docs_check.py) fails on any dead link or dead citation.

## What lives where

| Location | Contents | Lifetime |
|---|---|---|
| `docs/` root | this index · [`build-log.md`](build-log.md) (BL-NNN build/error record) | evergreen |
| [`guides/`](guides/) | operator/consumer docs, **kept current**: [`vista-meta-guide.md`](guides/vista-meta-guide.md) (start here) · [`DE-NOVO.md`](guides/DE-NOVO.md) (clean-clone runbook) · developer onramp · situational-awareness playbooks · per-TSV code-model reference · PIKS methodology · VSCode/CLI guide + extension internals · snapshot/restore runbook · dependency pins | evergreen, edited freely |
| [`reference/`](reference/) | durable contracts cited from code, **path-stable**: [`schema-v1-normalization-spec.md`](reference/schema-v1-normalization-spec.md) (the shipped `schema_version: 1` contract of record) · [`model-extraction-contract.md`](reference/model-extraction-contract.md) (spec-v0.4 §11.3–11.6, the extraction/PIKS contract) · [`xindex-reference.md`](reference/xindex-reference.md) (durable XINDEX catalog, code-cited) | evergreen; changes = version breaks |
| [`adr/`](adr/) | numbered decision records, immutable once accepted; supersede via new ADR ([index](adr/000-index.md)) | permanent |
| [`proposals/`](proposals/) | **live or parked-unfinished** workstreams only | until the workstream closes |
| [`releases/`](releases/) | release records: [`data-v1.manifest.json`](releases/data-v1.manifest.json) (what consumers verify a download against) · [`data-v1-peers.json`](releases/data-v1-peers.json) (Gate-R mutual pin with vdocs) | permanent |
| [`historical/`](historical/) | executed/superseded work — kept for the *why*, never updated | archive |

## Current state (2026-07-05)

- **Public (2026-07-04):** the repository is public under MIT; the `data-v1` release
  downloads anonymously (verified), so the vdocs ↔ vista-meta mutual pin chain is now
  fully third-party-verifiable. Clean-clone path: [`guides/DE-NOVO.md`](guides/DE-NOVO.md).
- **Shipped and stable:** the two models (data-model 4 TSVs · code-model 20 TSVs, `schema_version: 1`),
  the public **`vista-meta-data-v1`** release (mutually pinned with vdocs `data-v1`),
  the **VistA Compass** VSCode extension 0.2.0, the `vista-meta` CLI + `mfmt` + pre-commit hook,
  the generated AI surface (`vista/export/AI-CARD.md` + `ai-manifest.json`, `make ai-card`,
  drift-gated by `make card-check`; shipped 2026-07-05), and the vdocs entity bridge
  (`vista/export/bridge/entity-bridge.tsv` + meta, `make peer-fetch` + `make bridge`,
  dual-pinned to both `data-v1` releases with measured join-rate floors; shipped 2026-07-05).
- **Live proposals:** [`vista-orchestration-plan.md`](proposals/vista-orchestration-plan.md)
  (cross-repo TDD toolchain roadmap — largely about sibling repos; Status: Proposed) ·
  [`machine-friendly-exports.md`](proposals/machine-friendly-exports.md) (vdocs-parity AI
  consumability umbrella: generated AI card + drift gate, join surface, vdocs entity
  bridge, harness/agent wiring, fingerprint-pinned citations; Status: P1–P3 shipped
  2026-07-05, only the deferred tier open — W2b `meta.db` + W4c MCP await a consumer) ·
  [`ai-card.md`](proposals/ai-card.md) (its phase-1 child — content spec for the
  pipeline-generated `vista/export/AI-CARD.md`; Status: implemented 2026-07-05) — the docs-lifecycle
  reorganization itself closed 2026-07-04 (phases 0–3 executed; its record is in
  `historical/`; the `Packages.csv` relocation (T-005) closed 2026-07-04 — it lives at `host/vendor/Packages.csv` as vendored build input).
- **Recently closed → `historical/`:** producer-contracts implementation plan (V1–V7 + Gate R,
  all gate-PASS) · upstream data fixes P1–P5 · the vista-info-hub heads-up memo · spec v0.4
  (as-built build record; its live §11 extraction/PIKS contract was promoted to `reference/`) ·
  the relocate-and-publish record · the docs-lifecycle reorg proposal (executed).
- **Open follow-ups:** [`../TODO.md`](../TODO.md) (T-001 routine-count reconciliation,
  T-002 cohorts, T-003 unreferenced-routine reduction, T-004 orchestration execution) —
  anchored to RESEARCH.md RF numbers.
- **Governance:** ADRs through 051 (047 data-release model · 048 Compass architecture ·
  049 root path, superseding 044 · 050 local-only networking, superseding 008 ·
  051 unconsumed services WARN); the [ADR index](adr/000-index.md) carries a Reality
  column for decisions that diverged. `build-log.md` is the frozen Phase-1 record
  (BL-001–BL-013, Apr 2026), resumed 2026-07-04 for BL-014/BL-015 (broker xinetd fix;
  reproducibility pins + FMQL removal).
  `make docs-check` guards links/citations (also wired into the pre-commit hook);
  `make smoke` (tests/smoke/smoke.sh, S-01…S-12) is the ADR-027 post-build gate.
