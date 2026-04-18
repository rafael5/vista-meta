# ADR-041: YDB GUI — open (no authentication)

Date: 2026-04-18
Status: Accepted

## Context
YDB Web Server supports JSON-file authentication (`--auth-file users.json`) with hashed passwords and login token workflow. Services are bound to minty's Tailscale IP only (ADR-008), so network-layer access is already restricted to Tailnet members.

## Decision
Run YDB GUI without authentication. No `--auth-file`. No `--auth-stdin`. Tailscale identity is the sole access gate.

## Consequences
- Positive: Zero friction — open the URL, the GUI is there.
- Positive: One fewer credential store to maintain (no users.json, no rotation).
- Positive: Consistent with sshd posture (key-based auth is the baseline Tailscale gives you).
- Negative: Anyone on Rafael's Tailnet can use the GUI. Acceptable given Tailnet is Rafael's personal devices.
- Negative: If Tailnet grows to include shared members later, revisit. Easy to add auth later.

## Alternatives considered
- JSON-file auth: defense-in-depth, but friction every GUI open with no real threat model gain for personal Tailnet.
- TLS + auth: libsodium + cert management for dev tool UI. Overkill.
- Localhost-only (require SSH tunnel): friction every session; defeats the GUI's "browse and explore" purpose.
