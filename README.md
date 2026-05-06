# vista-meta

A deterministic, machine-readable model of **VistA** — the VA's
electronic health record system — covering both the data it stores
and the code that manipulates it. Plus the operational tooling
(VSCode extension, CLI, formatter, lint hook) built on top.

The single authoritative map is
[docs/vista-meta-guide.md](docs/vista-meta-guide.md). Read that
first for scope, thesis, and cross-references.

## The thesis

You cannot model VistA's data without modeling its code, and you
cannot model its code without modeling its data — they are the same
artifact viewed from two sides. vista-meta is the first project to
extract, reduce, and interlink both in the same deterministic
artifact set.

## What ships

| | Artifact | Produces |
|---|---|---|
| **A. Data model** | `vista/export/data-model/` (5 TSVs, ~170k rows) | PIKS classification of 8,261 FileMan files at 98.3% coverage; 69,810 field-level annotations; cross-PIKS pointer matrix |
| **B. Code model** | `vista/export/code-model/` (19 TSVs, ~1.0M rows) | Per-routine intelligence: calls, callers, globals, RPCs, options, protocols, XINDEX findings, package topology |
| **1. VSCode extension** | `vscode-extension/` | VISTA ROUTINE sidebar: tags, callers, callees, globals, XINDEX — all from TSV reads, no runtime dependency |
| **2. CLI + hook + formatter** | `bin/vista-meta`, `bin/mfmt`, `hooks/pre-commit` | doctor, pkg, context, where, callers, search, file, new-test, lint, xindex; SAC-compliant pre-commit gate |

## Requirements

- Linux host (macOS Docker should work but untested; Windows excluded)
- Docker
- Python ≥ 3.10 (host-side scripts and CLI)
- VSCode (optional — only for the extension)

MUMPS engine is **YottaDB-only**. The bake uses `mupip`, `$ZRO`, and
ydb-specific GDE syntax, so IRIS / Caché will not run it.

## Quick start

```bash
make build          # build Docker image (~20 min first time)
make run            # start container (bake runs in background on first run)
make wait-for-bake  # poll the sentinel until the bake completes
make shell          # SSH into the container as vehu

bin/vista-meta doctor             # environment health check
bin/vista-meta pkg "Pharmacy"     # package overview
bin/vista-meta context PSO        # AI context pack for a package
```

`make help` lists every Make target.

## Where code runs

Code is **edited on the host**, **executed in the container**.

| Location | Runs on | Contents |
|---|---|---|
| `docker/` | host (build context) | Dockerfile, entrypoint, configs |
| `vista/dev-r/` | container (bind mount) | Your M routines — shadows VEHU via `$ZRO` |
| `vista/scripts/` | container (bind mount) | Python + shell analysis scripts |
| `vista/export/` | container (bind mount) | Bake output, logs, sentinel JSON, research log |
| `vista/vista-m-host/` | host snapshot | Host-visible copy of the VistA-M source tree |
| `host/scripts/` | host | All host-side Python (CLI, model builders, mfmt) |
| `bin/`, `hooks/` | host | CLI entry points, pre-commit hook |
| `vscode-extension/` | host | VSCode extension source + built `.vsix` |
| `tests/smoke/` | host (against container) | Post-build verification |

## Documentation

The `docs/` tree is layered. Start at the top, drill where needed.

| What | Where |
|---|---|
| **Comprehensive project guide** | [docs/vista-meta-guide.md](docs/vista-meta-guide.md) |
| Authoritative technical spec | [docs/vista-meta-spec-v0.4.md](docs/vista-meta-spec-v0.4.md) |
| Developer onramp | [docs/vista-developers-guide.md](docs/vista-developers-guide.md) |
| Per-routine situational awareness | [docs/routine-situational-awareness.md](docs/routine-situational-awareness.md) |
| Per-package situational awareness | [docs/package-situational-awareness.md](docs/package-situational-awareness.md) |
| VSCode + CLI reference | [docs/vista-vscode-guide.md](docs/vista-vscode-guide.md) |
| VSCode extension internals | [docs/vscode-extension-internals.md](docs/vscode-extension-internals.md) |
| PIKS methodology | [docs/piks-analysis-guide.md](docs/piks-analysis-guide.md) |
| Code model TSVs | [docs/code-model-guide.md](docs/code-model-guide.md) |
| XINDEX reference | [docs/xindex-reference.md](docs/xindex-reference.md) |
| Decision rationale | [docs/adr/](docs/adr/) |
| Implementation log | [docs/build-log.md](docs/build-log.md) |
| Research findings | [vista/export/RESEARCH.md](vista/export/RESEARCH.md) |
| Upstream pinning | [docs/dependencies.md](docs/dependencies.md) |

## PIKS — the data-model first-pass abstraction

Every FileMan file and non-FM global is classified into:

- **P**atient — clinical care data (protected, longitudinal, exchange-ready)
- **I**nstitution — facility, org, scope of care (comparative, admin)
- **K**nowledge — terminologies, templates, workflows (informatics, declarative)
- **S**ystem — config, operations, VistA internals (IT, DevOps)

with four orthogonal properties: volatility, sensitivity,
portability, volume. Implemented by 52 DD-based heuristics
(H-01…H-52) across 9 tiers + 6 non-FM heuristics (G-01…G-06).
Coverage: 98.3%. Full details in
[docs/piks-analysis-guide.md](docs/piks-analysis-guide.md).

## License

See [LICENSE](LICENSE). The vendored VistA-M source under
`vista/vista-m-host/` follows its upstream public-domain status.

## Companion projects

- [py-kids-vc](https://github.com/rafael5/py-kids-vc) — KIDS
  decompose / assemble / round-trip CLI; vista-meta's
  `make patch-decompose|patch-assemble|patch-roundtrip` shells out
  to it.
- [py-kids-install](https://github.com/rafael5/py-kids-install) —
  drives KIDS installs into the same VEHU container vista-meta
  builds.
- **vista-cli** — downstream consumer that joins vista-meta TSVs
  with vista-docs SQLite for cross-artifact queries.
- [tree-sitter-m](https://github.com/rafael5/tree-sitter-m) —
  potential consumer of `mfmt` output for VSCode highlighting (not
  yet wired).

## Contributing

This is a personal hobbyist project; no formal contribution process.
The pre-commit hook enforces SAC compliance (line length ≤ 245, no
tabs, no trailing whitespace, no bare `HALT`, `@summary`/`@test` on
public tags for new files). TDD: tests before implementation.
`make test` / `make check` before committing.
