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
- `vista/export/data-model/` — tracked entirely (FileMan + PIKS slice, the project's actual output).
- `vista/export/code-model/` — tracked entirely (routines/packages/XINDEX slice, the project's actual output).
- `vista/export/RESEARCH.md` — tracked (research log, cross-cutting across both slices).
- `vista/export/logs/` — gitignored.
- `vista/export/.vista-meta-initialized` — tracked (sentinel JSON is small and meaningful).

*(Note: original wording was `vista/export/normalized/` — tracked entirely.
The normalized/ folder was split into `data-model/` and `code-model/` after
ADR-045 established the separate-data-and-code classification. RESEARCH.md
moved up one level to avoid being in either slice. The tracking intent is
unchanged.)*

`.gitignore` rules:
```
vista/export/**/raw/
vista/export/logs/
```

## Consequences
- Positive: Repo stays small; only meaningful diffs are tracked.
- Positive: INDEX.tsv diffs show what VEHU-M updates changed (new files, renamed fields).
- Positive: `data-model/` + `code-model/` are the project's IP — tracked everywhere they live.
- Negative: Raw dumps not in history; if you want to compare raw outputs from two dates, snapshot manually.
- Neutral: Clear mental model — "raw is regenerable, curated is versioned."

## Alternatives considered
- Track everything: repo bloats to GBs fast.
- Gitignore everything: lose ability to version-track your actual work.
- Track INDEX.tsv only, not summary.md: summaries are tiny and invaluable for "what did that bake find?"
