# DE-NOVO — from clean clone to verified VistA, unaided

The single ordered path for a third party (or future you, on a fresh machine)
to reproduce this stack with no prior context and no assistant. Each step names
its verification and the failure modes already hit (BL-NNN in
[`../build-log.md`](../build-log.md)).

Two distinct goals — pick yours:

- **A. Use the models** (most people): no build needed at all. Skip to §1.
- **B. Rebuild the container + re-extract the models**: §2 onward (~30 min,
  ~2 GB downloads, Linux + Docker required).

---

## 0. Prerequisites

| Need | For | Check |
|---|---|---|
| Linux host (macOS untested, Windows excluded) | B | — |
| Docker Engine + compose plugin | B | `docker compose version` |
| Python ≥ 3.10, **stdlib only** (no pip installs) | A + B | `python3 -V` |
| ~25 GB free disk (19 GB image + volume + source) | B | `df -h` |
| Node 20+ (only to rebuild the VSCode extension) | optional | `node -v` |

Clone, then let the CLI check the environment for you:

```bash
git clone https://github.com/rafael5/vista-meta.git && cd vista-meta
bin/vista-meta doctor        # host-side health: tools, hooks, TSV presence
```

## 1. Goal A — use the shipped models (no container)

The finished artifacts are **in the clone**: `vista/export/data-model/`
(4 TSVs), `vista/export/code-model/` (20 TSVs), `vista/export/RESEARCH.md`.
Shapes are `schema_version: 1` — contract in
[`../reference/schema-v1-normalization-spec.md`](../reference/schema-v1-normalization-spec.md);
integrity manifest in [`../releases/data-v1.manifest.json`](../releases/data-v1.manifest.json).

```bash
bin/vista-meta pkg "Pharmacy"      # package overview
bin/vista-meta context PSO         # AI context pack
bin/vista-meta callers PSOVCC      # caller graph
```

Guides: [`vista-meta-guide.md`](vista-meta-guide.md) (start here) ·
[`code-model-guide.md`](code-model-guide.md) (per-TSV schema) ·
[`piks-analysis-guide.md`](piks-analysis-guide.md) (classification queries).
Extension: `cd vscode-extension && npm ci && npm run compile` (or install the
packaged `.vsix`); it auto-discovers `vista/export/` as its data root.

**Done.** Everything below is only for rebuilding the engine.

## 2. Goal B — configure

```bash
cp .env.example .env
```

Defaults bind `127.0.0.1:{2222,9430,8001,1338,8089}` (ADR-050 — local-only).
If another container on your machine already holds a port, set the offsets in
`.env` (`RPC_PORT=9530`, `VLINK_PORT=8101`) — container-side ports never
change. *Failure mode: `make run` → "port is already allocated" — this is that.*

## 3. Build the image (~20 min, ~2 GB downloads)

```bash
make build
```

Every upstream fetch is pinned to an immutable ref (commit SHAs as `ARG`s in
`docker/Dockerfile`; the pin ledger is [`dependencies.md`](dependencies.md)).
Known sharp edges, already survived once:
- **BL-012**: `mupip load` chokes on paths with spaces — handled in bake.sh.
- **BL-009**: YDB r2.02 `$ZRO` source(object) syntax — handled (flat dirs).
- **BL-015**: never guard a fetch chain with a trailing `|| true` — a dead
  upstream then "succeeds" silently (this bit the removed FMQL layer).

## 4. Run + first bake

```bash
make run              # container up; FIRST run kicks a background bake
make wait-for-bake    # progress dots until the sentinel flips (ADR-022/035)
```

The bake extracts routines/globals inventories inside the container
(continue-on-error per ADR-023 — check `vista/export/logs/` if a phase fails).
Bind-mounted output lands in `vista/export/` owned by uid 1001 (ADR-009) —
host edits to those files need group 1001, in-container write, or a one-off
`docker run -u 1001` (see the restore runbook).

## 5. Verify — the two gates

```bash
make smoke            # S-01…S-12: engine, data plane, services, FileMan, data
bin/vista-meta doctor # host-side: TSVs present + fresh, tools wired
```

Expected smoke: **10 PASS / 0 FAIL / 2 WARN** — the warnings (rocto, YDB GUI)
are unconsumed baked services, non-gating by ADR-051. Any FAIL prints the
failing command's output; S-07 speaks real XWB protocol to the RPC Broker
(port-only probes hide handler crashes — BL-014).

## 6. Re-extract the models (optional)

The clone already carries the extracted models; to regenerate from *your*
container: the `make` pipeline targets are listed in
[`vista-meta-guide.md`](vista-meta-guide.md) §5.1 (`make inventory`,
`make xindex`, `make routine-calls`, … then `make normalize-dumps`).
Determinism check: `make validate` red-gates the schema_v1 contract, and the
`content_hash` recipe fingerprints the data independent of packaging. Note:
your corpus hash will match `data-v1` only if your image was built from the
same pinned VEHU-M commit (`VEHU_M_COMMIT` — see BL-015 pass).

## 7. When something breaks

1. `make smoke` output names the failing layer; `docker logs vista-vehu` has
   the entrypoint's per-service lines.
2. [`../build-log.md`](../build-log.md) — every build/runtime failure hit so
   far, with cause and fix (BL-001…BL-015).
3. [`vista-meta-restore.md`](vista-meta-restore.md) — snapshot/restore tiers
   if a KIDS install or experiment wrecked the globals.
4. `docs/README.md` — the docs index; `make help` — every target, one line each.
