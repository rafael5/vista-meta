# Heads-up: vista-info-hub workarounds retired by P1–P4 export changes

> **DELIVERED (closed 2026-07-04).** Cross-org coordination memo — the columns it announces
> shipped (P1–P4, see `../guides/code-model-guide.md` §7b) and the consumer was notified.
> Kept as the record of what vista-info-hub was told it could retire.


**To:** vista-info-hub owner
**Re:** vista-meta export now ships package→namespace/app_code data — workarounds can be retired
**PR:** [rafael5/vista-meta#2](https://github.com/rafael5/vista-meta/pull/2) (`package-namespace-bridge`)
**Tracking issue:** vista-cloud-dev/vista-info-hub (filed from this note)

The vista-meta code-model export (P1–P4 from `docs/upstream-data-fixes.md`) now
carries package association, consistent join keys, and a full namespace/app_code
bridge. All changes are **additive** — existing columns and casing are untouched,
so the byte-parity goldens against the Python tool's output are unaffected. Once
the export tree is regenerated, the following can go away.

## New columns / files

| File | Added |
|---|---|
| `rpcs.tsv` | `package`, `package_dir` |
| `options.tsv` | `package_dir` |
| `protocols.tsv` | `package_dir` |
| `package-namespace.tsv` *(new)* | `package, package_name, namespace, prefixes, app_code, vdl_id` — **all 174 packages** |

`package_dir` is byte-identical to `packages.tsv`'s `package` (canonical
directory name) across `rpcs/options/protocols/routines-comprehensive/package-data`.

## What can be retired

1. **`internal/core/canonical/` entirely** — the embedded 17-entry `packages.csv`
   + `canonical.Resolve`. Replace by loading `package-namespace.tsv`, which
   resolves by directory name, namespace, *and* app_code for all 174 packages
   (was ~10% coverage). This touches the **13+ `canonical.Resolve` call sites**
   across `ops/{coverage,routine,links,layers,tree,timeline,context,package,list}.go`
   — they can join on the export directly.

2. **Case-folding joins** — `RPCsByPackage` / `OptionsByPackage` and the
   `resolveDir()` helper in `ops/list.go` can join on the new `package_dir`
   column instead of `EqualFold`/case-insensitive matching. `options.tsv`/
   `protocols.tsv` keep their upper-cased `package`, but `package_dir` now gives
   an exact key.

3. **The "VA FileMan" vs "FileMan" reconciliation** — use `package_name` /
   `app_code` from `package-namespace.tsv` directly; no `"VA "`-prefix string
   surgery. (e.g. `VA FileMan` → `app_code=DI`, `vdl_id=5`.)

4. **The `list.docs` "no app_code mapping" error path** — `app_code` is now
   present per package, so docs↔package bridges through
   `package-namespace.tsv.app_code` → `frontmatter.db documents.app_code`. The
   5 FileMan docs under `DI` (and the other ~162 previously-unreachable packages)
   become resolvable.

## Coordination / caveats

- These are additive, so migration can be incremental — load
  `package-namespace.tsv` first, swap `canonical.Resolve` call sites over, then
  delete the embedded CSV in a follow-up once satisfied.
- **P5** (tagging docs with their package in the vista-docs `frontmatter.db`
  pipeline) is still open and lives in the vista-docs repo. P3 largely subsumes
  it via the `app_code` bridge, but a direct `doc → package` tag would be the
  most robust long-term answer — flagging in case it's preferable to wait for
  that than join on `app_code`.
