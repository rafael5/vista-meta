# ADR-043: Drop ViViaN/DOX (deferred)

Date: 2026-04-17 (initial scope decision); 2026-04-18 (finalized as drop)
Status: Accepted

## Context
ViViaN + DOX are OSEHRA's analytic HTML generators, fed by XINDEX and FileMan DD utilities. They produce cross-reference web pages for browsing VistA structure. WorldVistA's `docker-vista` marks them IRIS-only — the underlying M + Python generation scripts would likely work on YottaDB with porting, but this is unverified.

## Decision
Exclude ViViaN/DOX from v1. Drop the "ViViaN DD extraction routines" option (originally DD exporter C). Re-evaluate when YDB compatibility can be verified in a dedicated exercise.

## Consequences
- Positive: No unverified porting work in v1 critical path.
- Positive: Smaller image; one fewer install step.
- Positive: DD exporters A + B + D cover structured extraction needs.
- Negative: No HTML cross-reference browser out of the box. For visual exploration, rely on YDB GUI + ad-hoc analytics.
- Neutral: Can revisit post-v1 if the HTML format proves valuable; install is additive (no re-architecture needed).

## Alternatives considered
- Include with a first-run compat check (fall back gracefully): adds complexity and flaky first-boot experience.
- Include the M-side only, skip Python orchestration: partial install is worse than no install.
- Port to YDB ourselves: project scope is metadata analytics, not tooling resurrection.
