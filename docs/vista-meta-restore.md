# vista-meta — relocate, version-control, and restore

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
| **Dev routines** (yours + anything KIDS writes) | Host [vista/dev-r/](vista/dev-r/) ↔ container `/home/vehu/dev/r/` | Mutable | **Yes** (`*.m` tracked, `*.o` ignored) | `git checkout -- vista/dev-r` |
| **Extracted model** (PIKS, code-model TSVs — the analytical artifacts) | [vista/export/data-model/](vista/export/data-model/) + [vista/export/code-model/](vista/export/code-model/) | Mutable, regenerable | **Yes** | Re-run `make bake` (slow) or `git checkout` |
| **Upstream snapshot** (40k routines, 7.1 GB) | [vista/vista-m-host/](vista/vista-m-host/) | Mutable, regenerable | **No** ([gitignore](.gitignore)) | `make sync-routines` after `make run` |

Two design moves keep the repo small and the recovery story honest:

- **Globals are not on a bind mount.** They live in a Docker named volume, so
  they survive `make rm` but can be wiped surgically with `docker volume rm`.
- **Upstream routines are gitignored, not the work product.** The 7.1 GB
  `vista-m-host/` snapshot is a regenerable derivative of the image; the
  ~308 KB you've added in `dev-r/` is your work. Both currently coexist in the
  filesystem; only the second goes to GitHub.

---

## Part A — Relocate to `~/projects/vista-meta/`

