# vista-meta — Build & Implementation Log

Append-only record of errors, warnings, corrections, and verification
outcomes encountered during implementation. Entries are reverse-chronological.
Each entry captures what happened, why, what was fixed, and the evidence trail.

This is **not** an ADR. ADRs record design decisions and their rationale.
This log records what went wrong (or right) when those decisions met reality.

---

## 2026-04-18 — Dockerfile + entrypoint first draft

### BL-003: YDB Web Server startup routine was wrong

- **Layer**: entrypoint.sh, phase 3 (service startup)
- **Error**: Used `start^%ydbwebhandler` as the M entry point for the YDB Web Server.
- **Root cause**: Guessed routine name. `%ydbwebhandler` does not exist.
- **Fix**: Changed to `start^%ydbwebreq`, which is the documented entry point
  for the YDB Web Server installed via `ydbinstall.sh --webserver`.
  Also removed a spurious `--` separator before `--port`.
- **Before**: `$ydb_dist/yottadb -run start^%ydbwebhandler -- --port 8089`
- **After**: `$ydb_dist/yottadb -run start^%ydbwebreq --port 8089`
- **Source**: YottaDB Web Server documentation; `start^%ydbwebreq` runs in
  foreground and exits on SIGTERM — correct for entrypoint supervision.
- **File**: `docker/entrypoint.sh:48`

### BL-002: %YDBOCTOVISTAM not bundled with Octo

- **Layer**: Dockerfile layer 8 (Octo DDL mapping)
- **Error**: Assumed `%YDBOCTOVISTAM` routine was installed by `ydbinstall.sh --octo`.
  It is not. The routine lives in a separate project: `YottaDB/DBMS/YDBOctoVistA`.
- **Root cause**: Spec §4 layer 8 says "Run `D MAPALL^%YDBOCTOVISTAM`" without
  noting the routine must be fetched separately.
- **Fix (two parts)**:
  1. Added `curl` step to fetch `_YDBOCTOVISTAM.m` from GitLab and compile it.
  2. Fixed the invocation: MAPALL requires FileMan context — `DUZ=.5`,
     `DIQUIET=1`, `DUZ(0)="@"`, and `DT^DICRW` must be called first.
     It also takes an output file path as argument.
- **Before**: `mumps -r %XCMD 'D MAPALL^%YDBOCTOVISTAM'`
- **After**:
  ```
  curl ... _YDBOCTOVISTAM.m → /opt/VistA-M/r/
  mumps compile
  mumps -r %XCMD 'S DUZ=.5,DIQUIET=1,DUZ(0)="@" D DT^DICRW,MAPALL^%YDBOCTOVISTAM("/opt/VistA-M/ddl/vista.sql")'
  ```
- **Source**: [YDBOctoVistA README](https://gitlab.com/YottaDB/DBMS/YDBOctoVistA)
- **File**: `docker/Dockerfile` layer 8

### BL-001: YDBGUI missing build dependencies

- **Layer**: Dockerfile layer 2 (OS deps) + layer 10 (YDBGUI install)
- **Error**: YDBGUI cmake build requires `libsodium-dev` and `libcurl4-openssl-dev`,
  which were not in the apt install list. Build would fail at cmake configure.
- **Root cause**: Did not check YDBGUI's `CMakeLists.txt` dependencies before
  writing layer 2. The cmake build auto-fetches missing YDB plugins (YDBCurl,
  YDBPosix) but needs system-level libs present.
- **Fix**: Added `libsodium-dev libcurl4-openssl-dev` to layer 2 apt install.
- **Verification**: YDBGUI's cmake approach confirmed correct — it matches what
  `ydbinstall.sh --gui` does internally (clone + cmake + make install).
- **File**: `docker/Dockerfile` layer 2
