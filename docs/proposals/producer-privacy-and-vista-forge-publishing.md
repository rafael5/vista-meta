# Producer privacy & gold-data publishing to vista-forge — pre-decisional plan

**Status:** Pre-decisional / planning · 2026-07-07
**Owner:** rafael
**Scope:** The publishing supply chain for the two VistA data producers —
**vista-meta** (measured code + data model) and **vdocs** (VA documentation gold
corpus) — and how their *consumable* output reaches the vista-forge consumers
(**Vista Atlas**, **Vista Compass**) and a future **MCP** audience once the
producers stop being public.
**Relation to prior decisions:** extends
[`vista-atlas-and-compass-de-novo.md`](vista-atlas-and-compass-de-novo.md) (the
consumers were homed in vista-forge 2026-07-05 as read-only release fetchers) and
the Track-D producer-contracts work (mutually-pinned `data-v1` releases). This
document does **not** decide anything; it records current state, the constraints
that force the shape, the owner's stated leanings, and the decisions still open.

---

## 1. Why this document exists

Today both producers are **public** repos under the personal `rafael5` namespace,
and each publishes its own `data-v1` GitHub Release that the vista-forge extensions
fetch anonymously. The owner wants the producers to become **private** (they are
analytics workbenches, not clean org citizens), while keeping the extensions — and
a new non-VSCode/agent audience — able to consume the data.

Making a producer private **breaks every anonymous consumer** unless the data is
republished somewhere public first. This plan is the controlled way to get there.

---

## 2. Current state (measured 2026-07-06)

- **Producers, public, under `rafael5`:**
  - `github.com/rafael5/vista-meta` (public, MIT) — 25 data TSVs committed in-repo;
    stdlib-only MCP server (`host/scripts/mcp_server.py`) that builds `meta.db` from
    those TSVs on demand; `data-v1` Release ships prebuilt `vista-meta-data-v1.db`
    (94 MB) + raw tarball + manifest + `SHA256SUMS`.
  - `github.com/rafael5/vdocs` (public) — medallion lake; `serve-mcp` reads a 325 MB
    `index.db` that lives in the **local** lake (`~/data/vdocs`, never committed);
    `data-v1` Release ships `vdocs-data-v1.tar.gz` (98 MB, = index.db + gold tree) +
    manifest + `SHA256SUMS`. The MCP is coupled to the `vdocs` Python package
    (`from vdocs.kernel import db`, `from vdocs.server import ids, search`).
- **Consumers, in `vista-forge`, read-only:** `vista-atlas` + `vista-compass`
  (Node/VSCode). Both fetch by a **pinned release contract** and never re-derive.
- **The consumer seam (load-bearing):** `contracts/releases/<name>-data-v1.json`
  names `{repo, tag, files[].sha256}`; `src/store/release.ts` builds
  `https://github.com/${repo}/releases/download/${tag}/${asset}`, fetches into
  `globalStorage`, and verifies the shas. **The producer is decoupled from every
  consumer by exactly one field: `repo`.**
- **Cross-producer invariant:** the two `data-v1` releases are **mutually pinned**
  (`content_hash` / `bundle_sha256` cross-reference; Track-D gate R). A consumer must
  take both releases from the same coordinated vintage.

---

## 3. Constraints & findings that force the shape

1. **Private-repo Release assets are auth-gated.** An anonymous
   `releases/download/...` fetch from a private repo returns 404. This is *the*
   reason a public republish target is mandatory, not optional.
2. **The contract seam makes the consumer-side change tiny.** Re-point `repo`
   (`rafael5/vdocs` → `vista-forge/vdocs-data`) and refresh the shas in
   `contracts/releases/*.json`. `release.ts` is unchanged.
3. **Bronze/silver is large, dirty, churning — and stays off GitHub.** The vdocs
   pipeline needs raw bronze + intermediate silver to build gold; they are not useful
   to publish and change constantly. Same logic applies to vista-meta's VEHU bake and
   extraction intermediates. **Only gold + exported registry data is consumable.**
4. **Publishing gold discloses nothing new.** The gold corpus and the TSVs are
   *already public today*; relocating them to a vista-forge public repo is a move, not
   a new disclosure. Making the producers private actually *strengthens* the boundary.
