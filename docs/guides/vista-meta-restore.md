# vista-meta — snapshot & restore runbook

A single guide covering three related operations:

1. **Relocate** the project from `~/vista-meta/` to `~/projects/vista-meta/`
   so it sits alongside every other project under `~/projects/`.
2. **Publish to GitHub** in a way that tracks your own work (dev routines,
   KIDS patches, the extracted data + code model) but **does not** push the
   ~40k upstream VistA-M routines.
3. **Recover** when a KIDS install or a hand-rolled routine breaks VistA.
   Because KIDS is forward-only (ADR-046 (in `~/projects/py-kids-vc/docs/adr/046-*.md`)),
   "restore" here means rolling globals + dev routines back to a known-good
   state, not surgical patch removal.

The three sections are independent — read whichever you need.

---

## Big picture: what is mutable, what is regenerable, what is tracked

This is the mental model the rest of the document depends on. Five distinct
categories of state, each with a different durability story:

| Layer | Where it lives | Mutability | Git? | Restore from |
|---|---|---|---|---|
| **Image baseline** (VistA-M source + baked globals + compiled `.o`) | Docker image `vista-meta:latest` | Immutable once built | No | Rebuild via `make build` |
| **Runtime globals** (the live database — what KIDS mutates) | Named volume `vehu-globals` mounted at `/home/vehu/g/` | Mutable | No | Image baseline (first run) **or** `snapshots/globals-*.tar.gz` |
| **Dev routines** (yours + anything KIDS writes) | Host [vista/dev-r/](../../vista/dev-r/) ↔ container `/home/vehu/dev/r/` | Mutable | **Yes** (`*.m` tracked, `*.o` ignored) | `git checkout -- vista/dev-r` |
| **Extracted model** (PIKS, code-model TSVs — the analytical artifacts) | [vista/export/data-model/](../../vista/export/data-model/) + [vista/export/code-model/](../../vista/export/code-model/) | Mutable, regenerable | **Yes** | Re-run `make bake` (slow) or `git checkout` |
| **Upstream snapshot** (40k routines, 7.1 GB) | [vista/vista-m-host/](../../vista/vista-m-host/) | Mutable, regenerable | **No** ([gitignore](../../.gitignore)) | `make sync-routines` after `make run` |

Two design moves keep the repo small and the recovery story honest:

- **Globals are not on a bind mount.** They live in a Docker named volume, so
  they survive `make rm` but can be wiped surgically with `docker volume rm`.
- **Upstream routines are gitignored, not the work product.** The 7.1 GB
  `vista-m-host/` snapshot is a regenerable derivative of the image; the
  ~308 KB you've added in `dev-r/` is your work. Both currently coexist in the
  filesystem; only the second goes to GitHub.

---

## Relocation + GitHub publication (done)

The one-time relocate-to-`~/projects/`-and-publish procedure was executed (2026-05)
and is archived at
[`../historical/relocate-and-publish-record.md`](../historical/relocate-and-publish-record.md).

## Part C — Pre-install discipline (do this **before** every KIDS install)

KIDS is forward-only. Per ADR-046 (in `~/projects/py-kids-vc/docs/adr/046-*.md`):

> KIDS install is an imperative sequence that overwrites routine source,
> merges DD changes directly into `^DD`, adds entries in File 19/101/8994,
> and runs pre/post-install MUMPS code that can do arbitrary data
> transformation. KIDS keeps no previous-state snapshot.

