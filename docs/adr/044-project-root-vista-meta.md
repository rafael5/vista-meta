# ADR-044: Project root = ~/vista-meta, standalone repo

Date: 2026-04-18
Status: Accepted (supersedes earlier drafts locating project under ~/claude/)

## Context
Early spec drafts placed the project at `~/claude/vista-meta/` — inside Rafael's claude-skills repo (`rafael5/claude`). On reflection, vista-meta is application code (a Docker-hosted VistA analytics sandbox), not a skill. Claude skills and vista-meta have different lifecycles, different update cadences, and different intended audiences.

## Decision
Project root is `~/vista-meta/` on minty, as its own top-level directory and standalone git repository (will live at `github.com/rafael5/vista-meta`).

## Consequences
- Positive: Clean separation of concerns — skills repo stays focused on skills; vista-meta stays focused on vista-meta.
- Positive: Own git history, own issues, own release cadence.
- Positive: Claude skills can still reference `~/vista-meta/vista/export/` as an external path if a skill wants to consume vista-meta's output.
- Positive: Easier to share or open-source without dragging the whole claude-skills repo.
- Negative: One more top-level directory in `~`. Trivial.
- Neutral: Nothing inside the container changes — `/home/vehu/...` and `/opt/VistA-M/...` are independent of host-side location.

## Alternatives considered
- Keep under `~/claude/`: conflates skill infrastructure with an app project.
- Sub-directory of some `projects/` umbrella: adds a level of indirection for no benefit on a single-user machine.
- Keep the spec at `~/claude/vista-meta/` but the running code at `~/vista-meta/`: splits the project artifact; worse than deciding one place.
