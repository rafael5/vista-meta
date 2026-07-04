# Upstream data-quality fixes (P1–P5) — executed record

> **EXECUTED (2026-05-30; filed historical 2026-07-04).** All fixes shipped and the
> downstream consumer was notified. The *live* schema for `package-namespace.tsv` and the
> appended `package`/`package_dir` columns now lives in
> [`../guides/code-model-guide.md`](../guides/code-model-guide.md) §7b — consult that, not
> this record. RF-034 was appended to RESEARCH.md as planned.

Implements the data-quality gaps recorded in `upstream-data-fixes-prompt.md`,
which forced brittle workarounds in the downstream `vista-info-hub` consumer.
All changes are **additive** (one new file + appended columns) to preserve the
byte-parity contract between the Python `vista` tool and `vista-info-hub`.

## What changed

| Problem | Change | Where |
|---|---|---|
| **P1** RPCs had no package association | `rpcs.tsv` gains `package` + `package_dir` | `host/scripts/augment_registries.py` |
| **P2** package casing inconsistent across TSVs | `options.tsv`, `protocols.tsv`, `rpcs.tsv` gain `package_dir` (canonical directory name) | same |
| **P3** no per-package namespace / VDL app_code | new `package-namespace.tsv` | `host/scripts/build_package_namespace.py` |
| **P4** export dir name ≠ VDL/#9.4 name | resolved in `package-namespace.tsv` (carries both) + `package_dir` join key | same |
| **P5** docs not tagged with package | **vista-docs follow-up — not in this repo** (see below) | — |