5. **Text vs binary split.** Gold text (vista-meta TSVs, vdocs gold markdown,
   manifests, contract records) is diffable and belongs *committed* in git. Big
   binaries (`meta.db` 94 MB, `index.db`/tarball 98–325 MB) must **not** enter git
   history — they ride as **Release assets** on the same public repo.
6. **Sequencing is safety-critical.** Stand up the public data repos + publish +
   re-point contracts + verify the live extensions **before** flipping any producer to
   private. Reverse order breaks Atlas/Compass the moment the switch flips.

---

## 4. Proposed architecture — four tiers, split by visibility

```
TIER 0  local only            TIER 1  private producer        TIER 2  public data repo         TIER 3  public consumer
(Linux Mint, never GitHub)    (rafael5, private — for now)    (vista-forge)                    (vista-forge)
──────────────────────────    ────────────────────────────   ─────────────────────────────   ──────────────────────────
vdocs bronze + silver lake ─► rafael5/vdocs (analytics)   ─►  vista-forge/vdocs-data       ─►  vista-atlas   (extension)
  raw crawl, intermediates      pipeline → gold + index.db     · gold markdown committed        vista-compass (extension)
                                                               · Release: tarball, manifest     vista-docs-mcp (deferred)
vista-meta bake intermediates ► rafael5/vista-meta        ─►  vista-forge/vista-meta-data  ─►  vista-atlas   (extension)
  VEHU image, extraction raw     bake → TSVs + meta.db          · TSVs committed                 vista-compass (extension)
                                                               · Release: meta.db, tarball,      vista-code-mcp (deferred)
                                                                 manifest, SHA256SUMS
```

- **Tier 0 — local only.** Bronze + silver (vdocs raw crawl / intermediates; the VEHU
  bake image and extraction scratch for vista-meta) live on Linux Mint and never touch
  GitHub. Large, dirty, churning, not consumable.
- **Tier 1 — private producers, staying in `rafael5` *for now*.** The Python /
  analytics work stays where it is; the repos are flipped from public to **private**.
  Relocating the producers into vista-forge (as private repos) is a **future option,
  deferred** (§6) — the bronze/silver reality means these are personal workbenches, not
  yet clean org citizens.
- **Tier 2 — new public vista-forge data repos.** Hold **only** cleaned gold + exported
  registry data: committed text for browse/diff, Release assets for binaries. This is
  the anonymous, public fetch target that keeps consumers working after Tier 1 goes
  private.
- **Tier 3 — public consumers.** Atlas + Compass already consume by contract and need
  only a re-pointed `repo`. The MCP audience is the new secondary consumer (§7).

---

## 5. What publishes vs what stays back (per producer)

| Producer | Stays local/private (Tier 0/1) | Publishes to vista-forge (Tier 2) |
|---|---|---|
| **vdocs** | bronze raw crawl, silver intermediates, full lake `~/data/vdocs`, the `vdocs` Python package + pipeline | gold markdown corpus (committed) · `index.db` + gold tree as `data-v1` Release tarball · manifest · `SHA256SUMS` |
| **vista-meta** | VEHU Docker bake, extraction scratch, raw sentinel logs | 25 data TSVs (committed) · prebuilt `meta.db` + raw tarball as `data-v1` Release · `entity-bridge.tsv` · `ai-manifest.json` / AI-CARD · manifest · `SHA256SUMS` |

"Exported registry data" = the vista-meta join/registry artifacts (entity bridge,
ai-manifest, package registries) and any vdocs registry exports the consumers read.
The dividing line is exactly the current `data-v1` Release payload — that payload is
already the vetted, consumable gold slice.

---

## 6. Owner leanings & decision status

**Decided (this thread):**
- **D1 — Producers go private.** vista-meta + vdocs flip public → private.
- **D2 — Producers stay in `rafael5` for now.** Do *not* migrate the analytics/Python
  work into vista-forge yet; revisit later. (The doc title frames the migration
  question; the current disposition is *defer the producer move*.)
- **D3 — Bronze/silver never on GitHub.** Raw + intermediate data stays on Linux Mint.
- **D4 — Only gold + registry publishes** to vista-forge, for Atlas/Compass (+ MCP).
- **D5 — The vista-forge data repos are public.** (Required by the anonymous-fetch
  consumers and the external MCP audience.)

