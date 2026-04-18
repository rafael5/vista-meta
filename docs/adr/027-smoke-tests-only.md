# ADR-027: Smoke tests only, skip BATS

Date: 2026-04-18
Status: Accepted

## Context
Rafael has a `bash-quality-checker` skill and values script quality. But vista-meta is a personal sandbox, not a shared service. BATS tests for entrypoint and bake script would be sound practice but carry real maintenance overhead.

## Decision
Include `tests/smoke/post-build-smoke.sh` only. Validates that built image starts, services come up, basic RPC + SQL queries succeed. Skip BATS test suite for v1.

## Consequences
- Positive: Low maintenance overhead. Smoke test catches the most common failure mode (broken build).
- Positive: One file, shell-testable directly: `bash tests/smoke/post-build-smoke.sh` after `make build && make run`.
- Negative: No fine-grained test coverage of entrypoint/bake logic. Manual verification required when iterating on those scripts.
- Neutral: BATS can be added later if complexity grows or if the project becomes shared.

## Alternatives considered
- BATS tests + smoke: full coverage but doubles test-maintenance surface.
- Skip both: no verification of build correctness; too fragile even for personal use.
- pytest for in-container logic: overkill for shell-heavy code.
