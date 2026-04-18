# ADR-014: Python tooling baked in (yottadb bindings, git)

Date: 2026-04-17
Status: Accepted

## Context
Much of the analysis work (parsing XINDEX output, transforming FMQL JSON, building a normalized DD layer) is more naturally Python than M. Python must be callable inside the container where YDB is accessible.

## Decision
Bake into image: Python 3 (apt), pip, `yottadb` pip package (official YDB Python bindings), `click`, `pyyaml`, `requests`, plus git.

## Consequences
- Positive: `python3` scripts in `scripts/` can hit YDB globals directly via the `yottadb` package.
- Positive: git inside the container means you can commit from dev sessions without exiting.
- Positive: `click`/`pyyaml`/`requests` cover 80% of what analytics scripts need without future pip installs.
- Negative: ~150 MB image bloat for Python + deps.
- Neutral: Additional pip installs possible at runtime via `pip install --user`; persist via `host/` venv for production analyses.

## Alternatives considered
- No Python in image; run Python on host against export/ files: breaks live-data access pattern; loses YDB bindings.
- Conda/mamba: overkill for this project.
- Just Python stdlib, no packages: forces first-time friction for every user.
