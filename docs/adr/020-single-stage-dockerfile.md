# ADR-020: Single-stage Dockerfile, granular layers

Date: 2026-04-17
Status: Accepted

## Context
Dockerfile structures vary: single-stage (simple, larger final image), multi-stage (builder + runtime separation, smaller final image), few monolithic RUN commands vs. many granular ones (cache granularity).

## Decision
Single-stage Dockerfile. Granular `RUN` layers organized by cache-friendliness: stable base steps first (OS deps, user setup, YDB install), expensive one-time steps next (VEHU-M fetch + import), frequently-iterated steps last (entrypoint, healthcheck, configs).

## Consequences
- Positive: Iterating on entrypoint/bake scripts doesn't invalidate the VEHU-M import cache. Typical rebuild = seconds, not 10+ minutes.
- Positive: Layer boundaries correspond to logical install phases; easier to diagnose install failures.
- Positive: No multi-stage complexity for a workload that has no meaningful build/runtime artifact separation.
- Negative: Final image larger (~2-4 GB) than a hypothetical multi-stage minimum.
- Neutral: 15 named layers keeps the Dockerfile mid-length (~100 lines) and readable.

## Alternatives considered
- Multi-stage (builder stage produces `/opt/VistA-M`, copied to runtime stage): saves maybe 100 MB of build tools; doesn't meaningfully help a sandbox workload.
- Monolithic single RUN: any change invalidates the entire 20-min import step. Unworkable.
- Many tiny RUNs: layer count bloat, marginal cache benefit after the ~15-layer sweet spot.
