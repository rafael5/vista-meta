# ADR-010: Hybrid persistence — bind mounts + named volume + baked VEHU-M

Date: 2026-04-17
Status: Accepted

## Context
Docker persistence options: (a) bake everything into image (WorldVistA's default — reproducible but slow to rebuild), (b) bind-mount everything from host (fast dev loop, UID/perm overhead), (c) named volumes (Docker-managed), (d) hybrid combinations. vista-meta's workflow needs host-editable dev code but doesn't need host-visible globals.

## Decision
Three-way split:
1. **Baked into image**: YottaDB, VEHU-M routines + seed globals, Octo, M-Unit, FMQL, YDBGUI, Python tooling.
2. **Bind-mounted from host** (rw):
   - `~/vista-meta/vista/dev-r/` → `/home/vehu/dev/r/` (your M routines)
   - `~/vista-meta/vista/scripts/` → `/home/vehu/scripts/` (Python + shell)
   - `~/vista-meta/vista/export/` → `/home/vehu/export/` (analysis output)
3. **Named volume** `vehu-globals` → `/home/vehu/g/` (YDB globals .dat files)

## Consequences
- Positive: Edit routines on host, execute immediately in container. Core dev-loop win.
- Positive: Globals managed by Docker with correct perms; no host UID concerns for database files.
- Positive: Three distinct bind mounts mean scoped blast radius for accidental deletion.
- Positive: VEHU-M baked means reproducibility and fast rebuild when entrypoint changes (cache hits on expensive import step).
- Negative: Four distinct persistence mechanisms to document and reason about.
- Negative: Globals require `docker volume` commands for backup/restore (Makefile targets abstract this).

## Alternatives considered
- Bind-mount everything (including globals): UID/perm management pain for `.dat` files; no meaningful benefit since you never touch them from host.
- Named volume for everything: breaks live-edit workflow for routines.
- Bake everything: image rebuild on every code change; unworkable for iterative development.