So your only honest pre-install line of defense is: **snapshot first, install
second**. The Makefile already gives you both halves
([Makefile:132-148](../../Makefile#L132-L148)):

```bash
# 1. Snapshot globals BEFORE installing
make snapshot-globals
# → snapshots/globals-2026-05-04-235901.tar.gz
# → auto-prunes to last 5 snapshots

# 2. Commit dev/r BEFORE installing
git add vista/dev-r
git commit -m "pre-KIDS-install: ABC*1.0*42 baseline"

# 3. Now install the KIDS bill — via FORUM, KIDS menu, or kids-vc
```

Two snapshots, two layers of recovery. Globals snapshot covers the database
side (DD, Files 19/101/8994, FileMan data). Git commit covers the routine
side (anything written into `dev/r/`).

If the install succeeds and you're satisfied: keep going. The auto-pruner
keeps the last 5 globals snapshots, so old known-good states naturally
roll forward.

If the install breaks something: see Part D.

---

## Part D — Restore procedures (three tiers, escalating in scope)

Pick the tier matching the scope of damage. Tier 1 is the surgical
single-patch unwind, Tier 3 is the "blow it all away and rebuild from
image" option you asked about.

### Tier 1 — Surgical: roll back one bad install, keep everything else

**When**: the most recent KIDS install broke something, and you took a
snapshot + git commit immediately before it (Part C).

```bash
# 1. Stop and remove the container so the volume isn't in use
make stop
make rm

# 2. Restore globals from the pre-install snapshot
make restore-globals SNAPSHOT=snapshots/globals-2026-05-04-235901.tar.gz
# (prompts for confirmation — answer y)

# 3. Restore dev/r from git
git checkout -- vista/dev-r
git status   # confirm clean

# 4. Bring the container back up
make run
make doctor
```

The image is untouched. The named volume's contents are replaced from
the tarball. Your dev routines revert to the last commit. Total time:
maybe a minute.

This is the right tier ~95% of the time.

### Tier 2 — Volume reset: fall back to the image's baked globals

**When**: globals are corrupt, you have no usable snapshot, but the image
itself is still good. Wipes globals, keeps image and your dev routines.

```bash
make stop
make rm
docker volume rm vehu-globals
# → Docker re-creates the volume on next 'make run' and copies the image's
#   /home/vehu/g content into it (this is Docker's standard behavior for
#   named volumes mounted on directories with content)

# Optional: sweep dev/r if you suspect a routine there is the actual culprit
mv vista/dev-r vista/dev-r.broken-2026-05-04
mkdir vista/dev-r

make run
make doctor
```

You're now back to whatever globals state was baked into the image at
`make build` time — i.e., a clean post-VEHU-import VistA. The first run
will re-trigger the bake sentinel logic in
[entrypoint.sh:74-87](../../docker/entrypoint.sh#L74-L87) only if the bake
sentinel was on the volume; if export is on a bind mount (it is —
[Makefile:39](../../Makefile#L39)), bake state survives this. Good — you don't
re-bake unless you want to.

### Tier 3 — Full rebuild: nuke everything, restore from image rebuild

**When**: the image itself is suspect, or you want a guaranteed-pristine
starting point. ~20 minutes total.

```bash
# 1. Destroy container + volume + image (with prompt, per Makefile:57-64)
make clean
# This removes:
#   - container vista-meta
#   - volume vehu-globals
#   - images vista-meta:latest and vista-meta:<date>
# It does NOT touch:
#   - snapshots/  (your tarballs survive)
#   - vista/dev-r/  (your routines survive)
#   - vista/export/  (your TSVs survive)
#   - docs/, host/, vscode-extension/, etc.

# 2. (Optional) clear dev/r if a bad routine is suspected
mv vista/dev-r vista/dev-r.broken-2026-05-04
mkdir vista/dev-r

# 3. Rebuild from Dockerfile
make build           # ~20 min: re-fetches VEHU-M, re-bakes globals, recompiles
make run             # bake sentinel triggers in background
make wait-for-bake   # poll until done (optional)

# 4. Re-snapshot the host-visible upstream tree
make sync-routines   # restores vista/vista-m-host/ from the new image
make doctor
```

After this, you have an image identical to a fresh `make build` from the
current Dockerfile, an empty named volume re-populated from that image's
baked globals, and a clean `dev/r/` (or your saved-aside one if you
want to selectively restore individual routines).

### Tier-selection cheat sheet

| Symptom | Tier |
|---|---|
| One KIDS bill misbehaved; pre-install snapshot exists | 1 |
| Globals look corrupt; no snapshot; image is fine | 2 |
| Image was built against a stale upstream and you want a fresh fetch | 3 |
| Investigating "what was the baseline?" — comparing current state to image | 2 (then snapshot before resuming work) |
| YDB error on routine compile that survives `make restart` | 1 if dev/r-introduced; 2 if you suspect baked `.o`s |

### What survives every tier

| | Tier 1 | Tier 2 | Tier 3 |
|---|---|---|---|
| Image | yes | yes | rebuilt |
| Globals volume | replaced from snapshot | wiped, repopulated from image | wiped, repopulated from rebuilt image |
| `vista/dev-r/` | reverted via git | preserved (or saved aside) | preserved (or saved aside) |
| `snapshots/` | preserved | preserved | preserved |
| `vista/export/` (TSVs) | preserved | preserved | preserved |
| Git history | untouched | untouched | untouched |

---

## Future: surgical per-patch undo (Phase 9, proposed)

ADR-046 (in `~/projects/py-kids-vc/docs/adr/046-*.md`) outlines a planned
**kids-vc undo** feature: a pre-install MUMPS hook (`VMKVCUNDO`) that
captures pre-state into `^XTMP("KVC-UNDO",<patch>,...)` and a Python tool
that re-emits it as a reverse `.KID`. Per the ADR, that scope covers
declarative content (routines, DDs, options, protocols, RPCs, security
keys) — but not pre/post-install MUMPS side effects, FileMan data
mutations, or cascading data changes.

Until that ships, the snapshot-first / commit-first discipline in Part C
is the working answer.

---

## Appendix: quick-reference commands

```bash
# Lifecycle
make build               # build image (~20 min first time)
make run                 # start container (creates volume on first run)
make stop                # graceful stop
make rm                  # remove container, keep volume + image
make clean               # remove container + volume + image (prompts)
make restart             # stop + rm + run

# Pre-install discipline
make snapshot-globals    # tarball the volume (auto-prunes to last 5)
git add vista/dev-r && git commit -m "pre-install baseline"

# Restore tiers
make restore-globals SNAPSHOT=snapshots/globals-DATE.tar.gz   # Tier 1 (globals)
git checkout -- vista/dev-r                                   # Tier 1 (routines)
docker volume rm vehu-globals                                 # Tier 2
make clean && make build && make run                          # Tier 3

# Host-side sync
make sync-routines       # refresh vista/vista-m-host/ (7.1 GB)
make inventory           # rebuild routines.tsv + packages.tsv
make doctor              # health check
```

---

## Cross-references

- [Makefile](../../Makefile) — all the targets above
- [docker/Dockerfile](../../docker/Dockerfile) — image baseline (immutable layer)
- [docker/entrypoint.sh](../../docker/entrypoint.sh) — bake sentinel logic
- [.gitignore](../../.gitignore) — what's pushed and what's ignored
- [ADR-029](../adr/029-symlink-farm-routines.md) — flat routine namespace (now hard copies per BL-009)
- [ADR-045](../adr/045-data-code-separation-package-bridge.md) — host-side `vista/vista-m-host/` snapshot
- ADR-046 (in `~/projects/py-kids-vc/docs/adr/046-*.md`) — why KIDS undo is hard
- `~/projects/py-kids-vc/docs/kids-vc-guide.md` — patch decompose/assemble workflow
