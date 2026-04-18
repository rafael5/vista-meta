# ADR-024: HEALTHCHECK enabled

Date: 2026-04-18
Status: Accepted

## Context
Docker's `HEALTHCHECK` directive lets containers report health state via `docker ps` and to orchestrators. Adds a small runtime cost (one check per interval).

## Decision
Enable `HEALTHCHECK`. Script validates: sshd listening on 22, xinetd listening on 9430 + 8001, rocto listening on 1338, YDB GUI listening on 8089. Check interval 30s, timeout 5s, start period 60s.

## Consequences
- Positive: `docker ps` shows health at a glance — distinguishes "container up but services flapping" from "all green."
- Positive: Easy to integrate with any future orchestration or monitoring.
- Positive: Localized diagnostic: if health fails, `docker inspect` shows which check failed.
- Negative: Tiny runtime overhead (negligible).
- Negative: Bake status is NOT part of health — bake can be in progress and container is still "healthy." Distinction documented.

## Alternatives considered
- No HEALTHCHECK: loses at-a-glance status; forces `ss -ltn` over SSH for verification.
- Include bake status in health: conflates "services ready" with "analysis ready"; wrong semantics.
- External monitoring only: premature for a personal sandbox.
