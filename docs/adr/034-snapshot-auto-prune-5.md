# ADR-034: Snapshot auto-prune to last 5

Date: 2026-04-18
Status: Accepted

## Context
`make snapshot-globals` tars the `vehu-globals` named volume to `snapshots/vehu-globals-YYYY-MM-DD-HHMM.tar.gz`. Each snapshot is 1-3 GB. Unbounded accumulation fills disk. Options: unbounded (manual cleanup), auto-prune to N, tagged-only.

## Decision
Auto-prune to last 5 snapshots. Each `snapshot-globals` run deletes all but the 5 most recent files matching the pattern.

## Consequences
- Positive: Bounded disk usage (~15 GB max for snapshots/).
- Positive: Recent rollback targets always available without thinking about cleanup.
- Positive: No accidental "why is my snapshots/ dir 200 GB" surprise.
- Negative: Long-past snapshots lost. If you want to preserve a known-good baseline (e.g., pre-major-refactor), rename it outside the auto-prune pattern manually: `cp snapshots/vehu-globals-2026-04-18.tar.gz snapshots/baseline-before-refactor.tar.gz`.
- Neutral: 5 is a reasonable default; change via config variable in Makefile if needed.

## Alternatives considered
- Unbounded: disk fills eventually.
- Auto-prune to 10: same pattern, larger floor.
- Tag-required (`TAG=name` mandatory, no date-only snapshots): too much friction for frequent backups.
