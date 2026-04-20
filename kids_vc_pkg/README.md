# kids-vc

Version-control tool for **VistA KIDS** (Kernel Installation and Distribution System) distribution files. Decompose `.KID` patches into per-component files for git-tracking; reassemble back to `.KID` for deployment.

## What it does

KIDS bundles routines, FileMan data-dictionary changes, options, protocols, RPCs, and install logic into one monolithic `.KID` text file. Git's line-based diff/merge is destructive for this format because adjacent entries are semantically independent.

`kids-vc` provides:

- **`decompose`** — `.KID` → per-component directory tree (routines as `.m`, FileMan DDs as `.zwr`, Kernel components per-entry)
- **`assemble`** — directory tree → `.KID` (reversible)
- **`roundtrip`** — verify lossless round-trip
- **`canonicalize`** — substitute install-time IENs with stable `"IEN"` placeholder for cross-instance diff stability
- **`parse`** — summarize a `.KID` without decomposing

Plus `kids-vc-merge` — a git merge driver that does entry-level 3-way merge on `.zwr` files (`.gitattributes`-installable).

## Install

```bash
pip install kids-vc
```

## Usage

```bash
# Parse summary
kids-vc parse OR_3.0_484.KID

# Decompose for git tracking
kids-vc decompose OR_3.0_484.KID ./patches/

# Reassemble
kids-vc assemble ./patches/ rebuilt.KID

# Verify round-trip
kids-vc roundtrip OR_3.0_484.KID

# Canonicalize IENs (lossy — for cross-instance diffs)
kids-vc canonicalize ./patches/

# Install git merge driver (run once per repo)
kids-vc-merge --install   # (use the Makefile target from vista-meta for now)
```

## Background

Two prior VistA-on-git bridge attempts:

- **SKIDS** (WorldVistA, 2011–2013) — three disjoint spikes (Python `ParseKIDS.py` + MUMPS `ZDIOUT1.m` + unmerged Java `KIDSAssembler`) that never integrated. Abandoned.
- **XPDK2VC** (Sam Habiel, 2014–2020) — coherent in-VistA MUMPS implementation, 4 routines (~870 lines), handled 13 KIDS component types with diff-stability engineering.

`kids-vc` is a Python port of XPDK2VC's architecture, plus features neither predecessor had:

- **DD-embedded MUMPS extraction** — input transforms, xref SET/KILL, computed-field code extracted as per-field `.m` annotations
- **ZWR 3-way merge driver** — git-native entry-level merges for `.zwr` files
- **Corpus-verified** — 100% round-trip pass rate on all 2,406 real WorldVistA `.KID` patches (~3.5M subscripts)

## Provenance

The canonical source lives in the **[vista-meta](https://github.com/rafael5/vista-meta)** project's `host/scripts/` directory. This package is a thin installable wrapper; it locates the source-of-truth and re-exports the API.

For full context, see `docs/kids-vc-guide.md` in vista-meta.

## License

Apache 2.0 (matches both SKIDS and XPDK2VC).
