# ADR-028: ADR discipline adopted

Date: 2026-04-18
Status: Accepted

## Context
vista-meta accumulated 40+ design decisions in its specification phase. Without preserved rationale, the "why" of a decision fades while the "what" remains — leading to regression via "who decided this and why?" cycles. ADRs (Architecture Decision Records) address this.

## Decision
Adopt ADR discipline from project start. Each significant decision gets a numbered, dated, immutable ADR under `docs/adr/`. Format: Context / Decision / Consequences / Alternatives considered. Supersession via new ADR that references the old one. Backfill ADRs for all decisions made in spec v0.1–v0.3.1.

## Consequences
- Positive: Preserved rationale survives developer turnover, long time gaps between sessions, and scope changes.
- Positive: Supersession pattern makes decision evolution explicit (e.g., ADR-015's supersession of the initial M-Unit fork choice).
- Positive: `make adr-new TITLE="..."` Makefile target scaffolds new ADRs.
- Negative: Writing overhead per decision. Mitigated by compact format and batch backfilling.
- Neutral: ADRs in `docs/adr/` are tracked in git; diffs are low-volume but meaningful.

## Alternatives considered
- No ADRs, just the running spec: spec drifts; past rationale is reconstructed by guessing.
- ADRs only for new decisions (no backfill): historical decisions remain tribal knowledge.
- Heavier format (full RFC-style): too much ceremony for a personal project.
