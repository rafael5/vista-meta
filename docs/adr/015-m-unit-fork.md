# ADR-015: M-Unit — ChristopherEdwards fork

Date: 2026-04-18
Status: Accepted (supersedes initial plan to use joelivey/M-Unit)

## Context
Two forks of M-Unit exist, both with `%ut` namespace, both descended from Joel Ivey's original VA `XTMUNIT`:
- `github.com/joelivey/M-Unit`: packaged as VistA KIDS install, ~2017 frozen.
- `github.com/ChristopherEdwards/M-Unit`: packaged as YDB plugin via cmake, actively referenced by YottaDB's YDBGUI build.

Functional M code is equivalent. Difference is packaging/install model.

## Decision
Use `ChristopherEdwards/M-Unit`. Install as YDB plugin via `git clone ... && cd build && cmake .. && make && make install` into `$ydb_dist/plugin/`.

## Consequences
- Positive: Native YDB plugin install matches Octo, YDB Web Server, YDBGUI install pattern — one install idiom, not two.
- Positive: YDBGUI's own build expects this fork; eliminates compat risk.
- Positive: `%ut` routines callable from dev-r/ test routines identically to the KIDS version.
- Negative: Deviates from what VistA-world developers expect (they'd install via KIDS).
- Neutral: Both forks produce the same test runner behavior for test authors.

## Alternatives considered
- `joelivey/M-Unit` via KIDS install: matches VistA tradition but forces a separate install path from all other plugins. YDBGUI compat untested.
- Investigate full diff before choosing: done (diff confirmed equivalent M code); packaging choice decided this ADR.
