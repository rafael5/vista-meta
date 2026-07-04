# Architecture Decision Records — vista-meta

All significant design decisions for the vista-meta project. Each ADR is
immutable once accepted; amendments are new ADRs that supersede the old one.

## Format

```
# ADR-NNN: Title

Date: YYYY-MM-DD
Status: Accepted | Superseded by ADR-NNN | Deprecated

## Context
What problem, what constraints, what forced the choice.

## Decision
What we chose.

## Consequences
- Positive / Negative / Neutral

## Alternatives considered
What we rejected and why.
```

## Index

| ADR | Title | Status | Reality (2026-07-04) |
|-----|-------|--------|-----------------------|
| 001 | Project identity and analytics scope | Accepted |  |
| 002 | VEHU as VistA flavor | Accepted |  |
| 003 | Ubuntu 24.04 as base OS | Accepted |  |
| 004 | YottaDB via ydbinstall.sh, pinned | Accepted |  |
| 005 | ASCII-only, no UTF-8 | Accepted |  |
| 006 | Skip VistA bootstrap | Accepted |  |
| 007 | No post-install hook | Accepted |  |
| 008 | Tailscale IP as network perimeter | Accepted |  |
| 009 | Entrypoint chowns bind mounts | Accepted |  |
| 010 | Hybrid persistence: bind mounts + named volume + baked VEHU-M | Accepted |  |
| 011 | Image tag = latest + date tag | Accepted |  |
| 012 | $ZRO layering: dev-r first, VEHU-M fallback | Accepted |  |
| 013 | Services: RPC Broker, VistALink, sshd, Octo, YDB GUI | Accepted |  |
| 014 | Python tooling baked in (yottadb bindings, git) | Accepted |  |
| 015 | M-Unit — ChristopherEdwards fork | Accepted |  |
| 016 | DD exporters: FileMan utilities + FMQL + Print Templates | Accepted |  |
| 017 | Enhanced XINDEX via VEHU inheritance | Accepted |  |
| 018 | First-run XINDEX baseline: auto + manual rebake | Accepted |  |
| 019 | Interactive tools: ranger, micro, tree, btop, ncdu | Accepted |  |
| 020 | Single-stage Dockerfile, granular layers | Accepted |  |
| 021 | tini as PID 1, bash entrypoint | Accepted |  |
| 022 | Background first-run bake + wait-for-bake target | Accepted |  |
| 023 | Continue-on-error bake failure handling | Accepted |  |
| 024 | HEALTHCHECK enabled | Accepted |  |
| 025 | Hybrid git tracking for export/ | Accepted |  |
| 026 | Host Python venv at host/ | Accepted |  |
| 027 | Smoke tests only, skip BATS | Accepted | implemented 2026-07-04 as `tests/smoke/smoke.sh` (`make smoke`, S-01…S-12); first run caught 2 dead services (T-006) |
| 028 | ADR discipline adopted | Accepted |  |
| 029 | Symlink farm for VEHU-M routines | Accepted |  |
| 030 | Single region/segment globals topology | Accepted |  |
| 031 | dev-r object dir container-internal, ephemeral | Accepted |  |
| 032 | Makefile: lean v1 + adr-new | Accepted | outgrown — Makefile now carries release/patch/validate targets beyond lean v1 |
| 033 | Prompt always on destructive Makefile targets | Accepted |  |
| 034 | Snapshot auto-prune to last 5 | Accepted |  |
| 035 | wait-for-bake: progress dots | Accepted |  |
| 036 | bake.sh: configurable scope, default full | Accepted |  |
| 037 | bake.sh: configurable parallelism, default serial | Accepted |  |
| 038 | bake.sh: phase-level resume | Accepted |  |
| 039 | bake.sh: item-level error granularity | Accepted |  |
| 040 | YDB GUI on port 8089 | Accepted |  |
| 041 | YDB GUI open (no auth) | Accepted |  |
| 042 | Skip M Web Server (port 9080) | Accepted |  |
| 043 | Drop ViViaN/DOX (deferred) | Accepted |  |
| 044 | Project root = ~/vista-meta, standalone repo | Superseded by ADR-049 | superseded — root is `~/projects/vista-meta` (ADR-049) |
| 045 | Separate data and code classification; package as the bridge | Accepted |  |
| 046 | _(moved)_ kids-vc undo — pre-install snapshot. Now lives in `~/projects/py-kids-vc/docs/adr/046-*.md` | Proposed |  |
| 047 | Ship the models as a verifiable data release (schema_v1 + data-v1) | Accepted | backfill — executed 2026-07-03 |
| 048 | VistA Compass — offline TSV extension over the schema_v1 data root | Accepted | backfill — shipped as 0.2.0 |
| 049 | Project root is ~/projects/vista-meta (supersedes 044) | Accepted | |
