# VistA Orchestration Plan — End-to-End Modern TDD MUMPS Toolchain

**Status**: Proposed (2026-05-05)
**Tracker**: vista-meta TODO T-004
**Scope**: Cross-cutting roadmap spanning vista-meta, m-cli, m-stdlib,
m-standard, tree-sitter-m, py-kids-vc, py-kids-install, vista-cli,
vista-docs, ydbctl, and (re-seeded) m-modern-corpus + VistA-DataLoader-fork.

---

## 1. Intent

Stand up a complete, reproducible TDD development loop for MUMPS code
targeting VistA-on-YottaDB:

```
edit .m  →  format/lint  →  unit test (with fixtures + mocks)  →
KIDS components  →  reassemble  →  install into VEHU  →
integration test  →  coverage + report  →  CI gate
```

Today the language layer (parse / format / lint / test runner /
coverage / LSP) is ~80% complete in `m-cli`, KIDS round-trip is
production-grade in `py-kids-vc`, and silent install works in
`py-kids-install`. The missing pieces are **m-stdlib breadth**
(fixtures, mocks, JSON, regex, collections), **KIDS component
manifests**, an **end-to-end orchestrator**, and **CI wiring**.

This plan sequences the work so that each phase unblocks the next and
the end of every phase leaves the toolchain in a usable state.

---

## 2. Current state snapshot (2026-05-05)

| Layer | Component | State | Notes |
|---|---|---|---|
| Grammar | tree-sitter-m | v0.1 ready | 99.06% parse on 39,330 VistA routines; awaiting publish + prebuilt binaries |
| Language ref | m-standard | Mature | Reconciled AnnoStd / YottaDB / IRIS; consumed by tree-sitter-m, m-cli, m-stdlib |
| Toolchain | m-cli | Mature (Tier 1) | `fmt`, `lint` (77 rules / 7 profiles), `test`, `watch`, `coverage`, `lsp` |
| Stdlib | m-stdlib | v0.0.1 | Only STDASSERT + STDUUID shipped; 7 of 9 Phase 1 modules pending; Phase 2/3 not started |
| KIDS round-trip | py-kids-vc | Mature | 100% round-trip on 2,406 WorldVistA patches |
| KIDS install | py-kids-install | Functional | Silent install + checksum verify; no live integration test harness |
| Model | vista-meta | Mature | 5 data-model TSVs (~170k rows) + 19 code-model TSVs (~1.0M rows) + VSCode extension + pre-commit lint |
| Cross-artifact CLI | vista-cli | v0.1 mature | 24 commands; phases 1–4 done; phase 5 (semantic) deferred |
| Docs | vista-docs / vista-docs-api | Mature | 138,711 FTS5-indexed manual sections |
| Editor | tree-sitter-m-vscode | Active v0.1 | Syntax + LSP; definitions/references not wired |
| YDB control | ydbctl | Active | Env + container orchestration; light docs |
| Validation corpora | m-modern-corpus | Empty | High-leverage: validates M-MOD lint rules on non-VA code |
| Fixture loader | VistA-DataLoader-fork | Empty | Natural home for deterministic patient/site fixtures |

---

## 3. Critical gaps

### 3.1 m-stdlib gaps (ranked by TDD impact)

