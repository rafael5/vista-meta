# vista-meta — open follow-ups

Open questions flagged during analysis, anchored to their RESEARCH.md finding
(RF-NNN) — **RESEARCH.md is the single source for the detail**; each entry here
is just the question, the anchor, and what would close it. Executed items leave
this file in the commit that closes them (lifecycle rule: `docs/README.md`).

---

## T-001: Reconcile routine counts — source vs symlinks vs compiled (RF-010)

Source `.m` 39,330 = MANIFEST 39,330, but `/r/` symlinks +1 and `/o/` objects
+8 — small, real, unexplained (hypotheses in RF-010: percent-routines,
Octo bridge, build side-effects). schema_v1 re-extraction now counts
**39,373** rows in `routines.tsv`, so the divergence question extends to the
+43 as well. **Closes when:** each delta is attributed and recorded as an RF.
Detail: RF-010 + the four test hypotheses preserved in git history of this file.

## T-002: MANIFEST ↔ File 9.8 cohorts — characterize both sides (RF-016)

Intersection 29,102; **MANIFEST-only 10,228** (shipped, never
Kernel-registered — A1A1*/OIFO-style); **File 9.8-only 1,563** (registered,
not shipped — PSN/MAG/PRA top prefixes). Legitimate difference, hypotheses in
RF-016. **Closes when:** each cohort has a characterization RF (docs exercise,
no code change).

## T-003: Characterize the 14,658 truly-unreferenced routines (RF-024)

After call-graph + RPC + option + protocol passes, 14,658 routines have zero
inbound references, yet many are clearly live (Kernel, FileMan) — the
references arrive via paths the extractors don't see (indirection, `^%ZOSF`,
menus beyond TYPE=R, HL7/protocol event drivers, taskman). **Closes when:**
the cohort is decomposed into named reference-mechanism buckets and the
truly-dead residue is small enough to list (target < 5%). Detail: RF-024.

## T-004: Execute the VistA orchestration plan (master tracker)

**Plan:** [docs/proposals/vista-orchestration-plan.md](docs/proposals/vista-orchestration-plan.md)
(Status: Proposed) — the cross-repo `.m` → KIDS → install → integration-test →
report TDD pipeline. This is a **cross-repo** tracker; only a slice lands in
vista-meta.

> **Currency note (2026-07-04).** The plan predates the vista-forge org
> reorganization and understates sibling-repo progress — e.g. its Phase 0
> "land what's nearly done" items are largely DONE: vista-meta README ✓,
> tree-sitter-m published ✓ (`rafael5.tree-sitter-m-vscode` on the
> marketplace), and m-stdlib has shipped far beyond the 2-of-9 modules it
> cites (STDJSON/STDCRYPTO/STDLOG/regex/datetime/… now exist). Re-baseline
> the plan against `~/vista-forge/` before executing any phase.

**Closes when:** Phase 5 exit — a sample multi-component VistA package gets
automated lint + unit + integration + coverage on PR. Per-phase detail and
per-repo map: the plan §7; the original long-form tracker text is in this
file's git history.

## T-006: rocto + YDB GUI down at container start (non-gating; ADR-051)

Found by the first `make smoke` run (2026-07-04); on inspection neither service
has any consumer, so smoke treats them as **WARN, not FAIL** (ADR-051) and this
is opportunistic, not required. Diagnosis when picked up:
- **rocto (Octo SQL :1338)** dies at boot — `%YDB-E-ZLINKFILE … _ydboctoInit.m
  not found` (Octo plugin routines not on the rocto process's $ZRO).
- **YDB GUI (:8089)** — entrypoint logs "ydbgui: alive" but nothing listens.
**Closes when:** both ports answer (checks promoted back to FAIL), or a future
ADR drops the services from the image entirely.
