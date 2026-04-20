# Code-Model Guide

How the `vista/export/code-model/` artifacts fit together, what framework
they describe, and how VistA's code actually gets developed, tested,
installed, uninstalled, and tracked. Plus a direct comparison against
contemporary full-stack development practice and a list of what VistA
is missing.

Written 2026-04-19 after ADR-045 + Phase 7 (XINDEX run + validation).
Companion to [xindex-reference.md](xindex-reference.md), which covers
the XINDEX tool specifically.

---

## 1. What's in `code-model/`

19 TSV files organized in six logical layers. Each layer builds on the
ones above it.

### 1.1 Inventory layer — "what exists"

| File | Rows | Columns | Contents |
|---|---|---|---|
| `routines.tsv` | 39,330 | 10 | Every `.m` routine in `Packages/*/Routines/`: name, package, source_path, line_count, byte_size, first_line_comment, version_line, tag_count, comment_line_count, is_percent_routine |
| `packages.tsv` | 174 | 5 | Per-package aggregates: routine_count, percent_routine_count, total_lines, total_bytes |

Source: host-side Python extraction against the docker-cp'd `vista/vista-m-host/` snapshot of the VEHU image. Authority for *what ships* in the FOIA distribution.

### 1.2 Authoritative metadata layer — "what VistA itself knows"

Extracted from four FileMan files via MUMPS `VMDUMP*.m` routines.

| File | Source | Rows | Columns | Contents |
|---|---|---|---|---|
| `vista-file-9-8.tsv` | File 9.8 (ROUTINE) | 30,665 | 6 | Kernel's routine registry — name, type, size, rsum, checksum |
| `rpcs.tsv` | File 8994 (REMOTE PROCEDURE) | 4,501 | 8 | RPC Broker registry — name, tag, routine, return_type, availability, inactive, version |
| `options.tsv` | File 19 (OPTION) | 13,163 | 8 | Menu options — name, menu_text, type (R/M/A/B/...), package, routine_raw, tag, routine |
| `protocols.tsv` | File 101 (PROTOCOL) | 6,556 | 7 | Order Entry protocols — name, item_text, type (A/M/E/S/L/...), package, entry_action, exit_action |

These four are the *authoritative role signals* for routines. A routine listed in `rpcs.tsv.routine` IS an RPC entry point. A routine listed in `options.tsv.routine` with `type=R` IS a menu-invokable action. No heuristic interpretation needed.

### 1.3 Relationships layer — "how things connect"

Regex-based extraction from `.m` source and FileMan-stored MUMPS text.

| File | Rows | Columns | Contents |
|---|---|---|---|
| `routine-calls.tsv` | 241,309 | 6 | Routine → routine edges (DO/GOTO/JOB/$$): caller_name, caller_package, callee_tag, callee_routine, kind, ref_count |
| `routine-globals.tsv` | 77,838 | 4 | Routine → subscripted-global edges: routine_name, package, global_name, ref_count |
| `protocol-calls.tsv` | 5,081 | 7 | Protocol ENTRY/EXIT ACTION → routine invocations |

These are approximate (regex, not parsed MUMPS) but broad-coverage — they include routines that XINDEX can't process (the T-002 cohort of ~10,000 routines not in `$ydb_routines` paths).

### 1.4 Code-quality layer — "how the code behaves"

From XINDEX, VistA's own static analyzer (Toolkit XT*7.3*158, VEHU blend per RF-027). See [xindex-reference.md](xindex-reference.md) for the full catalog.

| File | Rows | Columns | Contents |
|---|---|---|---|
| `xindex-routines.tsv` | 29,098 | 6 | Per-routine: line_count, tag_count, xref_count, error_count, rsum_value |
| `xindex-errors.tsv` | 6,918 | 5 | One row per error instance across 66 error classes (F/S/W/I severity) |
| `xindex-xrefs.tsv` | 214,011 | 3 | Authoritative call graph (MUMPS parser, not regex) |
| `xindex-tags.tsv` | 292,148 | 3 | Tag/label inventory with Supported Entry Point classification |
| `xindex-validation.tsv` | 29,098 | 14 | Per-routine join of regex vs XINDEX — line/tag/callee agreement |