Most of this is portable already: the [Makefile](Makefile) uses `$(PWD)` for
all bind mounts ([Makefile:37-39](Makefile#L37-L39)), and the named globals
volume is referenced by name (`VOLUME := vehu-globals`,
[Makefile:9](Makefile#L9)) — not by path. So a directory move with the
container stopped is safe. Five things require explicit attention.

### A.1 — Stop the container before moving

A running container has bind mounts pointing at the old absolute paths;
moving the directory under it will leave the container with stale mounts
that fail silently on next write.

```bash
cd ~/vista-meta
make stop          # gracefully stops the container
make rm            # removes the container (KEEPS volume + image)
docker ps -a | grep vista-meta   # should be empty
```

`make rm` is safe — [Makefile:53-55](Makefile#L53-L55) only removes the
container, not the `vehu-globals` volume or the image. Your globals are
preserved on the named volume.

### A.2 — Move the directory

```bash
mkdir -p ~/projects
mv ~/vista-meta ~/projects/vista-meta
cd ~/projects/vista-meta
```

Watch out for two things:

- **`.env` is gitignored** but lives inside the directory, so it moves with
  it automatically. Verify after the move: `cat .env` should still show
  `TAILSCALE_IP=...`.
- **`snapshots/`** (also gitignored) — your globals tarballs. Moves with
  the directory. Confirm the size matches what it was before:
  `du -sh snapshots/`.

### A.3 — Recreate the auto-memory symlink at the new path

Claude's per-project memory lives at a path derived from the project's
absolute path (slashes converted to dashes):

- Old: `~/.claude/projects/-home-rafael-vista-meta/memory/`
- New: `~/.claude/projects/-home-rafael-projects-vista-meta/memory/`

Per `~/CLAUDE.md`, the canonical memory location is `~/claude/memory/`,
and per-project paths should symlink to it:

```bash
# If old project memory dir has anything you want to keep, copy it first
ls ~/.claude/projects/-home-rafael-vista-meta/memory/
# (currently empty — confirmed 2026-05-04)

# Replace the empty dir at the new path with a symlink
rm -rf ~/.claude/projects/-home-rafael-projects-vista-meta/memory
ln -s ~/claude/memory ~/.claude/projects/-home-rafael-projects-vista-meta/memory
```

This brings the project in line with your global convention so future
auto-memory writes land in the single source of truth at `~/claude/memory/`.

### A.4 — Restart the container at the new path

```bash
cd ~/projects/vista-meta
make run
docker inspect vista-meta --format '{{range .Mounts}}{{.Source}} -> {{.Destination}}{{"\n"}}{{end}}'
```

The mount lines should now show `/home/rafael/projects/vista-meta/...` for
the bind mounts. The `vehu-globals` mount is unchanged (volume name, not
path).

### A.5 — Sanity check

```bash
make doctor                         # environment health
make shell                          # ssh in
# inside the container:
ls /home/vehu/dev/r | head          # should match host vista/dev-r/
ls /home/vehu/g/mumps.dat           # globals file
exit
```

Optionally: scan for any stale absolute paths still pointing at the old
location (there shouldn't be any in tracked code, but local tooling may
have cached them):

```bash
grep -rn "/home/rafael/vista-meta" . \
  --exclude-dir=vista/vista-m-host \
  --exclude-dir=.git \
  --exclude-dir=host/.venv \
  --exclude-dir=node_modules
```

If anything turns up under `vscode-extension/dist/`, rebuild it.

---

## Part B — GitHub version control

### B.1 — What [.gitignore](.gitignore) already does for you

Your existing `.gitignore` is doing most of the work:

```
vista/export/**/raw/        # bake intermediates (regenerable)
vista/export/logs/          # bake logs
vista/vista-m-host/         # 7.1 GB upstream snapshot (regenerable)
snapshots/                  # globals tarballs (large, machine-local)
host/.venv/                 # python venv
*.o                         # YDB compiled object files
.env                        # contains TAILSCALE_IP
patches/                    # decomposed-on-disk KIDS work area
```

What this means concretely for the goals you stated:

- **40k upstream routines** → not pushed (`vista/vista-m-host/` is ignored).
- **Routines you write or edit** → pushed (`vista/dev-r/*.m` is tracked).
- **Routines installed by a KIDS bill** → pushed, because KIDS writes to
  the first writable `$ZRO` dir, which is `/home/vehu/dev/r/` ↔
  `vista/dev-r/`. New `.m` files appear there and get picked up by git.
- **Compiled `.o` files** → not pushed (`*.o` ignored). They're regenerated
  on next routine load.
- **The extracted model** (PIKS TSVs, code-model TSVs, ~1M rows total) →
  pushed. These are the analytical work product and are durably tracked.

### B.2 — One decision to make about [`patches/`](patches/)

[Makefile:333-345](Makefile#L333-L345) defines a `patch-new` workflow that
scaffolds decomposed KIDS patches under `patches/<NAME>/`. This directory
is **currently gitignored**, presumably because early-stage patch trees
are noisy / experimental.

If you want your hand-authored KIDS patches *version-controlled* as you
develop them, drop the `patches/` line from `.gitignore`. Recommended:

```bash
# Option 1: track all patches you author
sed -i '/^patches\/$/d' .gitignore

# Option 2: track a curated subset
# leave .gitignore as-is and put work you want tracked under
# vista/dev-r/ or a new top-level dir like my-patches/
```

The kids-vc round-trip on real corpus is 100% (per `~/projects/py-kids-vc/docs/kids-vc-guide.md`),
so committing decomposed patch trees is a reasonable workflow — you get
diffable patch authoring with a deterministic re-assembly path.

### B.3 — Confirm the working tree before pushing

```bash
cd ~/projects/vista-meta
git status                            # currently has uncommitted CLAUDE.md + docs
du -sh --exclude=vista/vista-m-host \
       --exclude=vista/export/logs \
       --exclude=snapshots \
       --exclude=host/.venv \
       --exclude=.git \
       .                              # ~197 MB — well under GitHub limits
```

Quick check that no individual tracked file exceeds GitHub's 100 MB
hard limit (none should, but worth verifying once):

```bash
git ls-files | xargs -I{} du -b "{}" 2>/dev/null \
  | sort -nr | head -10
```

The largest tracked files will be the code-model TSVs (XINDEX outputs run
to ~30-50 MB each; well under the limit). No need for git-LFS at this size.

### B.4 — Initial push

The repo is already `git init`-ed on `main`. Three steps:

```bash
# 1. Commit anything pending (your call on what to include)
git add -p          # or specific files
git commit -m "..."

# 2. Create the GitHub repo via gh CLI
gh repo create vista-meta --private --source=. --remote=origin
# --private is the safer default for a personal sandbox; flip to --public
# when you're ready

# 3. Push
git push -u origin main
```

Expect ~197 MB of upload on first push. Subsequent pushes are diffs.

### B.5 — How fresh clones reconstitute the 7.1 GB they didn't get

The clone-then-bootstrap path on a new machine:

```bash
git clone git@github.com:rafaelrichards/vista-meta.git ~/projects/vista-meta
cd ~/projects/vista-meta
cp .env.example .env                  # if you add one — see note below
make build                            # ~20 minutes
make run                              # globals come from baked image on first run
make sync-routines                    # restores vista/vista-m-host/ (7.1 GB)
make doctor                           # green
```

Two follow-ups worth doing alongside the first push:

- **Add a `.env.example`** with `TAILSCALE_IP=` (no value) so a fresh
  clone can copy it. Currently `.env` is required by [Makefile:5](Makefile#L5)
  (`include .env`); without it, `make build` fails immediately.
- **Mention in the README** that `make sync-routines` is the explicit
  step to reconstitute the 7.1 GB upstream snapshot — it's not in the
  default `make run` flow.

---

## Part C — Pre-install discipline (do this **before** every KIDS install)

KIDS is forward-only. Per ADR-046 (in `~/projects/py-kids-vc/docs/adr/046-*.md`):

> KIDS install is an imperative sequence that overwrites routine source,
> merges DD changes directly into `^DD`, adds entries in File 19/101/8994,
> and runs pre/post-install MUMPS code that can do arbitrary data
> transformation. KIDS keeps no previous-state snapshot.

So your only honest pre-install line of defense is: **snapshot first, install
second**. The Makefile already gives you both halves
([Makefile:132-148](Makefile#L132-L148)):

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
[entrypoint.sh:74-87](docker/entrypoint.sh#L74-L87) only if the bake
sentinel was on the volume; if export is on a bind mount (it is —
[Makefile:39](Makefile#L39)), bake state survives this. Good — you don't
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

- [Makefile](Makefile) — all the targets above
- [docker/Dockerfile](docker/Dockerfile) — image baseline (immutable layer)
- [docker/entrypoint.sh](docker/entrypoint.sh) — bake sentinel logic
- [.gitignore](.gitignore) — what's pushed and what's ignored
- [ADR-029](docs/adr/029-symlink-farm.md) — flat routine namespace (now hard copies per BL-009)
- [ADR-045](docs/adr/045-data-code-separation-package-bridge.md) — host-side `vista/vista-m-host/` snapshot
- ADR-046 (in `~/projects/py-kids-vc/docs/adr/046-*.md`) — why KIDS undo is hard
- `~/projects/py-kids-vc/docs/kids-vc-guide.md` — patch decompose/assemble workflow
