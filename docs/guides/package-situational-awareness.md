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

- **Routines come in clusters.** `PSOVCC0`, `PSOVCC1`, `PSOVCC2` are
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
=== Outpatient Pharmacy ===
421 routines, 142,318 lines (avg 338/routine)
PIKS: P=4 I=12 K=8 S=3   (← what kind of data this owns)
RPCs: 38   Options: 52   Protocols: 11   (← public surface)
Distinct globals touched: 67
Top FM files owned: PRESCRIPTION (52), PHARMACY PATIENT (55), ...
Top globals: ^PSRX (8421), ^PS(52, ...) (3120), ^DPT (1842), ...
Top inbound edges (who calls us):
   CPRS                 4,123 calls   91 routines
   Pharmacy Data Mgmt   2,418 calls   38 routines
   ...
Top outbound edges (who we call):
   Kernel              12,841 calls
   FileMan              8,212 calls
   ...
Top entry-point candidates (highest in-degree):
   PSOORNE              312 callers
   PSORENW              188 callers
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
12  PSOVC   PSOVCC0 PSOVCC1 PSOVCC2 PSOVCDF PSOVCMV ...
8   PSOREJ  PSOREJ0 PSOREJ1 PSOREJP2 PSOREJP3 ...
...
```

Each cluster is "one feature." When you read PSOVCC0, also open
PSOVCC1 and PSOVCC2 — they're the same conversation continued.

### 5.3 Cross-package outbound coupling per routine

"This routine calls into other packages — how heavily?"

```bash
awk -F'\t' -v p="Outpatient Pharmacy" '
  NR==1 { next }
  $2==p && $2 != $7 { ext[$1]++ }
  $2==p             { tot[$1]++ }
  END { for (r in tot) printf "%s\t%d\t%d\t%.0f%%\n",
        r, tot[r], ext[r]+0, (ext[r]+0)*100/tot[r] }
' vista/export/code-model/routine-calls.tsv \
  | sort -t$'\t' -k4,4 -n -r \
  | head -20
```

(Columns: routine, total calls, external calls, % external.) Routines
near 100% external are interfaces / shims; near 0% are pure
internals.

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

```bash
awk -F'\t' -v p="Outpatient Pharmacy" '
  NR==1 { next }
  $2==p && $7==p && $6+0 >= 5 {
    print "  " $1 " --> " $4
  }
' vista/export/code-model/routine-calls.tsv \
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

### RPCs (38)
| RPC name                        | Tag^Routine        | Return |
|---|---|---|
| ORWPS COVER                     | COVER^PSOORRX      | array |
| PSO LM ALLERGY                  | EN^PSOLMALL        | single |
| ...

### Options (52)
| Option                          | Tag^Routine        | Type |
|---|---|---|
| PSO MAINTENANCE                 | EN^PSOMAIN         | menu |
| ...

### Protocols (11)
| Protocol                        | Type    | Action |
|---|---|---|
| PSO REFILL EVENT                | event   | EN^PSOREFL |
| ...
```

**Implementation:** Filter `rpcs.tsv`, `options.tsv`, `protocols.tsv`
where `package = $PKG`. Group by routine, sort alphabetically. ~50
lines of Python.

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
PSO  (421 routines)
├── PSOVC*  (12)   — pharmacy verify / processing
│     PSOVCC0 PSOVCC1 PSOVCC2 PSOVCDF PSOVCMV ...
├── PSOREJ* (8)    — rejection handling
│     PSOREJ0 PSOREJ1 PSOREJP2 PSOREJP3 ...
├── PSOOR*  (24)   — order entry
│     ...
└── ungrouped (47)
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
| `^PSRX` | 52 PRESCRIPTION | P | yes | 312 | 8421 |
| `^DPT` | 2 PATIENT | P | no (Registration) | 18 | 1842 |
| `^DIC` | 1 FILE | S | no (FileMan) | 47 | 421 |
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
| Target package        | Edges  | Top targeted tags |
|---|---|---|
| Kernel                | 12,841 | DT^DICRW (842), $$EN^XUSCLEAN (412) |
| FileMan               |  8,212 | ^DIC (1283), ^DIE (842) |
| Registration          |    421 | DEM^VADPT (218) |
| ...

### Inbound (depends on us)
| Source package        | Edges | Top called tags here |
|---|---|---|
| CPRS                  | 4,123 | EN^PSOORNE (1841), $$RXACT^PSOORDIM (412) |
| Pharmacy Data Mgmt    | 2,418 | ... |
```