| Module | Phase | Purpose | TDD impact |
|---|---|---|---|
| `STDFIX` | 1 | Setup/teardown + per-test transaction isolation (`TSTART`/`TROLLBACK`) | **Hardest blocker** — without it, every test pollutes globals |
| `STDMOCK` | 1 | Call interception for tags via indirection (`@`) and per-test mock registry | Required to unit-test FileMan / MailMan / KERNEL callers |
| `STDSEED` | 1 | Declarative test data: TSV/JSON → `FILE^DIE` inside the per-test transaction | Removes "spin up a real patient" friction |
| `STDFMT`, `STDLOG`, `STDDATE`, `STDCSV`, `STDARGS`, `STDB64`, `STDHEX` | 1 | Quick-win utilities | Already specced; just unwritten |
| `STDJSON` | 2 | Encode/decode with `$ZWRITE`-style escape handling | Replaces every ad-hoc string-concat JSON in extensions |
| `STDREGEX` | 2 | `?` pattern wrapper + PCRE via `$ZF` fallback | Fills MUMPS's biggest string-tooling hole |
| `STDCOLL` | 2 | Typed collections (ordered dict, set, queue, stack) over `^TMP` with auto-cleanup | Enables data-structure-driven test assertions |
| `STDHTTP`, `STDCRYPT` | 3 | `$ZF` curl + openssl wrappers | Modern integration without RPC Broker |

### 3.2 MUMPS-side tooling missing from VistA

VistA itself doesn't ship standard equivalents for what every modern
language treats as table stakes:

- **In-VistA test runner** — XINDEX is static analysis; %INDEX is
  syntax check. Neither executes tests with assertions and isolation.
  `m test` is the right home; needs `STDFIX`+`STDMOCK` to be useful.
- **Structured logger** — KERNEL has `^XTMP` and `%ZTER` error trap,
  but no level/context/structured output. `STDLOG` fills this.
- **Config loader** — sites use `^XTV(8989.3)` Kernel parameters
  ad-hoc; `STDCONF` would normalize.
- **Routine-level dependency manifest** — vista-meta has
  `routine-calls.tsv` but no routine declares "I require ^DIC, ^DIE,
  ^XLFDT". Could be derived + checked at lint time.

### 3.3 Orchestration gaps

- No single command goes source → KIDS → install → test → report.
- No integration test harness against running VEHU.
- No CI wiring (no GitHub Actions / GitLab YAML).
- No reproducible test patient/site fixtures — `VistA-DataLoader-fork`
  is empty.
- No KIDS component manifest format — KIDS today is monolithic.

### 3.4 Empty-but-needed assets

- `m-modern-corpus` — validates M-MOD lint rules on real non-VA code
  before they gate VA work.
- `VistA-DataLoader-fork` — natural home for fixture seeding.
- `py-kids-install` integration tests against live vista-meta.

---

## 4. Phased roadmap

Phases are sequenced by dependency; ones marked "(parallel)" can run
alongside the prior phase once Phase 0 lands.

### Phase 0 — Land what's nearly done (~3 weeks)

Cheap wins that unblock everything else.

- **m-stdlib v0.0.2 → v0.1** — ship the 7 missing Phase 1 modules:
  `STDB64`, `STDHEX`, `STDFMT`, `STDLOG`, `STDDATE`, `STDCSV`,
  `STDARGS`. Prerequisites for fixtures and CI output.
- **tree-sitter-m v0.1 publish** — with prebuildify binaries so
  downstream parsers in CI containers don't need native build steps.
- **vista-meta README.md** — already in TODO.md; one afternoon.
- **Seed m-modern-corpus** — clone 5–10 non-VA M projects (FIS GT.M
  demos, MSM examples, RPMS subsets where licensable, MV1 samples).

**Exit criteria**: `m-stdlib v0.1` tagged; `tree-sitter-m` on npm/PyPI
with binaries; `m-modern-corpus` has ≥5 non-VA projects; vista-meta
README in place.

### Phase 1 — Missing TDD primitives (2–3 months)

The highest-leverage gap. `m test` runs tests; STDASSERT does
assertions; nothing else exists.

- **`STDFIX` (m-stdlib)** — fixture lifecycle:
  `SETUP^STDFIX(tag)`, `TEARDOWN^STDFIX(tag)`, transaction-wrapped
  per-test isolation using `TSTART`/`TROLLBACK` so tests don't leak
  into `^DPT`, `^DIC`, etc.
