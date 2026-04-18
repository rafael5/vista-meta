# ADR-037: bake.sh — configurable parallelism, default serial

Date: 2026-04-18
Status: Accepted

## Context
XINDEX over 30k routines and DD walks over 3.5k files are embarrassingly parallel. minty has multiple cores. Options: always serial (simple, slow), always parallel (fast, possible resource contention), configurable.

## Decision
Configurable via `BAKE_WORKERS` env var. Default `1` (serial). Users can set `BAKE_WORKERS=4` (or any value) when they want speed.

## Consequences
- Positive: Safe default — serial execution avoids YDB journal/lock contention surprises on first use.
- Positive: Opt-in speedup for those who've learned the behavior (4-8x is realistic on minty's hardware).
- Positive: Easy to debug when things go wrong — drop back to serial with `BAKE_WORKERS=1`.
- Negative: Users unaware of the flag run serial forever. Mitigated by documentation in README.
- Neutral: Parallel output interleaving handled by writing each worker's output to its own per-item file; aggregation in finalize step.

## Alternatives considered
- Always serial: wastes capacity on multi-core minty.
- Default auto (detect CPU count): fast by default but hides the knob; unexpected resource usage.
- Always parallel with fixed worker count: inflexible; hard to rein in when CPU contention matters.
