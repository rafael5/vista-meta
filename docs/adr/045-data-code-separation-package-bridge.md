# ADR-045: Separate data and code classification; package as the bridge

Date: 2026-04-19
Status: Accepted

## Context
PIKS (ADR implicit, spec §11.5.2) classifies FileMan files on an
audience/regulatory cut — Patient, Institution, Knowledge, System.
That cut is meaningful for data (retention, exchange, security) but
does not describe routines: a utility routine like `%DT` touches all
four categories; a print template runs against whatever data you hand
it. Extending PIKS to code would overload a term that was deliberately
scoped to data.

VistA is natively organized by **package** (~200 of them). A package
owns a namespace prefix, a set of files/globals, a set of routines,
and a set of options/protocols/templates/dialogs. FOIA tarballs, the
VA Documentation Library, and this project's symlink farm (ADR-029)
all reflect that structure. The package is the only organizing unit
that already spans code and data in VistA's own conventions.

Industry approaches considered: knowledge graphs over code (Kythe,
Glean), bounded-context catalogs (Backstage, DDD), hotspot analysis
(CodeScene), dependency/cycle analysis (Structure101). All point to
the same pattern: classify each kind of artifact on its own terms,
then connect through a neutral organizing unit.

## Decision
Three-part architecture for VistA cataloging:

1. **PIKS remains pure, data-only.** Four categories applied to
   FileMan files and globals. No routine gets a PIKS label.
2. **Routines get their own classification** on code-appropriate axes:
   package (namespace), role (API / UI / task / library / RPC / report
   / utility), entry-point vs leaf, routine size, and
   globals-touched. A separate taxonomy, not a PIKS dialect.
3. **Package is the unifying bridge.** A per-package manifest lists
   the package's files (with PIKS), routines (with roles), and
   options/protocols/templates. Traceability between data and code
   flows through the package and through explicit cross-reference
   edges (routine → globals read/written; file → routines touching it),
   not through a shared classification label.

Scope discipline: deliver in phases. Phase 1 = host-side sync of
`/opt/VistA-M/` + routine inventory (MANIFEST + size + package) and
nothing else. Phase 2 = role classification. Phase 3 = globals-touched
extraction. Phase 4 = package manifest that joins data and code sides.
Do not build phase N+1 until phase N is in place and validated.

## Consequences
- Positive: PIKS stays load-bearing for the analytical purposes it was
  designed for (exchange, retention, security review) without being
  stretched to code.
- Positive: Routines get classification axes that actually describe
  them; the resulting taxonomy is honest about what a routine is.
- Positive: Traceability ("what routines manage this file?" / "what
  data does this routine touch?") is expressed as graph edges, not as
  a forced shared label. Queries become explicit joins.
- Positive: The package-level manifest gives humans a single card per
  VistA package — the native unit they already reason in.
- Positive: Phased delivery keeps each step reviewable. Early stops
  still yield useful artifacts (e.g., Phase 1 alone answers "how big
  is each package?").
- Negative: Two classification schemes to maintain instead of one.
  Accepted cost — the alternative is a single scheme that fits
  neither side well.
- Neutral: Adds a code-side dimension to the project previously
  scoped to data. Spec §11 will need a companion section; CLAUDE.md
  references remain data-centric until code work reaches a stable
  shape.

## Alternatives considered
- **Extend PIKS to routines.** Rejected: overloads a term with a
  specific data-regulatory meaning; forces a label onto artifacts
  that legitimately cross categories (utilities, templates).
- **Single unified classification across code and data.** Rejected:
  would have to be generic enough to fit both, which means it fits
  neither usefully. Loses the regulatory precision PIKS gives data.
- **Classify routines only by package, no further taxonomy.** Rejected
  for Phase 2+: package answers "who owns this" but not "what kind of
  thing is this"; both are needed for cleanup and modeling work.
- **Build the full knowledge graph up front.** Rejected on pacing
  grounds: extracting globals-touched edges for 24k routines is
  non-trivial (MUMPS indirection, abbreviated commands) and should
  not block Phase 1 inventory value.
