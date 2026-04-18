# ADR-011: Image tag = latest + date tag

Date: 2026-04-17
Status: Accepted

## Context
Image tagging strategies: `:latest` only (simple, no history), single-fixed tag like `:v1` (requires manual bumps), date-stamped (`:2026-04-18`), semver, VEHU-M-date-based.

## Decision
Tag each build with both `:latest` and `:YYYY-MM-DD` (build date). Both point to the same image ID per build.

## Consequences
- Positive: `make run` uses `:latest` without ceremony.
- Positive: Date tags preserve rollback targets when VEHU-M or YDB upgrades break things.
- Positive: `docker images | grep vista-meta` shows history at a glance.
- Negative: Slow accumulation over time; manual cleanup of old date tags needed occasionally.
- Neutral: No semantic version commitment — date tags are purely chronological.

## Alternatives considered
- `:latest` only: no rollback path.
- Semver (`:v1.0.0`): imposes release ceremony for a single-user sandbox.
- VEHU-M-source-hash tag: most reproducible but opaque (`:a3f7c9d`); date wins on legibility.
