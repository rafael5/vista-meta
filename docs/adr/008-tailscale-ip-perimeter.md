# ADR-008: Tailscale IP as network perimeter

Date: 2026-04-17
Status: Accepted

## Context
Services (sshd, RPC Broker, VistALink, Octo, YDB GUI) need to be reachable from Rafael's Tailnet nodes (mac-rmr, pixel-8, pi5, glnet) but not from minty's home LAN or the public internet. Options: localhost-only with SSH tunnels, bind to Tailscale IPv4, bind to all interfaces with firewall, bind to all interfaces unrestricted.

## Decision
Bind all service ports to minty's Tailscale IPv4 address only via `-p $TAILSCALE_IP:<port>:<port>` in `docker run`. Resolve once via `tailscale ip -4`, store in `.env`.

## Consequences
- Positive: Simplest config that achieves Tailscale-only exposure. Zero firewall state to maintain.
- Positive: Defense in depth — even a misconfigured container cannot leak to LAN.
- Positive: Matches Rafael's existing Tailscale-first infrastructure patterns.
- Negative: `.env` must be updated if Tailscale IP changes (rare but possible).
- Negative: Cannot access services from minty's loopback without a separate local port mapping (easy workaround if needed).

## Alternatives considered
- Localhost-only + SSH tunnel: extra friction every time CPRS connects from Mac.
- `0.0.0.0` bind: exposes to home LAN; unnecessary attack surface.
- `0.0.0.0` + ufw allow only `tailscale0`: defense-in-depth but adds ufw state dependency that can drift silently.
