# ADR-038: bake.sh — phase-level resume

Date: 2026-04-18
Status: Accepted

## Context
Bake can be interrupted (container stop, OOM, manual abort). On next invocation, what happens? Options: no resume (re-run everything), item-level resume (skip completed items within a phase), phase-level resume (skip completed phases entirely).

## Decision
Phase-level resume. Invoking `bake.sh --all` after partial run consults sentinel:
- `ok` → skip (unless `--force`)
- `partial` → re-run whole phase
- `failed` → re-run whole phase
- `pending` → run (was interrupted)
- missing → run (never started)

## Consequences
- Positive: Fast re-bake after interrupt if some phases completed cleanly before the interruption.
- Positive: Phase-level granularity = minimal state. No per-item progress file to maintain, corrupt, or sync.
- Positive: Clear mental model — phases are atomic units of work.
- Negative: Re-running a `partial` phase wastes the successful items. Acceptable — phases are ~5-30 min, not hours.
- Neutral: `--force` flag bypasses resume for full re-runs.

## Alternatives considered
- No resume: forces redoing everything on any interrupt. Bad for hour-long bakes.
- Item-level resume (`.progress.tsv` per phase): faster but adds state management — file corruption, concurrent write safety, etc.
- Per-file checkpoints: same problems as item-level.
