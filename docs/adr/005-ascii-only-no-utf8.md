# ADR-005: ASCII-only, no UTF-8

Date: 2026-04-17
Status: Accepted

## Context
YottaDB supports UTF-8 chset via `-u` install flag. WorldVistA's Plan VI variant uses UTF-8 for internationalization (Korean ICD-10, etc.). VEHU's synthetic data is English-only ASCII.

## Decision
Install YottaDB in default M chset (ASCII). Do not pass `--utf8` to `ydbinstall.sh`. Set `ydb_chset=M`.

## Consequences
- Positive: Simpler install path, no locale pkg bloat.
- Positive: No chset mode-switching headaches when loading VEHU-M.
- Positive: Matches VEHU's upstream expectations.
- Negative: Cannot analyze internationalized VistA variants (Plan VI Korean, Arabic, etc.) without a rebuild.
- Neutral: Most VistA schema analysis is schema-level, not data-level; UTF-8 absence rarely limits DD work.

## Alternatives considered
- Enable UTF-8 (`-u`): adds locale handling complexity, fonts in container, no upside for VEHU's data.
- Dual-mode build arg: adds test matrix dimension; not needed for v1.