**Implementation:** Filter `routine-calls.tsv` on `caller_package`
(outbound) and `caller_routine`'s package (inbound, via
`routines-comprehensive.tsv`). Aggregate by package + top tags.

### 6.6 `vista-meta package-health PKG` — maintenance dashboard

**Answers Q5.** One row per routine:

| Routine | Lines | Patches | Last commit | Has test | XINDEX | Lint |
|---|---|---|---|---|---|---|
| PSOORNE | 842 | 18 | 2024-09 | yes | 2W | pass |
| PSORENW | 412 | 12 | 2023-05 | no | clean | fail |
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
    421 routines · 38 RPCs · 52 OPTs · 11 protocols

  ▾ Entry Points (101)
    ▾ RPCs (38)
       ORWPS COVER          → COVER^PSOORRX
       PSO LM ALLERGY       → EN^PSOLMALL
       ...
    ▾ Options (52)
       ...
    ▾ Protocols (11)
       ...

  ▾ Hub Routines (top 10)
    PSOORNE   in=312
    PSORENW   in=188
    ...

  ▾ Owned Globals (P=4 I=12 K=8 S=3)
    ^PSRX    [P · file 52 PRESCRIPTION]    8421 refs
    ^PS(52)  [P · file 52]                  3120 refs
    ...

  ▾ Coupling
    Outbound → Kernel (12,841), FileMan (8,212), ...
    Inbound  ← CPRS (4,123), ...

  ▾ Sub-namespaces (8)
    PSOVC* (12), PSOREJ* (8), PSOOR* (24), ...
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
(`vistaMeta.codeLens.packageContext: boolean`) — off by default since
CodeLens is visually noisy.

### 7.4 Status bar segment

Right-aligned: `PSO · 421R · 38RPC · 52OPT`. Click → command palette
filtered to `vista-meta package-*`. One line of code, always-visible
context.

### 7.5 Quick-open within package

Custom command `vistaMeta.quickOpenPackage`:

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

Output (abbreviated): 421 routines, 38 RPCs, 52 options, 11
protocols, 67 globals. Top FM files: PRESCRIPTION (52), PHARMACY
PATIENT (55). Top inbound: CPRS (4,123 calls). Top entry-point:
`PSOORNE` (in=312).

**0:30 — clusters.** Run §5.2:

```
PSOOR*   24 routines  — order entry, including PSOORNE
PSOVC*   12 routines  — verify / completion
PSOREJ*   8 routines  — rejection handling
PSORX*   18 routines  — prescription operations
...
```

Now I know the package decomposes into ~10 features.

**1:00 — public surface.** Until `package-map` lands:

```bash
awk -F'\t' '$5=="Outpatient Pharmacy"' \
  vista/export/code-model/rpcs.tsv | head
```

The 38 RPCs cluster heavily under PSOORNE, PSOLMALL, PSORX*.
Confirms the cluster picture.

**2:00 — coupling.** §5.3:

```
PSOORNE     842 calls   12 external (1.4%)   — internal hub
PSOOR1      412 calls   58 external (14%)    — calls Kernel & CPRS
PSOXMITQ     38 calls   38 external (100%)   — pure shim into MailMan
...
```

PSOXMITQ at 100% external is a bridge — read it last when learning
the package internals; first when learning how PSO talks to MailMan.

**2:30 — entry hub.** Open `PSOORNE.m`. Run the routine-level sweep
from
[routine-situational-awareness.md](routine-situational-awareness.md).
Now the routine sidebar makes sense in package context: callers
include CPRS, callees are mostly other PSO routines, globals
center on `^PSRX`.

**3:30 — handoff.**

```bash
vista-meta context "Outpatient Pharmacy" \
   --routines PSOORNE,PSOOR1,PSOLMALL,PSORX0 \
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
| **Treating sub-namespaces as informal** | Newcomers assume `PSOVCC0/1/2` are arbitrary. They aren't — same feature. | Cluster first (§5.2 / §6.3); read clusters as units. |
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
- [docs/vista-meta-spec-v0.4.md § 11](vista-meta-spec-v0.4.md) — bake contracts the new scans should respect
