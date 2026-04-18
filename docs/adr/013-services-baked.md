# ADR-013: Services — RPC Broker, VistALink, sshd, Octo, YDB GUI

Date: 2026-04-17
Status: Accepted

## Context
Baseline VistA containers run many services: RPC Broker (CPRS, DDR), VistALink, sshd, xinetd, MailMan, TaskMan, optionally QEWD, Panorama, Octo SQL, YDB GUI, M Web Server. Which to include depends on use case.

## Decision
Five services in v1:
- **sshd** on port 2222 (container port 22): user-level access for exec/debug.
- **RPC Broker** on port 9430 via xinetd: CPRS + DDR RPC access.
- **VistALink** on port 8001 via xinetd: M-side listener.
- **Octo SQL** (`rocto`) on port 1338: SQL queries against FileMan-mapped files.
- **YDB GUI** on port 8089 (YDBGUI + YDB Web Server): global/routine browsing UI.

## Consequences
- Positive: Covers all the analytics access patterns: shell (ssh), M sessions (via ssh + mumps), RPC (for DDR), SQL (Octo), visual exploration (YDBGUI).
- Positive: No TaskMan, MailMan, QEWD, Panorama — smaller image, fewer moving parts.
- Positive: Each service independently testable via the HEALTHCHECK script.
- Negative: Five services to manage in entrypoint signal handling.
- Neutral: If later work needs TaskMan (scheduled jobs), add it as ADR addendum.

## Alternatives considered
- Only RPC Broker + sshd: minimal but Octo and YDBGUI are high-value analytics aids.
- Include QEWD / Panorama: web UIs irrelevant for metadata analytics.
- Include TaskMan: no scheduled jobs in scope.
- Include M Web Server on 9080: redundant with YDB Web Server underlying YDBGUI (see ADR-042).
