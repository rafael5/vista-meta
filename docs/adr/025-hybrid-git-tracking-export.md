# ADR-025: Hybrid git tracking for export/

Date: 2026-04-18
Status: Accepted

## Context
`vista/export/` contains bake output that's substantial in size (FOIA-scale DD text ~hundreds of MB, FMQL JSON similar) but also contains your own analysis products. Pure track-everything bloats the repo; pure gitignore loses history of analytical work.

## Decision
Hybrid tracking:
- `vista/export/<exporter>/raw/` — gitignored (regenerable via bake).
- `vista/export/<exporter>/INDEX.tsv` — tracked (small manifest, diffable).
- `vista/export/<exporter>/summary.md` — tracked (human summary, diffable).
- `vista/export/normalized/` — tracked entirely (your conceptual layer, the project's actual output).
- `vista/export/logs/` — gitignored.
- `vista/export/.vista-meta-initialized` — tracked (sentinel JSON is small and meaningful).

`.gitignore` rules:
```
vista/export/**/raw/
vista/export/logs/
```

## Consequences
- Positive: Repo stays small; only meaningful diffs are tracked.
- Positive: INDEX.tsv diffs show what VEHU-M updates changed (new files, renamed fields).
- Positive: `normalized/` is the project's IP — tracked everywhere it lives.
- Negative: Raw dumps not in history; if you want to compare raw outputs from two dates, snapshot manually.
- Neutral: Clear mental model — "raw is regenerable, curated is versioned."

## Alternatives considered
- Track everything: repo bloats to GBs fast.
- Gitignore everything: lose ability to version-track your actual work.
- Track INDEX.tsv only, not summary.md: summaries are tiny and invaluable for "what did that bake find?"
