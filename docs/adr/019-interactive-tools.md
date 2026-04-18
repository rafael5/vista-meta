# ADR-019: Interactive tools — ranger, micro, tree, btop, ncdu

Date: 2026-04-18
Status: Accepted

## Context
vista-meta is used via SSH from mac-rmr or pixel-8, so interactive comfort tools matter. Rafael specifically requested ranger and micro (not nano or vim), plus a set of interactive exploration tools.

## Decision
Bake into image via apt (Ubuntu 24.04 universe):
- **ranger** — file manager (Python, ~5 MB)
- **micro** — terminal editor, modern keybindings (~10 MB); apt version preferred over GitHub static binary for noble cycle alignment
- **tree** — directory visualization
- **btop** — modern resource monitor
- **ncdu** — disk usage navigator
- **less** — already in base

## Consequences
- Positive: Pleasant SSH sessions; no per-session tool install friction.
- Positive: All packages from Ubuntu noble — no version drift or external source verification.
- Positive: Micro's modern keybindings (ctrl+s save, ctrl+c copy) reduce cognitive load vs. vim/nano.
- Negative: ~20-30 MB image bloat. Acceptable for a dev sandbox.
- Neutral: `less` covered by base image; no explicit apt install needed.

## Alternatives considered
- nano/vim instead of micro: Rafael explicitly rejected.
- GitHub static binary for micro: latest features but version drift vs. OS cycle; not worth the delta for this use case.
- htop instead of btop: btop has better defaults and visualization.
- Skip interactive tools (alpine philosophy): SSH usage is primary access pattern; friction would accumulate.
