# vista-meta — relocation + GitHub publication (executed record)

> **EXECUTED.** Part A (relocate `~/vista-meta` → `~/projects/vista-meta`) was carried out
> 2026-05-04/05 — the repo lives at the new path (CLAUDE.md `location:`). Part B (publish to
> GitHub) is also done — `origin = git@github.com:rafael5/vista-meta.git` (private), pushed.
> Kept for the *how* and the decisions embedded in it. The **live** snapshot/restore runbook
> (Parts C/D) stays in [`../guides/vista-meta-restore.md`](../guides/vista-meta-restore.md).

## Part A — Relocate to `~/projects/vista-meta/`

Most of this is portable already: the [Makefile](../../Makefile) uses `$(PWD)` for
all bind mounts ([Makefile:37-39](../../Makefile#L37-L39)), and the named globals
volume is referenced by name (`VOLUME := vehu-globals`,
[Makefile:9](../../Makefile#L9)) — not by path. So a directory move with the
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

`make rm` is safe — [Makefile:53-55](../../Makefile#L53-L55) only removes the
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

### B.1 — What [.gitignore](../../.gitignore) already does for you

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

### B.2 — One decision to make about `patches/` (created at runtime)

[Makefile:333-345](../../Makefile#L333-L345) defines a `patch-new` workflow that
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
  clone can copy it. Currently `.env` is required by [Makefile:5](../../Makefile#L5)
  (`include .env`); without it, `make build` fails immediately.
- **Mention in the README** that `make sync-routines` is the explicit
  step to reconstitute the 7.1 GB upstream snapshot — it's not in the
  default `make run` flow.

---

