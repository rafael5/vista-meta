# ADR-050: Local-only networking — loopback binding, Tailscale perimeter retired

Date: 2026-07-04
Status: Accepted (supersedes ADR-008)

## Context

ADR-008 bound all published container ports to the host's Tailscale IP so the
stack could be reached from other Tailnet machines. In practice the entire
stack is used from exactly one machine — the Linux Mint host it runs on. The
`TAILSCALE_IP` knob threaded through `.env`, the Makefile, compose port
bindings, the connection contract, and the smoke test, buying reach nobody
uses at the cost of a required env var and networking conditionals everywhere.

## Decision

Everything binds **`127.0.0.1`**, hardcoded:

- `docker/compose.yml` port bindings are `127.0.0.1:…` — the *interface* is
  hardcoded loopback. The *host port numbers* stay overridable (`RPC_PORT`,
  `VLINK_PORT` in `.env`) because loopback is shared with the sibling engine
  containers (the m-cli `vehu` stack binds 127.0.0.1:8001/9430) — discovered
  the hard way when the first loopback bind collided.
- The `TAILSCALE_IP` env var is deleted from `.env`, `.env.example`, and the
  Makefile; `make shell` SSHes to `vehu@127.0.0.1:2222`.
- The published connection contract (`write-conn`) declares
  `VISTA_HOST=127.0.0.1` — sibling projects (m-cli etc.) run on the same
  machine and are unaffected.
- The smoke test's SSH check targets loopback unconditionally (no skip logic).

ADR-041's rationale ("Tailscale identity is the access gate" for the
auth-less YDB GUI) is restated: **loopback-only binding is the access gate** —
only local processes can reach any service port.

## Consequences

- Positive: one less required env var; no networking conditionals in compose,
  Makefile, or smoke; the security posture is simpler and stronger
  (nothing leaves the machine).
- Negative: remote access now requires deliberate action (an SSH tunnel, or
  reverting this ADR) — accepted, since it was never used.
- Neutral: in-container services still bind 0.0.0.0; the restriction stays at
  the Docker `-p` layer, as before.

## Alternatives considered

- Keep the `${TAILSCALE_IP:-127.0.0.1}` default — rejected: dead flexibility
  that keeps the conditional plumbing and the "REQUIRED" env-var docs alive.
- Docker network isolation / no published ports — too far: host tools (CLI,
  smoke, sibling repos) legitimately use the loopback ports.
