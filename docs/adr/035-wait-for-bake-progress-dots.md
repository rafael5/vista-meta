# ADR-035: wait-for-bake — progress dots

Date: 2026-04-18
Status: Accepted

## Context
`make wait-for-bake` polls the sentinel JSON until all phases are complete. Output options: quiet (just block, exit 0/non-0), progress dots (one dot per poll), verbose (print phase status transitions).

## Decision
Progress dots. One dot per poll interval (default 30s). Final summary on completion with phase outcomes and total duration.

## Consequences
- Positive: Friendly interactive UX — visible proof the target is doing something.
- Positive: Pipeable and scriptable — dots go to stderr, exit code is the signal.
- Positive: Doesn't spam the terminal with JSON or phase transitions.
- Negative: Slightly less informative than verbose mode if you want to see which phase is currently in progress. Mitigated by `make bake-log` for real-time detail.
- Neutral: Interval tunable via config variable.

## Alternatives considered
- Quiet (no output): feels hung. Bad UX.
- Verbose status (print phase transitions as they happen): noisy; duplicates what bake-log shows.
- Spinner: fancier but character-set-dependent; dots are portable.