XINDEX is the ground-truth reference. Our regex extractions validated at 100% for static features and 98.75% for call graph.

### 1.5 Data-side integration — "what data each package ships"

| File | Rows | Columns | Contents |
|---|---|---|---|
| `package-data.tsv` | 3,138 | 7 | ZWR exports under `Packages/*/Globals/`: package, kind (file/global), file_number, chunk, entity_name, source_path, byte_size |
| `package-piks-summary.tsv` | 120 | 7 | Per-package PIKS distribution of shipped files (joins against `data-model/piks.tsv`) |

This is the code↔data bridge at the package level (ADR-045 Phase 2c/2d).

### 1.6 Unified views — "joined intelligence"

| File | Rows | Columns | Contents |
|---|---|---|---|
| `routines-comprehensive.tsv` | 39,330 | 20 | Per-routine join of all prior layers: identity + static features + role signals + call graph + globals |
| `package-manifest.tsv` | 175 | 13 | Per-package join: counts, shipped-data PIKS, role counts, edge counts, cross-package coupling |
| `package-edge-matrix.tsv` | 1,872 | 5 | Sparse (source_package, dest_package) matrix of call edges |

These are the **primary analytical artifacts**. Everything else feeds these. Answering questions like "which routines are RPCs in Lab Service that touch patient data" is a direct query over these three files.

---

## 2. How the framework works — VistA's code model

### 2.1 The basic units

VistA is built from four kinds of things:

- **Routines** — MUMPS `.m` source files. Each is one file, typically 50–500 lines, containing multiple tags (entry points). File-system-named; globally callable by name.
- **Tags** (a.k.a. labels) — named entry points *inside* a routine. Tag `GET` in routine `DIQ` is referenced as `GET^DIQ`. A routine with 20 tags has 20 possible entry points.
- **Globals** — persistent data storage. Named like `^DPT`, `^DIC(9.8,...)`, `^%ZOSF`. MUMPS treats globals as a hierarchical tree — `^DPT(1,0)` is a specific node under patient 1. Globals are the database layer; there's no separate DB server.
- **Packages** — logical groupings. Each package owns a namespace prefix (e.g., `PS*` for Pharmacy, `SD*` for Scheduling), ships a set of routines in `Packages/<Name>/Routines/*.m`, and ships data globals in `Packages/<Name>/Globals/*.zwr`.

The *physical* layout of a VistA installation: one flat namespace of routines, one hierarchical namespace of globals. No filesystem isolation at runtime. YDB's `$ZRO` environment variable controls where it finds routine source (a search path).

### 2.2 Entry points — how code gets invoked

Code execution starts at one of five surfaces:

1. **Menu options** (File 19) — user picks an option from a terminal-based menu; `type=R` options specify a routine to invoke. The TaskMan subsystem is driven entirely through File 19.
2. **Protocols** (File 101) — used by Order Entry, HL7, and CPRS. Triggered by events (patient admission, new order, lab result). ENTRY ACTION is MUMPS text that runs when the protocol fires. Subscribe/publish pattern.
3. **RPC Broker** (File 8994) — Delphi/Windows clients (notably CPRS) call routines remotely via `TAG^ROUTINE` references. The RPC Broker is the authoritative CPRS-facing surface.
4. **Direct invocation** (`DO ^ROUTINE`) — routines calling other routines via `DO`, `GOTO`, `JOB`, or `$$FUNC^ROU(args)`. This is the internal fabric.
5. **FileMan DD-embedded MUMPS** — input transforms, cross-references, computed fields, triggers. Executed by FileMan whenever data is added/modified.

Our code-model surfaces the first four directly: `options.tsv`, `protocols.tsv`, `rpcs.tsv`, `routine-calls.tsv`. The fifth (DD-embedded) is T-003 — unextracted and the main source of the "truly unreferenced" routine cohort.

### 2.3 The event fabric

