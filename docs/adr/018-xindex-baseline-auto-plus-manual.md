# ADR-018: First-run XINDEX baseline — auto + manual rebake

Date: 2026-04-17
Status: Accepted

## Context
XINDEX over ~30k VEHU routines takes substantial time (estimated ~30 min serial). Users need a baseline XINDEX report as analysis starting material. Question: run it once automatically on first container start, or only on demand?

## Decision
Both:
1. **Automatic on first run**: entrypoint detects absent sentinel, launches `bake.sh --all` in background. XINDEX baseline is one of the bake phases.
2. **Manual rebake**: `make bake-xindex` (or `bake.sh --only=xindex --force`) re-runs anytime to refresh.

## Consequences
- Positive: Out-of-box usefulness — by the time you SSH in and want to analyze, baselines are ready (or ready soon).
- Positive: Rebake target supports VEHU-M upgrades without rebuild.
- Positive: Sentinel-gated so a stop/restart doesn't redo a completed bake.
- Negative: First container start takes longer wall-clock time (bake runs in background; services come up fast).
- Neutral: `wait-for-bake` Makefile target covers scripted scenarios that need bake completion.

## Alternatives considered
- Manual-only: you'd forget, analysis sessions start with a "bake now" stall.
- Auto-only (no manual refresh): no way to refresh after VEHU-M update without image rebuild.
- Bake during image build: image bloats by gigabytes of XINDEX output; kills rebuild speed.
