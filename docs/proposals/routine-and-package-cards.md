# Routine card and package interface card — kickoff

**Status:** accepted by the owner 2026-11-09 · nothing built · run it in one
session with: `cd ~/projects/vista-meta && claude "Execute docs/proposals/routine-and-package-cards.md"`.

This repository answers only to its own `make check`. The measurement below
comes from the vista-forge `docs` repo
(`proposals/agent-discovery-surface/agent-discovery-surface-query-remediation.md`,
remediation R1 and the second half of R5). It is a request from that
analysis; nothing in vista-forge depends on what is built here.

## Why

Over 446 Claude Code sessions, from 2026-09-23 to 11-09, agents read VistA
routine source by hand **1,315 times in 129 sessions: 44 % of all the
context they spent on knowledge sources**, more than vdocs, vista-meta and
every other source together. The calls split three ways:

- 542 read lines of a routine;
- 443 grepped the source tree for who calls a tag;
- 125 grepped for where a tag is defined.

88 routines were re-read from scratch in three or more sessions, led by
VPRD (15 sessions), PXPXRM (15), PXRMINDX (14) and PXRMDATE (13). The work
was mostly Certo's (certo 624 calls, certo-reminders 553).

vista-meta already holds every measured part of those answers: the call
graph, the bindings, the globals, the tags. No tool hands them over in one
call, so agents went to the files. Separately, the server's SQL was used
mostly for three listings that have no keyed call: RPCs by namespace (the
`rpcs` table, 27 queries), the fields of a file (`field_piks`, 26) and files
(13).

Already fixed on 2026-11-09 (`848f781`):

- a malformed lookup is an input error;
- a key matches in any case;
- `orientation` lists every table's columns.

## Goal

Add to the MCP server (`host/scripts/mcp_server.py`) the following. None of
it exists yet.

1. **A routine card.** Given a routine name, or `TAG^ROUTINE`, one call
   returns:
   - the routine's measured row (`routines_comprehensive`);
   - for a tag: its lines with `TAG+n` offsets, its formal parameters and
     the comment lines that open it;
   - for a routine: its tags with their line numbers;
   - who calls it: `routine_calls` by callee, narrowed to the tag when one
     is given, with each caller's package and `ref_count`, and the
     `TAG+n` locations from `xindex_xrefs` where they exist;
   - what it calls (`routine_calls` by caller);
   - the globals it touches (`routine_globals`);
   - the RPCs, options and protocols bound to it (`rpcs`, `options`,
     `protocol_calls` by routine and tag);
   - its documented counterpart (`entity_bridge` rows of type `routine`).

   Every part carries its citation line in the existing form
   (`vista-meta <release> · <tsv> · <key>=<value>`). The text carries its
   host path and line range.
2. **A package interface card.** Given a package name (any case) or a
   namespace prefix (`package_namespace`), one call returns:
   - its RPCs, options and protocols;
   - the entry points other packages actually call: `routine_calls` rows
     whose callee is in the package and whose caller is not, grouped by
     `TAG^ROUTINE` with a count of calling packages.

   That is the measured answer to "what are this package's interfaces".
3. **Keyed listings** for the three shapes SQL was used for: RPCs and
   options by namespace prefix, and the fields of a file (`field_piks`).

## Constraints

- **Source text comes from the host tree.** `source_path` holds the
  container path `/opt/VistA-M/...`; the host copy is
  `vista/vista-m-host/...`, which is untracked and filled by
  `make sync-routines`. When the tree is absent, the card still returns
  every measured part and says plainly that the text is unavailable and
  why. It never fails for that. Make the source root injectable so tests
  use a tiny tree in a temporary directory.
- **Bound every part.** XLFDT alone has 10,375 caller rows. Cap each list,
  give the full count, aggregate callers by package past the cap, and mark
  what was cut. A card for a heavily called routine should stay readable,
  in the region of a few thousand tokens; report the sizes you measure.
- **meta.db is a published release asset** that VistA Compass fetches and
  verifies. Compose the cards from its existing tables at query time; do
  not rename columns, add tables or put source text into it. If a card is
  slower than about a second on the real database because an index is
  missing, report that rather than changing `build_meta_db.py` unasked.
- **The server stays stdlib-only and read-only.** Write the tests first,
  with the existing fixture (`tests/test_build_meta_db.py`'s `FIXTURE_ROWS`,
  extended as needed) and `tests/test_mcp_server.py`; see each red before
  making it green.
- **Document the tools where they are listed:** the module docstring, the
  tool descriptions, `orientation`, `README.md`'s MCP row, and the tool
  list in `host/scripts/build_ai_card.py`. Regenerate with `make ai-card`
  so `card-check` passes.

## Not here

- Renaming columns or changing the TSV model.
- vdocs, VistA Compass, the VSCode extension.
- A second definition of these facts anywhere else, such as a skill or a
  script.

## Done when

- The new tests pass, each seen red first, and `make check` is green.
- Against the real database (`dist/vista-meta-data-v1.db`) and the synced
  source tree:
  - routine cards for `PXRMINDX` and for one of its tags return every part
    above, each with its citation;
  - a card for `XLFDT` stays bounded and says what it cut;
  - the package interface card for `CLINICAL REMINDERS` lists its RPCs,
    options and protocols and its cross-package entry points;
  - a listing of RPCs for the prefix `ORWPT` and of the fields of file 2
    returns rows.
- The work is committed and pushed to `main`. The last message of the
  session reports:
  - what was built;
  - each card's size in characters and time on the real database;
  - anything found and not done.