File 101 protocols support **event-driven** integration: a package defines an **event driver** (`TYPE=E`) that fires on a business event; other packages register **subscribers** (`TYPE=S`) that react. Our `protocols.tsv` has 321 event drivers and 363 subscribers — 684 pub/sub pairs forming VistA's internal integration backbone (HL7, CPRS context, lab result flow).

### 2.4 The KIDS installer

**KIDS** (Kernel Installation and Distribution System) is VistA's package manager + release pipeline rolled into one. It ships "builds" — bundles of:
- Routines (source `.m` files)
- FileMan file DDs and seed data (ZWR globals)
- Options, Protocols, RPCs (entries in Files 19/101/8994)
- Pre-install routines (run before data load)
- Post-install routines (run after data load)
- Environment check routines (run first, can block install)
- Data-dictionary changes with version checking

A KIDS build is distributed as a `.KID` file (a text dump). Install workflow:
1. `D ^XPDNTEG` — load distribution, parse `.KID` into Kernel scratch
2. Run environment check (can refuse install)
3. Run pre-install
4. Load routines (replace existing)
5. Install FileMan files (with DD merge + data load)
6. Install options/protocols/RPCs
7. Run post-install
8. Update patch history (append to `;;` line in each touched routine)

Every touched routine has its patch list appended: `;;7.3;KERNEL;**20,27,48,...,156**;...`. This is the *only* form of version tracking at the routine level.

### 2.5 How our artifacts reflect the framework

Mapping the 19 code-model files back to VistA's framework:

| VistA concept | Primary artifact | Secondary |
|---|---|---|
| Routines | `routines.tsv` | `xindex-routines.tsv`, `vista-file-9-8.tsv` |
| Tags | `xindex-tags.tsv` | `routines.tsv.tag_count` |
| Packages | `packages.tsv` | `package-manifest.tsv` |
| Globals | `routine-globals.tsv` | (T-001: bare-global detection) |
| Menu options | `options.tsv` | `routines-comprehensive.tsv.option_count` |
| Protocols | `protocols.tsv` | `protocol-calls.tsv`, `routines-comprehensive.tsv.protocol_invoked_count` |
| RPCs | `rpcs.tsv` | `routines-comprehensive.tsv.rpc_count` |
| Call graph (internal) | `routine-calls.tsv` | `xindex-xrefs.tsv` (authoritative) |
| Event fabric | `protocols.tsv` (filtered TYPE=E/S) | — |
| Patch history | `routines.tsv.version_line` | `xindex-routines.tsv.rsum_value` |
| ZWR shipments | `package-data.tsv` | `package-piks-summary.tsv` |
| Code quality | `xindex-errors.tsv` | — |
| Package coupling | `package-edge-matrix.tsv` | `package-manifest.tsv.outbound_cross_pkg` |

**What's missing** from our code-model vs full framework coverage:
- DD-embedded MUMPS (cross-refs, computed fields, input transforms) — not extracted
- KIDS build manifests — not extracted
- Install-time dispatch via XECUTE'd strings — not traceable statically
- File 1 (FILE OF FILES) for file-level ownership metadata — not dumped
- File 3.5 (DEVICE), File 20 (TASK), etc. — not dumped (not code per se, but routines reference them)

These are the T-001/T-002/T-003 TODOs.

---

## 3. Code development lifecycle in VistA

### 3.1 Develop

**Traditional VA model** (1980s–2010s):
- Developer edits routines directly on a running VistA instance via a terminal-based MUMPS editor (ZED, JED, or the `%ZEDIT` utility).
- Edits are **live** — the routine is saved directly into the `^ROUTINE` global (Caché) or `/opt/VistA-M/r/*.m` file (YottaDB). The next caller picks up the new version immediately.
- Source lives in the database, not a filesystem-based source tree. (YDB fixes this — `.m` files live on disk.)
- Comments and first-line headers encode author: `ROUTINE ;SITE/DEV - description ;date`.

