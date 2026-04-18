# ADR-017: Enhanced XINDEX via VEHU inheritance

Date: 2026-04-17
Status: Accepted

## Context
VA's XINDEX (patch XT*7.3*140) covers most VistA M code but misses some FileMan execution points (Sort Templates, Input Transforms, Screens, etc.). WorldVistA's Enhanced XINDEX at `github.com/WorldVistA/XINDEX` extends coverage and fixes bugs. Available via OSEHRA VistA → VEHU inheritance chain.

## Decision
Use the Enhanced XINDEX that ships in VEHU-M. No separate install step. Verify presence during first-run bake.

## Consequences
- Positive: Zero install cost — it's already there.
- Positive: Same XINDEX as OSEHRA/WorldVistA users; output comparable across VistA community.
- Positive: Extended coverage captures M code that stock VA XINDEX misses.
- Negative: If VEHU ever regressed from OSEHRA's Enhanced XINDEX lineage, we'd silently use stock XINDEX. Mitigation: verify routine content on first bake (check for Enhanced XINDEX signature).
- Neutral: Version of Enhanced XINDEX in VEHU is pinned to VEHU's snapshot date.

## Alternatives considered
- Install Enhanced XINDEX separately from WorldVistA/XINDEX repo: duplicates what's already there; potential conflict.
- Use stock VA XINDEX only: misses FileMan coverage gaps that matter for metadata analytics.
