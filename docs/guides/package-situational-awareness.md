# Package-Folder Situational Awareness

Companion to
[routine-situational-awareness.md](routine-situational-awareness.md).
That guide answered "I'm looking at one routine — what is it?" This
one answers the next zoom-out: **"I'm in a package folder with 50–500
routines. How do I get oriented across all of them?"**

> Audience: anyone landing in `vista/vista-m-host/Packages/X/` for the
> first time (or coming back to it after months). The package is the
> second-most-useful unit of analysis after the individual routine —
> almost every "where do I start?" question is a package-scope question.

---

## Table of contents

- [1. Why scan the whole package](#1-why-scan-the-whole-package)
- [2. The five package-level questions](#2-the-five-package-level-questions)
- [3. The package fingerprint (60 seconds)](#3-the-package-fingerprint-60-seconds)
- [4. What the existing CLI already gives you](#4-what-the-existing-cli-already-gives-you)
- [5. Recipes you can run today](#5-recipes-you-can-run-today)
- [6. Recommended new automated scans](#6-recommended-new-automated-scans)
- [7. VSCode integrations to consider](#7-vscode-integrations-to-consider)
- [8. Worked example — PSO (Outpatient Pharmacy)](#8-worked-example--pso-outpatient-pharmacy)
- [9. Anti-patterns](#9-anti-patterns)
- [10. Reference](#10-reference)

---

## 1. Why scan the whole package

A VistA "package" is a directory with a coherent design intent — a
subsystem (Pharmacy, Lab, Accounts Receivable) with its own files,
RPCs, and options. The folder under `Packages/X/Routines/` is that
subsystem on disk.

The single-routine sweep ([routine-situational-awareness.md](routine-situational-awareness.md))
treats every file as an island. That's wrong at scale. In practice:

- **Routines come in clusters.** `PSOVCC0`, `PSOVCC1`, `PSOVCCA` are
  the same feature split across 8-char filename limits — read
  together or not at all.
- **Public surface is sparse.** A 421-routine package usually has
  20–40 entry-points (RPCs + options + protocols); the other 380 are
  internal helpers. Knowing which is which collapses the reading
  problem by 10×.
- **The data is shared.** Routines in a package mostly touch the same
  globals (the package's owned files); cross-package globals are the
  exception. Understanding the data layer once orients you for the
  whole folder.
- **Coupling is asymmetric.** Most calls are intra-package; the
  cross-package edges are the **interfaces** — the rest is plumbing.

A 60-second package fingerprint plus a few automated scans answer
80% of the questions you'd otherwise answer by reading 30 routines.

---

## 2. The five package-level questions

Run any package scan with these in mind:

1. **What's the public surface?** RPCs, Options, Protocols — plus
   tags called from outside the package.
2. **What's the internal structure?** Sub-namespace clusters
   (`PSOVCC*`, `PSOREJ*`); hub routines (top in-degree within the
   package).
3. **What data does this package own?** FileMan files shipped, top
   globals, PIKS distribution.
4. **Where does this package leak?** Cross-package outbound calls
   (this package's dependencies on others) and cross-package inbound
   calls (others' dependencies on this).
5. **What's the maintenance state?** Patch hotness, test coverage,
   XINDEX cleanliness, last commit date per routine.

Q1 is the API. Q2–3 is the architecture. Q4 is the coupling. Q5 is
the risk. The CLI answers Q1, Q3, and parts of Q4 today; Q2 and Q5
need new scans (§6).

---

## 3. The package fingerprint (60 seconds)

Two commands, side by side:

```bash
vista-meta pkg "Outpatient Pharmacy"
ls vista/vista-m-host/Packages/Outpatient\ Pharmacy/Routines/ | wc -l
```

What to read off `pkg`:

```
PACKAGE  Outpatient Pharmacy
PREFIX   PS  (99% of routines)

Routines            905  lines     119531
PIKS files       P=15 I=5 K=17 S=2   (of 39 FM files shipped)   ← what kind of data this owns
FM files owned       39
RPCs exposed         40
Options (pkg=)      242                                          ← public surface
Protocols (pkg=)    194
Globals touched      57  (distinct)

FILEMAN FILES OWNED
        52  PRESCRIPTION
      52.5  RX SUSPENSE
  ...

TOP GLOBALS (by total ref count)
  ^PSRX                6297
  ^TMP                 6094
  ^PS                  5712
  ...

TOP INBOUND (other packages calling INTO this one)
  Integrated Billing                        66 edges
  E Claims Management Engine                62 edges
  ...

TOP OUTBOUND (this package calling OUT to others)
  VA FileMan                              2353 edges
  Kernel                                   984 edges
  ...

ENTRY-POINT CANDIDATES (top 10 by in-degree)
  PSOBPSUT        in= 109  out=  14  lines=  351  -
  PSOLSET         in=  81  out=  11  lines=   85  -
  ...
```

Mental shortcut for the fingerprint:

| Signal | What it tells you |
|---|---|
| Routine count | < 50 = small / focused; 50–200 = normal subsystem; 200+ = top-10 package |
| Avg lines / routine | < 100 = utility-heavy; 200–500 = normal; > 800 = god-routines present |
| PIKS distribution | P-heavy → clinical / patient-facing; I/S-heavy → infrastructure |
| RPC+OPT+PROTO total | The size of the API. > 50 = big surface, expect external coupling |
| Top inbound packages | Who depends on us (don't break their callers) |
| Top outbound packages | Our hard dependencies |
| Top entry-points | These are the "front doors" — start reading here |

This is the package-level analog of the
[30-second routine fingerprint](routine-situational-awareness.md#2-the-30-second-fingerprint).

---

## 4. What the existing CLI already gives you

Three subcommands cover most of Q1, Q3, and Q4 right now:

| Command | Answers |
|---|---|
| `vista-meta pkg NAME` | Q1 (RPC/OPT/PROTO counts), Q3 (FM files, globals, PIKS), Q4 (top in/out edges, entry-points) |
| `vista-meta context NAME [--with-source]` | All of the above as one markdown doc, optionally with full source — the AI handoff |
| `vista-meta search PATTERN --package NAME` | Targeted regex within the package directory |

**Run order on a cold package:**

```bash
# 1. Static overview
vista-meta pkg "Outpatient Pharmacy"

# 2. Optional — full pack for AI handoff
vista-meta context "Outpatient Pharmacy" \
  --with-source --bytes 200000 \
  > /tmp/pso.md

# 3. Targeted searches once questions sharpen
vista-meta search "RXACTION" --package "Outpatient Pharmacy" --tags-only
vista-meta search "^PSRX" --package "Outpatient Pharmacy"
```

Don't skip step 1. Most questions have one-line answers there.

---

## 5. Recipes you can run today

Until the proposed scans in §6 land, these one-liners against the
existing TSVs cover Q2 (sub-namespace clusters) and Q5 (test
coverage, patch hotness). They're shell + `awk` — no new code.

> Notation: `$PKG` is the package name as it appears in
> `routines-comprehensive.tsv` column 2 (e.g. `Outpatient Pharmacy`).
> `$PKGDIR` is the matching directory under `Packages/`.

### 5.1 List every routine in the package, sorted by in-degree (entry-points first)

```bash
PKG="Outpatient Pharmacy"
awk -F'\t' -v p="$PKG" 'NR==1 || $2==p' \
  vista/export/code-model/routines-comprehensive.tsv \
  | sort -t$'\t' -k16,16 -n -r \
  | column -t -s$'\t' \
  | head -40
```

The first 10–20 rows are your **entry-points and hubs**. Read these
first. Routines with `in_degree=0` and `rpc_count=0` and `option_count=0`
near the bottom are dead-or-internal-only — defer.

### 5.2 Sub-namespace cluster spotting

Group routines by 4–6 char prefix; clusters of size ≥ 3 are likely
features.

```bash
awk -F'\t' -v p="Outpatient Pharmacy" '$2==p {print $1}' \
  vista/export/code-model/routines-comprehensive.tsv \
  | awk '{ for (n=4;n<=6;n++) print substr($0,1,n) "\t" $0 }' \
  | sort | awk -F'\t' '
      { c[$1]++; r[$1]=r[$1]" "$2 }
      END { for (k in c) if (c[k]>=3) print c[k]"\t"k"\t"r[k] }
    ' \
  | sort -nr | head -30
```

Output:

```
73  PSOERX  PSOERX PSOERX1 PSOERX1A PSOERX1B ...
13  PSOREJ  PSOREJP0 PSOREJP1 PSOREJP2 PSOREJP3 ...
...
```

Each cluster is "one feature." When you read PSOVCC0, also open
PSOVCC1 and PSOVCCA — they're the same conversation continued.

### 5.3 Cross-package outbound coupling per routine

"This routine calls into other packages — how heavily?"

`routine-calls.tsv` has **no callee-package column** — its six
columns are `caller_routine`, `caller_package`, `callee_tag`,
`callee_routine`, `kind`, `ref_count`. The callee's package has to be
joined in from `routines-comprehensive.tsv` (routine → package),
which is what the first file in this two-file awk does:

```bash
awk -F'\t' -v p="Outpatient Pharmacy" '
  NR==FNR { if (FNR>1) pkg[$1]=$2; next }
  FNR==1 { next }
  $2==p {
    tot[$1]++
    if (pkg[$4] != p) ext[$1]++
  }
  END { for (r in tot) printf "%s\t%d\t%d\t%.0f%%\n",
        r, tot[r], ext[r]+0, (ext[r]+0)*100/tot[r] }
' vista/export/code-model/routines-comprehensive.tsv \
  vista/export/code-model/routine-calls.tsv \
  | sort -t$'\t' -k4,4 -n -r \
  | head -20
```

(Columns: routine, total calls, external calls, % external.) Routines
near 100% external are interfaces / shims; near 0% are pure
internals. Callees missing from the inventory (uninstalled or
dynamically named) count as external — acceptable for a coupling
scan.

### 5.4 Test coverage check

For each routine in the package, does `T<NAME>.m` exist?

```bash
PKG="Outpatient Pharmacy"
PKGDIR="vista/vista-m-host/Packages/$PKG/Routines"
for r in "$PKGDIR"/*.m; do
  base=$(basename "$r" .m)
  trtn="T$(echo "$base" | head -c 7)"
  if find vista -name "${trtn}.m" -print -quit | grep -q .; then
    echo "covered  $base"
  else
    echo "no-test  $base"
  fi
done | sort | uniq -c | head -5
```

(Adjust truncation rule to match your testing convention.)

### 5.5 Patch-hotness ranking

Parse line 2 of every routine in the package; rank by patch count.

```bash
PKGDIR="vista/vista-m-host/Packages/Outpatient Pharmacy/Routines"
for r in "$PKGDIR"/*.m; do
  patches=$(sed -n '2{s/.*\*\*\([^*]*\)\*\*.*/\1/p}' "$r")
  count=$(echo "$patches" | tr ',' '\n' | grep -c .)
  printf "%4d  %s\n" "$count" "$(basename "$r" .m)"
done | sort -nr | head -20
```

High-patch-count routines are the ones the VA has had to fix
repeatedly — proceed with **extra** care.

### 5.6 XINDEX cleanliness map

```bash
awk -F'\t' -v p="Outpatient Pharmacy" '
  NR==FNR { if ($2==p) pkg[$1]=1; next }
  pkg[$1] { c[$1]++ }
  END { for (r in c) printf "%4d\t%s\n", c[r], r }
' vista/export/code-model/routines-comprehensive.tsv \
  vista/export/code-model/xindex-errors.tsv \
  | sort -nr | head -20
```

The top of this list is where lint debt lives.

### 5.7 Render the top-N intra-package call graph as Mermaid

Same callee-package join as §5.3 (there is no callee-package column
in `routine-calls.tsv`):

```bash
awk -F'\t' -v p="Outpatient Pharmacy" '
  NR==FNR { if (FNR>1) pkg[$1]=$2; next }
  FNR==1 { next }
  $2==p && pkg[$4]==p && $6+0 >= 5 {
    print "  " $1 " --> " $4
  }
' vista/export/code-model/routines-comprehensive.tsv \
  vista/export/code-model/routine-calls.tsv \
  | sort -u | head -100 \
  | awk 'BEGIN{print "```mermaid"; print "graph LR"} {print} END{print "```"}'
```

Pipe to a temp `.md` and preview in VSCode (`Ctrl+K V`). Cap at 100
edges or the diagram becomes illegible — Mermaid is best for
50-edge graphs, not 5,000-edge ones.

---

## 6. Recommended new automated scans

The recipes above are useful but ad-hoc. Promote them into proper
`vista-meta` subcommands, each producing both a human-readable
markdown report and a machine-readable TSV. Six are worth building.

### 6.1 `vista-meta package-map PKG` — entry-point matrix

**Answers Q1.** Markdown table mapping every entry-point to its
routine + tag, grouped by surface:

```
## Outpatient Pharmacy — Entry Points

### RPCs (40)
| RPC name                        | Tag^Routine        | Return |
|---|---|---|
| PSO ACTIVITY LOG                | ACT^PSOVCC1        | single |
| PSOERXA0 DRGMTCH                | DRGMTCH^PSOERXA0   | single |
| ...

### Options (242)
| Option                          | Tag^Routine        | Type |
|---|---|---|
| PSO COST STAT MENU              | —                  | menu |
| ...

### Protocols (194)
| Protocol                        | Type    | Action |
|---|---|---|
| PSO SHOW PROFILE                | action  | D EN^PSOLMPF |
| ...
```

**Implementation:** Filter `rpcs.tsv`, `options.tsv`, `protocols.tsv`
where `package = $PKG`. Group by routine, sort alphabetically. ~50
lines of Python. Two schema_v1 gotchas: `package` is **column 11** in
`rpcs.tsv` (column 5 in `options.tsv` / `protocols.tsv`), and its
values are the FileMan package name in **UPPERCASE**
(`OUTPATIENT PHARMACY`) — not the title-case directory name
(`Outpatient Pharmacy`) used by `routines-comprehensive.tsv`.

### 6.2 `vista-meta package-graph PKG [--top N] [--scope intra|all]` — Mermaid call graph

**Answers Q2 + Q4.** Renders the package's internal call graph as
Mermaid, with optional cross-package edges as dotted arrows.

```bash
vista-meta package-graph PSO --top 50 > /tmp/pso-graph.md
code /tmp/pso-graph.md         # opens in VSCode; Ctrl+K V to preview
```

**Implementation:** Filter `routine-calls.tsv` by `caller_package`;
keep top-N nodes by in-degree to bound the graph; render with
`subgraph` blocks for sub-namespace clusters (from §6.3).

Visualizing the graph **once** per package is worth more than
listing edges 100 times.

### 6.3 `vista-meta package-clusters PKG` — sub-namespace tree

**Answers Q2.** The §5.2 recipe formalized. Output:

```
PSO  (905 routines)
├── PSOERX* (73)   — e-prescribing (eRx)
│     PSOERX PSOERX1 PSOERX1A PSOERX1B ...
├── PSOREJ* (13)   — rejection handling
│     PSOREJP0 PSOREJP1 PSOREJP2 PSOREJP3 ...
├── PSOOR*  (48)   — order entry interface
│     ...
└── ungrouped (...)
```

**Implementation:** Iterate prefix lengths 3..7; pick the longest
prefix where group size ≥ 3; emit nested groups. ~80 lines of Python.

A nice-to-have augmentation: take the title from line 1 of the most
in-degree-popular routine in the cluster as the cluster's label.

### 6.4 `vista-meta package-data PKG` — data ownership matrix

**Answers Q3.** For each global touched by any routine in the
package:

| Global | FM file | PIKS | Owned by pkg? | Routines using it (n) | Total refs |
|---|---|---|---|---|---|
| `^PSRX` | 52 PRESCRIPTION | P | yes | 448 | 6297 |
| `^DPT` | 2 PATIENT | P | no (Registration) | 148 | 305 |
| `^DIC` | 1 FILE | S | no (FileMan) | 68 | 104 |
| ... | | | | | |

**Implementation:** Join `routine-globals.tsv` (filtered to package
routines) with `package-data.tsv` (for ownership) and the data-model
`files.tsv` + `piks.tsv`. Sort owned globals first.

The "owned vs not-owned" split is the **single most useful slice**:
the owned globals are the package's data; the not-owned are its
dependencies on other packages' data.

### 6.5 `vista-meta package-coupling PKG` — cross-package edges

**Answers Q4.** Two reports:

```
## Outpatient Pharmacy — Coupling

### Outbound (we depend on)
| Target package        | Edges | Top targeted tags |
|---|---|---|
| VA FileMan            | 2,353 | GET1^DIQ (3694 refs), ^DIR (1341) |
| Kernel                |   984 | FMTE^XLFDT (407), BMES^XPDUTL (293) |
| Registration          |   273 | DEM^VADPT (80), SITE^VASITE (58) |
| ...

### Inbound (depends on us)
| Source package             | Edges | Top called tags here |
|---|---|---|
| Integrated Billing         |    66 | RX^PSO52API (34), DIC^PSODI (9) |
| E Claims Management Engine |    62 | ... |
```

**Implementation:** Filter `routine-calls.tsv` on `caller_package`
(outbound) and on the `callee_routine`'s package (inbound — joined
via `routines-comprehensive.tsv`, since `routine-calls.tsv` carries
no callee-package column). Aggregate by package + top tags.

### 6.6 `vista-meta package-health PKG` — maintenance dashboard

**Answers Q5.** One row per routine:

| Routine | Lines | Patches | Last commit | Has test | XINDEX | Lint |
|---|---|---|---|---|---|---|
| PSOBPSUT | 351 | 15 | 2024-09 | yes | 2W | pass |
| PSOLSET | 85 | 8 | 2023-05 | no | clean | fail |
| ... | | | | | | |

Sortable by any column. Used to triage:

- "Sort by `patches` desc → top of the list = most-modified routines
  in the package; respect the precedent there."
- "Sort by `XINDEX` → uncovered lint debt."
- "Filter `Has test = no AND in-degree > 50` → high-traffic routines
  with no tests; write tests here first."

**Implementation:** Joins `routines-comprehensive.tsv`,
`xindex-errors.tsv`, on-disk patch parsing (§5.5), test-file
existence check, and `git log -1 --format=%cs` per file.

### 6.7 Output conventions for all six

For the bake-time discipline already in this repo:

- Always emit both `--format markdown` (default) and `--format tsv`.
- Markdown reports go to stdout; pipe to a file in `vista/export/`
  for caching.
- TSV outputs land in `vista/export/code-model/per-package/<PKG>.tsv`
  (gitignored or git-tracked depending on size).
- Determinism — same inputs → byte-identical outputs (the `mfmt`
  rule, applied to reports).

---

## 7. VSCode integrations to consider

The CLI scans above are the foundation. VSCode-side, these surfaces
make the data ambient instead of on-demand.

### 7.1 File-decoration provider — badges in the explorer

When the explorer renders a routine `.m` file under `Packages/X/Routines/`,
decorate it with a badge:

| Badge | Meaning | Source TSV |
|---|---|---|
| `R` (color: green) | Has an RPC entrypoint | `rpcs.tsv` |
| `O` (color: blue) | Has an Option entrypoint | `options.tsv` |
| `P` (color: purple) | Has a Protocol entrypoint | `protocols.tsv` |
| `★` | Top 10 in-degree of this package (hub) | `routines-comprehensive.tsv` |
| `!` (red) | Has Fatal XINDEX | `xindex-errors.tsv` |

VSCode API: `vscode.window.registerFileDecorationProvider`. The
decoration sees the file URI and returns a `FileDecoration`. Reads
already-cached TSV indexes — no new data, ~80 lines of TypeScript.

Effect: scrolling the explorer in `Packages/Pharmacy/Routines/` you
**see** the surface and the hubs without opening any file.

### 7.2 Per-package sidebar view — "VISTA PACKAGE"

A second tree view, sibling to the existing `VISTA ROUTINE`, that
activates whenever the active editor is in a `Packages/X/` folder.
Layout:

```
▾ VISTA PACKAGE
  ▣ Outpatient Pharmacy (PSO)
    905 routines · 40 RPCs · 242 OPTs · 194 protocols

  ▾ Entry Points (476)
    ▾ RPCs (40)
       PSO ACTIVITY LOG     → ACT^PSOVCC1
       PSOERXA0 DRGMTCH     → DRGMTCH^PSOERXA0
       ...
    ▾ Options (242)
       ...
    ▾ Protocols (194)
       ...

  ▾ Hub Routines (top 10)
    PSOBPSUT  in=109
    PSOLSET   in=81
    ...

  ▾ Owned Globals (P=15 I=5 K=17 S=2)
    ^PSRX    [P · file 52 PRESCRIPTION]    6297 refs
    ^PS      [P · files 52.x]              5712 refs
    ...

  ▾ Coupling
    Outbound → VA FileMan (2,353), Kernel (984), ...
    Inbound  ← Integrated Billing (66), ...

  ▾ Sub-namespaces
    PSOERX* (73), PSOOR* (48), PSOREJ* (13), ...
```

Same TSV-only constraints as the routine sidebar. Nodes click to
open the relevant routine. Builds on §6 scan logic — implement the
scans first, then read their cached TSVs.

### 7.3 CodeLens at routine header — package-relative coupling

Above line 1 of every `.m` file:

```
   N same-pkg callers · M cross-pkg callers · K globals owned-by-pkg · L not-owned
```

Clickable to open the relevant scan output. Setting-gated
(proposed `vistaCompass.codeLens.packageContext: boolean`) — off by default since
CodeLens is visually noisy.

### 7.4 Status bar segment

Right-aligned: `PSO · 905R · 40RPC · 242OPT`. Click → command palette
filtered to `vista-meta package-*`. One line of code, always-visible
context.

### 7.5 Quick-open within package

Custom command `vistaCompass.quickOpenPackage` (proposed):

1. Determine the package of the active editor's file.
2. List every routine in that package (from `routines-comprehensive.tsv`).
3. Show in `vscode.window.showQuickPick`, with line-1 title as
   description and in-degree as detail.

Bind to `Ctrl+K Ctrl+P`. Faster than `Ctrl+P` when you're already
oriented to a package and want to jump within it.

### 7.6 Workspace symbol provider scoped to package

Already proposed at workspace scope in
[vscode-extension-internals.md § 7.3](vscode-extension-internals.md#73-tier-c--diagnostics-workspace-symbols-codelens).
Add a quick-pick filter: `Ctrl+T` shows all packages by default;
prefix with `pkg:PSO ` to scope.

### 7.7 Open scan output as a virtual document

Don't write scan output to disk if it's ephemeral — register a
`vscode.TextDocumentContentProvider` for a custom URI scheme:

```
vista-meta:package-map/Outpatient Pharmacy.md
vista-meta:package-graph/Outpatient Pharmacy.md
```

The extension shells out to `vista-meta package-map "Outpatient
Pharmacy"`, returns the markdown. Mermaid blocks render automatically
in VSCode preview. Close the tab → no leftover file.

### 7.8 Implementation order

If you build only one of these, build **§7.1 file decorations**.
The badges are visible the moment you open the explorer; they cost
~80 lines; and they convey the public-surface map without any
clicks. Highest leverage per line of code in the entire roadmap.

---

## 8. Worked example — PSO (Outpatient Pharmacy)

Stopwatch from `cd vista/vista-m-host/Packages/Outpatient\ Pharmacy/`.

**0:00 — package fingerprint.**

```bash
vista-meta pkg "Outpatient Pharmacy"
```

Output (abbreviated): 905 routines, 40 RPCs, 242 options, 194
protocols, 57 globals. Top FM files: PRESCRIPTION (52), RX
SUSPENSE (52.5). Top inbound: Integrated Billing (66 edges). Top
entry-point candidate: `PSOBPSUT` (in=109).

**0:30 — clusters.** Run §5.2:

```
PSOERX*  73 routines  — e-prescribing (eRx holding queue)
PSOOR*   48 routines  — order entry interface
PSOREJ*  13 routines  — rejection handling
PSOBPS*  10 routines  — ECME/BPS billing bridge
...
```

Now I know the package decomposes into ~10 big features.

**1:00 — public surface.** Until `package-map` lands (note: in
`rpcs.tsv` the `package` column is **11**, and the value is the
UPPERCASE FileMan package name — see §6.1):

```bash
awk -F'\t' '$11=="OUTPATIENT PHARMACY"' \
  vista/export/code-model/rpcs.tsv | head
```

The 40 RPCs are backed by only ~13 routines, clustered under
PSOVCC* (patient Rx views) and PSOEP* (EPCS). The RPC surface is
much narrower than the option surface.

**2:00 — coupling.** §5.3:

```
PSOBPSUT     22 calls    7 external (32%)   — internal hub
PSOHLSN1     18 calls    9 external (50%)   — half its calls leave the package
PSOVRPT       7 calls    7 external (100%)  — pure shim into other packages
...
```

A routine at 100% external is a bridge — read it last when learning
the package internals; first when learning how PSO talks to its
neighbors.

**2:30 — entry hub.** Open `PSOBPSUT.m`. Run the routine-level sweep
from
[routine-situational-awareness.md](routine-situational-awareness.md).
Now the routine sidebar makes sense in package context: callers
include Integrated Billing and ECME, callees are mostly other PSO
routines, globals center on `^PSRX`.

**3:30 — handoff.**

```bash
vista-meta context "Outpatient Pharmacy" \
   --routines PSOBPSUT,PSOLSET,PSOORRL,PSOHLSN1 \
   --with-source > /tmp/pso.md
```

Paste into the AI chat. Question: "How does an order get verified
and dispensed end-to-end in PSO?" The model now has the full
critical-path source plus the package shape — can answer concretely.

**Total: under 5 minutes, package is mapped.** No file has been
read line-by-line.

---

## 9. Anti-patterns

| Pattern | Why it burns time | Defense |
|---|---|---|
| **Reading routines in alphabetical / filesystem order** | The filesystem ordering has nothing to do with importance. You'll burn 30 minutes on `PSOABRR.m` before getting to the entry-point hub. | Sort by in-degree (§5.1). Read top-down. |
| **Treating sub-namespaces as informal** | Newcomers assume `PSOVCC0/1/A` are arbitrary. They aren't — same feature. | Cluster first (§5.2 / §6.3); read clusters as units. |
| **Skipping the fingerprint** | `vista-meta pkg X` is 1 second. Most "what is this?" questions are answered there. | Always run it first. Tile against the directory listing. |
| **Mistaking infrastructure packages for owners of the data they touch** | A routine in `Order Entry` that touches `^PSRX` doesn't *own* `^PSRX` — Pharmacy does. | Use `package-data.tsv` (or §6.4) to distinguish owned from referenced data. |
| **Looking at one routine's external coupling without baseline** | "5% external — is that a lot?" Depends on the package. | Compare to package median (§5.3). |
| **Building Mermaid graphs without capping nodes** | A 421-routine package has ~50,000 edges. A diagram of all of them is unreadable. | `--top 50` or scope to one cluster. |
| **Ignoring `Packages/X/Globals/`** | Some packages also ship pre-populated globals; they live here, not under `Routines/`. | When in a package folder, glance at all sibling subdirs (`Globals/`, `Files/`, `KIDS/`). |
| **Trusting routine-name prefix as authoritative package** | `XU*` is normally Kernel — but a few `XU*` routines live in other packages. The directory wins. | Source of truth: `routines-comprehensive.tsv` column 2, derived from the directory. |

---

## 10. Reference

- [routine-situational-awareness.md](routine-situational-awareness.md) — the per-routine sweep that complements this doc
- [vista-vscode-guide.md § 3.2](vista-vscode-guide.md#32-pkg-name--package-overview) — the existing `vista-meta pkg` command
- [vista-vscode-guide.md § 3.3](vista-vscode-guide.md#33-context-name--ai-context-pack) — `vista-meta context` (the AI handoff)
- [code-model-guide.md](code-model-guide.md) — schema for every TSV the recipes use
- [vscode-extension-internals.md § 7](vscode-extension-internals.md#7-recommended-extensions-by-tier) — extension roadmap that the §7 integrations slot into
- [piks-analysis-guide.md](piks-analysis-guide.md) — what P/I/K/S means for owned globals
- [model-extraction-contract.md](../reference/model-extraction-contract.md) — the live §11 extraction contract the new scans should respect (promoted from spec-v0.4)