- **`STDMOCK` (m-stdlib)** — call interception for tags using
  indirection (`@`) plus a per-test mock registry. Critical for
  unit-testing routines that touch FileMan, MailMan, KERNEL.
- **`STDSEED` (m-stdlib)** — declarative test data: read TSV/JSON of
  file→record fixtures and `FILE^DIE` them inside the per-test
  transaction.
- **m-cli enhancements**:
  - `m test --junit` — JUnit XML output for CI consumers.
  - `m test --coverage-min N` — fail if line coverage < N.
  - `m test --changed` — run only tests touching modified routines
    (uses vista-meta `routine-calls.tsv` for reverse-dep closure).
- **Branch coverage in `m coverage`** — currently line-only via YDB
  TRACE; branch needs tree-sitter-m to instrument decision points.

**Exit criteria**: a sample VistA package can have its routines
unit-tested with fixtures, mocks, and isolation; coverage gate
enforced; JUnit out.

### Phase 2 — KIDS as components (1–2 months)

The user's explicit ask: build KIDS in pieces, reassemble, install,
test.

- **Component manifest schema** — `kids-component.toml` per
  component declaring: routines, FileMan files (with selective field
  sets), RPCs, options, protocols, install/post-install hooks,
  dependencies on other components. Validates against vista-meta TSVs
  so unknown identifiers fail fast.

  Sketch:
  ```toml
  [component]
  name = "MYPKG-CORE"
  version = "0.1.0"
  depends = ["KERNEL>=8.0", "FILEMAN>=22.2"]

  [routines]
  include = ["MYPKG*"]
  exclude = ["MYPKGTST*"]

  [files]
  "12345" = { fields = "all" }
  "12346.1" = { fields = [".01", "1", "2"] }

  [rpcs]
  include = ["MYPKG GET RECORD", "MYPKG LIST"]

  [hooks]
  pre_install  = "PRE^MYPKGINS"
  post_install = "POST^MYPKGINS"
  ```

- **`py-kids-vc kids component build <manifest>`** — emit a
  per-component `.KID` from source tree + manifest. Reuses existing
  decompose/assemble in reverse with a filter.
- **`py-kids-vc kids assemble <manifests...>`** — concatenate +
  topo-sort components into one master `.KID`, dedup
  environment-check / pre-install / post-install routines, validate
  that no two components own the same routine, surface dependency
  cycles.
- **Round-trip gate** — assemble → install → checksum-verify →
  re-decompose → diff against source must be empty. Extend the
  existing 2,406-patch corpus to gate this.

**Exit criteria**: a multi-component package can be built, assembled,
installed, and round-trip-verified; component ownership conflicts
fail the build.

### Phase 3 — End-to-end orchestrator (~1 month)

Tie the chain together. Probably lives in `vista-cli` (it already
joins vista-meta + vista-docs) under a new `build` namespace, or as
a sibling `vista-build`.

```
vista-cli build      # m fmt-check → m lint → m test (unit) per component
vista-cli package    # py-kids-vc assemble → smoke .KID
vista-cli install    # py-kids-install into running VEHU container
vista-cli verify     # routine checksums + RPC smoke + integration M tests
vista-cli ci         # all of the above, JUnit + lcov out
```

Driven by `vista-project.toml` at the repo root listing components.
Each step is independently invokable so devs can iterate fast (skip
install when only changing a unit test).

**Exit criteria**: `vista-cli ci` is green on a sample multi-component
project; each subcommand has its own exit code and structured output.

### Phase 4 — Integration test framework (~3–4 weeks)

Unit tests run in-process; integration tests need a live VistA. Right
now there's no harness.

- **`m test --integration`** — runs after `vista-cli install` against
  the live container.
- **RPC smoke harness** — drives RPCs via VistALink / RPC Broker from
  Python, asserts on results. Lives in `py-kids-install` (it already
  has a verification skeleton).
