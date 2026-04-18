# ADR-012: $ZRO layering — dev-r first, VEHU-M fallback, YDB libs last

Date: 2026-04-17
Status: Accepted

## Context
YottaDB's `$ZROUTINES` is a space-separated list of directories that determines routine lookup order; first match wins. Need dev routines to override VEHU-M without mutating the baked image.

## Decision
```
ydb_routines="/home/vehu/dev/r(/home/vehu/dev/o) /opt/VistA-M/r(/opt/VistA-M/o) $ydb_dist/libyottadbutil.so"
```
Three layers: dev-r (yours) → VEHU-M baked → YDB built-ins.

## Consequences
- Positive: You shadow upstream routines at will; no need to patch VEHU-M in place.
- Positive: Clean rollback — delete from `dev-r/` and the upstream version resumes.
- Positive: Readable lookup order for debugging (`which routine` equivalent is `$TEXT(+0^NAME)` + path inspection).
- Negative: A stale routine in `dev-r/` can silently shadow an updated VEHU-M version; discipline needed.
- Neutral: Extra directory in search path adds negligible lookup overhead.

## Alternatives considered
- VEHU-M first, dev-r second: defeats the override pattern; dev routines would never execute unless named uniquely.
- Single flat search path: no shadowing = must patch VEHU-M in place; contamination risk.
- Many-package preservation (one `$ZRO` entry per package): operationally equivalent; different routine layout choice (see ADR-029).
