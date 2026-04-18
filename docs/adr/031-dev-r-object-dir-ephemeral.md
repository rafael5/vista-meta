# ADR-031: dev-r object dir — container-internal, ephemeral

Date: 2026-04-18
Status: Accepted

## Context
YDB compiles M routines into `.o` object files. When routines change, objects must be regenerated. Options for where dev-r objects live:
- Container-internal, ephemeral: `/home/vehu/dev/o/` in container writable layer; rebuilt each container start.
- Bind-mount to host: persistent, at risk of arch skew.
- Named volume: Docker-managed, persistent + isolated.

## Decision
Container-internal, ephemeral. `/home/vehu/dev/o/` lives in the container's writable layer. Objects are regenerated on demand when routines execute.

## Consequences
- Positive: Always fresh — no stale .o files from a previous YDB version.
- Positive: Zero configuration — YDB's default compile-on-demand handles it.
- Positive: Host filesystem not polluted with arch-specific binaries.
- Negative: Small compile cost on first routine invocation after container start (~sub-second per routine). Negligible for a dev set.
- Neutral: YDB upgrade requires no object cleanup dance — objects vanish with the container.

## Alternatives considered
- Bind-mount to host: .o files are arch-specific (x86_64-linux) and YDB-version-specific; persistence across rebuilds is a foot-gun.
- Named volume: persistent but adds a volume to manage for no benefit — objects are cheap to regenerate.
- Pre-compile on container start: unnecessary; compile-on-demand is fast enough.
