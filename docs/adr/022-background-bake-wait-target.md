# ADR-022: Background first-run bake + wait-for-bake target

Date: 2026-04-18
Status: Accepted

## Context
First-run bake (XINDEX baseline + 3 DD exporters) takes ~45-90 min estimated. Options for when it runs: blocking (docker run doesn't return until done), synchronous on first login, background, or manual-only.

## Decision
Background. entrypoint's phase 4 launches `bake.sh --all` as a detached process, after services are up. A `make wait-for-bake` Makefile target polls the sentinel until all phases report non-pending status.

## Consequences
- Positive: Container is usable immediately — SSH in, start exploring baked content, monitor bake via `tail -f export/logs/first-run.log`.
- Positive: Scripted workflows (CI, automated benchmarking) use `make wait-for-bake` to block until ready.
- Positive: Bake failure doesn't prevent container from running; services are up even with partial baseline.
- Negative: First analysis session may need to wait if it depends on a specific bake phase. Mitigated by phase-level visibility in sentinel JSON.
- Negative: More state to reason about ("is the bake still running?"). Mitigated by status reporting.

## Alternatives considered
- Blocking bake: docker run command hangs for ~hour; poor UX.
- Synchronous on first login: forces an interactive SSH to trigger; bad for scripting.
- Manual-only: you'd forget; analysis sessions stall on cold cache.
