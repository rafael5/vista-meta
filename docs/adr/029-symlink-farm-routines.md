# ADR-029: Symlink farm for VEHU-M routines

Date: 2026-04-18
Status: Accepted

## Context
VEHU-M source layout is `Packages/<pkg>/Routines/*.m` across ~140 packages. YDB's `$ZRO` operates on directories. Three shapes:
- Flatten: copy all `.m` into single `/opt/VistA-M/r/`. $ZRO simple, lose package structure.
- Preserve packages: $ZRO gets 140 entries. Package structure visible, $ZRO unwieldy.
- Symlink farm: hybrid — flat dir of symlinks, packages still browseable.

## Decision
Symlink farm. Real `.m` files stay at `/opt/VistA-M/Packages/<pkg>/Routines/*.m`. Build creates `/opt/VistA-M/r/*.m` as symlinks pointing into `Packages/`. Build fails on duplicate routine names across packages. `MANIFEST.tsv` records routine → package → source path.

## Consequences
- Positive: `$ZRO` has one entry; fast lookup.
- Positive: Filesystem still reflects package boundaries — `ls /opt/VistA-M/Packages/` works normally.
- Positive: `readlink /opt/VistA-M/r/DIU2.m` tells you which package owns a routine in one command.
- Positive: MANIFEST.tsv is queryable by DD analyzers and bake phases for package-scoped iteration.
- Negative: Build step adds uniqueness check pass. Fails loud on conflicts instead of silent last-wins.
- Neutral: Symlinks occupy ~30k inodes but zero data duplication.

## Alternatives considered
- Flatten: loses package structure; can't answer "which package owns this routine?" from filesystem alone.
- Preserve packages: $ZRO with 140 entries is ugly and hits edge cases in YDB tooling.
- Single flat dir with filename prefix encoding package: defeats YDB's routine name conventions.
