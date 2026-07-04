# ADR-049: Project root is ~/projects/vista-meta (supersedes ADR-044)

Date: 2026-07-04 (backfill — relocation executed 2026-05-04/05)
Status: Accepted (supersedes ADR-044)

## Context

ADR-044 placed the repo at `~/vista-meta` as a standalone top-level directory.
The home directory's conventions later consolidated all active personal
projects under `~/projects/<name>/` (with `~/vista-forge/` and
`~/vista-copilot/` as the org workspaces), and the repo was relocated
accordingly — the executed procedure is
`docs/historical/relocate-and-publish-record.md` (Part A).

## Decision

The project root is **`~/projects/vista-meta/`**, a standalone git repo with
remote `github.com/rafael5/vista-meta` (private). Everything else in ADR-044
(standalone repo, self-contained layout) stands.

## Consequences

- Positive: consistent with the machine-wide `~/projects/` convention; the
  CLAUDE.md descriptor, docs, and tooling all agree with reality again.
- Negative: none observed; bind-mount paths are relative to the repo root and
  survived the move.
- Neutral: ADR-044's text remains as written (immutable); its Status line and
  the index now point here.

## Alternatives considered

- Editing ADR-044 in place — rejected: ADRs are immutable once accepted
  (ADR-028); corrections are superseding records.
