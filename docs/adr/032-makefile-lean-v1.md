# ADR-032: Makefile — lean v1 + adr-new

Date: 2026-04-18
Status: Accepted

## Context
Makefile can be the single unified UI for the project (build, run, shell, exec, backup, etc.). Target list can grow easily; more targets = more help text, more docs, more maintenance. Choice: kitchen-sink early vs. lean with gradual expansion.

## Decision
Lean v1 target set (18 targets), plus `adr-new TITLE="..."` since ADR discipline is adopted. Skipped from v1: `build-no-cache`, `nuke`, `root-shell`, `ssh`, `status`, `health`, `ports`, `du`, `list-snapshots`. Add them when they earn their keep.

Final v1 targets:
- Lifecycle: `build`, `run`, `stop`, `restart`, `rm`, `clean`
- Interactive: `shell`, `mumps`, `python`, `logs`, `bake-log`
- Bake: `bake`, `bake-xindex`, `bake-dd-text`, `bake-dd-fmql`, `bake-dd-template`, `wait-for-bake`
- Snapshot: `snapshot-globals`, `restore-globals SNAPSHOT=path`
- Verify: `smoke`
- Docs: `adr-new TITLE="..."`, `help`

## Consequences
- Positive: `make help` output fits on one screen; cognitive load low.
- Positive: Lean set covers 95% of daily ops.
- Positive: Clear growth path — missing targets are easy to add when actually needed.
- Negative: One-off operations (`--no-cache`, image nuke) need typing docker commands directly. Acceptable.
- Neutral: `adr-new` included because without it, ADR discipline has too much friction to sustain.

## Alternatives considered
- Kitchen sink (30+ targets): scanning `make help` becomes work.
- Minimal (5-6 targets): forces common ops onto the command line; defeats Makefile's purpose.
- Makefile per concern (one for Docker, one for docs, one for snapshots): fragmentation; single Makefile is findable.
