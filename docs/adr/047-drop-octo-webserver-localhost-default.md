# ADR-047: Drop Octo SQL + YDB Web Server; localhost-default binding (no Tailscale requirement)

Date: 2026-05-18
Status: Accepted (supersedes ADR-008, ADR-013, ADR-040, ADR-041)

## Context

ADR-013 selected five services for v1, including **Octo SQL** (`rocto`,
:1338) and the **YDB GUI** (:8089, served by the YDB Web Server).
ADR-040 fixed the GUI port; ADR-041 ran the GUI without auth; ADR-008
made a host **Tailscale IPv4** the mandatory bind address and network
perimeter for all ports.

Three things changed the calculus since those were accepted:

1. **Octo and the YDB Web Server are not used by VistA and not used by
   this project.** The data/code model is extracted via FileMan
   utilities, FMQL, Print Templates, and XINDEX (ADR-016/017) — never
   via SQL or a browser UI. Octo + YDBGUI were "high-value analytics
   aids" in theory that no workflow actually exercises.
2. **They impose real build cost.** Octo's `ydbinstall --octo` plugin
   preflight requires `clang` and a chain of `-dev` headers; it also
   pulled in a separate Octo-DDL-mapping image layer (YDBOctoVistA
   `MAPALL`) and a YDBGUI build layer (Angular + cmake). All of that is
   pure overhead for capabilities nothing consumes.
3. **The Tailscale requirement was a single-host friction tax.** This
   is a developer container for one engine shared by sibling projects
   on the same host (the shared-engine model). Forcing every operator
   to populate `TAILSCALE_IP` in `.env` before *any* `make` target
   would run (the Makefile `include .env`) gated builds on a network
   identity that local single-host use does not need.

## Decision

**Remove Octo SQL and the YDB Web Server / YDBGUI entirely.** The image
ships YottaDB core only. Drop the `--octo --webserver` ydbinstall flags,
the `clang` apt dependency (only Octo's preflight needed it), the Octo
DDL-mapping layer, the YDBGUI install layer, the rocto/ydbgui
start/verify/shutdown logic in the entrypoint, and ports 1338 + 8089
everywhere (`EXPOSE`, compose, the client `conn.env` contract).

**Make network binding localhost-default and Tailscale-optional.** The
mandatory `TAILSCALE_IP` becomes an optional, generically-named
`HOST_BIND_IP` defaulting to `127.0.0.1`. `.env` is optional
(`-include`); no configuration is required to build or run. Exposing
the engine beyond loopback (Tailscale, or any private overlay/VPN
interface) is a deliberate opt-in by setting `HOST_BIND_IP`, not a
precondition.

Surviving services: **sshd** (:2222), **RPC Broker** (:9430 via
xinetd), **VistALink** (:8001 via xinetd) — unchanged.

## Consequences

- Positive: Smaller image, fewer build layers, no `clang`/Octo `-dev`
  dependency chain, faster builds, fewer moving parts in entrypoint
  signal handling.
- Positive: Zero-config — `make build` / `make run` work on a fresh
  checkout with no `.env`. Removes the most common first-run failure.
- Positive: Removing Octo/GUI also removes ADR-041's "open GUI on the
  Tailnet" exposure entirely — the question no longer exists.
- Negative: No SQL access to FileMan-mapped files and no browser-based
  global/routine explorer. Acceptable: no workflow used them; `mumps
  -direct`, the CLI, and the TSV model cover exploration.
- Negative: Cross-machine access (CPRS from another node, etc.) now
  requires explicitly setting `HOST_BIND_IP` instead of it being the
  default posture. Acceptable: single-host is the common case;
  multi-host is the exception and is one env var.
- Neutral: ADR-042 (skip M Web Server) still stands and is unaffected.
- Neutral: If Octo or a GUI is ever genuinely needed, reintroduce via a
  superseding ADR — do not treat their absence as an accident
  (see project memory).

## Alternatives considered

- Keep Octo/GUI but fix only the clang dep: retains build weight and
  attack surface for capabilities nothing uses. Rejected.
- Keep Tailscale-mandatory but make `.env` optional with a Tailscale
  default: still couples local dev to a network identity; the variable
  stays misleadingly Tailscale-specific. Rejected in favor of a generic
  `HOST_BIND_IP`.
- Localhost-only with no override at all: would block the legitimate
  shared-engine / cross-node use case. Rejected — opt-in override kept.
- Edit ADR-008/013/040/041 in place: violates ADR immutability. This
  superseding ADR is the sanctioned mechanism; the superseded ADRs'
  Status lines are updated to point here (the one format-sanctioned
  mutation), bodies left intact.
