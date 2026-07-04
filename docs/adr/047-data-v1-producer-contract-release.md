# ADR-047: Ship the models as a verifiable data release (schema_v1 + data-v1)

Date: 2026-07-04 (backfill — decision executed 2026-07-03, commits f1e9d33…a27e04a)
Status: Accepted

## Context

The data-model/code-model TSVs had grown real downstream consumers (the Compass
extension; the vdocs corpus pipeline's entity-quality gate; vista-info-hub) but no
contract: column shapes drifted silently with each re-extraction, there was no way
to verify a copied dataset, and consumers pinned nothing. The producer-contracts
workstream (docs/historical/producer-contracts-implementation-plan.md) was executed
to close this.

## Decision

1. **Freeze the TSV shapes as `schema_version: 1`** — canonical `routine_name`
   keys, `_label` enum companions, leading `ien`, `Y/N` booleans, the P1–P4
   `package`/`package_dir` columns. The contract of record is
   `docs/reference/schema-v1-normalization-spec.md`; column changes from here are
   a v2 break, red-gated by `make validate` (full v1 contract asserted).
2. **Fidelity and typing are measured data, not prose** — per-column manifest
   (`meta/column-manifest.json`) and measured fidelity declarations
   (`meta/fidelity.json`) regenerate with the data and gate the release.
3. **Identity is a content hash** — a normative recipe over the shipped files
   (`content_hash`), independent of packaging.
4. **Release as a public GitHub Release** (`data-v1` on rafael5/vista-meta):
   deterministic bundle + standalone manifest with per-file sha256 +
   `bundle_sha256` outside the bundle, engine identity, and source commit.
   Record committed in-repo: `docs/releases/data-v1.manifest.json`.
5. **Mutual peer pin (Gate R)** — the vdocs corpus release measures its
   entity-quality floors against this data; both releases name each other's
   hashes (`docs/releases/data-v1-peers.json`). A silent re-release of either
   side is detectable by the other.

## Consequences

- Positive: consumers (Compass 0.2.0, vdocs) pin a verifiable artifact; drift is
  a gate failure, not a surprise; anyone can verify a download end-to-end.
- Negative: schema changes now cost a versioned release + consumer migration;
  the release preflight (clean tree, gate pass, quiescent export) adds ceremony.
- Neutral: the release excludes raw/ intermediates; only the contracted surface
  ships.

## Alternatives considered

- **Keep "the repo is the release"** (git clone as distribution) — rejected: no
  integrity story for the 337MB-class data, no version pinning for consumers.
- **Per-TSV versioning** — rejected: consumers join across files; the unit of
  compatibility is the whole surface.
- **Semantic-versioned PyPI-style data package** — over-engineered for a
  single-producer hobbyist scale; a tagged GitHub Release with hashes suffices.