- **Reproducible patient/site fixtures** — extend the empty
  `VistA-DataLoader-fork` or build a lightweight loader that seeds
  known patients/users/locations into a fresh VEHU volume snapshot,
  so integration tests are deterministic.
- **Snapshot/restore** — YDB `mupip backup`/`restore` of the globals
  volume between integration runs (faster than rebuilding VEHU).

**Exit criteria**: `vista-cli verify` runs RPC smokes + M-side
integration tests against a freshly installed package on a known
fixture site.

### Phase 5 — CI wiring (~2 weeks)

- **GitHub Actions reusable workflow** — `vista-meta/ci-action@v1`:
  pulls VEHU image, runs `vista-cli ci`, uploads JUnit + lcov,
  comments coverage delta on PRs.
- **vista-meta pre-commit hook** — already SAC-compliant; add
  `m test --changed` and `m fmt --check`.
- **Cache strategy** — VEHU image (~2 GB) in registry; globals volume
  snapshot per-PR keyed on KIDS hash.

**Exit criteria**: a PR to a sample VistA package gets automated
lint + unit + integration runs with comment-back of coverage delta.

### Phase 6 — m-stdlib Phase 2 (parallel; 2–3 months)

Once Phase 1 modules are in production, the long-tail wins.

- **`STDJSON`** — encode/decode with `$ZWRITE`-style escape handling.
- **`STDREGEX`** — `?` pattern match wrapper + PCRE via `$ZF` for
  what `?` can't do.
- **`STDCOLL`** — typed collections (ordered dict, set, queue, stack)
  over `^TMP` with auto-cleanup.
- **`STDHTTP`** — `$ZF` curl wrapper. Modern integration without
  RPC Broker.
- **`STDCRYPT`** — `$ZF` openssl wrapper for password hashing,
  JWT signing, etc.

**Exit criteria**: m-stdlib v0.2 covers JSON / regex / collections /
HTTP / crypto; consumed by at least one downstream extension.

### Phase 7 — Editor + dev-loop polish (parallel)

- **VSCode extension**: code-lens "▶ Run test" on `tXxx` labels;
  "📦 Show in KIDS" on routines belonging to a component;
  hot-reload on save (write into VEHU bind-mount, invalidate routine
  cache).
- **m-cli LSP**: complete go-to-definition / find-references using
  vista-meta `routine-calls.tsv` as the index (instant; no parse
  needed at query time).
