# Proposal: docs/ lifecycle reorganization — so it still makes sense in six months

**Status:** EXECUTED 2026-07-04 (phases 0–3; commits dffe514 · 16d13f3 · bc86e30 · 82212c7).
The optional phase 4 (relocate `Packages.csv` out of `docs/` — a code change across 5 scripts
+ Makefile + fixtures) was deliberately deferred and is tracked as TODO T-005.
**Date:** 2026-07-04
**Basis:** full deep-read audit of all 65 files under `docs/` + root strays + `CLAUDE.md`/`README.md`/`TODO.md`,
cross-checked against the repo state (schema-v1 TSV headers, Makefile, `vscode-extension/package.json`,
git history through Compass 0.2.0 / data-v1).

---

## 1. The problem, in evidence

The docs are good — the *filing system* is what's rotting. Five concrete failure modes, all verified:

1. **Yesterday's `guides/` move (19b655c) broke the index layer.** ~28 links in `CLAUDE.md` +
   `README.md` still point at `docs/<name>.md`; `TODO.md` T-004's link is dead; every
   `../`-relative link *inside* the moved guides is off by one directory; 30+ source files cite
   `# Spec: docs/vista-meta-spec-v0.4.md § N` at the old path. The project's primary map
   (CLAUDE.md's Documentation table) is now mostly dangling, and it also lists
   `docs/vista-cli-planning.md`, which does not exist anywhere.
2. **Executed work still sits in live positions.** `proposals/producer-contracts-implementation-plan.md`
   is fully executed (V1–V7 each landed with a gate-PASS commit, f1e9d33…a27e04a);
   `proposals/v4-session-kickoff.md` is a spent one-shot session prompt;
   `guides/heads-up-vista-info-hub.md` is a delivered cross-org memo;
   `guides/upstream-data-fixes.md` is an executed P1–P5 fix record;
   `guides/vista-meta-restore.md` Part A (relocation) already happened. In six months these read
   as instructions, not history.
3. **Live contracts are misfiled as proposals.** `proposals/schema-v1-normalization-spec.md` is
   cited as `# Spec:` by 8 host scripts + tests and materialized by the shipped data-v1 release
   and Compass 0.2.0 — yet its header still claims "pre-first-release… no consumer pinned… no
   code," all now false. A proposal folder is where documents go to be *closed*; a contract of
   record must never be closed.
4. **The data shipped past the docs.** schema-v1 normalization silently staled every per-TSV
   reference: `rpcs.tsv` is 12 columns (doc says 8), `options.tsv` 9 (doc says 8),
   `routine`→`routine_name`, new `ien`/`*_label`/`package_dir` columns undocumented; the
   PIKS guide's "primary output" `vista-fileman-piks-comprehensive.csv` **no longer exists** and
   all five of its §6 query recipes are dead; coverage numbers (98.3%, 7,886+217, 141 remaining)
   no longer reconcile with the shipped `piks.tsv` (8,261 rows, triage 220); a
   `package-situational-awareness` awk recipe filters `rpcs.tsv $5` where package is now `$11`
   (silently returns nothing). The extension docs still use the pre-Compass `vistaMeta.*`
   namespace and `vista-meta-0.1.0.vsix` (real: `vistaCompass.*`, `vista-compass-0.2.0.vsix`),
   and `vscode-extension-internals.md` describes the shipped PIKS hover as future roadmap.
5. **The governance record stopped.** No ADR since 045 (Apr 19) despite the two biggest
   externally-visible decisions of the project shipping since (the data-v1 producer-contract
   release model; the Compass extension architecture). ADR-044 states a project root that is no
   longer true (`~/vista-meta` vs actual `~/projects/vista-meta`); ADR-027's sole test artifact
   (`tests/smoke/post-build-smoke.sh`) doesn't exist. `build-log.md` died at BL-013 (Apr 19).
   `TODO.md` T-001/2/3 duplicate RESEARCH RF-010/016/024.

## 2. Target structure — classify by lifecycle, not topic

Adopt the proven vdocs pattern (`~/projects/vdocs/docs/README.md`): a document's folder tells
you its *lifecycle state*; an index README carries the filing rules and a dated current-state
block.

```
docs/
  README.md            ← NEW: index + filing rules + dated "Current state" block
  guides/              ← evergreen operator/consumer docs — kept CURRENT, edited freely
  reference/           ← NEW: durable contracts & lookups cited by code — PATH-STABLE
  adr/                 ← permanent, immutable; supersede via new ADR (unchanged)
  proposals/           ← ONLY live or parked-unfinished workstreams
  releases/            ← permanent release records (unchanged)
  historical/          ← NEW: executed/superseded work — kept for the why, never updated
    prompts/           ← spent session-kickoff prompts
```

**The filing rule (goes verbatim into `docs/README.md`):**

1. A workstream is born as a committed proposal (+ tracker) in `proposals/`.
2. Its kickoff prompts live beside it; each moves to `historical/prompts/` in the commit that
   lands its work.
3. When the last phase ships — or the workstream is dropped — the proposal moves to
   `historical/` in the closing commit, **after** promoting anything still load-bearing into
   `reference/` or `guides/`.
4. Decisions that must outlive the workstream become ADRs.
5. **Path-stability rule:** anything cited from code (`# Spec:` / `# Plan:` headers) lives in
   `reference/` or `historical/` and never moves without a same-commit tree-wide citation sweep
   (`grep -rn "docs/" host bin docker vista tests` must come back clean).

## 3. Disposition — every file

### 3.1 Moves to `historical/` (executed / superseded / delivered)

| File | Why | Pre-move extraction |
|---|---|---|
| `proposals/producer-contracts-implementation-plan.md` | V1–V7 + Gate-R all landed with gate-PASS commits; vdocs-side Track D completion is recorded by `releases/data-v1-peers.json` | update the 7 `# Plan:` cites in `host/scripts/*` to the new path |
| `proposals/v4-session-kickoff.md` → `historical/prompts/` | spent one-shot handoff prompt; zero inbound refs | none |
| `guides/heads-up-vista-info-hub.md` | delivered cross-org memo (its retirement list shipped) | none — near-duplicate of upstream-data-fixes content |
| `guides/upstream-data-fixes.md` | executed P1–P5 fix record | **first** move its live `package-namespace.tsv` / `package_dir` schema table into the code-model schema reference (§3.3) |
| `guides/vista-meta-spec-v0.4.md` (build-spec bulk: §1–§10, §12–§15) | as-built record: §15 "Pending" tables all shipped; §14 says the formatter/extension it now ships were "skipped"; §3/§11.3 name artifacts and routines that never shipped under those names | **first** extract §11.4–§11.6 (PIKS heuristic catalog H-01…H-52) to `reference/piks-heuristics.md` — it is a live contract implemented by `VMPIKS`; then sweep ALL `# Spec: …spec-v0.4.md § N` cites (30+ files) — §11 cites → the new reference doc, others → the historical path |
| `guides/vista-meta-restore.md` **Part A only** (relocation to `~/projects/vista-meta`) | executed — the repo is already there | Parts C/D (snapshot discipline, 3-tier restore) stay in `guides/` as the live runbook; Part B (first GitHub push) → one TODO line (the remote now exists — verify then delete) |
| `xindex-reference.md` §6 + §10 (point-in-time narrative only) | "XINDEX hasn't run batch-wide / File 9.8 empty / bake pending" — contradicted by the shipped, populated `xindex-*.tsv` | fold a 2-line "since executed" note; keep the evergreen catalog sections in `guides/` |

### 3.2 Reclassifications (wrong folder, still live)

| File | From → To | Why |
|---|---|---|
| `proposals/schema-v1-normalization-spec.md` | → `reference/` | contract of record: cited by 8 scripts + tests, materialized by data-v1 and Compass 0.2.0. Fix the now-false header ("pre-first-release / no consumer pinned / no code") to "shipped schema_version 1 contract of record". Sweep the 8 `# Spec:` cites in the same commit |
| `guides/vista-orchestration-plan.md` | → `proposals/` | Status: Proposed; a live cross-repo roadmap, not a guide. Fix its self-links (`docs/…` → correct relative) and drop the dead `docs/vista-cli-planning.md` ref |
| `docs/Packages.csv` | → `vista/vendor/Packages.csv` (or `data/`) | build-input data, not documentation: read by `Makefile:284`, `build_package_namespace.py`, `normalize_dumps.py`, `build_routine_inventory.py`, `augment_registries.py` (+ fixtures). **This is a code change** — update the ~5 hardcoded paths + Makefile guard + tests in the same commit. Defer to its own small increment if preferred |
| `screen-recording-how-to.md`, `screencasting-simple.md` (repo root) | → delete (or move out of repo) | the 2-of-5 leftover from 19b655c's screencasting purge; personal how-tos, not VistA modeling |

### 3.3 Stays in `guides/` — with named content fixes

| File | Fixes required |
|---|---|
| `vista-meta-guide.md` (start-here map) | counts: 19→**20** code-model TSVs (+`package-namespace.tsv` in §5.1); data-model **4** TSVs (drop nonexistent comprehensive CSV; piks 8,261 / triage 220); add a "schema_version 1 · data-v1 release · Compass 0.2.0" section (currently invisible); repair `(adr/)`→`(../adr/)`, `(build-log.md)`→`(../build-log.md)`, `../vista|../host`→`../../…` |
| `piks-analysis-guide.md` (**most dangerously stale**) | rewrite §5/§6 against the real 4 TSVs (`piks.tsv` 6 cols incl. `piks_source`; `field-piks.tsv` 9-col TSV, not 22-col CSV; all §6 recipes are dead today); **re-derive every coverage number from current data** and sync the corrected figure into CLAUDE.md/README |
| `code-model-guide.md` (becomes the schema SSoT) | regenerate §1 per-TSV tables from actual headers (`head -1` sweep): rpcs 12 / options 9 / protocols 8 cols, `ien`+`*_label` cols, `routine`→`routine_name`, `caller_name`→`caller_routine`, rows 39,373; absorb upstream-data-fixes' live package-namespace schema; state "these are schema_version 1 per `releases/data-v1.manifest.json`"; fix 3 broken relative links |
| `xindex-reference.md` | prune §6/§10 (see 3.1); **delete its duplicated per-TSV column counts** — defer to code-model-guide as the one schema source |
| `vista-vscode-guide.md` | `vista-meta-0.1.0.vsix` → `vista-compass-0.2.0.vsix` (2 places); `vistaMeta.codeModelPath` → `vistaCompass.…` (1 place); otherwise current |
| `vscode-extension-internals.md` | refresh to 0.2.0: "four source files" → six (+`model.ts`, `hover.ts`); `vistaMeta.*` → `vistaCompass.*` command/config IDs; demote §6/§7.1 PIKS-global hover from "not yet implemented" to shipped (`src/hover.ts`, `^DPT → File 2 PATIENT — PIKS P`) |
| `routine-situational-awareness.md` | namespace sweep `vistaMeta.*` → `vistaCompass.*` (4 places); vsix install line |
| `package-situational-awareness.md` | fix the dead recipe: `rpcs.tsv` package filter `$5` → `$11`; review the latent `routine-calls.tsv $7` reference (TSV has 6 cols); namespace sweep for the *proposed*-feature names |
| `vista-developers-guide.md` | link-only pass: kids-vc links → `~/projects/py-kids-vc` pointers; `adr/045` → `../adr/045`; `../vista/…` → `../../vista/…`. Content is evergreen |
| `dependencies.md` | either complete the placeholder digests/commits from the built image, or re-scope the header from "always reflects the current image" to "version pins only" — today it over-promises |
| `vista-meta-restore.md` (Parts C/D) | replace **Makefile line-number citations with target names** (`snapshot-globals`, `restore-globals`, `patch-new`) — line numbers are already wrong twice; fix `029-symlink-farm.md` → `029-symlink-farm-routines.md`; repair root-relative links |

### 3.4 Stays put, governance actions

| Item | Action |
|---|---|
| `adr/001–045` | unchanged (immutable). Add a **Reality** column to `000-index.md` (Implemented? / diverged — without touching bodies): flags ADR-027 (smoke file missing) and ADR-032 (lean-v1 outgrown) |
| New ADRs | **047** producer-contracts / data-v1 release model (backfill); **048** Compass extension architecture (backfill); **049** supersede ADR-044 — project root is `~/projects/vista-meta`; optionally **050** resolve ADR-027 (implement the smoke test or supersede it) |
| `build-log.md` | keep at its path (widely cited). Add a header banner: *"Phase-1 build record, Apr 2026 (BL-001–BL-013). Frozen — new build issues get BL-014+ only if the discipline is resumed; otherwise this is a closed record."* Decide: resume or freeze. Recommend **freeze** — RESEARCH.md carried the load since |
| `TODO.md` | T-001/2/3 → one-line open questions pointing at RF-010/016/024 (RESEARCH is the single source); T-004: check off the executed Phase-0 items (README exists — also fix CLAUDE.md's stale "README.md — missing" note) and repair its dead link |
| `releases/` | unchanged — permanent records (the manifest is what consumers and Compass verify against) |
| `CLAUDE.md` + `README.md` | repair all ~28 `docs/<name>.md` → `docs/guides/<name>.md` links; delete the `docs/vista-cli-planning.md` row; point both at `docs/README.md` as the index; **stop restating counts** — numbers live in `vista-meta-guide.md` only, CLAUDE/README link to it (kills the thesis/table triplication drift) |

## 4. Consistency rules going forward (the six-month guarantees)

1. **Lifecycle filing** — the rule in §2, printed in `docs/README.md`, applied in closing commits.
2. **One dated "Current state" block** in `docs/README.md` — the only place that says what is
   active/paused/done; updated when workstreams open/close.
3. **Path-stability for code-cited docs** — `# Spec:`/`# Plan:` targets live in `reference/` or
   `historical/`; every doc move ships with a same-commit citation sweep.
4. **Numbers have one home** — per-TSV schema in `code-model-guide.md` (regenerated from real
   headers), coverage figures in `piks-analysis-guide.md`, counts in `vista-meta-guide.md`;
   CLAUDE.md/README link instead of restating.
5. **Cite Makefile targets by name, never line number.**
6. **ADR discipline with a reality ledger** — externally-visible shipped decisions get ADRs;
   `000-index.md` carries the Implemented?/diverged column.
7. **Link gate** — add a `make docs-check` (or pre-commit step) that fails on dead intra-repo
   `docs/` links, so the next move cannot silently rot the index again.

## 5. Execution phasing

| Phase | Scope | Size |
|---|---|---|
| **0 — stop the bleeding** (no moves) | repair all broken links from 19b655c: CLAUDE.md, README.md, TODO.md, intra-guide relatives, 30+ `# Spec:` code headers (to current paths) | mechanical, one commit |
| **1 — structure** | create `docs/README.md`, `historical/`, `reference/`; execute §3.1 moves + §3.2 reclassifications (each move with its extraction + citation sweep in the same commit); delete root strays | several small commits |
| **2 — content refresh** | §3.3 fixes: piks re-derivation (worst first), code-model schema regen, extension-internals 0.2.0 rewrite, xindex pruning, dependencies decision | the real work; per-doc commits |
| **3 — governance** | ADR-047/048/049 (+050), 000-index Reality column, build-log freeze banner, TODO slimming, `make docs-check` link gate | small, high-value |
| **(optional) 4** | `Packages.csv` relocation (code change: 5 scripts + Makefile + fixtures) | own increment |

Phases 0–1 make the tree *truthful*; phase 2 makes it *current*; phase 3 keeps it that way.

## 6. What this proposal deliberately does NOT do

- No ADR bodies are edited (immutability preserved; corrections via new ADRs + index column).
- No data-model/code-model artifacts move — only their documentation.
- `releases/` and `adr/` numbering schemes are untouched.
- The vdocs pattern is adopted for *lifecycle*, not copied wholesale — vista-meta keeps its
  distinctive `guides/` (operator surface is bigger here) and `build-log`/`RESEARCH` split.