**Deferred:**
- **D6 — MCP topology.** Combined `vista-mcp` *vs* two servers. Owner leans **two**:
  `vista-docs-mcp` (over vdocs gold) + `vista-code-mcp` (over vista-meta model).
  Decision deferred. Note the effort asymmetry: the vista-meta MCP is stdlib-only and
  near-free to publish; the vdocs MCP needs the read-only serving slice
  (`server/{mcp,ids,search,search_pure}` + minimal `kernel`) extracted from the private
  package into a public consumer repo.
- **Producer relocation** to vista-forge private repos (the D2 revisit).

**Open (needs a call before execution):**
- **O1 — Data-repo count/naming.** Two repos (`vista-forge/vista-meta-data` +
  `vista-forge/vdocs-data`, recommended — smallest delta, independent cadence, mutual
  pin already spans two repos) *vs* one combined `vista-forge/vista-data`.
- **O2 — Cutover sequencing owner sign-off** (§3.6): publish-and-verify before
  privatizing.
- **O3 — Cross-repo publish mechanism.** rafael5-private → vista-forge-public needs a
  cross-owner PAT in producer CI (an argument that later favors relocating producers
  into vista-forge so an org-scoped token suffices — feeds D2).
- **O4 — License** on the public data repos (data-only; MIT/CC0/ODbL TBD).

---

## 7. The MCP secondary audience (deferred detail)

The Atlas/Compass proposal explicitly deferred this
([`vista-atlas-and-compass-de-novo.md:169`](vista-atlas-and-compass-de-novo.md)):
*"retired unless a non-VSCode audience materializes."* It is now materializing —
developers who want to query the data from an agent instead of an editor.

- **`vista-code-mcp`** (vista-meta): the existing stdlib server, re-pointed at the
  public data repo. Cheap.
- **`vista-docs-mcp`** (vdocs): requires lifting the read-only serving slice out of the
  private `vdocs` package into a standalone public repo that reads the published
  `index.db`. Bounded (the server layer is already isolated under `src/vdocs/server/`),
  but it is the main engineering cost in the whole plan.
- Both are **read-only-over-published-data** → non-waterline vista-forge repos (the
  `clikit` precedent). Combined-vs-split is D6.

---

## 8. Sketch migration sequence (pre-decisional — not a commitment)

1. Create public `vista-forge` data repo(s) per O1; commit the gold text.
2. Wire a producer→data-repo publish step (CI or manual): build gold, push text,
   cut a `data-v1` Release with the binaries + manifest + `SHA256SUMS`, preserving the
   **mutual pin** between the two releases.
3. Re-point consumer contracts (`contracts/releases/*.json`: `repo` + shas) in
   vista-atlas + vista-compass; run their smoke fetch/verify; confirm green.
4. **Only then** flip `rafael5/vista-meta` and `rafael5/vdocs` to **private**.
5. Verify anonymous fetch from the vista-forge data repos still succeeds (the auth-gate
   check) and the extensions load from a clean `globalStorage`.
6. (Later, D6) stand up the MCP repo(s) against the public data.

Invariants to hold throughout: the **mutual `data-v1` pin** (§2) and the **contract
re-pin is the only consumer-side code change** (§3.2).

---

## 9. Risks / open questions

- **Break-before-publish** (mitigated by §8 ordering; O2 sign-off).
- **Cross-owner publish token** friction (O3) — the recurring argument for eventually
  moving producers into vista-forge (D2).
- **Mutual-pin drift** if the two data repos release on independent cadences — the
  Track-D gate R must move with the data, not stay behind in the private producers.
- **Big-binary hygiene** — never commit `meta.db`/`index.db`/tarballs to the data
  repos' git history; Releases only.

---

## 10. References

- Consumer seam: `vista-forge/vista-atlas/src/store/release.ts`,
  `contracts/releases/vdocs-data-v1.json`
- Producer releases: `rafael5/vista-meta` + `rafael5/vdocs` `data-v1` (GitHub Releases)
- vista-meta MCP: `host/scripts/mcp_server.py`, `host/scripts/build_meta_db.py`
- vdocs MCP: `~/projects/vdocs/src/vdocs/server/mcp.py`
- Prior decision: [`vista-atlas-and-compass-de-novo.md`](vista-atlas-and-compass-de-novo.md) §6 (home = vista-forge, 2026-07-05)
