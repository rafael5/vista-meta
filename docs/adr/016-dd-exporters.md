# ADR-016: DD exporters — FileMan utilities + FMQL + Print Templates

Date: 2026-04-17
Status: Accepted

## Context
Multiple ways to extract FileMan DD exist:
- A: Standard FileMan utilities (`^DIU2`, `^DD` walks, `DIFROM`) — raw text output.
- B: FMQL (`github.com/caregraf/FMQL`) — structured JSON output.
- C: ViViaN M extraction routines — intermediate data tuned for HTML rendering.
- D: FileMan Print Templates applied to `^DD` — custom format per template design.

Goal is to build a normalized conceptual layer. Need both input data and comparison baselines.

## Decision
Bake three exporters: A, B, D. Skip C.

Output directory structure (per exporter):
```
export/<exporter>/
  INDEX.tsv        (tracked)
  summary.md       (tracked)
  raw/             (gitignored; per-item output)
```

## Consequences
- Positive: Three complementary perspectives on DD — raw text (A), structured JSON (B), custom template (D) — enable cross-comparison to validate your normalized layer.
- Positive: A and B are available day one as comparison baselines; D is scaffolding you extend.
- Negative: Three exporters = three bake phases = more first-run time.
- Neutral: Skipping ViViaN extraction (C) aligns with the broader ViViaN/DOX deferral (ADR-043).

## Alternatives considered
- A only: lose structured baseline; you'd build JSON yourself from text.
- B only: tempting but risks "normalized layer = FMQL with a coat of paint"; thesis muddied.
- All four (including C): C's output shape doesn't fit; adds noise.
- None (build your own option D only): no baselines for validation.
