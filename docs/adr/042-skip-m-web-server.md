# ADR-042: Skip M Web Server (port 9080)

Date: 2026-04-18
Status: Accepted

## Context
WorldVistA's `docker-vista` lists an "M Web Server" on port 9080 as a separate service — an older HTTP server used by some VistA web-facing components, distinct from the YDB Web Server that underlies YDBGUI.

## Decision
Skip the M Web Server. Do not bake it into the image. Port 9080 remains unused.

## Consequences
- Positive: One fewer service to configure, monitor, and document.
- Positive: Smaller attack surface (even on Tailnet).
- Positive: YDB Web Server (underlying YDBGUI) already provides HTTP access for our metadata analytics needs.
- Negative: If a future use case needs older VistA web pages (unlikely for metadata analytics), must add later.
- Neutral: No conflict with our existing port allocations regardless.

## Alternatives considered
- Include it anyway: YAGNI — no planned use.
- Lazy-install on demand: more complex than just not having it; `docker exec` plus pip install covers 1-off needs.