**Modern practice** (2015+, OSEHRA/WorldVistA):
- Git-based development against a forked VistA source tree.
- WorldVistA, OSEHRA, and Open Source EHR Alliance maintain GitHub repositories (github.com/OSEHRA, github.com/WorldVistA).
- Developer edits `.m` files in a normal editor (VSCode with MUMPS extensions, EmEditor, vim).
- Commits go to a branch; PR merged to master; releases tagged.
- Install into a running system still uses KIDS — the git repo is source-of-truth, the KIDS build is the deployment artifact.

The VA's internal development still uses the traditional model; the community model is overlaid on top. Our VEHU XINDEX blend (RF-027) shows this: VA-trunk patches 148–158 coexist with WorldVistA patches 10001/10003 in the same routines.

### 3.2 Test

**Static analysis**: XINDEX (Toolkit). 66 error classes across four severity levels. Run manually or as part of a patch release checklist. Not integrated into a commit hook or CI gate.

**Unit testing**: M-Unit (xt-MUnit). ChristopherEdwards fork at github.com/ChristopherEdwards/M-Unit is the most actively maintained. Writes test-XXXX routines that follow a naming convention; runs them via a test harness. **Adoption is sparse** — most VistA packages have minimal or no unit tests.

**Integration testing**: usually manual, terminal-menu-driven. A tester walks through workflows on a test system. VistA's "test accounts" are full parallel installations.

**Acceptance testing**: patch-by-patch. Each VA patch goes through a test cycle before release. Documentation of test plans lives in VA-internal change-request systems.

**No coverage measurement.** No test framework produces coverage reports that integrate with the build.

### 3.3 Install

