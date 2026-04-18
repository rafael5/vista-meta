# ADR-023: Continue-on-error bake failure handling

Date: 2026-04-18
Status: Accepted

## Context
Bake has multiple phases (XINDEX, DD-text, DD-fmql, DD-template). Each phase processes many items (30k routines, 3.5k files). Failure modes range from single-item errors (one malformed routine) to catastrophic phase failure (FMQL broken, environment misconfigured). Options: fail-fast (any error stops everything), continue-on-error (log and proceed), configurable.

## Decision
Continue-on-error. Phase status in sentinel reflects outcome: `ok` (no errors), `partial` (some items failed), `failed` (phase-level catastrophe), `pending` (interrupted), `skipped` (not requested).

## Consequences
- Positive: Dev-friendly — partial baseline is usable. If FMQL breaks on 200 of 3500 files, you still get 3300 files worth of structured DD.
- Positive: Failure diagnostics concentrated in `<phase>.errors.tsv`; don't lose context by stopping at first error.
- Positive: Non-recoverable failures (missing binary, permission denied) still surface as `failed` — status captures severity.
- Negative: `partial` status needs clear surfacing to avoid the "I thought my baseline was complete" trap. Mitigated by summary.md showing counts.
- Neutral: Strict fail-fast mode could be added later via `BAKE_STRICT=1` env var if a CI use case emerges.

## Alternatives considered
- Fail-fast: blocks analysis when a single routine has a quirk. Wrong tradeoff for exploration.
- Configurable strict/lenient: deferred; one mode is simpler and continue-on-error is the right default.
