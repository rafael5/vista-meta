# ADR-021: tini as PID 1, bash entrypoint

Date: 2026-04-17
Status: Accepted

## Context
Need to run multiple processes (sshd, xinetd, rocto, YDB GUI, background bake) inside one container. PID 1 is responsible for signal forwarding and zombie reaping — shell scripts do both badly. Options: systemd, supervisord, s6, tini, plain bash.

## Decision
`tini` as PID 1 (ENTRYPOINT). tini invokes a bash script `entrypoint.sh` that launches services in background and `wait`s.

```
ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/entrypoint.sh"]
```

## Consequences
- Positive: tini is ~200 KB, zero config, handles SIGTERM/SIGINT forwarding and zombie reaping correctly.
- Positive: bash entrypoint is trivially readable and debuggable.
- Positive: `docker stop --time 30 vista-meta` works cleanly — tini forwards SIGTERM, bash trap handles graceful shutdown of YDB-facing services.
- Negative: Not a real init system; no service dependency ordering beyond what the script does manually.
- Negative: No auto-restart if a service crashes. Acceptable for a dev sandbox; revisit if flapping becomes a real issue.

## Alternatives considered
- systemd inside container: overkill, heavyweight, requires --privileged or specific cgroup setup.
- supervisord: extra config format (INI), extra daemon, no meaningful gain for 5 services.
- s6-overlay: more capable than tini but more config; we don't need its features.
- No tini, bash as PID 1: zombie processes accumulate; signal forwarding is buggy.