Authoritative source: **`docs/Packages.csv`** (the FOIA build manifest that
*created* the source-tree directory names). It maps, per package: `Package Name`
(upper-case PACKAGE-file #9.4 NAME), `Directory Name` (the export directory),
`Prefixes` (namespace), and a numeric `VDL ID`. No live container or
`VMDUMP9_4.m` is required — the CSV resolves all 174 packages deterministically.

## New / changed schema

### `package-namespace.tsv` (new, joined by `package`)

| column | meaning | example |
|---|---|---|
| `package` | export directory name (byte-identical to `packages.tsv`) | `VA FileMan` |
| `package_name` | upper-case PACKAGE-file (#9.4) NAME | `VA FILEMAN` |
| `namespace` | primary namespace (first non-`!` prefix) | `DI` |
| `prefixes` | all prefixes, first-seen order; `!`=excluded namespace | `DI,DD,DM` |
| `app_code` | VDL documentation app_code (== primary namespace) | `DI` |
| `vdl_id` | numeric VistA Document Library application id | `5` |

Coverage: **174/174** packages have a row; **173** have a namespace (the
synthetic `Uncategorized` bucket has none — it is not a real package).

### Appended columns (existing files, byte-safe)

- `rpcs.tsv`        → `package` (upper #9.4 NAME) + `package_dir` (directory)
- `options.tsv`    → `package_dir`
- `protocols.tsv`  → `package_dir`

`package_dir` is the **canonical directory name** — byte-identical across
`packages.tsv`, `routines-comprehensive.tsv`, `package-namespace.tsv`,
`rpcs.tsv`, `options.tsv`, `protocols.tsv` — so consumers can join on it
without case-folding. Existing columns are left **byte-for-byte unchanged**
(the append is a raw line-concatenation, never a `csv` re-serialization —
Python's `csv` writer would otherwise quote any field containing a `"`).

Resolution coverage (this export):

| file | rows with `package_dir` |
|---|---|
| rpcs | 4327 / 4501 (96%) |
| options | 10445 / 13163 (79%) |
| protocols | 4801 / 6556 (73%) |

Uncovered rows are registry entries whose #9.4 package is blank or maps to a
#9.4 NAME absent from `Packages.csv` (e.g. the generic `PHARMACY`), or RPCs
whose routine is not package-attributable. These are genuinely unresolvable
from the available data, not silent drops.

## Regenerating

```bash
make package-namespace     # P3/P4 — package-namespace.tsv
make augment-registries    # P1/P2 — rpcs/options/protocols package_dir
```

Both are pure host-side post-processing over `docs/Packages.csv` +
already-exported TSVs; neither needs the container running.
`augment-registries` is idempotent (it strips and re-appends its own columns).

> **Note on permissions:** `vista/export/code-model/` is owned by the
> in-container `vehu` user (uid 1001). Run the two `make` targets as a user
> with write access to that tree (group 1001, in-container, or `sudo`).

Tests (stdlib `unittest`, no pytest dependency):

```bash
python3 host/scripts/tests/test_build_package_namespace.py   # 12 tests
python3 host/scripts/tests/test_augment_registries.py        # 15 tests
```

## Deliverable 4 — vista-info-hub workarounds now retireable

Once vista-info-hub migrates to the new columns it can delete:

- `rpcsByPackageRoutine()` (`internal/ops/list.go`) — the RPC→package link is
  now in `rpcs.tsv` (`package` / `package_dir`).
- `optionsByPackageFold()` and the protocols `EqualFold` matching — join on
  `package_dir` instead of case-folding `package`.
- The entire `internal/core/canonical` stopgap (`packages.csv` +
  `canonical.Resolve`) — `package-namespace.tsv` resolves **all 174** packages,
  not the curated 16. Cross-checked: every curated entry that exists in the
  export matches exactly; the curated entries that *didn't* match were
  directory-name typos the new table avoids by keying on the real export
  directory name.
- The `"VA "`-prefix hack in `listDocs` and the `list.docs` "no app_code
  mapping" error path — `app_code` is now present per package.

**Heads-up for the vista-info-hub owner:** these are additive columns, so the
byte-parity goldens in *both* tools are unaffected until you choose to migrate.
Migrate readers to `package_dir` / `app_code`, then drop the canonical map and
regenerate goldens in one coordinated change.

## Deliverable 3 — P5 vista-docs follow-up (coordinated, NOT in this repo)

P5 lives in the **vista-docs** pipeline that builds `frontmatter.db`, not in
vista-meta. The `documents` table groups docs by `app_code`/`pkg_ns` but has no
column linking a document to the code-model package **directory name**.

- **Now unblocked by P3:** `app_code` is the bridge. A consumer can join
  `documents.app_code` → `package-namespace.tsv.app_code` → `package`
  (directory) today, with no vista-docs change required for the common case.
- **Recommended robust fix (vista-docs side):** tag each document with its
  originating package directory name during the doc pipeline (a direct
  `doc → package` column), so the join survives the handful of packages where
  app_code ≠ primary namespace (e.g. a future Inpatient Pharmacy `PSI`/`PSJ`
  split, where the curated map already recorded a divergence — that package is
  not in the current export). Alternatively publish an authoritative
  `app_code → package` table.

Action: open a vista-docs issue referencing this section.

## Appendix — RESEARCH.md finding (paste as RF-034)

`vista/export/RESEARCH.md` is owned by the in-container `vehu` user and was not
writable from the host during this work. Append the following as **RF-034**
(next free number) from a writable context:

> ## RF-034 — Packages.csv is the authoritative package→namespace/app_code bridge
>
> Date: 2026-05-30 · Spec: docs/vista-meta-spec-v0.4.md § 11
>
> - `docs/Packages.csv` (the FOIA build manifest) carries, per package:
>   `Package Name` (upper #9.4 NAME), `Directory Name` (export directory),
>   `Prefixes` (namespace), and numeric `VDL ID`. **173/174** export
>   directories match `Directory Name` exactly; the one miss is the synthetic
>   `Uncategorized` bucket. This makes a live `VMDUMP9_4.m` unnecessary for the
>   namespace bridge — the CSV resolves all 174 packages with no running
>   container.
> - **app_code == primary namespace** = the first prefix that is not `!`-excluded.
>   It equals the VDL documentation app_code for every export-present package we
>   cross-checked (16/16 vs the curated vista-info-hub map). Caveat: the curated
>   map listed `Inpatient Pharmacy` as ns=`PSI`/app_code=`PSJ` (a genuine
>   divergence), but that package is not present in this VEHU export. If such a
>   package ever enters the export, app_code may need an editorial override from
>   vista-docs' frontmatter.db.
> - Multi-row packages in the CSV use the **blank-continuation** form (a row that
>   blanks both Package/Directory Name to add prefixes); no package repeats a
>   non-blank Directory Name (verified: 0). The parser appends prefixes from
>   blank-continuation rows in first-seen order.
>
> See `docs/upstream-data-fixes.md` for schema, coverage, and the downstream
> workaround-retirement list.
