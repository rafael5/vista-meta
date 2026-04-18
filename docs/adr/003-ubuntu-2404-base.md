# ADR-003: Ubuntu 24.04 as base OS

Date: 2026-04-17
Status: Accepted

## Context
WorldVistA's `docker-vista` uses CentOS 7/8 base — now effectively EOL for CentOS Linux. Need modern, supported base with good YottaDB compatibility.

## Decision
Use `ubuntu:24.04` (noble) as Dockerfile base.

## Consequences
- Positive: Matches minty (Linux Mint 22.3 is noble-based); consistent apt/package toolchain with host.
- Positive: YottaDB LLC officially supports Ubuntu 24.04; `ydbinstall.sh` has native support.
- Positive: Interactive tooling (ranger, micro, btop, ncdu) available in noble universe repo.
- Positive: Long-term support until 2029.
- Negative: Diverges from WorldVistA reference implementation; must port yum→apt idioms.
- Neutral: Image size similar to CentOS base (~80 MB compressed).

## Alternatives considered
- Rocky Linux 9: closer to WorldVistA's CentOS lineage, but diverges from minty's Debian/Ubuntu base.
- Debian 12 bookworm: stable but older package versions for interactive tools.
- Alpine: musl libc incompatibility with YottaDB; hard no.