- **DAP debugger** (m-cli Tier 2 #10) — deferred but high-value once
  the rest is stable.

### Phase 8 — Quality gates (later)

- **Mutation testing** (`m mutate`) — flip operators / conditionals,
  re-run `m test`, report kill rate.
- **Performance profiling** (`m prof`) — YDB TRACE with flame-graph
  output.
- **Data-flow taint** (M-MOD-036 phase 9 in m-cli) — SAST for
  SQLi-equivalent (DI / DIE injection), unsafe `XECUTE`.

---

## 5. Cross-cutting concerns

### 5.1 No M package manager

m-stdlib is consumed via git submodule today. A registry / versioning
/ dependency-resolution layer is **out of scope** for this plan —
submodules suffice until at least three independent extensions
consume m-stdlib.

### 5.2 Reproducibility

Every phase must keep `make build` (vista-meta) deterministic. New
components added to the bake (e.g. STDFIX install during build)
require an ADR.

### 5.3 Documentation cadence

Each phase ships with:
- Updated `docs/vista-meta-guide.md` cross-refs.
- New per-feature guide in `docs/` (e.g. `docs/m-tdd-guide.md`).
- Skill update in `~/claude/skills/m-unit-testing/SKILL.md` once
  STDFIX/STDMOCK/STDSEED ship.

### 5.4 Versioning

- m-stdlib follows semver; pin via submodule SHA in vista-meta.
- vista-cli tags `vN.N.N` per phase exit.
- KIDS component manifests carry their own `version` field independent
  of containing package.

---

## 6. Suggested execution order

```
Phase 0 (3w) ──► Phase 1 (10w) ──┐
                                  ├──► Phase 3 (4w) ──► Phase 4 (4w) ──► Phase 5 (2w)
                 Phase 2 (8w)  ──┘
                 Phase 6 (parallel from Phase 1 exit)
                 Phase 7 (parallel from Phase 3 exit)
                 Phase 8 (after Phase 5)
```

Working end-to-end TDD loop: **~5–6 months** to Phase 5 exit.
Phase 6+ is continuous improvement after.

---

## 7. Per-repo deliverable map

| Repo | Phase 0 | Phase 1 | Phase 2 | Phase 3 | Phase 4 | Phase 5 | Phase 6 | Phase 7 |
|---|---|---|---|---|---|---|---|---|
| m-stdlib | v0.1 ship | STDFIX/STDMOCK/STDSEED | — | — | — | — | STDJSON/STDREGEX/STDCOLL/STDHTTP/STDCRYPT | — |
| tree-sitter-m | v0.1 publish | branch points | — | — | — | — | — | — |
| m-cli | — | --junit / --coverage-min / --changed; branch coverage | — | — | --integration | pre-commit additions | — | LSP defs/refs; mutate/prof |
| py-kids-vc | — | — | component build/assemble; round-trip gate | — | — | — | — | — |
| py-kids-install | — | — | — | — | RPC smoke harness | — | — | — |
| vista-cli | — | — | — | build/package/install/verify/ci | — | — | — | — |
| vista-meta | README | — | — | vista-project.toml example | snapshot/restore tooling | CI action | — | — |
| VistA-DataLoader-fork | — | — | — | — | fixture loader | — | — | — |
| m-modern-corpus | seed | — | — | — | — | — | — | — |
| tree-sitter-m-vscode | — | — | — | — | — | — | — | code-lens; hot-reload |

---

## 8. Open questions

- **Scope of `vista-cli build`** — does it own component-level
  testing (each component runs its own `m test` set) or does it
  delegate entirely to `m test --component`? Decide at Phase 3 entry.
- **Fixture format** — TSV is simplest; JSON is richer; YAML is
  human-friendliest. Decide at Phase 1 entry when designing STDSEED.
- **Mock semantics** — full call interception (replace `D ^FOO` with
  a stub) requires indirection rewrites at parse time, which means
  STDMOCK is parser-aware. Alternative: tag-level wrappers the test
  must opt into. Decide at Phase 1 entry.
- **Snapshot granularity** — per-test rollback (TSTART) vs per-suite
  volume snapshot (mupip). Probably both, at different layers.
- **Whether Phase 8 mutation testing is worth it** — only valuable
  if Phase 1–5 yields a corpus of high-quality tests to mutate.
  Re-evaluate at Phase 5 exit.

---

## 9. Cross-references

- `docs/vista-meta-guide.md` — comprehensive vista-meta map.
- `docs/vista-cli-planning.md` — vista-cli design predating this plan;
  `vista-cli build/package/install/verify/ci` extends that surface.
- `docs/vista-meta-spec-v0.4.md` — authoritative technical spec for
  the model layer.
- `~/projects/m-stdlib/README.md` — Phase 1/2/3 module roadmap.
- `~/projects/m-stdlib/docs/tdd-orchestration-plan.md` — m-stdlib ↔ m-cli joint milestones; carves the m-stdlib slice out of this plan and sequences m-cli runner protocol changes alongside STDFIX/STDMOCK/STDSEED. Owns the Phase 1 TDD-primitives detail; m-stdlib drives it.
- `~/projects/m-cli/` Tier 1 / Tier 2 plans — current m-cli status.
- `~/claude/skills/m-unit-testing/SKILL.md` — current testing
  conventions; will gain STDFIX/STDMOCK/STDSEED sections at Phase 1
  exit.
