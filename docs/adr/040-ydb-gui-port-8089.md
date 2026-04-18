# ADR-040: YDB GUI on port 8089

Date: 2026-04-18
Status: Accepted

## Context
YDBGUI (`gitlab.com/YottaDB/UI/YDBGUI`) runs behind YDB Web Server. Two port conventions exist:
- YottaDB Inc's `yottadb/yottadbgui` Docker image: 8080 internally, demo forwarded to 8089.
- WorldVistA's `docker-vista` and YottaDB's `octo-vehu` image: 8089.

## Decision
YDB GUI on port 8089. Started by entrypoint as `vehu` user:
```
yottadb -run start^%ydbwebreq --directory /opt/ydbgui/web --port 8089 --log 1
```

## Consequences
- Positive: Consistent with broader VistA-on-YDB ecosystem conventions.
- Positive: Matches WorldVistA's docker-vista port layout — if Rafael cross-references with WorldVistA images later, port expectations align.
- Positive: No conflict with other services (2222, 8001, 1338, 9430 all distinct).
- Negative: Not the upstream YottaDB container's internal port (8080). Negligible — we're configuring, not consuming.
- Neutral: Port easily changed via single constant in service config if conflict arises.

## Alternatives considered
- 8080: matches yottadb/yottadbgui internal port, but 8080 is extremely common and often conflicts with other tools on dev machines.
- Random high port: loses the ecosystem convention alignment.
