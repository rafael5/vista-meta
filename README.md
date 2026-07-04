# vista-meta

[![ci](https://github.com/rafael5/vista-meta/actions/workflows/ci.yml/badge.svg)](https://github.com/rafael5/vista-meta/actions/workflows/ci.yml)

A deterministic, machine-readable model of **VistA** — the VA's electronic
health record system — covering both the data it stores and the code that
manipulates it, plus the operational tooling built on top: the **VistA
Compass** VSCode extension, a CLI, an M formatter, and a lint hook.

## New here? Two ways in

| You want to… | Path | Needs |
|---|---|---|
| **Use the models** — query 8,261 classified FileMan files and ~1M rows of code intelligence | [§ Use the models](#use-the-models-no-build) below — the finished TSVs are in the clone | Python ≥ 3.10, nothing else |
| **Reproduce everything** — build the VistA container from pinned sources and re-extract the models yourself | [docs/guides/DE-NOVO.md](docs/guides/DE-NOVO.md) — the ordered clean-clone runbook | Linux, Docker, ~25 GB disk, ~30 min |

The narrative map of the whole project (scope, thesis, methodology, every
artifact) is [docs/guides/vista-meta-guide.md](docs/guides/vista-meta-guide.md)
— **start there** when you want to understand rather than run.

## The thesis

You cannot model VistA's data without modeling its code, and you cannot model
its code without modeling its data — they are the same artifact viewed from
two sides. vista-meta extracts, reduces, and interlinks both in the same
deterministic artifact set.

## What ships

| | Artifact | Produces |
|---|---|---|
| **A. Data model** | `vista/export/data-model/` (4 TSVs) | PIKS classification of every FileMan file (100% coverage: auto + triage + subfile inheritance); field-level annotations; cross-PIKS pointer matrix |
| **B. Code model** | `vista/export/code-model/` (20 TSVs, ~1.0M rows) | Per-routine intelligence: calls, callers, globals, RPCs, options, protocols, XINDEX findings, package topology |
| **1. VistA Compass** | `vscode-extension/` | VSCode sidebar + hovers: tags, callers, callees, globals→PIKS joins — pure TSV reads, no runtime dependency |
| **2. CLI + hook + formatter** | `bin/vista-meta`, `bin/mfmt`, `hooks/pre-commit` | doctor, pkg, context, where, callers, search, file, new-test, lint, xindex; SAC-compliant pre-commit gate |
| **3. Data release** | [`data-v1`](https://github.com/rafael5/vista-meta/releases/tag/data-v1) | The models as a verifiable public bundle (`schema_version: 1`, per-file sha256, content hash) — mutually pinned with the [vdocs](https://github.com/rafael5/vdocs) corpus release |

## Use the models (no build)

Everything is in the clone; the CLI is stdlib-only Python:

```bash
git clone https://github.com/rafael5/vista-meta.git && cd vista-meta
bin/vista-meta doctor              # environment health check
bin/vista-meta pkg "Pharmacy"      # package overview
bin/vista-meta context PSO         # AI context pack for a package
bin/vista-meta callers PSOVCC      # caller graph
```

Data shapes are the frozen `schema_version: 1` contract
([docs/reference/schema-v1-normalization-spec.md](docs/reference/schema-v1-normalization-spec.md));
per-TSV schema in [docs/guides/code-model-guide.md](docs/guides/code-model-guide.md);
classification queries in [docs/guides/piks-analysis-guide.md](docs/guides/piks-analysis-guide.md).
The Compass extension builds with `cd vscode-extension && npm ci && npm run compile`
and auto-discovers `vista/export/` as its data root.

## Build the engine (full reproduction)

The complete path — prerequisites, `.env`, pinned build, first bake,
verification gates, failure modes — is **[docs/guides/DE-NOVO.md](docs/guides/DE-NOVO.md)**.
The short version:

```bash
cp .env.example .env   # defaults bind 127.0.0.1 only (ADR-050)
make build             # ~20 min; every upstream fetch is commit-SHA pinned
make run               # container up; first run kicks a background bake
make wait-for-bake     # progress dots until the bake sentinel flips
make smoke             # S-01…S-12 — expect 10 PASS / 0 FAIL / 2 WARN
```

`make help` lists every target. Requirements: Linux host (macOS untested,
Windows excluded), Docker, ~25 GB free. MUMPS engine is **YottaDB-only** —
the bake uses `mupip`, `$ZRO`, and ydb-specific GDE syntax.

## Verify what you got

```bash
make check             # host-side gate: 13 unit suites + docs link/citation gate
make smoke             # container gate: engine, data plane, RPC broker (real XWB), data
```

Every released byte is hash-covered by
[docs/releases/data-v1.manifest.json](docs/releases/data-v1.manifest.json);
the pin ledger for every build input is
[docs/guides/dependencies.md](docs/guides/dependencies.md).

## Where code runs

Code is **edited on the host**, **executed in the container**.

| Location | Runs on | Contents |
|---|---|---|
| `docker/` | host (build context) | Dockerfile (SHA-pinned fetches), entrypoint, xinetd/sshd configs |
| `vista/dev-r/` | container (bind mount) | Your M routines — shadow VEHU via `$ZRO` |
| `vista/scripts/` | container (bind mount) | In-container analysis scripts |
| `vista/export/` | container (bind mount) | The models, bake logs, sentinel, RESEARCH.md |
| `vista/vista-m-host/` | host snapshot (untracked) | Host-visible copy of the VistA-M source tree, synced from the container |
| `host/scripts/` | host | All host-side Python (CLI, model builders, mfmt, gates) |
| `host/vendor/` | host | Vendored build inputs (WorldVistA `Packages.csv`) |
| `bin/`, `hooks/` | host | CLI entry points, pre-commit hook |
| `vscode-extension/` | host | VistA Compass source + packaged `.vsix` |
| `tests/smoke/` | host (against container) | The post-build smoke suite |

## Documentation

`docs/` is organized by **lifecycle, not topic** — the filing rules and a
dated current-state snapshot live in **[docs/README.md](docs/README.md)**.

| Folder | What lives there | Start with |
|---|---|---|
| [docs/guides/](docs/guides/) | Current operational docs, kept in step with the code | [vista-meta-guide.md](docs/guides/vista-meta-guide.md) (the map) · [DE-NOVO.md](docs/guides/DE-NOVO.md) (reproduce) · [vista-developers-guide.md](docs/guides/vista-developers-guide.md) (VistA onramp for Python/JS/Go devs) · situational-awareness playbooks ([routine](docs/guides/routine-situational-awareness.md) / [package](docs/guides/package-situational-awareness.md)) · [vista-vscode-guide.md](docs/guides/vista-vscode-guide.md) (every tool) · [vista-meta-restore.md](docs/guides/vista-meta-restore.md) (snapshot/restore runbook) |
| [docs/reference/](docs/reference/) | Durable contracts & lookups, path-stable (cited from code) | [schema-v1-normalization-spec.md](docs/reference/schema-v1-normalization-spec.md) (the shipped data contract) · [model-extraction-contract.md](docs/reference/model-extraction-contract.md) (extraction/PIKS spec) · [xindex-reference.md](docs/reference/xindex-reference.md) (XINDEX catalog) |
| [docs/adr/](docs/adr/) | 51 immutable decision records + [index with reality column](docs/adr/000-index.md) | why each choice was made |
| [docs/releases/](docs/releases/) | Release manifests — what consumers verify downloads against | [data-v1.manifest.json](docs/releases/data-v1.manifest.json) |
| [docs/historical/](docs/historical/) | Executed plans, the as-built v0.4 spec, closed workstreams | read for the *why*, never execute |
| [docs/build-log.md](docs/build-log.md) | BL-001…BL-015 — every build/runtime failure hit, with cause and fix | when something breaks |

Research findings (RF-001…RF-034) live with the data:
[vista/export/RESEARCH.md](vista/export/RESEARCH.md).

## PIKS — the data-model first-pass abstraction

Every FileMan file and non-FM global is classified into **P**atient /
**I**nstitution / **K**nowledge / **S**ystem, with four orthogonal properties
(volatility, sensitivity, portability, volume), by 52 DD-based heuristics +
6 non-FM heuristics. Coverage: 100% of 8,261 files (7,904 automatic,
220 triaged, 137 subfile-inherited). Details:
[docs/guides/piks-analysis-guide.md](docs/guides/piks-analysis-guide.md).

## License

[MIT](LICENSE). The VistA-M source (synced into `vista/vista-m-host/`, baked
into the image from [WorldVistA/VistA-VEHU-M](https://github.com/WorldVistA/VistA-VEHU-M))
follows its upstream public-domain status.

## Companion projects

- [v-pkg](https://github.com/vista-forge/v-pkg) — modern KIDS package
  management (decompose / assemble / round-trip / install / verify /
  back-out); `make patch-*` shells out to it.
- [vdocs](https://github.com/rafael5/vdocs) — the VA documentation corpus
  whose `data-v1` release and this repo's release pin each other
  ([docs/releases/data-v1-peers.json](docs/releases/data-v1-peers.json)).
- [tree-sitter-m](https://github.com/rafael5/tree-sitter-m) — M grammar
  powering the `rafael5.tree-sitter-m-vscode` extension.

## Contributing

Personal hobbyist project; no formal process. Gates: `make check`
(host-side: unit suites + docs link/citation gate) and `make smoke`
(container) — CI runs the host-side half on every push. The pre-commit hook
enforces SAC compliance for M code (line length ≤ 245, no tabs, no trailing
whitespace, no bare `HALT`, doc comments on public tags). TDD: tests before
implementation.
