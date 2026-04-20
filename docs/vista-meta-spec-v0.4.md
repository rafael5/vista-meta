# vista-meta — Specification (v0.4)

Snapshot date: 2026-04-18

A VistA metadata analytics sandbox. Docker-hosted VEHU instance on YottaDB,
running on minty (Linux Mint 22.3, Tailscale-networked), used for FileMan
classification, DD extraction, XINDEX analysis, and global-structure
archaeology. The primary analytical goal is **PIKS classification** — sorting
every FileMan file and global into one of four data categories (Patient,
Institution, Knowledge, System) that determine audience, security posture,
storage strategy, and analytical approach.

Code developed and git-versioned on the host; executed inside the container.

Not a wrapper over FileMan via gRPC. Not a production VistA. A laboratory.

---

## Table of contents

1. [Architecture](#1-architecture)
2. [Locked decisions](#2-locked-decisions)
3. [Host-side directory layout](#3-host-side-directory-layout)
4. [Dockerfile layer structure](#4-dockerfile-layer-structure)
5. [Entrypoint script](#5-entrypoint-script)
6. [bake.sh pipeline](#6-bakesh-pipeline)
7. [$ZRO / .gld layering](#7-zro--gld-layering)
8. [Makefile targets (v1)](#8-makefile-targets-v1)
9. [Sentinel JSON schema](#9-sentinel-json-schema)
10. [Documentation system](#10-documentation-system)
11. [Research system](#11-research-system)
12. [Environment configuration](#12-environment-configuration)
13. [Smoke tests](#13-smoke-tests)
14. [Out of scope / deferred / skipped](#14-out-of-scope--deferred--skipped)
15. [Remaining open work](#15-remaining-open-work)

---

## 1. Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│  HOST: minty  (Linux Mint 22.3, Tailscale IP 100.x.y.z)              │
│                                                                      │
│   ~/vista-meta/               (standalone git repo)                  │
│   ├── vista/                                                         │
│   │   ├── dev-r/     ──┐  your M routines                            │
│   │   ├── scripts/   ──┤  Python + shell analyses                    │
│   │   └── export/    ──┤  XINDEX / zwr / DDR / DD-exporter output    │
│   ├── docker/          │  Dockerfile, entrypoint.sh, bake.sh,        │
│   │                    │  healthcheck.sh, .env, configs              │
│   ├── docs/            │  spec + ADRs                                │
│   ├── snapshots/       │  named-volume tarballs (gitignored)         │
│   ├── host/            │  host Python venv for post-hoc analysis     │
│   └── tests/smoke/     │  post-build smoke tests                     │
└────────────────────────┼─────────────────────────────────────────────┘
                         │ bind-mount (rw)
                         ▼
┌──────────────────────────────────────────────────────────────────────┐
│  CONTAINER: vista-meta  (Ubuntu 24.04)                               │
│                                                                      │
│   ┌─────── BAKED IN IMAGE ────────┐  ┌── MOUNTED AT RUNTIME ──┐      │
│   │  YottaDB  (pinned version)    │  │  /home/vehu/dev/r/     │ bind │
│   │  /opt/VistA-M/                │  │  /home/vehu/scripts/   │ bind │
│   │    Packages/<pkg>/Routines/   │  │  /home/vehu/export/    │ bind │
│   │    r/      (symlink farm)     │  │  /home/vehu/g/         │      │
│   │    o/      (pre-compiled)     │  │    ← named volume:     │      │
│   │  Octo SQL engine              │  │      vehu-globals      │      │
│   │  YDB Web Server + YDBGUI      │  └────────────────────────┘      │
│   │  M-Unit (ChristopherEdwards)  │                                  │
│   │  FMQL, FileMan DD utilities   │                                  │
│   │  Python 3 + yottadb + git     │                                  │
│   │  ranger, micro, tree, btop,   │                                  │
│   │    ncdu                       │                                  │
│   └───────────────────────────────┘                                  │
│                                                                      │
│     $ZRO routine path:                                               │
│       /home/vehu/dev/r(o)  →  /opt/VistA-M/r(o)  →  $ydb_dist libs   │
│                                                                      │
│   ┌─ SERVICES (bound to Tailscale IP only, no auth) ───┐             │
│   │   sshd         :2222                               │             │
│   │   RPC Broker   :9430    (CPRS · DDR)               │             │
│   │   VistALink    :8001                               │             │
│   │   Octo SQL     :1338                               │             │
│   │   YDB GUI      :8089                               │             │
│   └────────────────────────────────────────────────────┘             │
└─────────────────────────────▲────────────────────────────────────────┘
                              │
                     ┌────────┴─────────┐
                     │  Tailnet only    │
                     │  mac-rmr         │
                     │  pixel-8         │
                     │  pi5 · glnet     │
                     └──────────────────┘
```

---

## 2. Locked decisions

### 2.1 Project meta

| # | Decision | Value |
|---|---|---|
| 17 | Project name | `vista-meta` (analytics scope; was `vista-grpc`) |
| 18 | Primary analytical goal | PIKS classification — classify every FileMan file AND non-FileMan global into Patient, Institution, Knowledge, or System |
| 19 | Analytical scope | ALL data in the database, not just FileMan-described data. Pharmacy and Lab write substantial patient data directly to globals outside `^DD`. |
| 20 | Classification approach | Automated heuristics first (52 DD-based + 6 non-FM rules), then human triage for remainder |
| 21 | Portability goal | Heuristic rules and PIKS framework are VistA-universal; site-specific data stays local |

### 2.2 VistA selection & runtime

| # | Decision | Value |
|---|---|---|
| 1  | VistA flavor | VEHU (synthetic patient data) |
| 2  | Base OS | Ubuntu 24.04 |
| 3  | M implementation | YottaDB via `ydbinstall.sh`, pinned version |
| 4  | UTF-8 | Off |
| 6  | Bootstrap | Skip (`-b`) |
| 7  | Post-install hook | None |
| 12 | Network exposure | Bind to Tailscale IPv4 only |
| 16 | UID alignment | Entrypoint chowns bind mounts on start |

### 2.3 Persistence

| # | Decision | Value |
|---|---|---|
| 8+9 | Persistence model | Hybrid: 3 bind mounts + named volume + baked VEHU-M |
| 11  | Image tagging | `:latest` + date tag (e.g., `:2026-04-18`) |
| 13  | `$ZRO` path | `dev-r/` first, VEHU-M fallback, YDB libs last |

### 2.4 Services baked into image

| # | Component | Port | Notes |
|---|---|---|---|
| 5a | RPC Broker | 9430 | Started by xinetd |
| 5b | VistALink (M side) | 8001 | Started by xinetd |
| 5c | sshd | 2222 (from 22) | Password auth for `vehu` user |
| 15 | Octo SQL engine | 1338 | `rocto` daemon |
| 5d | YDB GUI (YDBGUI + YDB Web Server) | 8089 | Open auth; Tailscale is perimeter |
| 5e | Python 3 + yottadb + git | n/a | Tooling, not a service |

### 2.5 Analysis tooling baked into image

| # | Tool | Notes |
|---|---|---|
| —   | Enhanced XINDEX | In VEHU via OSEHRA inheritance — verify on first run |
| 24  | `^XTSUMBLD` build summary | In VEHU Kernel Toolkit; expose via helper |
| 19  | M-Unit (**ChristopherEdwards/M-Unit**) | YDB plugin via cmake; `%ut` namespace |
| 23a | DD exporter A — FileMan utilities | Helper wrappers around `^DIU2`, `^DD` walks, `DIFROM` |
| 23b | DD exporter B — FMQL | `github.com/caregraf/FMQL` |
| 23d | DD exporter D — FileMan Print Template scaffolding | Starter template + invocation helper |
| 14  | XINDEX baseline run | Auto on first run (background) + manual rebake |

### 2.6 Interactive / shell tooling

| # | Tools | Source |
|---|---|---|
| 18 | ranger, micro, tree, btop, ncdu | apt (Ubuntu 24.04 universe) |
| —  | less | base |

### 2.7 Build / runtime mechanics

| # | Decision | Value |
|---|---|---|
| 10 | Entrypoint | Single bash wrapper, `tini` as PID 1 |
| —  | Build approach | Single-stage Dockerfile, granular `RUN` layers |
| —  | Build args | `YDB_VERSION`, `VEHU_M_URL`, `VEHU_UID`, `BUILD_DATE` |
| —  | Runtime args | `TAILSCALE_IP` (from `.env`) |

### 2.8 Entrypoint / bake / health

| # | Decision | Value |
|---|---|---|
| —  | Bake mode | Background on first run + `make wait-for-bake` target |
| —  | Bake failure handling | Continue-on-error, per-phase in sentinel |
| —  | HEALTHCHECK | Enabled (sshd, xinetd, rocto, YDB GUI listening) |
| —  | Bake pipeline | `bake.sh` — single entry point for first-run + manual rebake |
| —  | Iteration scope | Configurable (`--files=`, `--packages=`), default full VEHU |
| —  | Parallelism | Configurable (`BAKE_WORKERS`), default serial |
| —  | Resume support | Phase-level; skip phases marked `ok` unless `--force` |
| —  | Error granularity | Item-level within a phase; per-phase status = `ok`/`partial`/`failed`/`pending` |

### 2.9 $ZRO / .gld layering

| # | Decision | Value |
|---|---|---|
| —  | Routine flattening | Symlink farm (`/opt/VistA-M/r/` symlinks → `Packages/<pkg>/Routines/`) |
| —  | Regions/segments | Single region (DEFAULT → one segment → `mumps.dat`) |
| —  | dev-r object dir | Container-internal, ephemeral (`/home/vehu/dev/o/`) |
| —  | `.gld` builder | `mumps -r GDE` at build time |

### 2.10 Host layout / workflow

| # | Decision | Value |
|---|---|---|
| —  | Git tracking for `export/` | Hybrid: raw dumps gitignored, manifests + `data-model/` + `code-model/` tracked |
| —  | Host Python venv | Yes, at `host/` |
| —  | Tests | Smoke only (no BATS) |
| —  | ADR discipline | Adopted from start; backfill deferred |

### 2.11 Makefile

| # | Decision | Value |
|---|---|---|
| —  | Confirmation on destructive targets | Prompt always |
| —  | Snapshot retention | Auto-prune to last 5 |
| —  | `wait-for-bake` output | Progress dots |
| —  | Target scope for v1 | Lean + `adr-new` |

### 2.12 Analytical methodology

| # | Decision | Value |
|---|---|---|
| —  | Classification framework | PIKS: Patient, Institution, Knowledge, System. Every file/global gets exactly one primary category. |
| —  | Classification scope | ALL globals in database — FileMan-described AND non-FileMan. Pharmacy/Lab non-FM data is a first-class workstream, not an afterthought. |
| —  | Orthogonal properties | Four properties assigned alongside PIKS: volatility, sensitivity, portability, volume |
| —  | Heuristic classifier | `VMPIKS`: 52 DD-based heuristics (H-01–H-52) across 12 tiers + 6 non-FM heuristics (G-01–G-06). Deterministic, reproducible, VistA-universal. |
| —  | Global census | `VMCENSUS`: two-phase (recon + full census). Inventories ALL globals independent of `^DD`. Phase 2 always runs. |
| —  | Pipeline state | TSV files are the working state. Column ownership rules: extraction refreshes structural data, heuristics write only to unclassified files, manual overrides are immutable. Unknowns decrease monotonically. |
| —  | Traceability | Every classification records method (`piks_method`) + evidence (`piks_evidence`). Machine: which heuristic + what data triggered it. Manual: RF-NNN research log entry. |
| —  | Coverage tracking | `coverage.json` tracks PIKS coverage, property coverage, FileMan coverage, extraction completeness. Primary metric: `piks_classification.coverage_pct`. |
| —  | Triage strategy | 5 categories for unmatched files: vestigial, package-identifiable, mixed-signal, cross-cutting, unresolvable. Learning classifier: triage findings feed back into heuristic tables. |
| —  | Analysis phases | Phase 0 (extraction + census) → Phase 1a (auto PIKS) → Phase 1b (human triage) → Phase 2 (subdomains) → Phase 3+ (ongoing research) |

### 2.13 Documentation system

| # | Decision | Value |
|---|---|---|
| —  | Document types | Six artifacts: CLAUDE.md, spec, ADRs, build log (BL-NNN), research log (RF-NNN), dependency manifest |
| —  | Code documentation | Script headers with `RUNS IN`/`RUNS ON` context, comment the "why" not the "what", spec/ADR/BL cross-references |
| —  | Build log | Append-only, records implementation errors/corrections, NOT design decisions (ADRs) or analytical findings (RF-NNN) |
| —  | Research log | Append-only, records analytical discoveries about VistA metadata, NOT implementation errors |
| —  | Spec errata | Code fix → BL-NNN entry → `[Errata: see BL-NNN]` annotation in spec. Never silently rewrite the spec. |
| —  | Known risk lifecycle | open → confirmed/falsified/deferred. Resolution annotated with BL-NNN reference. |

---

## 3. Host-side directory layout

```
~/vista-meta/                  (standalone git repo; own top-level dir, not under ~/claude/)
├── CLAUDE.md                  project orientation for Claude sessions (<80 lines)
├── README.md                  project overview, quickstart
├── Makefile                   18 targets (lean v1 + adr-new)
├── .env                       TAILSCALE_IP, runtime config (gitignored)
├── .env.example               checked-in template
├── .gitignore
├── .gitattributes
│
├── docs/                      spec + ADRs + implementation records
│   ├── vista-meta-spec-v*.md  specification (versioned snapshots)
│   ├── build-log.md           implementation log (append-only, BL-NNN)
│   ├── dependencies.md        pinned upstream versions + provenance
│   └── adr/                   one file per decision (ADR-NNN format)
│
├── docker/                    container source (build context)
│   ├── Dockerfile
│   ├── entrypoint.sh
│   ├── bake.sh
│   ├── healthcheck.sh
│   └── etc/
│       ├── xinetd.d/
│       │   ├── xwb            RPC Broker :9430
│       │   └── vlink          VistALink :8001
│       ├── sshd_config
│       └── ydb_env.sh         /etc/profile.d/ entries
│
├── vista/                     bind-mounted into container
│   ├── dev-r/                 → /home/vehu/dev/r/
│   ├── scripts/               → /home/vehu/scripts/
│   └── export/                → /home/vehu/export/
│       ├── xindex-baseline/   {INDEX.tsv, summary.md, raw/ (ignored)}
│       ├── dd-text/           {INDEX.tsv, summary.md, raw/ (ignored)}
│       ├── dd-fmql/           {INDEX.tsv, summary.md, raw/ (ignored)}
│       ├── dd-template/       {INDEX.tsv, summary.md, raw/ (ignored)}
│       ├── RESEARCH.md            research findings journal (RF-NNN, both slices)
│       ├── data-model/             FileMan + PIKS slice (tracked)
│       │   ├── files.tsv           FileMan file inventory
│       │   ├── piks.tsv            automated PIKS classifications (VMPIKS)
│       │   ├── piks-triage.tsv     manual triage overrides
│       │   ├── field-piks.tsv      field-level PIKS (VMFPIKS)
│       │   ├── vista-fileman-piks-comprehensive.csv  joined 69k-row output
│       │   └── ...                 (future: fields.tsv, pointers.tsv, xrefs.tsv, globals.tsv, global-census.tsv)
│       ├── code-model/             routines + packages + XINDEX slice (ADR-045, tracked)
│       │   ├── routines.tsv        per-routine inventory + static features
│       │   ├── packages.tsv        per-package aggregates
│       │   ├── package-manifest.tsv         Phase 6a bridge
│       │   ├── routines-comprehensive.tsv   Phase 6b bridge
│       │   ├── package-edge-matrix.tsv      Phase 6c cross-package edges
│       │   ├── routine-calls.tsv   routine→routine edges (regex)
│       │   ├── routine-globals.tsv routine→global edges (regex)
│       │   ├── protocol-calls.tsv  protocol ENTRY ACTION → routine
│       │   ├── package-data.tsv    ZWR shipment inventory
│       │   ├── package-piks-summary.tsv  per-package PIKS distribution
│       │   ├── {vista-file-9-8,rpcs,options,protocols}.tsv  FileMan metadata dumps
│       │   ├── xindex-{routines,errors,xrefs,tags}.tsv  XINDEX authoritative output
│       │   └── xindex-validation.tsv  regex-vs-XINDEX validation join
│       ├── logs/              gitignored
│       └── .vista-meta-initialized  sentinel JSON (tracked)
│
├── snapshots/                 named-volume tarballs (gitignored)
├── host/                      host Python venv
│   ├── pyproject.toml
│   └── analysis/
└── tests/smoke/               post-build smoke verification
```

`.gitignore` core rules:

```
vista/export/**/raw/
vista/export/logs/
.env
snapshots/
host/.venv/
```

---

## 4. Dockerfile layer structure

Single-stage Dockerfile. Build context = `docker/` directory only.

| # | Layer | Responsibility | Cache behavior |
|---|---|---|---|
| 1 | `FROM ubuntu:24.04` | Base | Stable |
| 2 | OS deps | apt: curl, wget, unzip, sudo, openssh-server, xinetd, tini, git, python3, python3-pip, python3-venv, build-essential, cmake, ca-certificates, locales, ranger, micro, tree, btop, ncdu. [Errata: also requires libsodium-dev, libcurl4-openssl-dev for YDBGUI — see BL-001] | Rarely changes |
| 3 | User setup | Create `vehu` user with UID `${VEHU_UID}` (default 1001), sudo-capable. Create subdirs: `dev/r`, `dev/o`, `scripts`, `export`, `g`, `o` | Rarely changes |
| 4 | YottaDB install | Run `ydbinstall.sh --webserver` (pinned via `${YDB_VERSION}`). Writes `/etc/profile.d/ydb_env.sh` with env vars | Changes on YDB version bump |
| 5 | VEHU-M fetch | `curl ${VEHU_M_URL}` into `/tmp`, unzip, rsync into `/opt/VistA-M/Packages/`, remove zip | Changes when VEHU-M source updates |
| 6 | Symlink farm + YDB env | Build `/opt/VistA-M/r/` of symlinks into `Packages/<pkg>/Routines/`. Fail on duplicate routine names. Write MANIFEST.tsv. Generate `.gld` via `mumps -r GDE` | Rare |
| 7 | VEHU-M import | As `vehu` user: `D ^%RI` from symlink farm, `D ^%GI` from globals `.zwr` files, `D ^%RCOMPIL` → objects in `/opt/VistA-M/o/` | **Expensive** (~5-15 min). Rare changes |
| 8 | Octo DDL mapping | Fetch `_YDBOCTOVISTAM.m` from YDBOctoVistA repo, compile, run `MAPALL^%YDBOCTOVISTAM` with DUZ context → baseline DDL at `/opt/VistA-M/ddl/`. [Errata: routine not bundled with Octo — see BL-002] | Rare |
| 9 | M-Unit install | Clone `ChristopherEdwards/M-Unit`, cmake + make install → YDB plugin at `$ydb_dist/plugin/` | Rare |
| 10 | YDBGUI install | Clone `YottaDB/UI/YDBGUI`, cmake + make install → web assets at `/opt/ydbgui/web/`, M routines into YDB plugin path | Rare |
| 11 | FMQL install | Clone `caregraf/FMQL`, install M routines, compile | Rare |
| 12 | Python tooling | pip install yottadb, click, pyyaml, requests (+ any curated set) | Rare |
| 13 | Service configs | Write `/etc/xinetd.d/xwb`, `/etc/xinetd.d/vlink`, sshd_config | Rare |
| 14 | Entrypoint + bake + healthcheck | COPY `entrypoint.sh`, `bake.sh`, `healthcheck.sh` to `/usr/local/bin/`; chmod | Frequently iterated |
| 15 | Meta | `EXPOSE`, `HEALTHCHECK`, `ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/entrypoint.sh"]` | Frequent |

### Build args

| Arg | Default | Purpose |
|---|---|---|
| `YDB_VERSION` | (current stable) | Pin YDB version |
| `VEHU_M_URL` | `https://github.com/WorldVistA/VistA-VEHU-M/archive/master.zip` | Source of VistA-M |
| `VEHU_UID` | `1001` | UID for `vehu` user |
| `BUILD_DATE` | `$(date +%F)` | For tagging |

---

## 5. Entrypoint script

`/usr/local/bin/entrypoint.sh`, invoked by `tini` as PID 1.

### Phases

| Phase | Run as | Idempotent? | Blocking? | Description |
|---|---|---|---|---|
| 1. Pre-flight | root | yes | yes | Validate env. Generate SSH host keys if missing |
| 2. UID reconciliation | root | yes | yes | `chown -R vehu:vehu` bind mounts + globals dir |
| 3. Service startup | mixed | yes | non-blocking | Start sshd → xinetd → rocto → YDB GUI (in order) |
| 4. First-run bake | vehu | sentinel-gated | **background** | If sentinel absent or incomplete, invoke `bake.sh --all` in background |
| 5. Supervise | tini | n/a | forever | `wait` on background PIDs. SIGTERM forwarded for graceful shutdown |

### Signal handling

Trap `SIGTERM`: stop rocto (`rocto -stop`) → stop xinetd → stop sshd → exit 0. Docker `--stop-timeout 30` recommended in run command.

### HEALTHCHECK

Validates: sshd listening on 22, xinetd listening on 9430 and 8001, rocto listening on 1338, YDB GUI listening on 8089. Bake status NOT a health criterion.

---

## 6. bake.sh pipeline

`/usr/local/bin/bake.sh` — invoked by entrypoint on first run AND by `make bake*` targets.

### Phase pipeline

| Phase | Reads from | Writes to |
|---|---|---|
| 0. Init | sentinel + flags | `export/logs/bake-<timestamp>.log` |
| 1. XINDEX baseline | `/opt/VistA-M/r/MANIFEST.tsv` | `export/xindex-baseline/` |
| 2. DD exporter A — FileMan | DD globals via `^DIU2` | `export/dd-text/` |
| 3. DD exporter B — FMQL | DD globals via FMQL routines | `export/dd-fmql/` |
| 4. DD exporter D — Templates | DD-of-DDs via starter Print Template | `export/dd-template/` |
| 5. Finalize | All phase results | Update sentinel JSON |

### Output structure per phase

| Subdir/file | Git-tracked? |
|---|---|
| `raw/` (per-item output) | No |
| `INDEX.tsv` (manifest of items) | Yes |
| `summary.md` (human summary) | Yes |

### Contract

```
bake.sh [PHASE-FLAGS] [SCOPE-FLAGS] [BEHAVIOR-FLAGS]

PHASE-FLAGS (default: --all)
  --all                  All phases; skip those marked 'ok' in sentinel
  --xindex               XINDEX baseline only
  --dd-only              DD exporters only (A, B, D)
  --only=NAME            Specific: xindex | dd-text | dd-fmql | dd-template

SCOPE-FLAGS (default: full VEHU)
  --files=N,N,N          Restrict to these FileMan file numbers
  --packages=PKG,PKG     Restrict to these package namespaces

BEHAVIOR-FLAGS
  --force                Re-run phases marked 'ok'; overwrites output
  --workers=N            Parallelism (or BAKE_WORKERS env; default 1)
```

### Resume semantics

| Phase status in sentinel | Action |
|---|---|
| `ok` | Skip (unless `--force`) |
| `partial` | Re-run whole phase |
| `failed` | Re-run whole phase |
| `pending` | Run (was interrupted) |
| missing | Run (never started) |

### Phase outcome rules

| Within-phase result | Sentinel status |
|---|---|
| All items succeeded | `ok` |
| Some items failed | `partial` |
| All items failed / catastrophic | `failed` |
| Aborted before completion | `pending` |

---

## 7. $ZRO / .gld layering

### Routine search path

```
ydb_routines="
  /home/vehu/dev/r(/home/vehu/dev/o)
  /opt/VistA-M/r(/opt/VistA-M/o)
  $ydb_dist/libyottadbutil.so
"
```

First-match-wins. Your dev routines shadow VEHU-M; VEHU-M shadows built-ins.

### Symlink farm (VEHU-M routine layout)

Real `.m` files live at `/opt/VistA-M/Packages/<pkg>/Routines/*.m`. Build-step creates `/opt/VistA-M/r/*.m` as symlinks pointing to those. Build fails on any duplicate routine name across packages. `/opt/VistA-M/r/MANIFEST.tsv` records routine → package → source path.

### Global directory

| Item | Value |
|---|---|
| `.gld` | `/home/vehu/g/mumps.gld` |
| `.dat` | `/home/vehu/g/mumps.dat` |
| Region | `DEFAULT` |
| Segment | single → mumps.dat |

### YDB env vars

| Var | Value |
|---|---|
| `ydb_dist` | `/usr/local/lib/yottadb/rX.YY` |
| `ydb_routines` | 3-layer path above |
| `ydb_gbldir` | `/home/vehu/g/mumps.gld` |
| `ydb_chset` | `M` |
| `ydb_log` | `/home/vehu/export/logs/ydb/` |
| `ydb_tmp` | `/tmp/ydb` |
| `LD_LIBRARY_PATH` | prepend `$ydb_dist` |
| `PATH` | append `$ydb_dist` |

Set in `/etc/profile.d/ydb_env.sh` AND exported in entrypoint.

---

## 8. Makefile targets (v1)

18 targets. Reads `.env` for `TAILSCALE_IP`. Default = `help`.

| Group | Targets |
|---|---|
| Lifecycle | `build`, `run`, `stop`, `restart`, `rm`, `clean` (prompt) |
| Interactive | `shell`, `mumps`, `python`, `logs`, `bake-log` |
| Bake | `bake`, `bake-xindex`, `bake-dd-text`, `bake-dd-fmql`, `bake-dd-template`, `wait-for-bake` (progress dots) |
| Snapshot | `snapshot-globals` (auto-prune to 5), `restore-globals SNAPSHOT=path` |
| Verify | `smoke` |
| Docs | `adr-new TITLE="..."`, `help` |

Destructive operations (`clean`) prompt; no `FORCE=1` escape hatch in v1.

---

## 9. Sentinel JSON schema

Path: `/home/vehu/export/.vista-meta-initialized` (git-tracked)

```json
{
  "initialized_at": "2026-04-18T14:30:00Z",
  "image_tag": "vista-meta:2026-04-18",
  "ydb_version": "rX.YY",
  "vehu_m_source": "<URL>#<sha256>",
  "phases": {
    "xindex": {
      "status": "ok",
      "items_ok": 30234,
      "items_failed": 12,
      "duration_sec": 1812,
      "log": "logs/xindex.log"
    },
    "dd-text": { "status": "ok", "items_ok": 3421, "items_failed": 0, "duration_sec": 945, "log": "logs/dd-text.log" },
    "dd-fmql": { "status": "partial", "items_ok": 1200, "items_failed": 2221, "duration_sec": 320, "log": "logs/dd-fmql.log" },
    "dd-template": { "status": "ok", "items_ok": 1, "items_failed": 0, "duration_sec": 3, "log": "logs/dd-template.log" }
  }
}
```

`status` ∈ {`ok`, `partial`, `failed`, `pending`, `skipped`}. `wait-for-bake` polls until none are `pending`.

---

## 10. Documentation system

The project uses four complementary documentation artifacts. Together they
form a complete record: the spec says what to build, ADRs say why, the build
log says what happened when we built it, and the dependency manifest pins
exactly what we built it from.

### 10.1 Document inventory

| Artifact | Path | Purpose | Mutability |
|---|---|---|---|
| CLAUDE.md | `CLAUDE.md` | Project orientation — loaded at every Claude session start | Updated as architecture evolves |
| Specification | `docs/vista-meta-spec-v*.md` | What to build: architecture, contracts, schemas | Versioned snapshots; append changelog |
| ADRs | `docs/adr/NNN-title.md` | Why we chose X over Y | Immutable once accepted; supersede via new ADR |
| Build log | `docs/build-log.md` | What happened during implementation | Append-only; reverse-chronological |
| Research log | `vista/export/RESEARCH.md` | What was discovered about VistA metadata | Append-only; RF-NNN entries |
| Dependency manifest | `docs/dependencies.md` | Pinned versions + provenance for every upstream | Updated on version bumps |

### 10.2 Build log (`docs/build-log.md`)

Append-only record of errors, warnings, corrections, and verification
outcomes encountered during implementation and operation. **Not** an ADR —
ADRs record choices between alternatives; the build log records what happened
when those choices met reality.

**Entry format**:

```
### BL-NNN: <short title>

- **Layer**: which file / Dockerfile layer / component
- **Error**: what went wrong or was incorrect
- **Root cause**: why it was wrong (spec gap, bad assumption, upstream change)
- **Fix**: what was changed, with before/after where useful
- **Source**: documentation, repo, or evidence that validates the fix
- **File**: affected file path(s) with line numbers
```

**What gets logged** (any of these):

| Category | Example |
|---|---|
| Spec-vs-reality divergence | Spec says `%YDBOCTOVISTAM` ships with Octo; it does not |
| Wrong API / routine / flag | Used `start^%ydbwebhandler`; correct is `start^%ydbwebreq` |
| Missing dependency | YDBGUI needs `libsodium-dev`; was not in apt list |
| Build failure + resolution | Layer 7 `mupip load` fails on specific `.zwr`; root cause + workaround |
| Runtime observation | VEHU-M import took 11 min on minty; adjusts estimate in spec §4 |
| Verification of known risk | Spec §15 risk #1 confirmed: Enhanced XINDEX present in VEHU |
| Upstream breakage | FMQL repo archived; fork URL updated |

**What does NOT go here**: design decisions (use ADRs), task tracking (use
git issues or TODO comments), general notes (use commit messages).

Entries are numbered `BL-NNN` with a monotonically increasing counter. The
number is a stable reference — commit messages and ADRs can cite `BL-003`
to point at a specific finding.

### 10.3 Dependency manifest (`docs/dependencies.md`)

Pins every upstream component to a specific version, URL, and (where
available) commit SHA or checksum. This is the single source of truth for
"what exact bits went into this image."

| Field | Required? | Example |
|---|---|---|
| Component | yes | YottaDB |
| Version | yes | r2.02 |
| Source URL | yes | `https://gitlab.com/YottaDB/DB/YDB/-/raw/master/sr_unix/ydbinstall.sh` |
| Commit / SHA | if available | `abc1234` |
| Dockerfile layer | yes | 4 |
| Notes | optional | Installed via `ydbinstall.sh --webserver --octo` |

Components to track:

- Ubuntu base image tag + digest
- YottaDB version + installer URL
- VEHU-M archive URL + SHA256
- YDBOctoVistA (`_YDBOCTOVISTAM.m`) commit
- YDBGUI commit
- M-Unit (ChristopherEdwards) commit
- FMQL (caregraf) commit
- Python packages (yottadb, click, pyyaml, requests) — pinned versions
- tini version (from apt)
- Octo version (bundled with ydbinstall)

Updated whenever a dependency version changes. Old versions stay in git
history; the file always reflects the current image.

### 10.4 Known risks lifecycle

Spec §15 lists known risks and unverified assumptions. Each risk has a
defined lifecycle:

| State | Meaning | Where recorded |
|---|---|---|
| **open** | Not yet tested against reality | Spec §15 |
| **confirmed** | Verified true; works as expected | Build log entry, risk marked `[confirmed BL-NNN]` in spec |
| **falsified** | Assumption was wrong; fix applied | Build log entry with fix, risk marked `[falsified BL-NNN]` in spec |
| **deferred** | Cannot verify yet; blocked on prerequisite | Spec §15, with blocking reason |

When a risk is resolved, the spec gets a one-line annotation pointing to the
build log entry. The build log has the full detail.

### 10.5 Spec errata

When implementation reveals that the spec was wrong (not just incomplete, but
factually incorrect), the correction process is:

1. Fix the code
2. Log the finding in `build-log.md` with category "spec-vs-reality divergence"
3. Add `[Errata: see BL-NNN]` annotation to the affected spec section
4. Do **not** silently edit the spec to hide the original error — the spec is a
   versioned snapshot; corrections are visible in the changelog

### 10.6 Code documentation standards

Code documentation serves two audiences: a future developer and a new Claude
session (which starts with no project context). Claude can read code; it
cannot read your mind. The highest-value documentation is what **isn't
derivable from the code itself**.

#### Script headers (every executable file)

Every script or config file gets a header block with:

1. **One-line purpose** — what this file does
2. **Spec cross-reference** — `Spec: docs/vista-meta-spec-v0.4.md § N`
3. **Execution context** — where it runs and who invokes it

```bash
#!/usr/bin/env bash
# bake.sh — first-run + manual analytics pipeline.
# Spec: docs/vista-meta-spec-v0.4.md § 6
# ADR-022: background on first run
#
# RUNS IN: container, as vehu user
# INVOKED BY: entrypoint.sh (first run) or `make bake*` (manual)
# USAGE: bake.sh [--all|--xindex|--dd-only|--only=NAME] [--force] [--workers=N]
```

The `RUNS IN` / `RUNS ON` line is critical for this project because code
crosses the host/container boundary. Use:

| Tag | Meaning |
|---|---|
| `RUNS ON: host` | Executed on minty (Makefile targets, smoke tests) |
| `RUNS IN: container` | Executed inside the Docker container |
| `RUNS ON: host (docker build)` | Executed during `docker build` |

#### Inline comments: why, not what

Comment when the code would **look wrong to a competent reader who doesn't
know VistA or YottaDB**. If someone would ask "why not the simpler way?",
that's where the comment goes.

```bash
# Good — explains a non-obvious VistA requirement
'change -region DEFAULT -null_subscripts=always'  # VistA requires null subscripts

# Good — explains why a failure is tolerated
xargs ... $ydb_dist/mumps 2>&1 || true  # some routines have known compile errors

# Bad — restates the code
# Create the vehu user
useradd -m vehu
```

Categories that warrant comments:

| Category | Example |
|---|---|
| VistA/FileMan conventions | DUZ, DIQUIET, null subscripts, $ZRO layering |
| Workarounds for tool limitations | ydb-run wrapper for xinetd, `--break-system-packages` |
| Intentionally tolerated failures | `\|\| true` on compilation, `\|\| echo WARN` on load |
| Non-obvious flag choices | `-D` (sshd foreground), `-ignorechset` (chset mismatch) |
| Build-time vs. runtime differences | Temporary 2-layer ZRO during build |

#### Cross-reference format

| Reference type | Format |
|---|---|
| Spec section | `# Spec: docs/vista-meta-spec-v0.4.md § 5` |
| ADR | `# ADR-029: symlink farm for flat routine namespace` |
| Build log entry | `# See BL-002 for why this is a separate fetch` |

### 10.7 Documentation layout

```
docs/                                 project-level documentation
├── vista-meta-spec-v0.4.md         specification (versioned snapshots)
├── build-log.md                      implementation log (BL-NNN entries)
├── dependencies.md                   pinned upstream versions + provenance
└── adr/                              architecture decision records
    ├── 000-index.md
    └── ...

vista/export/                         project's structured output (git-tracked)
├── RESEARCH.md                       research log (RF-NNN entries — covers both slices)
├── data-model/                       FileMan DD + PIKS slice (data-side)
│   ├── files.tsv                     FileMan file inventory (^DD/^DIC walk)
│   ├── piks.tsv                      automated PIKS classifications
│   ├── piks-triage.tsv               manual triage classifications
│   ├── field-piks.tsv                field-level PIKS
│   └── vista-fileman-piks-comprehensive.csv   joined 69k-row output
└── code-model/                       routines, packages, XINDEX slice (code-side, ADR-045)
    ├── routines.tsv                  per-routine inventory + static features
    ├── packages.tsv                  per-package aggregates
    ├── package-manifest.tsv          Phase 6a bridge (per-package)
    ├── routines-comprehensive.tsv    Phase 6b bridge (per-routine)
    ├── package-edge-matrix.tsv       Phase 6c cross-package edges
    ├── package-data.tsv              ZWR shipment inventory
    ├── package-piks-summary.tsv      per-package PIKS distribution
    ├── routine-calls.tsv             routine→routine edges (regex)
    ├── routine-globals.tsv           routine→global edges (regex)
    ├── protocol-calls.tsv            protocol ENTRY ACTION → routine edges
    ├── vista-file-9-8.tsv            File 9.8 ROUTINE dump
    ├── rpcs.tsv                      File 8994 REMOTE PROCEDURE dump
    ├── options.tsv                   File 19 OPTION dump
    ├── protocols.tsv                 File 101 PROTOCOL dump
    ├── xindex-routines.tsv           XINDEX per-routine summary
    ├── xindex-errors.tsv             XINDEX diagnostic errors (66 classes)
    ├── xindex-xrefs.tsv              XINDEX call-graph (authoritative)
    ├── xindex-tags.tsv               XINDEX tag/label inventory
    └── xindex-validation.tsv         regex-vs-XINDEX validation join
```

Extractor code lives in `vista/dev-r/` (MUMPS) and `host/scripts/`
(Python). See `docs/xindex-reference.md` §8 for the coverage matrix
of what each side produces.

---

## 11. Research system

The project's purpose is to build a normalized conceptual layer above raw
FileMan. The research system is how analytical findings get recorded,
validated, and built upon across sessions.

### 11.1 The problem

Every analytical session discovers things about VistA metadata — file
structures, cross-reference patterns, computed pointer chains, MUMPS global
naming conventions. Without a defined home for these findings, each session
(human or Claude) starts from scratch. The build log records implementation
errors; ADRs record design decisions. Neither captures "FileMan file 200 has
847 fields, 23 of which are computed pointers to file 8989.5."

### 11.2 Research log (`vista/export/RESEARCH.md`)

Append-only journal of analytical discoveries about VistA metadata. This is
the project's primary intellectual output — a growing body of verified
knowledge about how VistA's data structures actually work.

**Entry format:**

```
### RF-NNN: <short title>

- **Date**: 2026-04-18
- **Scope**: FileMan file(s), package(s), or global(s) examined
- **Method**: how the finding was obtained (XINDEX, DD walk, FMQL query, direct global inspection)
- **Finding**: what was discovered (the fact)
- **Evidence**: command/query used, output snippet, or pointer to raw export
- **Implications**: what this means for the normalized model or future analysis
- **Status**: provisional | verified | superseded by RF-NNN
```

**What gets logged:**

| Category | Example |
|---|---|
| File structure discovery | File 200 (NEW PERSON) has 847 fields across 12 multiples |
| Cross-reference mapping | File 200 field .01 has a regular cross-ref "B" and a MUMPS cross-ref "BS5" |
| Pointer chain | File 200.03 → File 4 (INSTITUTION) → File 4.014 via computed pointer |
| Global layout | `^DIC(200,` stores NEW PERSON; subscript structure is `(ien,field_group)` |
| FileMan convention | DINUM files have IEN = .01 value; list of DINUM files in VEHU: ... |
| XINDEX pattern | 1,204 routines reference `^DIC(200` — package breakdown: ... |
| Anomaly / inconsistency | File 8989.5 (PACKAGE) has 3 orphan entries with no routines |
| Tool behavior | FMQL returns 0 results for files >10000; appears to be a hardcoded limit |

**What does NOT go here:** implementation errors (build log), design decisions
(ADRs), or task tracking.

Entries are numbered `RF-NNN` with a monotonically increasing counter.

### 11.3 Structured output (`vista/export/data-model/` + `vista/export/code-model/`)

The research log is prose. The structured-output directories hold machine-
readable artifacts — the as-is extracted models of VistA's data and code.
Two sibling folders reflect the ADR-045 separation of concerns: PIKS
classification stays on the data side, routine/package/XINDEX analysis
stays on the code side, and the package is the native bridge.

**Data-model slice — `vista/export/data-model/`** (FileMan DD + PIKS):

| File | Generated by | Contents |
|---|---|---|
| `files.tsv` | `VMFILES` | FileMan file inventory — schema in §11.5.4 |
| `piks.tsv` | `VMPIKS` | Automated PIKS classifications |
| `piks-triage.tsv` | (manual) | Manual triage overrides |
| `field-piks.tsv` | `VMFPIKS` | Field-level PIKS with cross-PIKS flags |
| `vista-fileman-piks-comprehensive.csv` | (host script) | Joined comprehensive output |

**Code-model slice — `vista/export/code-model/`** (ADR-045 + XINDEX):

| File | Generated by | Contents |
|---|---|---|
| `routines.tsv` | `build_routine_inventory.py` | Per-routine inventory + static features |
| `packages.tsv` | `build_routine_inventory.py` | Per-package aggregates |
| `routine-calls.tsv` | `build_routine_calls.py` | Routine→routine edges (regex) |
| `routine-globals.tsv` | `build_routine_globals.py` | Routine→global edges (regex) |
| `package-data.tsv` | `build_package_data_inventory.py` | ZWR shipment inventory |
| `package-piks-summary.tsv` | `build_package_piks_summary.py` | Per-package PIKS distribution |
| `package-manifest.tsv` | `build_package_manifest.py` | Phase 6a bridge |
| `routines-comprehensive.tsv` | `build_routines_comprehensive.py` | Phase 6b bridge |
| `package-edge-matrix.tsv` | `build_package_edge_matrix.py` | Phase 6c cross-package edges |
| `vista-file-9-8.tsv` | `VMDUMP98` | File 9.8 ROUTINE dump |
| `rpcs.tsv` | `VMDUMP8994` | File 8994 REMOTE PROCEDURE |
| `options.tsv` | `VMDUMP19` | File 19 OPTION |
| `protocols.tsv` | `VMDUMP101` | File 101 PROTOCOL |
| `protocol-calls.tsv` | `build_protocol_calls.py` | Protocol ENTRY ACTION → routine |
| `xindex-{routines,errors,xrefs,tags}.tsv` | `VMXIDX` | XINDEX authoritative output |
| `xindex-validation.tsv` | `validate_against_xindex.py` | Regex-vs-XINDEX join |

**Project-level**: `RESEARCH.md` lives at `vista/export/RESEARCH.md`
(cross-cutting — RF-NNN entries cover both slices).

All listed files are git-tracked. Raw bake output in `export/dd-text/raw/`,
`export/dd-fmql/raw/`, etc. is gitignored. The two structured folders are
the curated, verified distillation.

### 11.4 Extraction pipeline

The bake pipeline (§6) produces raw dumps. The extraction pipeline turns
those raw dumps — plus direct DD interrogation — into the structured TSVs
in `data-model/` and `code-model/`. This is the bridge between "we ran
the exporters" and "we have a queryable model."

#### 11.4.1 Three-pass methodology

**Pass 0 — Automated extraction (machine).**
M routines in `vista/dev-r/` walk FileMan's own metadata globals and produce
complete, machine-generated inventories. These are exhaustive but unclassified.

| Routine | Reads | Writes | What it extracts |
|---|---|---|---|
| `VMFILES` | `^DIC`, `^DD` | `data-model/files.tsv` | All FileMan files: number, name, global root, field count, top-level vs. multiple, DINUM flag |
| `VMFIELDS` | `^DD(file,field,...)` | `data-model/fields.tsv` | All fields in all files: file, field#, name, type, pointer target, required flag, computed flag |
| `VMPTRS` | `^DD(file,field,0)`, `^DD(file,field,"V",...)` | `data-model/pointers.tsv` | All pointer relationships: source file.field → target file, pointer type (simple/variable/computed/implicit) |
| `VMXREFS` | `^DD(file,field,1,...)`, `^DD("IX",...)` | `data-model/xrefs.tsv` | All cross-references: file, field, xref name, type (regular/MUMPS/new-style/compound), kill logic |
| `VMGSTAT` | Actual globals (`^DPT`, `^DIC(200,`, etc.) | `data-model/globals.tsv` | Record counts, global size, subscript depth, first/last IEN per global |
| `VMPKGS` | `^DIC(9.4,...)`, MANIFEST.tsv | `code-model/packages.tsv` | Packages: namespace, name, routine count, file list, version |
| `VMCENSUS` | Global directory (`$ORDER`), `^DIC`, XINDEX output | `data-model/global-census.tsv` | ALL globals: FileMan coverage status, undocumented branches, referencing routines, package ownership. See §11.4.4 |

These routines are idempotent — rerun them anytime to refresh the baseline.
They produce TSV (not JSON) for grep/awk/sort friendliness and git-diff
readability.

**Pass 1a — Automated PIKS heuristics (machine, routine: `VMPIKS`).**
Apply deterministic rules to auto-classify files before any human review.
The heuristics are ordered by confidence tier. Higher tiers override lower.
Each classified file gets a `piks_method` value recording which heuristic
fired.

**Tier 1 — Certain (structural identity)**

| # | Rule | PIKS | Rationale |
|---|---|---|---|
| H-01 | Global root = `^DPT(` | P | IS the PATIENT file/subfile |
| H-02 | Global root = `^DD(` or file number < 2 | S | FileMan's own DD metadata |
| H-03 | File IS File 2 | P | PATIENT file itself |
| H-04 | File IS File 4 | I | INSTITUTION file itself |
| H-05 | Subfile of an already-classified file | (inherit) | Subfiles inherit parent PIKS |

**Tier 2 — High confidence (pointer to anchor files)**

| # | Rule | PIKS | Rationale |
|---|---|---|---|
| H-06 | Has a pointer field targeting File 2 (PATIENT) | P | Per-patient data — file stores records keyed or linked to a patient |
| H-07 | Has a pointer field targeting File 2 AND field name contains "PATIENT" or "DFN" | P | Explicit patient-linked file |
| H-08 | Has a pointer field targeting File 4 (INSTITUTION) but NOT File 2 | I | Facility-linked, not patient-linked |
| H-09 | Has a pointer field targeting File 200 (NEW PERSON) but NOT File 2 and NOT File 4 | S | User/access-linked system data |

Note: H-06 dominates H-08 and H-09. If a file points to BOTH File 2 and
File 4, it is P (patient data that references a facility). Patient always wins.

**Tier 3 — High confidence (global root patterns)**

| # | Rule | PIKS | Globals |
|---|---|---|---|
| H-10 | Global root matches known Patient globals | P | `^LR(`, `^GMR(`, `^TIU(`, `^OR(`, `^PS(52`, `^PS(55`, `^AUPN`, `^PXRM(800`, `^SRF(` |
| H-11 | Global root matches known Institution globals | I | `^SC(`, `^DIC(4`, `^DIC(40.8`, `^DIC(42`, `^DG(43` |
| H-12 | Global root matches known Knowledge globals | K | `^ICD(`, `^ICPT(`, `^LEX(`, `^PXD(`, `^PS(50`, `^ORD(101.4`, `^DIC(9999999` |
| H-13 | Global root matches known System globals | S | `^XTV(`, `^XTMP(`, `^%ZTER(`, `^XMB(`, `^DIC(19`, `^DIC(9.4`, `^DIC(3.5` |

**Tier 4 — Moderate confidence (package namespace)**

| # | Rule | PIKS | Namespaces |
|---|---|---|---|
| H-14 | File belongs to a Patient-domain package | P | DG (Registration), GMRV (Vitals), TIU (Notes), OR (Orders), PS (Pharmacy-patient), LR (Lab-patient), RA (Radiology-patient), SR (Surgery), PX (PCE) |
| H-15 | File belongs to an Institution-domain package | I | SD (Scheduling-facility), DG (ADT-facility subset), AG (Beneficiary Travel) |
| H-16 | File belongs to a Knowledge-domain package | K | ICD, LEX (Lexicon), PXRM (Reminders-definitions), PS (Pharmacy-drug file), LR (Lab-test defs), RA (Rad-procedure defs) |
| H-17 | File belongs to a System-domain package | S | XU (Kernel), XT (Toolkit), DI (FileMan), XM (MailMan), HL (HL7 infrastructure), A (General utilities) |

Package namespace is determined by matching the file to `packages.tsv` via
the PACKAGE file (9.4). Some packages span PIKS categories (e.g., Pharmacy
has both P and K files) — namespace alone is moderate confidence.

**Tier 5 — Moderate confidence (pointer topology)**

| # | Rule | PIKS | Rationale |
|---|---|---|---|
| H-18 | `pointer_in` >= 10 AND `pointer_out` <= 2 AND no pointer to File 2 | K | Reference/lookup table pattern — many files point TO it, it points to few |
| H-19 | `pointer_in` = 0 AND `pointer_out` = 0 AND `record_count` < 100 | S | Isolated low-volume file — typically config or meta |

**Tier 6 — Low confidence (name patterns)**

| # | Rule | PIKS | Name contains |
|---|---|---|---|
| H-20 | File name suggests Knowledge | K | "TYPE", "CATEGORY", "CLASS", "CODE", "DEFINITION", "TEMPLATE", "REMINDER", "RULE" |
| H-21 | File name suggests System | S | "PARAMETER", "OPTION", "KEY", "DEVICE", "ERROR", "TASK", "BULLETIN", "LOG", "AUDIT" |
| H-22 | File name suggests Institution | I | "INSTITUTION", "FACILITY", "DIVISION", "LOCATION", "WARD", "CLINIC", "SERVICE" |
| H-23 | File name suggests Patient | P | "PATIENT", "VISIT", "ENCOUNTER", "ADMISSION", "EPISODE" |

Name heuristics fire only if no higher-tier rule matched. They are the
weakest signal — "LOCATION" could be a patient's location (P) or a
facility location (I).

**Tier 7 — Moderate confidence (design-time mutability signals)**

FileMan encodes the architect's intent about how data should be treated —
whether it's audited, append-only, or deletion-protected. These structural
signals in `^DD` are proxies for the mutability characteristics that
distinguish Patient data (immutable, append-only, audit-required) from
other categories (mutable, replaceable, no audit trail). They do not
require runtime change data — they work on a static sandbox.

| # | Rule | Signal | PIKS | Rationale |
|---|---|---|---|---|
| H-24 | File has ≥3 fields with audit flag enabled in `^DD(file,field,"AUDIT")` | Audit density | P | High audit density = data with regulatory change-tracking requirements; characteristic of clinical records |
| H-25 | File's `.01` field is DATE/TIME type AND file is a subfile (multiple) | Date-keyed event subfile | P | VistA's standard pattern for longitudinal clinical data: each encounter/event is an append-only subfile entry keyed by date |
| H-26 | File has deletion restrictions (`^DD(file,0,"DEL")` or equivalent flag) | No-delete | P | Patient records cannot be deleted — only amended with audit trail |
| H-27 | File has ≥1 field named "DATE ENTERED" or "DATE/TIME ENTERED" or "DATE CREATED" | Creation timestamp | P or I | Files designed to track when records were created; common in clinical and administrative records |
| H-28 | File has WRITE ACCESS or field-level WRITE ACCESS restrictions in DD | Write-restricted | P or S | Tight write controls suggest protected or operationally sensitive data |
| H-29 | File has NO audit flags, NO delete restrictions, NO date-entered fields, AND `record_count` < 500 | Freely mutable, small | K or S | Reference tables and config files — designed to be edited without ceremony |

These heuristics fire at moderate confidence because the signals are
suggestive, not definitive. A System file tracking error logs (File 3.075)
may have date-keyed entries (H-25) without being Patient data. Combine
with other tiers for best results.

**Why design-time signals beat runtime measurement:**
In a VEHU sandbox, all data has the same change rate (zero — no clinical
activity). Runtime rate-of-change requires a live production system. But
the DD's audit flags, delete restrictions, and date-keyed subfile patterns
encode the **architect's intent** about mutability — a stronger signal
that works without any runtime data.

**Tier 8 — Moderate confidence (structural composition)**

The mix of field types, subfile depth, and file width are distinctive
signatures. These require `fields.tsv` data (Pass 0 must complete first).

| # | Rule | Signal | PIKS | Rationale |
|---|---|---|---|---|
| H-30 | File has subfile depth ≥ 3 (multiples within multiples within multiples) | Deep hierarchy | P | Longitudinal clinical records accumulate data in nested subfiles — vitals within visits within encounters. Knowledge and System files are flat. |
| H-31 | File has ≥ 3 WORD PROCESSING fields | Narrative density | P | Clinical files have notes, descriptions, reports. Knowledge tables and config files almost never have word processing fields. |
| H-32 | > 50% of fields are SET OF CODES type | Enumeration density | K | The file defines categorical values — it IS a terminology/classification artifact. |
| H-33 | File has > 50 fields AND not yet classified by higher tiers | Wide file | P or I | Large field counts indicate complex real-world entities (patients, facilities). Knowledge tables are narrow. |
| H-34 | DINUM file (`is_dinum` = Y) AND `record_count` < 1000 | DINUM + small | K | DINUM files (IEN = .01 value) with small record sets are enumerated reference data — code tables, type definitions. |
| H-35 | File has ≥ 3 COMPUTED or MUMPS-type fields | Computed density | S | Files with heavy programmatic content are infrastructure — computed values, executable data, transform logic. |

**Tier 9 — Graph propagation (runs AFTER single-pass tiers)**

These heuristics use the PIKS assignments from Tiers 1–8 to classify
remaining unclassified files based on their position in the pointer graph.
Run iteratively until no new classifications are produced.

| # | Rule | Signal | PIKS | Rationale |
|---|---|---|---|---|
| H-36 | > 70% of this file's pointer targets are already classified P | Patient neighborhood | P | A file that overwhelmingly points to Patient files is itself patient data — it lives in the patient data cluster. |
| H-37 | > 70% of files pointing TO this file are already classified P | Consumed by patient data | K or I | Many Patient files reference this file, but it doesn't point back — it's a lookup/reference table used by clinical records. Cross-check with H-18 (pointer topology). |
| H-38 | This file has pointers to files in ≥ 3 distinct PIKS categories | Cross-PIKS bridge | P | Clinical transaction files (orders, encounters, prescriptions) connect Patient, Institution, Knowledge, and System. The act of care itself bridges all categories — bridge files are Patient data. |
| H-39 | File has 0 pointers in AND 0 pointers out (isolated node) | Orphan | S | Completely disconnected files are typically obsolete system metadata, error logs, or temporary structures. |
| H-40 | File has pointers only to files classified K (and ≥ 2 such pointers) | Knowledge-internal | K | A file that only references other Knowledge files is itself part of the knowledge layer — sub-terminology, cross-walk table, or classification hierarchy. |

Propagation is powerful: after Tiers 1–8 classify ~70–80% of files, the
graph neighborhood of unclassified files is mostly resolved. Two to three
propagation iterations typically classify another 10–15% of remaining files.

**Propagation order**: H-38 (bridge → P) fires first, then H-36/H-37/H-40,
then H-39 (orphan → S) as the catch-all. Patient-wins rule applies if
propagation heuristics conflict.

**Tier 10 — Moderate confidence (cross-reference signals)**

Cross-references encode how a file is searched and indexed — which
dimensions matter for retrieval. The xref names, counts, and trigger
targets are PIKS-diagnostic. Requires `xrefs.tsv` data.

| # | Rule | Signal | PIKS | Rationale |
|---|---|---|---|---|
| H-41 | File has an xref named "ADFN", "DFN", or "ADFN2" | Patient-identity xref | P | The file is indexed by patient DFN — it exists to be looked up per-patient. Certain signal, same strength as H-06. |
| H-42 | File has a trigger xref whose target global is a known P global (`^DPT(`, `^LR(`, etc.) | Trigger writes patient data | P | Trigger xrefs write data into another file's global on SET/KILL. If the target is a Patient global, this file participates in the patient data lifecycle. |
| H-43 | File has ≥ 8 cross-references | High xref density | P or I | Clinical and administrative files need fast lookup across many dimensions (name, SSN, date, ward, provider, status). Knowledge tables typically have only a "B" xref. |
| H-44 | File has exactly 1 xref AND it is named "B" AND `record_count` < 5000 | Minimal index + small | K | Classic reference/lookup table — only needs name lookup, few records. |

**Tier 11 — Low confidence (file-level access codes + number ranges)**

File-level access strings from `^DIC(file,0)` encode who can read, write,
create, and delete records. These are set by the package developer to
match the intended audience. File number ranges follow loose VistA
conventions. Both are weak individually but useful for unmatched files.

| # | Rule | Signal | PIKS | Rationale |
|---|---|---|---|---|
| H-45 | File WRITE ACCESS or DELETE ACCESS = `@` (programmer only) | Locked-down | S | Only programmers can modify — system infrastructure, not end-user data. |
| H-46 | File has LAYGO ACCESS with no restrictions (open LAYGO) AND `pointer_in` > 5 | Open-create + widely referenced | K | Anyone can add entries and many files point to it — reference table that grows by convention (e.g., local code additions). |
| H-47 | File number in 9000000–9000099 range | PCE/IHS file range | P | Patient Care Encounter and Indian Health Service patient data files. |
| H-48 | File number in 9999999.x range | Lexicon file range | K | Lexicon Utility terminology files. |
| H-49 | File number < 2 AND file number ≥ 0 (excluding file 0 and 1 already caught by H-02) | FileMan low-number meta | S | FileMan internal files: .1 (DATA TYPE), .11 (INDEX), .2 (PRINT TEMPLATE), .31 (KEY), .4 (SORT TEMPLATE), .401 (FORM), etc. |

**Tier 12 — Low confidence (template and form associations)**

Files with many associated templates and forms are files that humans
actively interact with. Template count is a proxy for operational
importance. Requires querying File .2 (PRINT TEMPLATE), File .402
(INPUT TEMPLATE), and File .403 (FORM) for references to each file.

| # | Rule | Signal | PIKS | Rationale |
|---|---|---|---|---|
| H-50 | File has ≥ 5 associated print templates (in File .2) | High report demand | P or I | Heavily reported files are clinically or administratively important — people need many views of this data. |
| H-51 | File has ≥ 2 associated input templates (in File .402) | Active data entry | P | Multiple data entry pathways = file is central to a workflow. Clinical files have many input contexts (admit, transfer, discharge, etc.). |
| H-52 | File has ≥ 1 associated ScreenMan form (in File .403) | Dedicated UI | P or I | Files with dedicated screen forms are important enough to warrant UI investment — typically patient or facility management. |

**Automated property inference**

Data properties can also be partially inferred alongside PIKS:

| Property | Inference rule |
|---|---|
| `volume` | Directly from `record_count`: <1000 = `reference`, 1000–100000 = `moderate`, >100000 = `high-volume` |
| `sensitivity` | P → `protected`; I → `operational` (default, review files with staff PII); K → `public`; S → `operational` |
| `volatility` | `record_count` = 0 or file is definition/template → `static`; P + high-volume → `dynamic`; S + ephemeral global → `ephemeral`; else → `slow` |
| `portability` | K → `universal` (default); I → `site-specific`; P → `site-specific`; S → `site-specific` |

**`VMPIKS` output**

The routine writes results to `files.tsv`, adding/updating these columns:

| Column | Value |
|---|---|
| `piks` | Classified category |
| `piks_method` | Heuristic that fired: `H-01` through `H-52`, or `manual*` |
| `piks_confidence` | `certain` / `high` / `moderate` / `low` |
| `piks_evidence` | The specific input data that triggered the rule (see evidence format below) |
| `piks_secondary` | Set by tier 2 rules when multiple anchor files are pointed to |
| `volatility` | Inferred value |
| `sensitivity` | Inferred value |
| `portability` | Inferred value |
| `volume` | Inferred from `record_count` |

Files that match NO heuristic get `piks` = blank, `piks_method` = `none`,
`piks_confidence` = blank, `piks_evidence` = blank. These are the files
requiring human review.

**Evidence format (`piks_evidence` column)**

Every classification — machine or human — records WHY it was made, not
just which rule fired. The evidence string makes each classification
independently auditable: you can verify it without re-running the
classifier.

| Method type | Evidence format | Example |
|---|---|---|
| H-01 | `global=<root>` | `global=^DPT(` |
| H-02 | `global=<root>` or `file#=<n>` | `file#=.11` |
| H-06 | `field=<n> points to file 2` | `field=.02 points to file 2` |
| H-07 | `field=<n> "<name>" points to file 2` | `field=.02 "PATIENT" points to file 2` |
| H-08 | `field=<n> points to file 4; no ptr to file 2` | `field=.06 points to file 4; no ptr to file 2` |
| H-10–H-13 | `global=<root> in <category>-list` | `global=^LR( in P-list` |
| H-14–H-17 | `package=<ns> (<name>)` | `package=DG (Registration)` |
| H-18 | `ptr_in=<n> ptr_out=<n>` | `ptr_in=47 ptr_out=1` |
| H-24 | `audit_fields=<n>: <field_list>` | `audit_fields=5: .01,.03,.09,.1,.13` |
| H-25 | `.01 type=DATE; subfile of <parent>` | `.01 type=DATE; subfile of 2` |
| H-30 | `subfile_depth=<n>` | `subfile_depth=4` |
| H-31 | `wp_fields=<n>: <field_list>` | `wp_fields=3: 1,2,11` |
| H-34 | `dinum=Y record_count=<n>` | `dinum=Y record_count=247` |
| H-36 | `<n>/<total> targets classified P` | `5/6 targets classified P` |
| H-38 | `targets span <categories>` | `targets span P,I,K` |
| H-41 | `xref=<name> on field <n>` | `xref=ADFN on field .01` |
| H-43 | `xref_count=<n>` | `xref_count=12` |
| H-45 | `write_access=@ delete_access=@` | `write_access=@ delete_access=@` |
| H-47–H-49 | `file#=<n> in range <range>` | `file#=9000001 in range 9000000-9000099` |
| H-50–H-52 | `<type>_templates=<n>` | `print_templates=7` |
| `manual` | `RF-NNN` | `RF-023` |
| `manual-vestigial` | `RF-NNN; record_count=0 field_count=<n>` | `RF-045; record_count=0 field_count=3` |
| `manual-package` | `RF-NNN; package=<ns>` | `RF-046; package=XX` |

Not every heuristic is listed — the pattern is consistent: name the
specific data values that matched the rule's condition. A reviewer
reading `H-06` + `field=.02 points to file 2` can verify the
classification in seconds by checking `^DD(file,.02,0)`.

**Pipeline state management**

The TSV files in `data-model/` + `code-model/` are not just output — they are the
**working state** of the classification pipeline. Each tool reads them,
updates its owned columns, and writes them back. The pipeline is
designed for repeated runs where unknowns decrease monotonically and
human work is never lost.

*Column ownership:*

| Owner | Columns | Re-run behavior |
|---|---|---|
| Extraction routines (`VM*`) | `file_number`, `file_name`, `global_root`, `parent_file`, `field_count`, `pointer_in`, `pointer_out`, `pointer_in_files`, `pointer_out_files`, `record_count`, `is_dinum` | **Always refresh.** Structural data may change after VEHU-M update or snapshot restore. |
| Heuristic classifier (`VMPIKS`) | `piks`, `piks_method`, `piks_confidence`, `piks_secondary`, `volatility`, `sensitivity`, `portability`, `volume` | **Write only if `piks_method` is blank, `none`, or starts with `H-`.** Never overwrite `manual*` values. |
| Human analyst | `piks` (override), `piks_method` = `manual*`, `subdomain`, all annotation TSVs | **Never machine-touched.** Only a human with `--force` can reset. |

*State progression per file:*

```
extracted ─── VMPIKS ───→ classified ─── human ───→ annotated ─── validation ───→ verified
    │                         │                         │                            │
    │  structural data        │  PIKS + properties      │  subdomain + semantic      │  VMVAL* passes
    │  from VM* routines      │  from heuristics        │  types + entity groups     │  all green
    │                         │  or manual triage        │                            │
    └── re-extractable ◄──────┴── monotonic ◄───────────┴── cumulative ◄─────────────┘
```

*Run modes:*

| Mode | Command | What happens |
|---|---|---|
| **Fresh** | `VMPIKS` on first run | All heuristics fire. ~85–95% of files classified. |
| **Incremental** | `VMPIKS` after human triage | Re-runs tiers 1–8 on unclassified files only. Then runs tier 9 (propagation) using both machine and manual labels as seeds. Newly classified files may seed further propagation. |
| **Re-extract** | `VM*` routines after VEHU-M update | Refreshes structural columns. Does NOT touch PIKS columns. Then `VMPIKS` re-evaluates `H-*` classified files against new structural data (a pointer count change might flip a heuristic). Manual classifications preserved. |
| **Force** | `VMPIKS --force` | Re-evaluates ALL files including manual. Use only when heuristic rules have changed substantially. Logs all overrides. |

*Monotonic guarantee:*

After each run, the count of unclassified files can only decrease (or
stay the same). Specifically:

1. Extraction never removes a PIKS classification — it only refreshes
   structural data.
2. `VMPIKS` only writes to blank or `H-*` classified files — it never
   clears a classification.
3. Manual classifications are immutable unless `--force` is used.
4. Tier 9 propagation uses ALL prior classifications (machine + manual)
   as seeds, so human triage of 10 files can cascade to classify 20 more
   neighbors on the next run.

*Run log:*

Each `VMPIKS` run appends to `data-model/vmpiks-runs.log`:

```
2026-04-20T14:30:00Z  mode=incremental  total=9247  newly_classified=142  re_evaluated=0  unchanged=9105  unresolved=48
2026-04-21T10:00:00Z  mode=incremental  total=9247  newly_classified=31   re_evaluated=0  unchanged=9216  unresolved=17
```

This log is the evidence trail for monotonic progress — every run
shows the unresolved count trending toward zero.

**Pass 1b — Human review of heuristic output.**

Step 1: Verify automated results (quick scan, not exhaustive):

| Task | Focus |
|---|---|
| Spot-check `certain` and `high` confidence | Scan for obvious errors in H-06 through H-13 |
| Review all `moderate` and `low` confidence files | Confirm or reclassify; record overrides as RF-NNN |
| Check property anomalies (§11.5.2, "Interaction between PIKS and properties") | A `K` file that is `dynamic` + `high-volume` + `protected` is likely misclassified |

Step 2: Triage unmatched files (`piks_method` = `none`).

After 52 heuristics, remaining files resist classification for specific
reasons. Triage them by type rather than reviewing each in isolation.

**Triage category A — Empty/vestigial files.**
Files with `record_count` = 0, `field_count` < 5, no templates, no xrefs
beyond "B". These are decommissioned, never-populated, or placeholder files.

| Action | Classification |
|---|---|
| Verify the file has no active globals: `$D(^globalroot)` = 0 | Classify as S with `piks_method` = `manual-vestigial` |
| If globals exist despite `record_count` = 0, investigate | May be a VMGSTAT bug or non-standard storage |
| Record the batch in a single RF-NNN entry | "RF-045: N vestigial files classified S — zero records, minimal DD" |

Expected yield: classifies 30–50% of unmatched files in one batch.

**Triage category B — Package-identifiable but namespace not in H-14–H-17.**
Files whose package can be determined (from `packages.tsv` or by namespace
prefix in the file name or global root) but whose package wasn't in the
known namespace lists. These are packages we haven't mapped yet.

| Action | Classification |
|---|---|
| Look up the package name in `packages.tsv` or `^DIC(9.4)` | Determine the package's purpose |
| Classify the entire package at once, not file-by-file | Add the namespace to the appropriate H-14–H-17 list for future runs |
| Record as RF-NNN | "RF-046: Package XX (Example Package) classified as K — 14 files" |

Expected yield: classifies another 20–30% of unmatched files. Also
improves the heuristic for future runs.

**Triage category C — Mixed-signal files.**
Files that triggered multiple heuristics pointing to different PIKS
categories, or that have roughly equal pointer counts to P, K, and I
anchor files. These are genuinely cross-cutting.

| Signal pattern | Resolution |
|---|---|
| Points to File 2 AND File 80 (ICD) in roughly equal proportion | P — the file is clinical data that references terminology. Patient always wins. |
| Points to File 4 AND File 200 but not File 2 | I — facility data that references staff. Institution dominates System when both are present. |
| No anchor pointers, but high xref count + date-keyed subfiles | P — structural signals override the absence of pointer signals. |
| No anchor pointers, moderate xrefs, moderate fields, moderate records | **Inspect the file name and help text in `^DD(file,0)`**. This is where human domain knowledge is unavoidable. |

For the last case — truly ambiguous files with no strong signals — use
the **5-second rule**: read the file name, read the first 3 field names.
If a competent VistA user would say "that's patient data" in 5 seconds,
it's P. If they'd say "that's a code table", it's K. Record each as
RF-NNN with the reasoning.

**Triage category D — Genuinely cross-cutting files.**
A small number of files legitimately serve two PIKS audiences roughly
equally. These are not misclassified — they are boundary files.

| Action | Classification |
|---|---|
| Assign primary PIKS based on the **data sensitivity** rule: P > I > K > S | Higher sensitivity wins primary |
| Assign `piks_secondary` for the secondary audience | |
| Record as RF-NNN with explicit reasoning | "RF-047: File 350 (IB ACTION TYPE) — primary K (defines billing actions), secondary P (actions reference patient encounters)" |

Expected count: < 5% of top-level files are genuinely cross-cutting.

**Triage category E — Unresolvable without runtime data.**
Files where the DD structure provides no useful signal and the file name
is opaque. These are rare after exhausting all other categories.

| Action | Classification |
|---|---|
| Mark as `piks` = `U` (unresolved), `piks_method` = `manual-unresolved` | Do not force a classification without evidence |
| Add to `anomalies.tsv` with details | Future sessions can revisit with more context |
| Set a threshold: if unresolved files < 2% of total, accept and move on | Diminishing returns — don't block Pass 2 for a handful of outliers |

**Summary: expected Pass 1b triage flow**

```
Unmatched files (piks_method = none)   ~5-10% of top-level files
  ├── A. Empty/vestigial → S           ~30-50% of unmatched
  ├── B. Package-identifiable → batch  ~20-30% of unmatched
  ├── C. Mixed-signal → resolve        ~15-25% of unmatched
  ├── D. Cross-cutting → dual PIKS     ~5% of unmatched
  └── E. Unresolvable → U             ~1-5% of unmatched
                                        ────────────────
  Net: < 1% of all files remain unresolved
```

Every human classification gets an RF-NNN entry. Every new package-to-PIKS
mapping gets added back to the H-14–H-17 heuristic lists so `VMPIKS`
improves on each run. This is a **learning classifier** — the heuristic
tables grow with each triage session.

Goal: 100% of top-level files classified (PIKS + properties), with < 2%
marked `U` (unresolved). Subfiles inherit. Progress tracked in
`coverage.json` → `piks_classification.coverage_pct`.

**Pass 2 — Subdomain annotation (detailed modeling).**
Within each PIKS category, add finer meaning:

| Annotation | What it adds | Where recorded |
|---|---|---|
| Subdomain assignment | Finer grouping within PIKS (e.g., "Pharmacy" within Patient) | `files.tsv` → `subdomain` column, `domains.tsv` |
| Semantic type | What a field represents beyond its FM type (person name, facility code, clinical narrative, ICD code, ...) | `semantic-types.tsv` |
| Canonical relationship | Which pointer is the primary relationship vs. ancillary/lookup | `pointers.tsv` (annotated column) |
| Entity grouping | Which multiples should be understood as sub-entities vs. repeating fields | `entity-groups.tsv` |
| Anomaly flag | Inconsistencies between DD metadata and actual global structure | `anomalies.tsv` |

Every human annotation gets an RF-NNN research log entry recording the
evidence and reasoning. Do not start Pass 2 before PIKS classification
is substantially complete (>80% of top-level files).

#### 11.4.2 FileMan DD globals reference

The extraction routines read these globals. This is the source-of-truth
mapping for anyone writing or reviewing the extraction code.

| Global | Contents | Key subscript patterns |
|---|---|---|
| `^DD(file,0)` | File header | `piece 1` = name, `piece 4` = field count |
| `^DD(file,field,0)` | Field definition | `piece 1` = name, `piece 2` = type/pointer spec, `piece 3` = value constraints |
| `^DD(file,field,1,xref,...)` | Old-style cross-references | Type, set/kill logic |
| `^DD(file,field,3)` | Help text | Input transform description |
| `^DD(file,field,4)` | Computed expression | MUMPS code for computed fields |
| `^DD(file,field,"V",n,0)` | Variable pointer definition | Target file, prefix, order |
| `^DD(file,.01)` | .01 field (primary key) | Always exists; defines the file's identity |
| `^DD("IX",...)` | New-style cross-references (FM 22+) | Cross-file and compound indexes |
| `^DD(file,field,"AUDIT")` | Field audit flag | If set, changes to this field are logged to AUDIT file (1.1) |
| `^DD(file,0,"DEL")` | File deletion control | Restrictions on deleting records from this file |
| `^DD(file,field,9)` | Read/write access | Field-level access restrictions (read access, write access, delete access) |
| `^DIC(file,0)` | File dictionary entry | `piece 1` = name, `piece 2` = global root, `piece 3` = attributes, `piece 5` = READ ACCESS, `piece 6` = WRITE ACCESS, `piece 7` = DELETE ACCESS, `piece 8` = LAYGO ACCESS |
| `^DIC(9.4,...)` | PACKAGE file | Package names, namespaces, versions |
| `^DIPT(.2,...)` | PRINT TEMPLATE file | Template name, associated file number — count per file for H-50 |
| `^DIE(.402,...)` | INPUT TEMPLATE file | Template name, associated file number — count per file for H-51 |
| `^DIST(.403,...)` | FORM file (ScreenMan) | Form name, associated file number — count per file for H-52 |

#### 11.4.3 Pointer type taxonomy

FileMan has several pointer mechanisms, each requiring different extraction
logic. The conceptual model must distinguish them because they have different
semantic strength.

| Type | DD signature | Example | Semantic strength |
|---|---|---|---|
| Simple pointer | `P<file>#` in field type | File 2, field .104 → File 4 | Strong — declared, enforced |
| Variable pointer | `V` type + `"V"` subnode | File 120.5 field .02 → File 2 or File 200 | Strong — declared, multiple targets |
| Computed pointer | Field type includes `C` | MUMPS code returns IEN into target | Weak — logic-dependent, may be conditional |
| Implicit pointer | No DD declaration | Code does `S X=^DPT(DFN,...)` | None — convention-only, discoverable via XINDEX |
| DINUM link | File attribute `"DD"` | File 2 subfile 2.01 — IEN = parent IEN | Structural — parent-child identity |
| Backward pointer | Triggered cross-ref writes to another file | File 200 xref sets `^VA(200,` | Derived — exists as side effect |

The extraction routine `VMPTRS` captures the first four from the DD.
Implicit pointers require XINDEX analysis (phase 1 of bake). Backward
pointers require cross-reference analysis (`VMXREFS`).

#### 11.4.4 Non-FileMan globals

FileMan does not describe all data in VistA. **Pharmacy and Lab — two of
VistA's largest and most clinically critical packages — write substantial
amounts of operational patient care data directly to globals, bypassing
FileMan's DBS API entirely.** This is by design, not by accident:
high-volume dispensing, order verification, specimen processing, and
result accumulation need performance that FileMan's journaling and
cross-reference overhead cannot provide. Other packages (Integrated
Billing, Order Entry, Radiology) use similar patterns to varying degrees.

This is not a minor gap. It is a **major body of core Patient data** that
the DD-based extraction pipeline (§11.4.1) cannot see. Any PIKS
classification that only walks `^DD` will systematically undercount
Patient data in exactly the packages where the most clinically important
data lives.

**Three categories of FileMan coverage:**

| Category | Description | Example | Detection |
|---|---|---|---|
| **Fully FileMan** | Global has `^DIC` entry; all subscript branches described in `^DD` | `^DPT(` (File 2, PATIENT) | `^DIC` lookup succeeds; all data reachable via DBS API |
| **Partially FileMan** | `^DIC` entry exists, `^DD` describes some subscripts, but routines use undocumented branches | `^PS(55,DFN,"P",n,...)` — File 55 is in FileMan but the "P" subscript tree is package-maintained | `^DIC` lookup succeeds; `$ORDER` walk reveals subscripts not in `^DD` |
| **Non-FileMan** | No `^DIC` entry; global is entirely package-managed | Package scratch globals, legacy index globals, direct-write data stores | `^DIC` lookup fails; global exists in database |

**Known major non-FileMan data areas:**

| Package | Globals | What's stored outside `^DD` | Volume |
|---|---|---|---|
| Pharmacy (PS) | `^PS(55,DFN,"P"`, `^PSRX(`, `^PS(52.6,` etc. | Active prescriptions, dispensing history, IV solutions, unit dose, pending orders | High — every prescription action |
| Lab (LR) | `^LR(`, `^LRO(`, `^LA(` etc. | Accession records, verified results, specimen tracking, cumulative results, interim reports | High — every lab order/result |
| Integrated Billing (IB) | `^IBA(`, `^IBE(` | Claims data, billing events, insurance verification | Moderate-high |
| Order Entry (OR) | `^OR(100,` non-DD branches | Order action tracking, notification state | Moderate |
| Radiology (RA) | `^RADPT(`, `^RA(` | Exam tracking, report text, procedure status | Moderate |

This data is overwhelmingly Patient data (PIKS = P). It represents a
large fraction of the clinical record — often MORE operationally active
than the FileMan-described portions. Any PIKS classification that only
walks `^DD` will miss the most active clinical data in the system.

**`VMCENSUS` — global census routine (two phases)**

Runs before the full extraction pipeline to scope the non-FileMan
problem before committing to a detailed inventory.

**Phase 1: Recon (fast — minutes)**

Enumerate every global root in the database, match against `^DIC`,
count first-level entries. No deep subscript walking. Goal: answer
"how big is this problem?" in under 5 minutes.

| Step | What it does | How | Cost |
|---|---|---|---|
| 1 | Enumerate all global names | `$ORDER(^$GLOBAL(""))` loop | Seconds — just names |
| 2 | Match each to `^DIC` | For each name, scan `^DIC(file,0)` piece 2 for matching global root | Seconds — `^DIC` is small |
| 3 | Count first-level entries | For unmatched globals: `$ORDER` loop at depth 1, count nodes | Minutes — depth 1 only, no recursion |
| 4 | Tag known scratch globals | `^TMP(`, `^UTILITY(`, `^XTMP(`, `^%ZOSF(` → ephemeral, exclude from "real" count | Pattern match |
| 5 | Group unmatched by prefix | First 2–3 chars of global name → package cluster (PS=Pharmacy, LR=Lab, etc.) | String ops |
| 6 | DFN spot-check | For top 20 unmatched by size: check if first-level subscripts are sequential integers matching `^DPT` IEN range | `$ORDER` first 10 subscripts + `$DATA(^DPT(sub))` |

**Recon output: `data-model/global-recon.txt`** (human-readable report,
not a TSV — this is a scoping decision, not data):

```
VMCENSUS Recon — 2026-04-20T14:00:00Z

Global directory:
  Total global roots:           1,847
  Matched to ^DIC (FileMan):    1,203   (65.1%)
  Unmatched:                      644   (34.9%)

Unmatched breakdown:
  Scratch/temp (^TMP, ^XTMP, ^UTILITY):   12 roots,  6,331,459 nodes  ← exclude
  Persistent non-FM:                      632 roots,  2,847,102 nodes  ← scope this

Persistent non-FM by package prefix:
  PS  (Pharmacy)       187 roots   1,204,338 nodes   42.3%
  LR  (Lab)             94 roots     847,221 nodes   29.8%
  IB  (Integrated Billing) 43 roots  312,108 nodes   11.0%
  OR  (Order Entry)     28 roots     201,442 nodes    7.1%
  (other < 5%)         280 roots     281,993 nodes    9.9%

DFN correlation (top 10 persistent non-FM by size):
  ^PS(55,"P"    1,204,338 nodes  DFN-indexed=YES  → Patient data
  ^LR(63.04     847,221 nodes   DFN-indexed=YES  → Patient data
  ^IBA(355      312,108 nodes   DFN-indexed=YES  → Patient data
  ^ORD(100.98   201,442 nodes   DFN-indexed=NO   → likely Knowledge/System
  ...

Assessment:
  Scratch globals are high-volume but irrelevant (exclude from PIKS scope).
  Persistent non-FM is dominated by Pharmacy + Lab patient data.
  ~80% of persistent non-FM volume is DFN-indexed → Patient.
  Full census (Phase 2) required for all 632 persistent non-FM globals.
```

**Decision gate after recon:**

The recon scopes the work, it does not gate whether to do it. Pharmacy
and Lab non-FM data is expected to be substantial on every VistA system.
Phase 2 always runs — the recon determines HOW to prioritize it.

| Recon finding | Phase 2 prioritization |
|---|---|
| PS/LR/IB/RA prefixes dominate unmatched volume | Start Phase 2 with these packages — they are known Patient data producers. Batch-classify DFN-indexed globals as P. |
| Significant volume in unexpected prefixes | Investigate before classifying — may reveal packages not in the known namespace lists. |
| Scratch globals dominate raw count | Exclude from Phase 2 scope; note in recon report but do not classify. |
| DFN-indexed percentage | High percentage confirms Patient data volume. Low percentage means more non-patient non-FM data than expected — investigate. |

**Phase 2: Full census (thorough — may take hours on large databases)**

Scoped to persistent non-FM globals (scratch/temp excluded). Always runs
because Pharmacy and Lab non-FM data is a guaranteed substantial
workstream on any VistA system.

| Step | What it does | How | Cost |
|---|---|---|---|
| 1 | Deep subscript walk | For each persistent non-FM global: walk depth 2–3, record subscript patterns | Minutes to hours depending on volume |
| 2 | Partial-FM detection | For `^DIC`-matched globals: compare observed subscripts to `^DD` field list, flag undocumented branches | Moderate — requires cross-referencing |
| 3 | XINDEX cross-reference | For each non-FM global: find routines that SET/KILL it, map to packages | Requires XINDEX baseline (bake phase 1) |
| 4 | Write `global-census.tsv` | Full per-global detail | I/O only |

**`global-census.tsv`** — one row per global root

| Column | Type | Description |
|---|---|---|
| `global_root` | string | Global reference (e.g., `^PS(55,`) |
| `fm_file` | decimal | FileMan file number if `^DIC` match; blank if non-FM |
| `fm_coverage` | enum | `full-fm` / `partial-fm` / `non-fm` |
| `undoc_branches` | string | Pipe-delimited list of subscript branches not in `^DD` (for partial-fm) |
| `record_count` | integer | Top-level entry count |
| `subscript_depth` | integer | Maximum subscript depth observed |
| `sample_subscripts` | string | First 3 subscript paths for structure inference |
| `referencing_routines` | integer | Count of routines that SET/KILL this global (from XINDEX) |
| `package_namespace` | string | Inferred package from referencing routines |
| `piks` | enum | PIKS classification (blank until classified) |
| `piks_method` | string | Heuristic or `manual` |
| `piks_evidence` | string | Evidence string |

**PIKS heuristics for non-FileMan globals:**

The DD-based heuristics (H-01 through H-52) don't apply to non-FileMan
globals. A separate set of rules classifies them:

| # | Rule | Signal | PIKS | Rationale |
|---|---|---|---|---|
| G-01 | Global root matches a known Patient package namespace (PS, LR, GMRV, etc.) | Package ownership | P | If Pharmacy routines are the only writers, it's pharmacy data — Patient. |
| G-02 | Subscript structure contains DFN-like values (integer subscript matching `^DPT` IEN range) | DFN in subscripts | P | Data indexed by patient identity is per-patient data. |
| G-03 | Global root starts with `^TMP(` or `^UTILITY(` or `^XTMP(` | Temporary/scratch | S | Ephemeral working storage, not persistent data. |
| G-04 | Global root starts with `^%Z` | Site-specific utility | S | VA convention for local/site utility globals. |
| G-05 | All referencing routines belong to a single package namespace | Single-package ownership | Infer from package | Use the package's known PIKS affinity (H-14–H-17 namespace lists). |
| G-06 | `partial-fm` global where the undocumented branches appear under DFN-keyed subscripts | Per-patient extension | P | FileMan defines the file but the package extends it with patient-keyed data outside the DD. |

**Relationship to the model layers:**

Non-FileMan globals sit at the Physical layer but have no Logical layer
representation (no `^DD` entries). The `global-census.tsv` fills this
gap — it IS the logical description for non-FileMan data. PIKS
classification applies to all three global categories equally.

```
┌─────────────────────────────────────────────────┐
│  PIKS classification                            │
│  Applies to ALL globals: full-fm + partial-fm   │
│  + non-fm                                       │
├─────────────────────────────────────────────────┤
│  Logical layer                                  │
│  FileMan: files.tsv, fields.tsv (from ^DD)      │
│  Non-FM:  global-census.tsv (from $ORDER walk)  │
├─────────────────────────────────────────────────┤
│  Physical layer                                 │
│  ALL globals in the database                    │
└─────────────────────────────────────────────────┘
```

**Coverage metric impact:**

`coverage.json` should track FileMan coverage separately:

```json
"fileman_coverage": {
  "total_globals": 1847,
  "full_fm": 1203,
  "partial_fm": 412,
  "non_fm": 232,
  "full_fm_pct": 65.1
}
```

This answers a question no one has quantified at scale: **what percentage
of VistA's data is actually described by FileMan?** Based on the known
Pharmacy and Lab patterns, the answer is likely well below 100% — a
substantial fraction of the most clinically active data lives outside
FileMan's DD. The exact number is a significant finding — log it as an
RF-NNN entry. It has direct implications for anyone attempting VistA
data migration, FHIR mapping, or modernization.

### 11.5 Conceptual model

The conceptual model is the project's primary deliverable — a clean
logical schema that sits above FileMan's raw DD and makes VistA's data
architecture navigable and queryable by someone who has never seen M code.

#### 11.5.1 Model layers

```
┌─────────────────────────────────────────────────┐
│  PIKS classification (first pass — this drives  │
│  everything else)                               │
│  Patient | Institution | Knowledge | System     │
├─────────────────────────────────────────────────┤
│  Conceptual layer (second pass)                 │
│  Subdomains → Entities → Attributes → Relations │
│  Human-readable, semantically typed             │
├─────────────────────────────────────────────────┤
│  Logical layer (automated extraction)           │
│  Files → Fields → Pointers → Cross-references  │
│  Complete, machine-generated from ^DD           │
├─────────────────────────────────────────────────┤
│  Physical layer (VistA globals)                 │
│  ^DPT, ^DIC(200,), ^OR(100,) — M subscripts    │
│  Actual storage; walked by VMGSTAT              │
└─────────────────────────────────────────────────┘
```

Every element traces down through all layers. PIKS classification is
the first analytical act — it determines audience, security, storage,
and analytical approach BEFORE detailed modeling begins. Every element
in the physical layer traces up to at least the logical layer (and
ideally through PIKS classification once the first pass is complete).

#### 11.5.2 PIKS classification — the primary analytical act

Before normalizing, grouping, or modeling VistA's data, we must answer a
more fundamental question: **what kind of data is this?** Knowing the kind
determines the audience, security posture, storage strategy, regulatory
exposure, and analytical approach. Classification comes before modeling.

Every FileMan file and global gets assigned to exactly one of four PIKS
categories. This is the first and most important pass over the schema.

```
┌──────────────────────────────────────────────────────────────────┐
│                        PIKS Framework                            │
│                                                                  │
│  ┌──────────┐  ┌─────────────┐  ┌───────────┐  ┌──────────┐     │
│  │ PATIENT  │  │ INSTITUTION │  │ KNOWLEDGE │  │  SYSTEM  │     │
│  │          │  │             │  │           │  │          │     │
│  │ Clinical │  │ Facility &  │  │ Terms,    │  │ Config,  │     │
│  │ care data│  │ org scope   │  │ templates,│  │ ops, dev │     │
│  │          │  │             │  │ workflows │  │          │     │
│  └────┬─────┘  └──────┬──────┘  └─────┬─────┘  └────┬─────┘     │
│       │               │               │              │           │
│  Protected       Comparative     Informatics     IT/DevOps      │
│  Clinicians      Administration  Knowledge wkrs  Developers     │
│  Longitudinal    Cross-facility  Declarative     Operational    │
│  Exchange-ready  Benchmarking    Terminology     Maintenance    │
└──────────────────────────────────────────────────────────────────┘
```

##### P — Patient

The actual data of a patient: the basis of clinical care, clinical decision
support, patient record exchange, and long-term longitudinal storage. This
is the system-independent gold of VistA — the data that outlives any
specific installation and must move with the patient.

| Aspect | Detail |
|---|---|
| **Contents** | Demographics, encounters, diagnoses, medications, labs, vitals, notes, orders, allergies, immunizations, procedures, images, consults |
| **Audience** | Clinicians, patients (via portal), care coordinators, researchers (de-identified) |
| **Security** | Protected — HIPAA Privacy & Security Rules, 38 CFR Part 1, VA Directive 6502 |
| **Storage concern** | Longitudinal retention (decades), audit trail, encryption at rest, access logging |
| **Analytical approach** | Record-centric: one patient → all their data across files. Pointer chains from File 2 outward. |
| **Exchange** | CCR/CDA, FHIR, Blue Button, VHIE — these standards map FROM Patient data |
| **Key files (expected)** | 2 (PATIENT), 9000001 (PATIENT/IHS), 120.5 (GMRV VITAL MEASUREMENT), 8925 (TIU DOCUMENT), 52 (PRESCRIPTION), 63 (LAB DATA), 100 (ORDER), 9000011 (PROBLEM), 70 (RADIOLOGY), 130 (SURGERY) |
| **Key globals** | `^DPT(`, `^GMR(`, `^TIU(`, `^PS(`, `^LR(`, `^OR(` |

##### I — Institution

Data about the specific location, facility, and scope of care. Describes
WHERE and BY WHOM care is delivered — not the care itself. Enables
cross-facility comparison, administrative reporting, and organizational
analysis.

| Aspect | Detail |
|---|---|
| **Contents** | Facility identifiers, station numbers, divisions, service lines, clinic definitions, ward/bed structure, provider roles, team assignments, operating hours, catchment areas |
| **Audience** | Administrators, planners, VISN leadership, compliance officers |
| **Security** | Mixed — provider/staff personal data is protected; facility structure is operational |
| **Storage concern** | Referential stability — many Patient records point to Institution data |
| **Analytical approach** | Facility-centric: one institution → its configuration, scope, capacity. Compare across facilities. |
| **Key files (expected)** | 4 (INSTITUTION), 40.8 (MEDICAL CENTER DIVISION), 44 (HOSPITAL LOCATION), 200 (NEW PERSON, secondary: also System), 42 (WARD LOCATION), 8932 (PERSON CLASS) |
| **Key globals** | `^DIC(4,`, `^DIC(40.8,`, `^SC(`, `^VA(200,` |

##### K — Knowledge

The underlying know-how: terminologies, code systems, templates, order
sets, clinical reminders, health factors, decision logic, and workflow
definitions. This is the **declarative semantic infrastructure** that
makes VistA a clinical system rather than a database. Managed by clinical
informatics, coding specialists, and knowledge workers.

| Aspect | Detail |
|---|---|
| **Contents** | ICD/CPT/SNOMED code tables, drug classes, formulary entries, order dialog definitions, reminder rules, health factors, TIU document definitions, print templates, input transforms, help text |
| **Audience** | Clinical informaticists, terminology specialists, pharmacy formulary managers, reminder coordinators |
| **Security** | Generally public; some content may be proprietary (licensed code sets) or VA-internal policy |
| **Storage concern** | Version-controlled content — changes affect clinical behavior. Needs audit trail for "why did this reminder fire?" |
| **Analytical approach** | Content-centric: what knowledge is encoded, how is it structured, what references what. Terminology mapping to external standards. |
| **Key files (expected)** | 80 (ICD DIAGNOSIS), 81 (CPT), 50 (DRUG), 50.605 (VA DRUG CLASS), 101.41 (ORDER DIALOG), 811.9 (CLINICAL REMINDER), 9999999.27 (HEALTH FACTOR), 8925.1 (TIU DOCUMENT DEFINITION), .2 (PRINT TEMPLATE), .4 (SORT TEMPLATE) |
| **Key globals** | `^ICD(`, `^ICPT(`, `^PSDRUG(`, `^ORD(`, `^PXD(`, `^DD(` |

##### S — System

Technical and configuration data used by IT staff, VistA developers, and
system maintainers. Covers installation, configuration, operations,
monitoring, and the meta-structure of VistA itself (including FileMan's
own data dictionary).

| Aspect | Detail |
|---|---|
| **Contents** | Kernel site parameters, device configurations, option menus, security keys, user classes, RPC definitions, HL7 link configurations, package version tracking, error traps, task scheduler entries, FileMan DD-of-DDs |
| **Audience** | System administrators, VistA developers, IRM staff, DevOps |
| **Security** | Operational — may contain credentials, access keys, security configurations |
| **Storage concern** | Backup/restore scope, reproducibility of installation state. Often site-specific, not portable. |
| **Analytical approach** | Configuration-centric: what is installed, what is enabled, what depends on what. Infrastructure mapping. |
| **Key files (expected)** | 8989.3 (KERNEL SYSTEM PARAMETERS), 8989.5 (PACKAGE), 19 (OPTION), 19.1 (SECURITY KEY), 101 (PROTOCOL), 870 (HL LOGICAL LINK), 9.4 (PACKAGE), 3.5 (ERROR), .11 (INDEX), .1 (DATA TYPE), 1 (FILE) |
| **Key globals** | `^XTV(8989.3,`, `^DIC(9.4,`, `^DIC(19,`, `^ORD(101,`, `^%ZTER(` |

##### PIKS boundary cases

Some files serve multiple categories. Classification rules:

| Rule | Example |
|---|---|
| Assign to the category of the **primary consumer** | File 200 (NEW PERSON): primary=System (user accounts), secondary=Institution (provider roster) |
| Patient data **always wins** in ambiguity | A file with both patient records and system config → Patient |
| Subfiles inherit the parent's PIKS category | File 2.312 (PATIENT APPOINTMENT subfile) → Patient (inherits from File 2) |
| Pointer targets do not determine category | File 80 (ICD) is Knowledge even though Patient files point to it |
| Cross-reference infrastructure follows the file | A trigger xref on a Patient file is Patient, not System |

##### Orthogonal data properties

PIKS answers WHO cares about this data. Four orthogonal properties answer
HOW it should be handled. These cut across all PIKS categories — a Patient
file and a System file can both be `high-volume` and `protected`. Assigned
alongside PIKS classification (same pass).

**Volatility** — how frequently the data changes

| Value | Meaning | Examples |
|---|---|---|
| `static` | Set once, rarely or never modified | ICD code tables, drug classes, file DD |
| `slow` | Changes on administrative cycles (weeks/months) | Facility config, clinic definitions, formulary |
| `dynamic` | Changes with each clinical encounter or operational event | Patient records, orders, lab results, notes |
| `ephemeral` | Runtime state, discarded after use | HL7 queue, TaskMan jobs, lock tables, error traps |

Why it matters: backup frequency, cache strategy, replication priority,
archival policy. Static data can be baked into images; ephemeral data
should never be archived.

**Sensitivity** — regulatory and security classification

| Value | Meaning | Examples |
|---|---|---|
| `protected` | Identifies a person — patient OR staff (HIPAA, Privacy Act, 38 CFR Part 1) | Patient demographics, diagnoses, meds, provider SSNs, employee records |
| `operational` | Not personal but operationally sensitive | Security keys, access controls, system passwords, network configs |
| `public` | No sensitivity restrictions | Code tables, standard terminologies, public formulary |

PHI and PII are not distinguished — both patients and providers/staff
are persons whose data requires protection under overlapping regulations.
The single value `protected` covers any data that identifies a person.

Why it matters: encryption requirements, access logging, de-identification
scope, data sharing constraints. A file's sensitivity may be HIGHER than
its PIKS category suggests (e.g., System files containing credentials are
`operational`, not `public`).

**Portability** — can this data move between VistA instances?

| Value | Meaning | Examples |
|---|---|---|
| `universal` | Same everywhere, not site-specific | ICD/CPT codes, drug ingredients, FileMan DD |
| `national` | VA-wide standard, not site-specific | National formulary, CPRS order dialogs, reminder definitions |
| `site-specific` | Meaningful only at this facility | Local clinic defs, division setup, device configs, site parameters |

Why it matters: migration planning (what travels with a patient vs. what
stays behind), data exchange (what can be shared with external systems),
reproducibility (what must be rebuilt at a new site).

**Volume** — data scale characteristics

| Value | Meaning | Typical record count |
|---|---|---|
| `reference` | Small lookup table | <1,000 entries |
| `moderate` | Medium operational tables | 1,000 – 100,000 |
| `high-volume` | Large transactional/clinical stores | >100,000 |

Why it matters: storage planning, query performance, archival strategy,
export feasibility. High-volume files need different analytical approaches
than reference tables.

##### Interaction between PIKS and properties

The properties are independent of PIKS but tend to cluster:

| PIKS | Typical volatility | Typical sensitivity | Typical portability | Typical volume |
|---|---|---|---|---|
| Patient | dynamic | protected | site-specific (the records) | high-volume |
| Institution | slow | protected/operational | site-specific | moderate |
| Knowledge | static/slow | public | universal/national | reference/moderate |
| System | slow/ephemeral | operational | site-specific | reference/moderate |

Deviations from these typical patterns are especially interesting — they
often indicate boundary cases or files that warrant a closer look. For
example, a Knowledge file that is `high-volume` and `dynamic` may actually
be Patient data misclassified.

##### PIKS vs. clinical subdomains

PIKS is the **first-pass classification** — broad, exhaustive, audience-
driven. Within each PIKS category, finer subdomains exist:

| PIKS | Subdomains (second pass) |
|---|---|
| Patient | Demographics, Encounters, Orders, Pharmacy, Lab, Radiology, Surgery, Vitals, Problems, TIU, Consults, Immunizations |
| Institution | Facilities, Clinics/Wards, Providers, Teams, Scheduling |
| Knowledge | Terminology, Formulary, Order Dialogs, Reminders, Templates, Health Factors |
| System | Kernel, FileMan meta, Protocols, HL7, Security, TaskMan, Devices |

The subdomain pass happens AFTER PIKS classification is complete. Do not
skip to subdomains before every file has a PIKS assignment.

#### 11.5.3 Conceptual model entities

| Concept | Maps to | Defined in | Example |
|---|---|---|---|
| **PIKS category** | Broad data classification | `files.tsv` (`piks` column) | "P" for File 2, "K" for File 80 |
| **Subdomain** | Finer grouping within PIKS | `domains.tsv` | "Pharmacy" within Patient, "Terminology" within Knowledge |
| **Entity** | One FM file (or cluster of parent + key multiples) | `files.tsv` + `entity-groups.tsv` | "Patient" = File 2 + subfiles 2.01, 2.312, ... |
| **Attribute** | One FM field | `fields.tsv` + `semantic-types.tsv` | "Date of Birth" = File 2, field .03, type: date |
| **Relationship** | One FM pointer (any type) | `pointers.tsv` | "Patient → Institution" = File 2, field .104 → File 4 |
| **Index** | One FM cross-reference | `xrefs.tsv` | "B" xref on File 2, field .01 — lookup by name |

#### 11.5.4 Output file schemas

Complete column definitions for every TSV in `data-model/` and `code-model/`.

**`files.tsv`** — one row per FileMan file

| Column | Type | Description |
|---|---|---|
| `file_number` | decimal | FileMan file number (e.g., 2, 200, 9000011) |
| `file_name` | string | Name from `^DIC(file,0)` |
| `global_root` | string | Global reference (e.g., `^DPT(`) |
| `parent_file` | decimal | Parent file number if this is a multiple; blank if top-level |
| `field_count` | integer | Total fields in this file |
| `pointer_in` | integer | Count of fields in OTHER files that point TO this file |
| `pointer_in_files` | string | Pipe-delimited list of distinct file numbers that point TO this file (e.g., `2|52|100`) |
| `pointer_out` | integer | Count of pointer fields in this file that point to OTHER files |
| `pointer_out_files` | string | Pipe-delimited list of distinct file numbers this file points TO (e.g., `2|4|80|200`) |
| `record_count` | integer | Actual records in the global (from VMGSTAT pass) |
| `is_dinum` | boolean | Y if IEN = .01 value |
| `piks` | enum | `P` / `I` / `K` / `S` / `U` (unresolved). Blank until classified |
| `piks_method` | string | `H-01`–`H-52`, `manual`, `manual-vestigial`, `manual-package`, `manual-unresolved`, or `none` |
| `piks_confidence` | enum | `certain` / `high` / `moderate` / `low` (blank if unclassified) |
| `piks_evidence` | string | Machine: the specific data that triggered the rule (see below). Manual: `RF-NNN` reference. |
| `piks_secondary` | enum | Secondary PIKS if file serves two categories; blank if single |
| `volatility` | enum | `static` / `slow` / `dynamic` / `ephemeral` (blank until classified) |
| `sensitivity` | enum | `protected` / `operational` / `public` (blank until classified) |
| `portability` | enum | `universal` / `national` / `site-specific` (blank until classified) |
| `volume` | enum | `reference` / `moderate` / `high-volume` (blank until classified) |
| `subdomain` | string | Subdomain within PIKS (blank until second-pass annotation) |
| `status` | enum | `extracted` / `classified` / `annotated` / `verified` |

**`fields.tsv`** — one row per field per file

| Column | Type | Description |
|---|---|---|
| `file_number` | decimal | Containing file |
| `field_number` | decimal | Field number |
| `field_name` | string | Name from `^DD(file,field,0)` piece 1 |
| `data_type` | string | FileMan type: `FREE TEXT`, `DATE`, `NUMERIC`, `SET`, `POINTER`, `VARIABLE-POINTER`, `COMPUTED`, `WORD PROCESSING`, `MUMPS` |
| `pointer_target` | decimal | Target file number if pointer; blank otherwise |
| `required` | boolean | Y if required field |
| `computed` | boolean | Y if computed/derived |
| `multiple` | boolean | Y if this field is a multiple (subfile) |
| `subfile_number` | decimal | Subfile number if multiple |
| `semantic_type` | string | Semantic annotation (blank until annotated) |
| `xref_count` | integer | Number of cross-references on this field |

**`pointers.tsv`** — one row per pointer relationship

| Column | Type | Description |
|---|---|---|
| `source_file` | decimal | File containing the pointer field |
| `source_field` | decimal | Field number |
| `source_field_name` | string | Field name |
| `source_piks` | enum | PIKS of source file (back-filled after VMPIKS runs) |
| `target_file` | decimal | File pointed to |
| `target_file_name` | string | Target file name |
| `target_piks` | enum | PIKS of target file (back-filled after VMPIKS runs) |
| `cross_piks` | boolean | Y if `source_piks` != `target_piks` — marks cross-category pointers |
| `pointer_type` | enum | `simple` / `variable` / `computed` / `implicit` / `dinum` / `backward` |
| `is_canonical` | boolean | Y if primary relationship (blank until annotated) |
| `evidence` | string | RF-NNN reference if annotation is human-provided |

**`xrefs.tsv`** — one row per cross-reference

| Column | Type | Description |
|---|---|---|
| `file_number` | decimal | File containing the cross-reference |
| `field_number` | decimal | Field the cross-reference is on |
| `xref_name` | string | Cross-reference name (e.g., "B", "C", "AC") |
| `xref_type` | enum | `regular` / `mumps` / `new-style` / `compound` / `trigger` |
| `set_logic` | string | MUMPS SET code (abbreviated) |
| `kill_logic` | string | MUMPS KILL code (abbreviated) |
| `target_global` | string | Global written to by the xref, if different from file's own |

**`domains.tsv`** — one row per file-subdomain assignment (second pass, after PIKS)

| Column | Type | Description |
|---|---|---|
| `file_number` | decimal | FileMan file number |
| `piks` | enum | PIKS category (from `files.tsv`) |
| `subdomain` | string | Subdomain within PIKS (e.g., "Pharmacy", "Terminology") |
| `role` | enum | `primary` / `secondary` |
| `evidence` | string | RF-NNN reference |

**`semantic-types.tsv`** — one row per annotated field

| Column | Type | Description |
|---|---|---|
| `file_number` | decimal | FileMan file number |
| `field_number` | decimal | Field number |
| `semantic_type` | string | Type name (person-name, date-time, icd-code, facility, narrative, ...) |
| `evidence` | string | RF-NNN reference |

**`entity-groups.tsv`** — clusters of files that form a logical entity

| Column | Type | Description |
|---|---|---|
| `group_name` | string | Logical entity name (e.g., "Patient Record") |
| `file_number` | decimal | FileMan file in this group |
| `role` | enum | `primary` / `subfile` / `extension` / `lookup` |
| `evidence` | string | RF-NNN reference |

**`globals.tsv`** — physical global statistics (from VMGSTAT)

| Column | Type | Description |
|---|---|---|
| `global_root` | string | Global reference (e.g., `^DPT(`) |
| `file_number` | decimal | Corresponding FileMan file |
| `record_count` | integer | Number of top-level entries |
| `max_subscript_depth` | integer | Deepest subscript level observed |
| `first_ien` | string | First IEN |
| `last_ien` | string | Last IEN |
| `estimated_size_kb` | integer | Approximate size from `$DATA` walk |

### 11.6 Traceability and coverage

#### 11.6.1 Traceability matrix

Every element in the conceptual model must be traceable to its source:

```
PIKS classification: File 2 = "P" (Patient)                          [RF-003]
  → Subdomain: "Demographics"                                        [RF-012]
    → Entity group: "Patient Record", primary file=2                  [RF-012]
      → files.tsv: file_number=2, name="PATIENT", global="^DPT("     [VMFILES]
        → ^DIC(2,0) = "PATIENT^...^..."                               [live DD]
```

The chain has four layers:
1. **PIKS** — broad classification with RF-NNN evidence (first pass)
2. **Conceptual** — subdomain + entity grouping with RF-NNN evidence (second pass)
3. **Logical** — machine extraction with routine name as provenance
4. **Physical** — the actual `^DD` / `^DIC` global reference, verifiable via `mumps -r %XCMD`

A finding that can't complete this chain is **provisional**. A finding
with a complete chain is **verified**.

#### 11.6.2 Coverage metrics

Track completeness at each level. These metrics are generated by a
Python script in `host/scripts/` and written to `data-model/coverage.json`.

```json
{
  "extraction_date": "2026-04-20T14:00:00Z",
  "piks_classification": {
    "total_files": 9247,
    "classified": 842,
    "unclassified": 8405,
    "coverage_pct": 9.1,
    "by_category": { "P": 312, "I": 87, "K": 241, "S": 202 }
  },
  "data_properties": {
    "volatility_classified": 842,
    "sensitivity_classified": 842,
    "portability_classified": 620,
    "volume_classified": 842,
    "fully_classified_pct": 6.7
  },
  "files": {
    "total": 9247,
    "extracted": 9247,
    "classified_piks": 842,
    "classified_properties": 620,
    "annotated_subdomain": 340,
    "verified": 120
  },
  "fields": {
    "total": 347291,
    "extracted": 347291,
    "annotated_semantic_type": 2100,
    "coverage_pct": 0.6
  },
  "pointers": {
    "total": 28430,
    "extracted": 28430,
    "annotated_canonical": 450,
    "coverage_pct": 1.6
  }
}
```

Coverage tells you how much of the schema has been not just extracted
(automated — should be 100% after first pass) but **understood**
(annotated, grouped, typed). It prevents false confidence: "we exported
the DD" is not "we understand the schema."

#### 11.6.3 Validation queries

M routines that verify the conceptual model against live data:

| Routine | What it validates | Failure mode |
|---|---|---|
| `VMVALPT` | Every pointer in `pointers.tsv` resolves to an existing file | Pointer target doesn't exist in `^DD` |
| `VMVALXR` | Every xref in `xrefs.tsv` has matching SET/KILL logic in `^DD` | Xref deleted or renamed since extraction |
| `VMVALRC` | Record counts in `globals.tsv` match current `$O` walk | Data changed since last VMGSTAT run |
| `VMVALFLD` | Field counts in `files.tsv` match current `^DD(file,0)` | File structure changed |

Run validation after any VEHU-M update or snapshot restore. Validation
failures get RF-NNN entries in the research log.

### 11.7 Session continuity

At the start of an analytical session, read:

1. `CLAUDE.md` — project orientation
2. `vista/export/RESEARCH.md` — prior findings (both slices)
3. `vista/export/data-model/coverage.json` — FileMan PIKS schema coverage
4. `vista/export/code-model/package-manifest.tsv` — routine/package state
5. `vista/export/.vista-meta-initialized` — what bake phases have completed
5. `docs/build-log.md` — recent implementation issues (if doing infra work)

During an analytical session:

1. If extraction TSVs don't exist yet, run the `VM*` routines first (§11.4.1 Pass 1)
2. Pick a domain or file cluster to investigate
3. Record findings as RF-NNN entries in `RESEARCH.md`
4. Update annotation TSVs (`domains.tsv`, `semantic-types.tsv`, etc.)
5. Re-run coverage script to update `coverage.json`

At the end of an analytical session:

1. Commit all changed TSVs + RESEARCH.md with RF-NNN references in the message
2. Note any new risks, anomalies, or tool issues for §15 or the build log
3. If coverage increased significantly, note the delta in the commit message

This ensures the next session — whether 2 hours or 2 months later — can
pick up where this one left off, see exactly what has been covered, and
continue from the frontier of understood schema.

### 11.8 Portability across VistA systems

The project runs on VEHU, but it produces two layers of output with
different portability characteristics.

#### 11.8.1 What is VistA-universal

These artifacts work on ANY VistA/FileMan system — VEHU, FOIA,
production VA, Indian Health Service (RPMS), or community forks:

| Artifact | Why it's portable |
|---|---|
| PIKS framework (P/I/K/S definitions, boundary rules, sensitivity priority) | The concepts of patient data vs. system config are inherent to VistA's architecture, not to any specific installation |
| 52 heuristic rules (H-01 through H-52) | They read `^DD`/`^DIC` structure, which is standardized FileMan. Same subscript patterns everywhere. |
| Core file classifications (File 2=P, File 4=I, File 200=S/I, File 80=K, etc.) | File numbers and DD structure are VA-standard |
| Extraction routines (`VM*`) | They walk FileMan globals using documented APIs |
| Pointer type taxonomy (simple/variable/computed/implicit/dinum/backward) | FileMan encodes pointers the same way everywhere |
| DD globals reference (§11.4.2) | `^DD` subscript semantics are FileMan fundamentals |
| Research findings about FileMan conventions (DINUM, xref patterns, etc.) | Conventions are VA-wide, not site-specific |

A new VistA system can clone the `VM*` routines and `VMPIKS`, run them,
and get an 85–95% PIKS classification with no prior human work. The
VEHU baseline serves as a reference to compare against.

#### 11.8.2 What is site-specific

| Artifact | Why it varies |
|---|---|
| Record counts (`globals.tsv`) | VEHU has synthetic data; FOIA has none; production has millions |
| Which packages are installed | Not every site has every package — affects pointer graph and namespace coverage |
| Threshold-based heuristic outcomes (H-33, H-34, H-43, H-44, H-50–H-52) | Thresholds calibrated to VEHU counts may not apply elsewhere |
| Template/form counts | Sites add local templates |
| Local files and fields | Sites add files in site-specific number ranges |
| Manual classifications and RF-NNN evidence | Reasoning may transfer; specific findings are VEHU-bound |

#### 11.8.3 Portability design rules

To maximize reusability, the pipeline separates portable rules from
site-specific data:

| Design rule | Implementation |
|---|---|
| Heuristic rules reference file NUMBERS (universal), not record COUNTS (variable) | H-06 says "points to File 2", not "points to the file with the most records" |
| Global root lists and namespace lists are configuration, not code | Stored as data tables that `VMPIKS` reads, not hardcoded in the routine |
| Threshold values are parameters with documented defaults | `VMPIKS` reads thresholds from a config section; VEHU defaults documented; other sites can override |
| Evidence format records the rule AND the site-specific data that triggered it | A reviewer on a different system can see whether the heuristic would fire the same way on their data |

#### 11.8.4 Cross-system comparison

When the same heuristic produces a DIFFERENT classification on two
systems, that difference is itself a finding:

| Scenario | What it means |
|---|---|
| File exists on VEHU but not on Site B | Site B doesn't have that package installed |
| Same file, same heuristic, different PIKS | A local modification changed the DD structure — investigate |
| Same file, different heuristic tier fires | Different packages installed change the pointer graph — propagation (tier 9) follows different paths |
| VEHU has 0 records, Site B has 500,000 | Volume heuristic may flip; PIKS should be the same if based on DD structure not record count |

These differences are valuable — they reveal how VistA installations
diverge in practice, which is exactly the kind of institutional knowledge
that is currently undocumented across the VA.

---

## 12. Environment configuration

### 12.1 `.env` file

Runtime configuration, gitignored. Read by the Makefile.

| Variable | Required | Default | Description |
|---|---|---|---|
| `TAILSCALE_IP` | yes | (none) | Tailscale IPv4 address of host machine. Services bind to this IP via Docker `-p`. |
| `VEHU_PASSWORD` | no | `vehu` | Password for SSH login to container. Overrides build-time default on rebuild. |
| `BAKE_WORKERS` | no | `1` | Parallelism for bake.sh. Values >1 not yet verified safe (risk #7). |
| `DOCKER_STOP_TIMEOUT` | no | `30` | Seconds for graceful shutdown before Docker kills the container. |

### 12.2 `.env.example`

Checked-in template. Copy to `.env` and fill in values.

```bash
# vista-meta runtime configuration
# Copy to .env and fill in your values. This file is gitignored.

# REQUIRED: Your Tailscale IPv4 address. All services bind to this IP.
# Find it with: tailscale ip -4
TAILSCALE_IP=

# Optional: SSH password for the vehu user (default: vehu)
# VEHU_PASSWORD=vehu

# Optional: bake.sh parallelism (default: 1, serial)
# BAKE_WORKERS=1
```

### 12.3 Build-time vs. runtime configuration

| Setting | Where | When applied |
|---|---|---|
| `YDB_VERSION` | Dockerfile `ARG` | Build time — baked into image |
| `VEHU_M_URL` | Dockerfile `ARG` | Build time — baked into image |
| `VEHU_UID` | Dockerfile `ARG` | Build time — baked into image |
| `VEHU_PASSWORD` | Dockerfile `ARG` | Build time — default, overridable at build |
| `TAILSCALE_IP` | `.env` | Runtime — Docker `-p` bind address |
| `BAKE_WORKERS` | `.env` | Runtime — passed to bake.sh via `docker exec` |

---

## 13. Smoke tests

Post-build verification to catch common failures before relying on the
container. Located in `tests/smoke/`. Run via `make smoke`.

### 13.1 Test inventory

| # | Test | Check | Pass criteria |
|---|---|---|---|
| S-01 | Container running | `docker ps` shows `vista-meta` | Container listed and status "Up" |
| S-02 | SSH connectivity | `ssh -p 2222 vehu@$TAILSCALE_IP echo ok` | Exit 0, stdout = "ok" |
| S-03 | YottaDB responds | `docker exec vista-meta yottadb -run %XCMD 'W $ZV'` | Outputs YottaDB version string |
| S-04 | Global directory exists | `docker exec vista-meta stat /home/vehu/g/mumps.dat` | Exit 0 |
| S-05 | Symlink farm populated | `docker exec vista-meta test -s /opt/VistA-M/r/MANIFEST.tsv` | Exit 0 |
| S-06 | Routine compilation | `docker exec vista-meta ls /opt/VistA-M/o/*.o \| head -1` | At least one .o file exists |
| S-07 | RPC Broker port | `docker exec vista-meta timeout 2 bash -c 'echo >/dev/tcp/127.0.0.1/9430'` | Exit 0 |
| S-08 | VistALink port | `docker exec vista-meta timeout 2 bash -c 'echo >/dev/tcp/127.0.0.1/8001'` | Exit 0 |
| S-09 | Rocto port | `docker exec vista-meta timeout 2 bash -c 'echo >/dev/tcp/127.0.0.1/1338'` | Exit 0 |
| S-10 | YDB GUI port | `docker exec vista-meta timeout 2 bash -c 'echo >/dev/tcp/127.0.0.1/8089'` | Exit 0 |
| S-11 | FileMan responds | `docker exec vista-meta yottadb -run %XCMD 'S DUZ=.5 D DT^DICRW W $$NOW^XLFDT'` | Outputs a FileMan date |
| S-12 | VEHU patient data | `docker exec vista-meta yottadb -run %XCMD 'W $D(^DPT(1))'` | Outputs `1` (patient 1 exists) |

### 13.2 Implementation

Single bash script at `tests/smoke/smoke.sh`. No test framework (ADR-027:
skip BATS). Output format:

```
[smoke] S-01 container running ............ PASS
[smoke] S-02 SSH connectivity ............. PASS
[smoke] S-03 YottaDB responds ............. PASS
...
[smoke] 12/12 passed, 0 failed
```

Exit 0 if all pass, exit 1 if any fail. Failed tests print the failing
command's stderr for diagnosis.

### 13.3 When to run

| Trigger | How |
|---|---|
| After `make build` + `make run` | `make smoke` |
| After restoring a snapshot | `make smoke` |
| After YDB or VEHU-M version bump | `make smoke` |
| CI (if added later) | `make build && make run && make smoke` |

---

## 14. Out of scope / deferred / skipped

| # | Item | Disposition |
|---|---|---|
| 22 | DOX (full ViViaN/DOX HTML pipeline) | Deferred — re-evaluate after YDB compatibility check |
| 20 | M code formatter/linter | Skipped — no standard tool exists |
| 21 | VistA Test Harness (VTH) | Skipped |
| —  | ViViaN M extraction routines (option C of DD exporters) | Dropped (same YDB-compat concern as ViViaN/DOX) |
| —  | M Web Server (port 9080) | Skipped — not needed for metadata analytics |
| —  | QEWD, Panorama, Java VistALink-J2EE | Out of scope |
| —  | YDB Web Server TLS | Skipped — Tailscale provides transport encryption |
| —  | YDB GUI authentication | Skipped — Tailscale = perimeter |
| —  | Multi-flavor support (FOIA, RPMS alongside VEHU) | Single-flavor structure for now |
| —  | Docker compose | Plain `docker run`; compose later if sidecars added |
| —  | BATS tests | Skipped; smoke only |
| —  | `build-no-cache`, `nuke`, `root-shell`, `ssh`, `status`, `health`, `ports`, `du`, `list-snapshots` make targets | Skipped from v1 |

---

## 15. Remaining open work

### 15.1 Implementation status by phase

**Infrastructure (Phase 0 prerequisites)**

| Item | Status | Spec |
|---|---|---|
| Dockerfile | Done (v1) — BL-001 through BL-003 | §4 |
| entrypoint.sh | Done (v1) — BL-003 | §5 |
| healthcheck.sh | Done (v1) | §5 |
| Service configs (xinetd.d, sshd_config, ydb_env.sh) | Done (v1) | §4 L13 |
| `.env.example` | Done (v1) | §12 |
| CLAUDE.md | Done (v1) | §10.1 |
| Research log scaffold | Done (v1) | §11.2 |
| bake.sh | Pending | §6 |
| Makefile | Pending | §8 |
| Smoke test (`tests/smoke/smoke.sh`) | Pending | §13 |
| Dependency manifest — fill in SHAs after first build | Pending | §10.3 |
| Host venv bootstrap | Pending | §3 |
| README + quickstart | Pending | §3 |
| ADR backfill (~28 records) | Deferred | §10 |

**Extraction & census (Phase 0a–0c)**

| Item | Status | Spec |
|---|---|---|
| `VMCENSUS` Phase 1 — global recon | Pending | §11.4.4 |
| `VMCENSUS` Phase 2 — full census | Pending | §11.4.4 |
| `VMFILES` — FileMan file inventory | Pending | §11.4.1 |
| `VMFIELDS` — field extraction | Pending | §11.4.1 |
| `VMPTRS` — pointer extraction | Pending | §11.4.1 |
| `VMXREFS` — cross-reference extraction | Pending | §11.4.1 |
| `VMGSTAT` — global statistics | Pending | §11.4.1 |
| `VMPKGS` — package inventory | Pending | §11.4.1 |

**PIKS classification (Phase 1a–1b)**

| Item | Status | Spec |
|---|---|---|
| `VMPIKS` — 52 DD-based heuristics (H-01–H-52, 12 tiers) | Pending | §11.4.1 |
| `VMPIKS` — 6 non-FM heuristics (G-01–G-06) | Pending | §11.4.4 |
| `VMPIKS` — pipeline state management + run log | Pending | §11.4.1 |
| `VMPIKS` — automated property inference | Pending | §11.4.1 |
| Human triage (Pass 1b — 5-category) | Blocked on Phase 1a | §11.4.1 |

**Validation & analysis (Phase 2+)**

| Item | Status | Spec |
|---|---|---|
| `VMVALPT` — pointer validation | Pending | §11.6.3 |
| `VMVALXR` — cross-reference validation | Pending | §11.6.3 |
| `VMVALRC` — record count validation | Pending | §11.6.3 |
| `VMVALFLD` — field count validation | Pending | §11.6.3 |
| Coverage script (`coverage.py`) | Pending | §11.6.2 |
| Subdomain annotation | Blocked on PIKS completion | §11.4.1 Pass 2 |

### 15.2 Known risks / unverified assumptions

Each risk has a verification protocol. When verified, annotate with
`[confirmed BL-NNN]` or `[falsified BL-NNN]` per §10.4.

**Infrastructure risks**

| # | Risk | Status | Verification protocol |
|---|---|---|---|
| 1 | Enhanced XINDEX presence in VEHU | open | After first bake: `docker exec vista-meta yottadb -run %XCMD 'D ^XINDEX'`. If it prompts for a routine, XINDEX is present. Log routine count from MANIFEST.tsv vs. XINDEX output count. |
| 2 | FMQL compatibility with current VEHU | open | After FMQL install: `docker exec vista-meta yottadb -run %XCMD 'D QUERY^CGFMQL("2")'`. Check for output or error. Also check `git log --oneline -1` on the FMQL clone to record last commit date. |
| 3 | FileMan Print Template exporter scaffolding | open | Deferred until bake.sh dd-template phase is implemented. Verify by running a DD print on file 2 (PATIENT) and confirming output appears in `export/dd-template/raw/`. |
| 4 | VEHU-M import time on minty | open | During first `make build`, time layer 7: `docker build` outputs timestamps per step. Record actual duration in BL-NNN. Adjust spec §4 layer 7 estimate accordingly. |
| 5 | Routine compilation with symlink farm | open | After build, compare counts: `wc -l /opt/VistA-M/r/MANIFEST.tsv` (routines) vs. `ls /opt/VistA-M/o/*.o \| wc -l` (compiled objects). If object count < 90% of routine count, investigate. Some failures are expected. |
| 6 | YDBGUI compatibility with VEHU FileMan | open | After `make run`: open `http://$TAILSCALE_IP:8089` in browser. Navigate to global listing. If `^DPT` (PATIENT file) is browsable, YDBGUI works with this VEHU. If blank page or JS errors, log as BL-NNN. |
| 7 | Bake workers >1 safety | open | After baseline bake completes with workers=1: run `BAKE_WORKERS=2 make bake` with `--force` on a non-destructive phase (xindex). Compare output to workers=1 baseline. Check YDB syslog for LOCK conflicts. |

**Analytical risks**

| # | Risk | Status | Verification protocol |
|---|---|---|---|
| 8 | Non-FileMan data volume in VEHU | open | Run `VMCENSUS` Phase 1 recon. Record: total globals, `^DIC`-matched count, persistent non-FM count, scratch exclusion. If persistent non-FM > 500 globals, flag as major workstream. Log exact numbers as RF-NNN. |
| 9 | Pharmacy non-FM global structure | open | After VMCENSUS: examine `^PS(55,DFN,"P"` subscript tree. Document the subscript convention used for dispensing, IV, unit dose. Compare to `^DD(55,...)` to quantify how much is in FileMan vs. not. Log as RF-NNN. |
| 10 | Lab non-FM global structure | open | Same as #9 for `^LR(` and `^LRO(`. Lab has some of the most complex non-FM subscript conventions in VistA. Document subscript patterns for accessions, verified results, cumulative data. |
| 11 | PIKS heuristic accuracy on VEHU | open | After VMPIKS first run: sample 50 files from each confidence tier (certain, high, moderate, low). Manually verify PIKS classification. Calculate accuracy per tier. If any tier < 90% accuracy, investigate which heuristics are misfiring. |
| 12 | FileMan coverage percentage | open | After VMCENSUS: calculate `full-fm / total_globals`. This is a significant finding regardless of value. If < 70%, the non-FM workstream is larger than the FM workstream for PIKS classification. Log as RF-NNN. |
| 13 | Heuristic coverage gap | open | After VMPIKS: count files with `piks_method=none`. If > 10% of top-level files, the heuristic set has a gap. Analyze unmatched files to identify missing patterns for new heuristics. |
| 14 | Cross-PIKS pointer density | open | After PIKS classification: count `cross_piks=Y` rows in `pointers.tsv`. High cross-PIKS density indicates tight coupling between categories — affects storage partitioning assumptions. |

---

## Changelog

- **v0.3.15** (2026-04-18): Comprehensive spec update to reflect all new assumptions and goals. Added §2.12 Analytical methodology locked decisions (PIKS, heuristics, non-FM scope, pipeline state, traceability, coverage, triage, analysis phases). Added §2.13 Documentation system locked decisions (six artifact types, code standards, errata process). Updated §2.1 with project goal, analytical scope, classification approach, portability goal. Updated §3 directory layout with global-census.tsv, global-recon.txt, vmpiks-runs.log. Rewrote §15 as phase-ordered status view (infrastructure/extraction/classification/validation). Added 7 analytical risks (#8–#14): non-FM data volume, Pharmacy/Lab global structure, heuristic accuracy, FileMan coverage percentage, heuristic coverage gap, cross-PIKS pointer density.
- **v0.3.14** (2026-04-18): Added §11.4.4 Non-FileMan globals. Pharmacy and Lab bypass FileMan by design for performance — this is a major body of operational patient data, not a minor gap. Split `VMCENSUS` into two phases: Phase 1 recon (minutes — enumerate globals, `^DIC` match, depth-1 counts, scratch exclusion, package prefix clustering, DFN spot-check) produces `global-recon.txt`; Phase 2 full census (hours — deep subscript walk, partial-FM detection, XINDEX cross-reference) produces `global-census.tsv`. Phase 2 always runs — recon scopes the work, does not gate it. Added 6 non-FM heuristics (G-01–G-06). Added `fileman_coverage` metrics to `coverage.json`. Added known non-FM package table (PS, LR, IB, OR, RA).
- **v0.3.13** (2026-04-18): Added §11.8 Portability across VistA systems: separated VistA-universal artifacts (PIKS framework, 52 heuristics, extraction routines, core classifications, DD reference) from site-specific output (record counts, local files, manual classifications). Added portability design rules: heuristics reference file numbers not counts, global/namespace lists are configuration not code, thresholds are parameterized. Added cross-system comparison framework for detecting institutional divergence.
- **v0.3.12** (2026-04-18): Added pipeline state management: column ownership rules (extraction vs. heuristic vs. human), monotonic guarantee (unknowns can only decrease), four run modes (fresh/incremental/re-extract/force), state progression diagram (extracted → classified → annotated → verified), run log (`vmpiks-runs.log`). Added `piks_evidence` column to `files.tsv` — every classification records the specific data that triggered it (field number, pointer target, xref name, etc.) making each classification independently auditable. Defined evidence format per heuristic type.
- **v0.3.11** (2026-04-18): Replaced generic "classify unmatched files" in Pass 1b with structured 5-category triage: A) empty/vestigial → batch-S, B) package-identifiable → batch by package, C) mixed-signal → resolution rules, D) cross-cutting → dual-PIKS with sensitivity priority, E) unresolvable → U with <2% threshold. Added learning classifier feedback loop (triage findings update heuristic tables). Added `U` (unresolved) to PIKS enum, extended `piks_method` values. Expected net: <1% of files remain unresolved.
- **v0.3.10** (2026-04-18): Added tiers 10–12 to PIKS heuristics (H-41–H-52, total now 52). Tier 10: cross-reference signals — DFN-named xrefs (H-41, certain P), trigger xref targets (H-42), xref density (H-43/H-44). Tier 11: file-level access codes from `^DIC(file,0)` — programmer-only write → S (H-45), open LAYGO + wide reference → K (H-46), file number ranges for PCE/IHS → P (H-47), Lexicon → K (H-48), FM meta → S (H-49). Tier 12: template/form associations — print template count (H-50), input template count (H-51), ScreenMan form presence (H-52). Added access code pieces and template file globals to §11.4.2 DD reference.
- **v0.3.9** (2026-04-18): Added `pointer_in_files` and `pointer_out_files` columns to `files.tsv` — pipe-delimited lists of distinct target/source file numbers for heuristic development without joins. Added `source_piks`, `target_piks`, `cross_piks` columns to `pointers.tsv` — back-filled after VMPIKS runs, enables direct filtering of cross-category pointers.
- **v0.3.8** (2026-04-18): Split Pass 1 into 1a (automated heuristics) and 1b (human review). Added 40 deterministic PIKS classification heuristics across 9 confidence tiers. Tiers 1–7 single-pass: structural identity (H-01–H-05), pointer-to-anchor (H-06–H-09), global root patterns (H-10–H-13), package namespace (H-14–H-17), pointer topology (H-18–H-19), name patterns (H-20–H-23), design-time mutability (H-24–H-29). Tier 8 structural composition: subfile depth, word-processing density, SET-OF-CODES density, field count, DINUM pattern, computed field density (H-30–H-35). Tier 9 graph propagation: patient-neighborhood, consumed-by-patient, cross-PIKS bridge, orphan detection, knowledge-internal clustering (H-36–H-40). Added automated property inference, `VMPIKS` routine spec, `piks_method`/`piks_confidence` columns. Added audit/delete/access globals to §11.4.2 DD reference.
- **v0.3.7** (2026-04-18): Added four orthogonal data properties to PIKS classification: volatility (static/slow/dynamic/ephemeral), sensitivity (protected/operational/public), portability (universal/national/site-specific), volume (reference/moderate/high-volume). Collapsed PHI/PII into single `protected` value — both patients and staff are persons whose data requires protection. Properties answer HOW data should be handled; PIKS answers WHO cares. Added expected PIKS-property correlation table for anomaly detection. Added property columns to `files.tsv`. Updated Pass 1 methodology, coverage metrics.
- **v0.3.6** (2026-04-18): Project goal pivoted from "FileMan normalization" to "FileMan classification." Introduced PIKS framework (§11.5.2): Patient, Institution, Knowledge, System as the primary first-pass classification of every FileMan file. PIKS determines audience, security posture, storage strategy, and analytical approach before detailed modeling begins. Replaced 14-domain taxonomy with PIKS + subdomains. Added PIKS boundary rules, four-layer model (PIKS → Conceptual → Logical → Physical), `piks`/`piks_secondary`/`subdomain` columns to `files.tsv`, PIKS-centric coverage metrics. Updated project description, CLAUDE.md, traceability matrix.
- **v0.3.5** (2026-04-18): Major expansion of §11 Research system: added extraction pipeline (§11.4) with six M extraction routines and two-pass methodology; pointer type taxonomy (§11.4.3); conceptual model definition (§11.5) with four-layer architecture, entity types, and complete TSV schemas for all output files; traceability matrix and coverage metrics (§11.6) with validation routines; updated §11.3 and §11.7 to reflect full methodology. Added extraction + validation routines to §15 open work.
- **v0.3.4** (2026-04-18): Added §11 Research system (research log, normalized output format, session continuity protocol). Added §12 Environment configuration (.env spec + .env.example). Added §13 Smoke tests (12 tests with pass criteria). Rewrote §15 known risks with concrete verification protocols. Renumbered §11–§12 → §14–§15.
- **v0.3.3** (2026-04-18): Added §10.6 code documentation standards (script headers, inline comment rules, cross-reference formats). Added CLAUDE.md to document inventory and directory layout. Applied Tier 1–3 documentation to all existing scripts.
- **v0.3.2** (2026-04-18): Added §10 Documentation system (build log, dependency manifest, known-risk lifecycle, spec errata process). Updated §3 directory layout and §12 open work to reflect Dockerfile/entrypoint implementation (v1) and build log corrections BL-001–BL-003.
- **v0.3.1** (2026-04-18): Project root moved from `~/claude/vista-meta/` to `~/vista-meta/`. vista-meta is now a standalone git repo, not a subdirectory of the claude skills repo.
- **v0.3** (2026-04-18): Added full entrypoint + bake + $ZRO + Makefile + YDB GUI specs. Switched M-Unit fork from joelivey to ChristopherEdwards. Locked 30+ decisions.
- **v0.2** (2026-04-17): First comprehensive snapshot after project rename to vista-meta. DD exporter C (ViViaN) dropped. Added ADR discipline.
- **v0.1** (2026-04-17): Initial architecture + first-pass decision table.
