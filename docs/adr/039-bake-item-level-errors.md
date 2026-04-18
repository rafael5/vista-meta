# ADR-039: bake.sh — item-level error granularity

Date: 2026-04-18
Status: Accepted

## Context
Within a bake phase (e.g., XINDEX over 30k routines), individual items can fail for routine-specific reasons (one malformed routine, one file with unusual DD structure). Phase-level all-or-nothing would be too blunt. Options: phase-level only (any item error stops the phase), item-level (log and continue).

## Decision
Item-level within a phase. Per-item errors logged to `export/logs/<phase>.errors.tsv` (columns: item_id, error_class, message). Phase ends as:
- `ok` — no errors
- `partial` — some items failed
- `failed` — all items failed OR catastrophic error (missing binary, env broken)

## Consequences
- Positive: One bad routine doesn't torpedo 30,000 good ones.
- Positive: Error triage via a single TSV per phase. Grep-friendly.
- Positive: `partial` status surfaces the reality — you get useful output and a list of what to investigate.
- Negative: `partial` must be clearly communicated; otherwise users think bake completed when it actually has 200 item failures. Mitigated by summary.md and sentinel JSON counts.
- Neutral: Catastrophic failures (not per-item) still mark phase `failed` — the distinction is preserved.

## Alternatives considered
- Phase-level only (any error → `failed`): loses 99.3% successful output because of 0.7% failures.
- Exit on first error within phase: fast-fails usefully only if errors are rare and important; here they're common and diagnosable post-hoc.
- Retry-per-item policy: overengineering for a bake pipeline.
