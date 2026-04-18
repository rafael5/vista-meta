# ADR-026: Host Python venv at host/

Date: 2026-04-18
Status: Accepted

## Context
Some analysis tasks run better on host than in container — e.g., notebook-style exploration, plotting, large-memory DuckDB queries across many export/ files, or anything benefiting from tools already installed on minty. Rafael uses uv + direnv for venvs per standing pattern.

## Decision
Include `host/` subdirectory with `pyproject.toml`. Host venv lives at `host/.venv/` (gitignored). Purpose: post-hoc analysis of `vista/export/` output without needing a running container.

## Consequences
- Positive: Ad-hoc analysis (quick pandas queries, Jupyter, plotting) runs on host with full system resources.
- Positive: Container Python stays lean (yottadb bindings + minimal deps); host venv can be heavy (polars, duckdb, jupyter, matplotlib, networkx, graphviz).
- Positive: Matches Rafael's venv-setup.sh / uv / direnv pattern.
- Negative: Two Python environments to reason about. Mitigated by clear separation: in-container for YDB access, host for file-based analysis.
- Neutral: Host venv is optional; you can do all analysis inside container if preferred.

## Alternatives considered
- No host venv: fine for the simple case, but notebook/plotting workflows are clunky over SSH.
- Host venv only, no container Python: loses live YDB access for analytics.
- Shared venv between host and container: impossible (arch/path issues).
