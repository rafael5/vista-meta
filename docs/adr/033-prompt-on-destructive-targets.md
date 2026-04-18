# ADR-033: Prompt always on destructive Makefile targets

Date: 2026-04-18
Status: Accepted

## Context
`make clean` removes the container AND the named volume `vehu-globals` — destroying all accumulated state (database, first-run bake output). Easy to misfire. Options: prompt always, require `FORCE=1` override, no protection.

## Decision
Prompt always. `clean` issues `read -p "delete vehu-globals volume? [y/N] "` before destructive action. Same pattern for any future destructive target.

## Consequences
- Positive: Safest default. Catches the `make clean` vs. `make rm` typo.
- Positive: Zero-ceremony for normal ops (build, run, stop don't prompt).
- Negative: CI/scripted teardown can't currently use `make clean`. If that need arises, add `FORCE=1` escape hatch in a future ADR.
- Neutral: Prompts don't fire when run in a pipe or non-tty; consider using `[ -t 0 ]` check if that becomes an issue.

## Alternatives considered
- `FORCE=1` required: mildly more annoying in the common case ("oh right I need FORCE=1").
- No protection: trusts the user always gets the target right. Eventually they won't.
- Two-stage (`make clean-confirm`): uglier target name; same friction as prompt.
