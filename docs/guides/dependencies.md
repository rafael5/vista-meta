# vista-meta — Dependency Manifest

Pinned versions and provenance for every upstream component baked into the
Docker image. This file always reflects the **current** image; old versions
are visible in git history.

Last updated: 2026-04-18

---

## Base image

| Field | Value |
|---|---|
| Component | Ubuntu |
| Version | 24.04 (noble) |
| Source | `docker.io/library/ubuntu:24.04` |
| Digest | (pin after first successful build) |
| Dockerfile layer | 1 |

## YottaDB

| Field | Value |
|---|---|
| Component | YottaDB |
| Version | r2.02 (build arg `YDB_VERSION`) |
| Installer URL | `https://gitlab.com/YottaDB/DB/YDB/-/raw/master/sr_unix/ydbinstall.sh` |
| Install flags | `--webserver --octo --force-install` |
| Dockerfile layer | 4 |
| Notes | Includes YDB core, YDB Web Server plugin, and Octo SQL engine (rocto) |

## VEHU-M (VistA routines + globals)

| Field | Value |
|---|---|
| Component | VistA-VEHU-M |
| Version | master (build arg `VEHU_M_URL`) |
| Source URL | `https://github.com/WorldVistA/VistA-VEHU-M/archive/master.zip` |
| SHA256 | (pin after first successful build) |
| Dockerfile layer | 5 |
| Notes | FOIA VistA + synthetic VEHU patient data |

## YDBOctoVistA (Octo DDL mapping)

| Field | Value |
|---|---|
| Component | YDBOctoVistA |
| Version | master (single file fetch) |
| Source URL | `https://gitlab.com/YottaDB/DBMS/YDBOctoVistA/-/raw/master/_YDBOCTOVISTAM.m` |
| Commit | (pin after first successful build) |
| Dockerfile layer | 8 |
| Notes | Generates SQL DDL from FileMan SQLI tables. See BL-002 for install details |

## M-Unit

| Field | Value |
|---|---|
| Component | M-Unit |
| Version | HEAD (shallow clone) |
| Source URL | `https://github.com/ChristopherEdwards/M-Unit.git` |
| Commit | (pin after first successful build) |
| Dockerfile layer | 9 |
| Notes | YDB plugin via cmake. ADR-015 |

## YDBGUI

| Field | Value |
|---|---|
| Component | YDBGUI |
| Version | HEAD (shallow clone) |
| Source URL | `https://gitlab.com/YottaDB/UI/YDBGUI.git` |
| Commit | (pin after first successful build) |
| Dockerfile layer | 10 |
| Notes | Angular frontend for YDB Web Server. Requires libsodium-dev, libcurl4-openssl-dev. See BL-001 |

## FMQL

| Field | Value |
|---|---|
| Component | FMQL |
| Version | HEAD (shallow clone) |
| Source URL | `https://github.com/caregraf/FMQL.git` |
| Commit | (pin after first successful build) |
| Dockerfile layer | 11 |
| Notes | FileMan Query Language. M routines copied to symlink farm. ADR-016 |

## Python packages

| Package | Version | Dockerfile layer | Notes |
|---|---|---|---|
| yottadb | (latest) | 12 | Python bindings for YottaDB |
| click | (latest) | 12 | CLI framework |
| pyyaml | (latest) | 12 | YAML parser |
| requests | (latest) | 12 | HTTP client |

Pin exact versions after first successful `pip install` by recording output
of `pip freeze` inside the built container.

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
