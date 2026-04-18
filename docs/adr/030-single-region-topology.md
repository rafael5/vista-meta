# ADR-030: Single region/segment globals topology

Date: 2026-04-18
Status: Accepted

## Context
YottaDB supports partitioning globals across regions, segments, and database files. VistA traditionally uses multiple regions (ROU for routines, sometimes separate regions for journal, audit, patient). Single region maps everything to one `.dat` file.

## Decision
Single region DEFAULT → one segment → `/home/vehu/g/mumps.dat`. All globals (`^*`) map to this file.

## Consequences
- Positive: Simplest possible GDE configuration. `mumps -r GDE` script is a few lines.
- Positive: Matches WorldVistA's `docker-vista` pattern; no surprises for VistA-on-YDB users.
- Positive: Performance fine into many GBs on modern hardware for the workloads we care about (metadata reads, occasional writes).
- Positive: One file to snapshot, one file to restore.
- Negative: Cannot tune per-region parameters (block size, journal settings, cache). Not needed for analytics.
- Negative: Partial database corruption affects everything. Mitigated by snapshot discipline.

## Alternatives considered
- VistA-namespace partitioned (separate regions for patient/audit/journal): more VistA-traditional but adds GDE complexity, and partial partitioning is worse than no partitioning when concerns about blast radius arise.
- Single region for now, document future partitioning: effectively what this is — partitioning is reversible via global remap if ever needed.
