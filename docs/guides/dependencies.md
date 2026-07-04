# vista-meta — Dependency Manifest

Pinned versions for every upstream component baked into the Docker image.

**Reproducibility pass (2026-07-04, BL-015):** every network fetch in the
Dockerfile is now pinned to an immutable ref (commit SHA or release tag) via
build ARGs — this file records those pins and is updated in the same commit as
any bump. Two documented residuals: the base image is pinned by tag (not
digest), and YDBGUI's cmake auto-fetches its plugin deps (YDB-Web-Server,
YDBCurl, YDBPosix) at build time — transitive and unpinned upstreamly.
Note: the *currently running* image predates these pins (built from
then-current masters in April 2026); the first `make build` after this pass
becomes the canonical pinned build.

Last updated: 2026-07-04 (all source pins to commit SHAs; FMQL removed)

---

## Base image

| Field | Value |
|---|---|
| Component | Ubuntu |
| Version | 24.04 (noble) |
| Source | `docker.io/library/ubuntu:24.04` |
| Digest | pinned by tag only (accepted residual — record digest at next build if desired) |
| Dockerfile layer | 1 |

## YottaDB

| Field | Value |
|---|---|
| Component | YottaDB |
| Version | r2.02 (build arg `YDB_VERSION`) |
| Installer URL | `https://gitlab.com/YottaDB/DB/YDB/-/raw/r2.02/sr_unix/ydbinstall.sh` (release-tag ref) |
| Install flags | `--webserver --octo --force-install` |
| Dockerfile layer | 4 |
| Notes | Includes YDB core, YDB Web Server plugin, and Octo SQL engine (rocto) |

## VEHU-M (VistA routines + globals)

| Field | Value |
|---|---|
| Component | VistA-VEHU-M |
| Version | commit `62622e63fc7d` (build arg `VEHU_M_COMMIT`) |
| Source URL | `https://github.com/WorldVistA/VistA-VEHU-M/archive/${VEHU_M_COMMIT}.zip` |
| Commit | `62622e63fc7dffad27fc79f107fd7689c2ac4eff` |
| Dockerfile layer | 5 |
| Notes | FOIA VistA + synthetic VEHU patient data |

## YDBOctoVistA (Octo DDL mapping)

| Field | Value |
|---|---|
| Component | YDBOctoVistA |
| Version | commit `a943ff7ffc25` (build arg `YDBOCTOVISTAM_COMMIT`) |
| Source URL | `https://gitlab.com/YottaDB/DBMS/YDBOctoVistA/-/raw/${YDBOCTOVISTAM_COMMIT}/_YDBOCTOVISTAM.m` |
| Commit | `a943ff7ffc25ee94dde7e9f27a18beb73b79d89e` |
| Dockerfile layer | 8 |
| Notes | Generates SQL DDL from FileMan SQLI tables. See BL-002 for install details |

## M-Unit

| Field | Value |
|---|---|
| Component | M-Unit |
| Version | commit `a31638202f92` (build arg `MUNIT_COMMIT`, archive zip) |
| Source URL | `https://github.com/ChristopherEdwards/M-Unit/archive/${MUNIT_COMMIT}.zip` |
| Commit | `a31638202f9283e02e253fe59b85722ece7cfae9` |
| Dockerfile layer | 9 |
| Notes | YDB plugin via cmake. ADR-015 |

## YDBGUI

| Field | Value |
|---|---|
| Component | YDBGUI |
| Version | commit `19bc88a42c0f` (build arg `YDBGUI_COMMIT`, archive zip) |
| Source URL | `https://gitlab.com/YottaDB/UI/YDBGUI/-/archive/${YDBGUI_COMMIT}/…zip` |
| Commit | `19bc88a42c0f96593be4610cc2d23e0918748205` |
| Dockerfile layer | 10 |
| Notes | Angular frontend for YDB Web Server. Requires libsodium-dev, libcurl4-openssl-dev. See BL-001 |

## FMQL — REMOVED (2026-07-04, BL-015)

The upstream (`github.com/caregraf/FMQL`) is gone (404), and the original
layer's trailing `|| true` had rescued the whole clone-and-copy chain — FMQL
was never actually present in any built image (verified: zero FMQL routines).
Layer removed; ADR-016's other two DD-exporter baselines are unaffected.

## Python packages

| Package | Version | Dockerfile layer | Notes |
|---|---|---|---|
| yottadb | ==2.0.1 | 12 | Python bindings for YottaDB |
| click | ==8.4.0 | 12 | CLI framework |
| pyyaml | ==6.0.3 | 12 | YAML parser |
| requests | ==2.34.2 | 12 | HTTP client |

Versions recorded from the running image (`pip3 show`, 2026-07-04) and pinned
in the Dockerfile.

## System packages (apt)

Installed in layer 2. Version pinning deferred to Ubuntu 24.04 archive
snapshots. Key packages:

| Package | Purpose |
|---|---|
| tini | PID 1 init (ADR-021) |
| openssh-server | sshd on :22 |
| xinetd | RPC Broker + VistALink listeners |
| build-essential, cmake, pkg-config | Build tools for YDB plugins |
| libsodium-dev | YDBGUI auth support (BL-001) |
| libcurl4-openssl-dev | YDBGUI HTTP client (BL-001) |
| libelf-dev, libicu-dev, libconfig-dev, libreadline-dev, libssl-dev | YDB + Octo build deps |
| python3, python3-pip, python3-venv | Python runtime |
| ranger, micro, tree, btop, ncdu, less, jq | Interactive tools (ADR-019) |
