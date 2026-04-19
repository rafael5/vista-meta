# vista-meta — Build & Implementation Log

Append-only record of errors, warnings, corrections, and verification
outcomes encountered during implementation. Entries are reverse-chronological.
Each entry captures what happened, why, what was fixed, and the evidence trail.

This is **not** an ADR. ADRs record design decisions and their rationale.
This log records what went wrong (or right) when those decisions met reality.

---

## 2026-04-18 — First build attempt

### BL-011: First successful build — VistA sandbox functional

- **Date**: 2026-04-19
- **Milestone**: Core VistA system operational after 7 build iterations.
- **Working**: YottaDB r2.02, FileMan (date functions verified), patient data
  (VEHU synthetic), 39,338 compiled routines, 11 percent routines, sshd,
  RPC Broker, VistALink.
- **Not working**: Rocto (Octo plugin path — `_ydboctoInit.m` not in $ZRO),
  YDBGUI (Node.js WebSocket server starts but port check fails).
  Both are non-critical for PIKS classification work.
- **Build corrections applied**: BL-004 through BL-010 (7 fixes).
- **Build time**: ~8 min cached rebuild, ~12 min full rebuild on minty.
  Layer 7 (VEHU-M import + compile + ZTMGRSET) takes ~30 sec.
  Spec §4 estimated 5-15 min for import alone — actual is much faster.
  [Risk #4 confirmed: import time well under estimate]
- **Image size**: 1.31 GB content

### BL-010: VistA % routines not in VEHU-M distribution

- **Layer**: Dockerfile layer 7 / runtime
- **Error**: `%YDB-E-ZLINKFILE, Error while zlinking "_DTC"` — FileMan calls
  `D NOW^%DTC` but `%DTC.m` does not exist anywhere in the VEHU-M archive.
- **Root cause**: VistA `%` routines (`%DTC`, `%DT`, `%ZIS`, etc.) are Kernel
  system routines stored in the `^%` global namespace, not as `.m` files in
  `Packages/`. They are normally installed during VistA initialization via
  `%RI` from globals or a separate routine restore. The VEHU-M archive has
  the globals (`Packages/Kernel/Globals/%Z.zwr` etc.) but no corresponding
  `.m` routine files.
- **Fix**: TBD — need to either extract `%` routines from the `^%` globals
  after import, or source them from the YottaDB installation, or use `%RI`
  to load them from a routine file.
- **Impact**: Critical — FileMan and most Kernel utilities depend on `%` routines.
  Container starts but VistA functionality is broken.
- **File**: Investigation ongoing

### BL-009: YottaDB $ZRO parenthesized source(object) syntax broken in r2.02

- **Layer**: Dockerfile layers 7, 15, ydb_env.sh / runtime
- **Error**: `%YDB-E-FILENOTFND, File ZTMGRSET.m not found` despite the file
  existing at `/opt/VistA-M/r/ZTMGRSET.m` (hard copy, not symlink) and
  `$ZRO` containing `/opt/VistA-M/r(/opt/VistA-M/o)`.
- **Root cause**: The parenthesized `source(object)` syntax in `$ZRO` / 
  `ydb_routines` does not work in YottaDB r2.02 (GT.M V7.0-005). Confirmed
  with a controlled test: same file, same dirs — parenthesized = FILENOTFND,
  flat dirs = works. This may be a YDB r2.02 bug or a change in behavior.
  Original assumption was also that symlinks were the problem (they weren't —
  hard copies fail the same way with parenthesized syntax).
- **Fix**: Use flat directory entries in `$ZRO` instead of `source(object)` pairs.
  Object dirs listed BEFORE source dirs so pre-compiled `.o` files are found
  first. Changed in: Dockerfile ENV (build-time and runtime), `ydb_env.sh`.
- **Before**: `"/opt/VistA-M/r(/opt/VistA-M/o) $ydb_dist/libyottadbutil.so"`
- **After**: `"/opt/VistA-M/o /opt/VistA-M/r $ydb_dist/libyottadbutil.so"`
- **Impact**: Critical — without this fix, no VistA routines can be resolved.
- **File**: `docker/Dockerfile` layers 7+15, `docker/etc/ydb_env.sh`

### BL-008: /opt/VistA-M/o/ not writable by vehu — routine compilation silently failed

- **Layer**: Dockerfile layer 7 (VEHU-M import)
- **Error**: 39,331 .m routines in symlink farm but only 1 .o object file.
  Manual test: `$ydb_dist/mumps /opt/VistA-M/r/DICRW.m` → `%YDB-E-OBJFILERR`
  `Permission denied` on `/opt/VistA-M/o/DICRW.o`.
- **Root cause**: Layer 6 creates `/opt/VistA-M/o/` as root. Layer 7 runs as
  USER vehu. The `|| true` on the xargs compilation swallowed all 39K permission
  errors. Result: VistA routines exist as source (.m) but none are compiled (.o).
  YottaDB can compile on demand but FileMan routines can't be found because the
  object directory isn't writable.
- **Fix**: Added `chown -R vehu:vehu /opt/VistA-M/o` to layer 6 alongside the
  existing chown of `/home/vehu/g`.
- **Impact**: Critical — without compiled routines, no FileMan operations work.
  The container appeared functional but `D DT^DICRW` failed with ZLINKFILE.
- **File**: `docker/Dockerfile` layer 6

### BL-007: YDBGUI requires Node.js, web server is not an M routine

- **Layer**: entrypoint.sh phase 3 / Dockerfile layer 2
- **Error**: `%YDB-E-ZLINKFILE, Error while zlinking "%ydbwebreq"` — the routine
  `start^%ydbwebreq` does not exist. YDBGUI uses a Node.js WebSocket server
  (`plugin/etc/ydbgui/node/startup.js`), not an M routine.
- **Root cause**: BL-003 corrected the routine name but the web server is not
  an M process at all. `ydbinstall.sh --webserver` installs
  `_ydbmwebserver.so` (a shared library plugin). The YDBGUI frontend uses
  Node.js, which was not in the apt install list.
- **Fix (two parts)**:
  1. Added `nodejs` to Dockerfile layer 2 apt packages.
  2. Changed entrypoint.sh to start YDBGUI via
     `node $ydb_dist/plugin/etc/ydbgui/node/startup.js --port=8089`.
     Added graceful skip if node is not available.
- **File**: `docker/entrypoint.sh`, `docker/Dockerfile` layer 2

### BL-006: rocto not in PATH for vehu user

- **Layer**: entrypoint.sh phase 3
- **Error**: `bash: exec: rocto: not found` — the `rocto` binary is at
  `$ydb_dist/plugin/bin/rocto` which is not in the default PATH.
- **Root cause**: `ydbinstall.sh` installs Octo binaries under
  `$ydb_dist/plugin/bin/` and `$ydb_dist/plugin/octo/bin/`, neither of
  which is in PATH. The entrypoint used bare `rocto` command.
- **Fix**: Changed entrypoint.sh to use full path:
  `$ydb_dist/plugin/bin/rocto -p 1338`
- **File**: `docker/entrypoint.sh:47`

### BL-005: ydbinstall.sh requires file, bison, flex

- **Layer**: Dockerfile layer 4 (YottaDB install)
- **Error**: `ydbinstall.sh` exits with "Program(s) required to install YottaDB
  not found: file" and "Program(s) required to install selected plugins not
  found: bison flex".
- **Root cause**: `file` is a basic utility not in Ubuntu minimal. `bison` and
  `flex` are parser generators required by Octo's SQL engine build. Neither
  were in the layer 2 apt install list.
- **Fix**: Added `file`, `bison`, `flex` to layer 2 apt packages.
- **File**: `docker/Dockerfile` layer 2

### BL-004: Dockerfile inline comments break Docker parser

- **Layer**: Dockerfile layers 6 and 7
- **Error**: Docker build fails with `unknown instruction: 'exit'` on line 129.
- **Root cause**: Bare `#` comments on continuation lines inside `RUN` blocks.
  Docker's parser treats `#` after a `\` continuation as a Dockerfile
  instruction boundary, not a shell comment. Also, inline comments after
  `\` (e.g., `command \  # comment`) are invalid — `\` must be the last
  character on the line.
- **Fix**: Removed all bare `#` comment lines inside RUN blocks (3 occurrences
  in layer 6) and inline comments after `\` continuations (2 occurrences in
  layer 7: `-ignorechset` and `|| true` explanations).
- **Lesson**: In Dockerfiles, comments inside multi-line RUN commands must use
  shell comment syntax within the command itself (e.g., embedded in `echo`
  or moved to a comment line BEFORE the RUN), not standalone `#` lines
  between continuation lines.
- **File**: `docker/Dockerfile` layers 6–7

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