**Distribution**:
- VA internally: `.KID` files distributed through FORUM (VistA's mail system) to field sites via the Anonymous Software Directory.
- Community: GitHub releases + manual KIDS `.KID` download.

**Install workflow** (interactive through Kernel menus):
1. Site's system manager (IRM) loads `.KID` via `D ^XPDNTEG` or menu option `Load a Distribution`.
2. KIDS parses the `.KID` into the Kernel scratch area.
3. Environment check routine (EC) runs — can refuse install if prerequisites missing.
4. IRM answers install prompts (test mode? queue for off-hours?).
5. Pre-install, routine update, FileMan file update, option/protocol update, post-install run in sequence.
6. Each modified routine has its patch list extended (`**20,27,48**` → `**20,27,48,<new-patch>**`).
7. `INSTALL` file records the install event.

**Typical install time**: minutes to hours depending on data load size.

### 3.4 Uninstall

**There is no uninstall.** VistA has no rollback mechanism. Once a patch is installed:

- Routines are overwritten (previous version gone).
- FileMan DD changes are merged (previous schema gone).
- Options/protocols/RPCs are added or modified (previous version gone unless explicitly marked "Deleted by Patch" via field 6.2).

**The documented workaround**: restore from backup. Before an install, the IRM is expected to take a full backup of the globals volume. If the patch fails or regresses, restore the backup.

**"Delete by patch"** (Files 19/101/8994/9.8 field 6.2) lets a patch *mark* a previously-installed patch's items as deleted — but this is a **forward-delete**, not an undo. The deletion is itself a patch.

**Consequence**: production VistA systems are forward-only. No atomic rollback. Every patch needs to be right the first time.

### 3.5 Track changes

**At routine level**:
- `;;` line 2: `;;VERSION;PACKAGE;**patch1,patch2,...**;BUILD_DATE;...`. This is the patch list — a flat list of integer patch numbers.
- File 9.8 fields: `1.5 RSUM VALUE` (computed checksum), `1.6 RSUM DATE`, `7.2 CHECKSUM VALUE`, `7.3 PATCH LIST AT CHECKSUM TIME`, `1.4 DATE OF %INDEX RUN`, `6.1 LOCALLY MODIFIED`, `6.2 DELETED BY PATCH`.
- XINDEX updates these when run with `INP(7)=Y` (save to File 9.8).

**At FileMan file level**:
- DD has a `VERSION NUMBER` field per DD entry.
- No per-field change history.

**At install level**:
- File 9.7 (INSTALL) records each installed KIDS build with its components.
- Field `7.4 KIDS INSTALL DATE` on File 9.8 per-routine.

**What's missing from this tracking**:
- **No atomic commit** — you can't group a set of related changes as a unit with a single identifier. A patch is the closest analog but is heavyweight (a full KIDS build).
- **No diff** — given two versions of a routine, you can't ask "show me what changed between patch 27 and patch 48." You see the *list* of patches but not their individual content.
- **No branch/merge** — the patch list is linear. If two patches touch the same routine in parallel development, the second one to install wins silently.
- **No blame** — no record of who changed what line.
- **No rollback** — see §3.4.

The modern OSEHRA/WorldVistA git overlay adds all of this on top, but VA trunk doesn't use it.

### 3.6 Observability in operation

**Logs**: `^ERROR`, `^XTMP("XUS..."`, `^XTV(8989.3)` (sign-on logs). Not structured. Not shipped off-box. No standard log format.

**Metrics**: none built in. VistA has no Prometheus exporter, no OpenTelemetry, no StatsD. System managers infer load from user counts and response times.

**Tracing**: `ZBREAK` for interactive debugging; `$ZTRAP` for error trap handlers. No distributed tracing across routines.

**Alerting**: MailMan-based. When something goes wrong, a routine sends a bulletin to a pre-configured user group. Users read alerts in their MailMan inbox.

---

## 4. Comparison — VistA vs contemporary full-stack

### 4.1 Side-by-side matrix

| Dimension | VistA / KIDS | Contemporary full-stack |
|---|---|---|
| **Source control** | Patch list (`;;**20,27,48**`) — flat linear accumulation. No DAG, no merge semantics. Community overlays use git. | Git with commit DAG, branches, merges, tags, blame, bisect. Central source-of-truth. |
| **Atomic change unit** | KIDS patch — coarse-grained, weeks of development bundled. | Git commit — fine-grained, can be a single-line fix. |
| **Versioning scheme** | Patch number (integer, per-routine). Package version (`7.3`) is separate. | Semantic versioning (MAJOR.MINOR.PATCH) with clear compatibility contracts. |
| **Dependency declaration** | Implicit. KIDS build's environment check (EC) routine manually probes for prerequisites. | Explicit manifests: `package.json`, `requirements.txt`, `Cargo.toml`, `pom.xml`. Machine-resolvable. |
| **Package manager** | KIDS — monolithic, interactive, VA-controlled registry. | npm, pip, cargo, maven — distributed registries, automated transitive resolution. |
| **Build system** | KIDS (packaging) + M compiler (YDB/Caché transparently). No separate build step for developers. | Make/Gradle/Webpack/etc. — explicit build graph with caching, incremental builds, cross-compilation. |
| **Artifact registry** | Anonymous FTP + FORUM (VA-internal). GitHub releases (community). | Central registries (npm, PyPI, Docker Hub, Maven Central) with search, deprecation, signing. |
| **CI/CD** | None in VA trunk. OSEHRA has some GitHub Actions. Patches go through VA-internal manual QA. | GitHub Actions / GitLab CI / Jenkins — automated on every commit. Merge gates on CI green. |
| **Code review** | Informal peer review within VA development teams; no tooling. | PR workflow (GitHub/GitLab) with required reviewers, inline comments, approval rules. |
| **Testing framework** | M-Unit (sparse adoption); manual menu-walking; test accounts. | pytest / Jest / JUnit / etc. — standard, mandatory in most codebases. Coverage reports standard. |
| **Static analysis** | XINDEX (66 error classes); not integrated into commit workflow. | ESLint / Pylint / clippy / SonarQube — pre-commit, CI-gated, often auto-fixing. |
| **Formatter** | None standard. SAC (VA Standards and Conventions) is a style *document* enforced manually. | Prettier / black / rustfmt / gofmt — auto-run on save, CI-enforced. |
| **Type system** | None. MUMPS is untyped; everything is a string. | TypeScript / mypy / Rust / Kotlin — strong types, compile-time safety. |
| **IDE support** | Terminal editor (ZED, JED, %ZEDIT); some VSCode MUMPS extensions (limited). | Rich IDEs (VSCode, IntelliJ) with autocomplete, refactoring, cross-reference navigation, debugging. |
| **Refactoring** | Manual find-replace across routine source. XINDEX catches broken refs post-hoc. | IDE-driven — rename-symbol, extract-function, move-file with full graph awareness. |
| **Documentation** | Inline `;` comments + VA Documentation Library (VDL) maintained separately. Sparse and often out of date. | Inline docstrings (JSDoc, Sphinx, rustdoc) generated into searchable sites. Docs-as-code. |
| **Dependency graph** | Not declared; recoverable via XINDEX xref analysis (what we do in Phase 5). | Declared explicitly in manifest files; tools like `npm ls` visualize it. |
| **Rollback** | Restore from backup. No atomic undo. | `git revert`, container redeploy, blue-green, canary. Rollback is routine. |
| **Testing environments** | Production, Test, Training — full parallel installations. Heavy infra cost. | Preview deploys per PR, ephemeral env per branch, staging, dev-loop in seconds. |
| **Hot reload** | Live edit of running routines (traditional) — changes visible on next call. | Webpack HMR / Vite / Django dev server — subsecond reload on file save. |
| **Secret management** | Mixed — some in `^%ZOSF`, some in kernel site parameters, some in routine source (historically). | Vault / AWS Secrets Manager / env vars + secret stores. Secrets never in source. |
| **Configuration** | Site parameters in `^XTV(8989.3)` globals + Kernel options. | Env vars, config files, feature flags (LaunchDarkly). Hierarchical overrides. |
| **Observability** | `^ERROR` log, MailMan bulletins, no metrics, no tracing. | Prometheus + Grafana, OpenTelemetry, Sentry, PagerDuty — structured + distributed. |
| **Logging** | Routine-specific, unstructured, stays on-box. | JSON structured logs, aggregation (ELK / Datadog / Loki), log levels, correlation IDs. |
| **Deployment model** | Manual KIDS install by site IRM. Hours. | Automated deploy on merge, containerized, rolling update. Minutes. |
| **Infrastructure as code** | None. Each VistA install is hand-configured. | Terraform / Pulumi / CloudFormation. VistA-in-Docker (this project) is one of few examples. |
| **Containerization** | Not standard. Each VistA is a VM / bare-metal install. | Docker everywhere. Kubernetes for orchestration. |
| **Microservices** | No. Monolithic MUMPS global namespace. RPC Broker + HL7 are the only network boundaries. | Services communicate over HTTP/gRPC. Service mesh (Istio). Per-service DB. |
| **API contracts** | RPCs defined in File 8994; HL7 v2 messages. No machine-readable schema. | OpenAPI / GraphQL schema / gRPC Protobuf — machine-generated clients. |
| **Database migration** | DD merges via KIDS. No diff tool. | Alembic / Flyway / rails migrations — versioned, reversible, auditable. |
| **Feature flags** | Kernel options can be enabled/disabled per user/site, but not per-feature at the code level. | LaunchDarkly / Unleash / Statsig — runtime flags, A/B testing, gradual rollout. |
| **Access control** | Kernel security keys + user menus. Flat ACL. | RBAC / ABAC / OPA — fine-grained, policy-as-code. |
| **Testing strategy** | Manual, production-like test accounts. Integration-heavy. | Test pyramid: unit heavy, integration moderate, e2e light. |
| **Mocking** | Essentially none. Most tests hit real FileMan + real globals. | Mock frameworks (pytest-mock, Jest mocks, gomock) — isolate unit under test. |
| **Release cadence** | VA: patch releases every few months per package. Community: bursts. | Continuous deployment (multiple per day) to weekly releases depending on product. |
| **Time to ship a small fix** | 2–12 weeks (patch development + QA + distribution + site install). | Minutes to hours (commit → CI → deploy). |
| **Rollback window** | Hours of backup restore if it's even possible. | Seconds (previous container image). |

### 4.2 Where VistA wins

A fair comparison goes both ways. VistA has real strengths contemporary stacks lack:

- **Data-code colocation** — MUMPS globals are the database; code that touches data doesn't serialize/deserialize through an ORM. Fewer moving parts.
- **Stability under load** — some VA hospitals run routines from 1995 untouched in 2026. That kind of decade-plus stability is hard in JS land.
- **Minimal deploy complexity** — no container orchestration, no service mesh, no sidecars. One MUMPS process.
- **Built-in persistence** — globals are ACID-durable by default. No separate DB tier to operate.
- **Audit simplicity** — every action logs to known globals.
- **Patch forward-only discipline** — forces you to think through backward compatibility.
- **Terminal-first UX** — works over the worst network conditions.
- **No dependency hell** — no transitive dependency trees to resolve; Kernel+FileMan are shared.

---

## 5. What's missing in VistA's code-development lifecycle

Gaps that a contemporary full-stack developer would immediately feel. Grouped by category.

### 5.1 Source-control / change-tracking gaps

- **No commit-level atomicity** — a patch is the unit. Fine-grained changes can't be individually reverted.
- **No diff** — given two versions of a routine, no tool tells you "line 47 changed".
- **No branches / merges** — serial patch numbering doesn't model parallel development.
- **No blame** — who wrote line 47 is unrecoverable.
- **No bisect** — you can't bisect patch history to find when a bug was introduced.
- **No tag/release abstraction separate from patch list**.
- **Modern overlay exists** (OSEHRA/WorldVistA on GitHub) but isn't authoritative; VA trunk doesn't round-trip through git.

### 5.2 Build / install / release gaps

- **No declarative dependency graph** — you can't `npm install` a VistA package and have its dependencies auto-resolve. Environment check routines do this manually, one patch at a time.
- **No reproducible builds** — the same source + same compiler don't guarantee the same output globals after install (interactive prompts during install, site-specific state).
- **No CI/CD** — there's no automated gate between "commit" and "installable build" in VA trunk.
- **No package isolation** — all routines share a global namespace. Name collisions between packages are only detected at install time and are fatal.
- **No atomic rollback**.
- **No semantic versioning contract** — "patch 27 installed" doesn't tell you whether breaking changes happened.

### 5.3 Development-experience gaps

- **No modern IDE** — MUMPS support in VSCode / IntelliJ exists but is shallow (syntax highlighting, basic symbol jump). No rename-symbol, no refactoring, no deep navigation.
- **No type system** — every variable is a string; type errors surface only at runtime.
- **No autocomplete across packages** — the call graph we reverse-engineered in Phase 5 doesn't exist in a developer's IDE.
- **No linter enforcement at commit** — XINDEX is run manually, maybe at release time.
- **No formatter** — SAC is enforced by convention and code review, not tooling.
- **No hot-reload dev loop** — live-editing routines works but has no test feedback.
- **No unit-test culture** — M-Unit exists but adoption is thin. Code changes rarely accompanied by new tests.
- **No mocking framework** — testing pieces in isolation is prohibitive.
- **No code coverage tooling**.

### 5.4 Operational gaps

- **No structured logs** — diagnosing a production issue is global-archeology.
- **No metrics** — VistA has no equivalent to Prometheus. Capacity planning is informal.
- **No distributed tracing** — finding which routine is slow in a multi-routine workflow requires `ZBREAK`-level debugging.
- **No alerting beyond MailMan** — critical events go to humans' inboxes, not to pagers / Slack / incident tooling.
- **No infrastructure as code** — site configuration drifts.
- **No containerization standard** — this project (vista-meta) is a rare example.

### 5.5 API / integration gaps

- **No machine-readable API schema** — File 8994 records RPC names and routine targets but not request/response shapes. Client code (CPRS) hardcodes the contract.
- **No GraphQL / OpenAPI equivalent** — HL7 v2 messages are the closest thing to a formal contract; HL7 v2 is 1989-vintage pipe-delimited text.
- **No FHIR native** — FHIR adapters exist (VA's HDR/CDW → FHIR) but are overlays, not core.

### 5.6 Security gaps

- **No secret management** — site-specific secrets live in Kernel globals with per-user access keys. Not rotated, not vaulted.
- **No SBOM** — you can't ask "does this VistA install contain a log4j-equivalent vulnerability?"
- **No standard vulnerability scanning** — there's no Dependabot equivalent.
- **No per-feature access control** — security keys are coarse (who can run Option X), not fine (who can read field Y of file Z).

### 5.7 What our project (vista-meta) surfaces that VistA itself doesn't

Several of these "gaps" are now *recoverable* from the artifacts we built:

- **Call graph** (`routine-calls.tsv` + `xindex-xrefs.tsv`) — VistA developers don't have this visualized; we do.
- **Package coupling matrix** (`package-edge-matrix.tsv`) — reveals the architecture.
- **Code-quality hotspots** (`xindex-errors.tsv`) — 6,918 ranked issues across 66 classes.
- **Role intersection** (RF-024's 7-cell matrix) — which routines back RPC + option + protocol surfaces.
- **Cross-package PIKS flow** — `package-manifest.tsv` tells you which packages own which PIKS of data.
- **Dead-code candidates** (T-003's 14,658 "truly unreferenced" cohort) — something a conventional IDE's "unused function" linter would give for free.
- **Dependency DAG** (derived from `package-edge-matrix.tsv`) — not declared by VistA itself.

**Our code-model is, in effect, the metadata layer a full-stack developer assumes the language ecosystem provides for free.** We had to build it by scanning 39,330 `.m` files and correlating against FileMan's own metadata files. That this was necessary is itself evidence of the framework gap.

---

## 6. Reading the artifacts in practice

Quick patterns for common questions.

### "Which routines does the Lab Service package expose to CPRS via RPC?"
```bash
awk -F'\t' 'NR>1 && $2=="Lab Service" && $12+0>0 {print $1, $12}' \
  vista/export/code-model/routines-comprehensive.tsv
```

### "Which packages depend most on VA FileMan?"
```bash
awk -F'\t' 'NR>1 && $2=="VA FileMan" {print $1, $3}' \
  vista/export/code-model/package-edge-matrix.tsv | sort -k2 -rn | head
```

### "Which routines have the most XINDEX errors?"
```bash
awk -F'\t' 'NR>1 {c[$1]++} END{for(r in c) print c[r], r}' \
  vista/export/code-model/xindex-errors.tsv | sort -rn | head
```

### "What FileMan files does package X own, by PIKS?"
```bash
grep -P "^Integrated Billing\t" vista/export/code-model/package-manifest.tsv
```

### "Find all dual-role routines (both RPC and menu option)"
```bash
awk -F'\t' 'NR>1 && $12+0>0 && $13+0>0 {print $1, $2}' \
  vista/export/code-model/routines-comprehensive.tsv
```

---

## 7. Forward work

Per the TODOs and closure RFs:

- **T-001**: reconcile the 39,330 / 39,331 / 39,338 count divergence in Dockerfile build artifacts.
- **T-002**: characterize the 10,228 MANIFEST-only + 1,563 File-9.8-only cohorts.
- **T-003**: reduce the 14,658 "truly unreferenced" cohort via DD-embedded MUMPS extraction.
- **Phase 7b** (candidate): re-run with WorldVistA/XINDEX/master for comparative analysis.
- **Code-quality phase**: surface `xindex-errors.tsv` per-package and per-severity into a ranked hotspot view.
- **DD-code extraction**: parse `^DD` cross-references, input transforms, and computed fields for a full call graph including FileMan callbacks.

---

## 8. Related documents

- [ADR-045](adr/045-data-code-separation-package-bridge.md) — the architecture decision this guide operates under
- [xindex-reference.md](xindex-reference.md) — detailed XINDEX catalog and coverage matrix
- [piks-analysis-guide.md](piks-analysis-guide.md) — the data-model side companion
- [vista-meta-spec-v0.4.md](vista-meta-spec-v0.4.md) §11 — research system, extraction pipeline
- [vista/export/RESEARCH.md](../vista/export/RESEARCH.md) — RF-001 through RF-027 analytical findings log
