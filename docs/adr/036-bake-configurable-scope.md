# ADR-036: bake.sh — configurable scope, default full

Date: 2026-04-18
Status: Accepted

## Context
VEHU has ~3,500 FileMan files and ~30k routines. Analytics sessions often target a subset (e.g., just PSO pharmacy, or just clinical files). But first-run baseline needs to be comprehensive.

## Decision
bake.sh accepts optional scope flags:
- `--files=N,N,N` — restrict to specific FileMan file numbers
- `--packages=PKG,PKG` — restrict to specific package namespaces

Default (when no scope flags given): full VEHU.

## Consequences
- Positive: First-run always produces a complete baseline (no opinionated "curated" list to explain or defend).
- Positive: Targeted re-bakes are trivial — `make bake-dd-fmql -- --packages=PSO` to iterate on pharmacy DD.
- Positive: Sentinel tracks what was actually done (full vs. partial scope), so future full bakes don't skip legitimately incomplete state.
- Negative: Full first-run bake is slow (~hour). Mitigated by background execution (ADR-022).
- Neutral: Scope flag syntax is simple; no need for YAML config files.

## Alternatives considered
- Full-always: forces long waits even for narrow analyses.
- Curated default subset: opinionated curation list becomes its own maintenance burden; users who need other files go without baselines.
- Interactive picker: adds complexity for a flag-driven tool.
