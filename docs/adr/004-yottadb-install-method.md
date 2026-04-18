# ADR-004: YottaDB via ydbinstall.sh, pinned version

Date: 2026-04-17
Status: Accepted

## Context
YottaDB can be installed from prebuilt binaries via `ydbinstall.sh`, or built from source (`-o` flag in WorldVistA's installer). Version pinning matters for reproducibility.

## Decision
Install YottaDB from prebuilt binaries via `ydbinstall.sh`. Pin version via `YDB_VERSION` Dockerfile build arg. Default to current stable (rX.YY to be determined at first build).

## Consequences
- Positive: Build time ~30 seconds vs. 30+ minutes for source build.
- Positive: Reproducible builds — same `YDB_VERSION` arg always yields same YDB.
- Positive: Matches YottaDB-supported installation path; easy to upgrade later.
- Negative: Binary-only means no debug symbols; harder to diagnose YDB bugs. Acceptable tradeoff for a metadata sandbox.
- Neutral: Forces Ubuntu 24.04 compatibility (covered by ADR-003).

## Alternatives considered
- Build from source (`-o`): wastes build time for zero gain in dev environment.
- Install from OS package manager: YDB isn't in apt; would require adding YDB's apt repo.
- Use `latest` unpinned: fails reproducibility goal; a future rebuild could silently pick up a breaking YDB version bump.
