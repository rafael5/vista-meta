#!/usr/bin/env python3
# W1 of the machine-friendly-exports umbrella: the generated AI card.
# Plan: docs/proposals/machine-friendly-exports.md
# Spec: docs/proposals/ai-card.md

"""Emit the AI orientation surface beside the TSVs, as data.

Two generated projections (one fact, one owner — nothing here is
hand-maintained):

  vista/export/AI-CARD.md        human/AI orientation card
  vista/export/ai-manifest.json  machine-readable catalog + query
                                 recipe + join-key registry

Inputs: schema_v1 (structure), the live TSVs (row counts), and the
in-repo release record docs/releases/data-v1.manifest.json (the
provenance pin — hashes are copied verbatim, never recomputed into
the card). Static prose fragments (caveats, PIKS one-liners, recipes)
live in this module.

Gate:  --check regenerates both artifacts and diffs against the
       committed files (a stale or hand-edited card is RED), and
       asserts the live tree's content_hash ≡ the release record's
       (a card whose pin lies about the TSVs beside it is RED).
Everything is deterministic — no wall-clock, no environment.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import content_hash
import schema_v1

PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXPORT_DIR = PROJECT_ROOT / "vista/export"
RECORD_JSON = PROJECT_ROOT / "docs/releases/data-v1.manifest.json"

CARD_NAME = "AI-CARD.md"
MANIFEST_NAME = "ai-manifest.json"

CAPABILITIES = (
    "call-graph",
    "package-topology",
    "piks-classification",
    "rpc-option-protocol-bindings",
    "routine-metrics",
    "global-usage",
    "xindex-findings",
    "vdocs-bridge-keys",
)

CLI_VERBS = {
    "pkg <name>": "package overview (namespace, footprint, PIKS mix)",
    "file <N> [--fields N]": "FileMan file + PIKS + pointers + fields",
    "where TAG^ROUTINE": "locate source",
    "callers [TAG^]ROUTINE": "reverse call graph (measured, ranked)",
    "search <regex> [--package P] [--tags-only]": "annotated corpus grep",
    "context <pkg> [--with-source]": "AI context pack",
    "doctor": "environment health check",
}

SQLITE_RECIPE = """cd ~/projects/vista-meta/vista/export
sqlite3 :memory: <<'SQL'
.mode tabs
.import code-model/rpcs.tsv rpcs
.import code-model/routines-comprehensive.tsv r
SELECT rpcs.name, rpcs.tag, rpcs.routine_name, r.package, r.line_count
FROM rpcs JOIN r ON r.routine_name = rpcs.routine_name
WHERE rpcs.name LIKE 'ORWPT%' LIMIT 20;
SQL"""

AWK_RECIPES = """VM=~/projects/vista-meta/bin/vista-meta
X=~/projects/vista-meta/vista/export

$VM pkg PSO                        # package overview (Outpatient Pharmacy)
$VM file 52 --fields 15            # file #52 + PIKS + pointers + first fields
$VM callers SITE^VASITE            # who calls TAG^ROUTINE (measured, ranked)
$VM search 'MERGE \\^DPT' --package DG   # annotated regex over package source
$VM context OR --routines ORWPT    # AI context pack incl. budgeted source

# Which routine implements an RPC?
awk -F'\\t' '$2=="ORWPT SELECT"{print $3"^"$4}' $X/code-model/rpcs.tsv
# PIKS class + evidence for a file
awk -F'\\t' '$1=="200"' $X/data-model/piks.tsv
# Top globals a routine touches
awk -F'\\t' '$1=="ORWPT"' $X/code-model/routine-globals.tsv | sort -t$'\\t' -k4,4nr | head
# Cross-package coupling into FileMan
awk -F'\\t' '$2=="VA FileMan"' $X/code-model/package-edge-matrix.tsv | sort -t$'\\t' -k3,3nr | head"""


def row_count(path: Path) -> int:
    """Data rows = newlines minus the header (files end with LF)."""
    return path.read_bytes().count(b"\n") - 1


def _join_key_registry() -> list[dict]:
    """Every declared FK edge, grouped by its target column."""
    reg: dict[str, list[str]] = {}
    for name, spec in sorted(schema_v1.FILES.items()):
        for col, target in sorted(spec.fks.items()):
            reg.setdefault(target, []).append(f"{spec.model}/{name}:{col}")
    return [{"target": t, "referenced_by": refs}
            for t, refs in sorted(reg.items())]


def build_manifest_doc(export_dir: Path, record: dict) -> dict:
    tag = record["tag"]
    return {
        "artifact": "vista-meta-ai-manifest",
        "schema_version": record["schema_version"],
        "generated_by": "host/scripts/build_ai_card.py",
        "card": f"vista/export/{CARD_NAME}",
        "release": {
            "tag": tag,
            "content_hash": record["content_hash"],
            "db_state_fingerprint": record["db_state_fingerprint"],
            "extraction_timestamp": record["extraction_timestamp"],
            "engine": record["engine"],
            "engine_image": record["engine_image"],
            "source_commit": record["source_commit"],
            "manifest": "docs/releases/data-v1.manifest.json",
            "schema_contract":
                "docs/reference/schema-v1-normalization-spec.md",
        },
        "capabilities": list(CAPABILITIES),
        "citation": {
            "format": f"vista-meta {tag} · <tsv path> · <key>=<value>",
            "example": f"vista-meta {tag} · code-model/rpcs.tsv · "
                       "name=ORWPT SELECT",
            "no_answer": f"not measured in vista-meta {tag}",
        },
        "query": {
            "cli": "bin/vista-meta",
            "cli_on_path": False,
            "verbs": CLI_VERBS,
            "tsv_root": "vista/export",
            "sqlite_recipe": SQLITE_RECIPE,
            "meta_db": "make meta-db → dist/vista-meta-data-v1.db — "
                       "generated SQLite projection (24 tables + "
                       "entity_bridge + join views v_rpc_impl / "
                       "v_option_impl / v_global_file_piks / "
                       "v_routine_global_piks / v_rpc_data_piks / "
                       "v_package_overview); the TSVs stay canonical",
        },
        "join_keys": _join_key_registry(),
        "shared_vocabularies": [
            {"file": f, "column": c}
            for f, c in schema_v1.SHARED_VOCABULARIES],
        "external_bridges": [{
            "companion": "vdocs",
            "via": "code-model/package-namespace.tsv",
            "columns": ["app_code", "vdl_id"],
            "note": "vdocs search hits carry app_code; both releases are "
                    "mutually pinned (Gate R, docs/releases/"
                    "data-v1-peers.json)",
        }, {
            "companion": "vdocs",
            "via": "vista/export/bridge/entity-bridge.tsv",
            "columns": ["entity_id", "vista_tsv", "vista_key_column",
                        "vista_key_value"],
            "note": "generated W3 bridge — one row per vdocs data-v1 "
                    "entity mapped to its vista-meta vocabulary value "
                    "(join_method/join_confidence, undetermined legal); "
                    "dual release pins + measured join rates in "
                    "bridge/entity-bridge.meta.json",
        }],
        "tables": {
            f"{spec.model}/{name}": {
                "rows": row_count(export_dir / spec.model / name),
                "pk": list(spec.pk),
                "columns": list(spec.columns),
                "sha256": record["files"][f"{spec.model}/{name}"]["sha256"],
                "bytes": record["files"][f"{spec.model}/{name}"]["bytes"],
            }
            for name, spec in sorted(schema_v1.FILES.items())},
    }


def render_manifest(doc: dict) -> str:
    return json.dumps(doc, indent=2, sort_keys=True) + "\n"


def _dictionary_table(export_dir: Path, model: str) -> str:
    lines = ["| TSV | rows | key | columns |", "|---|---|---|---|"]
    for name, spec in sorted(schema_v1.FILES.items()):
        if spec.model != model:
            continue
        rows = row_count(export_dir / spec.model / name)
        key = "+".join(f"`{c}`" for c in spec.pk)
        cols = " · ".join(spec.columns)
        lines.append(f"| `{name}` | {rows:,} | {key} | {cols} |")
    return "\n".join(lines)


def render_card(export_dir: Path, record: dict) -> str:
    tag = record["tag"]
    verbs = " ·\n   ".join(f"`{v}` {d}" for v, d in CLI_VERBS.items())
    return f"""# vista-meta — AI card (the measured model of VistA)

> **GENERATED — do not edit.** Emitted by `host/scripts/build_ai_card.py`
> from `schema_v1` + the live TSVs + the pinned release record
> (`docs/releases/data-v1.manifest.json`). Regenerate with `make ai-card`;
> drift-gated by `make card-check` (stale card = RED, card pin must equal
> the release manifest's `content_hash`). Machine-readable twin:
> `vista/export/ai-manifest.json`.

## What this is

`vista-meta` is a deterministic, **measured** model of VistA — extracted from a pinned
VEHU instance (YottaDB), not transcribed from documentation. It answers *what the code
and data actually are*: which routine calls which, which package owns what, how every
FileMan file is classified (PIKS), where every RPC/option/protocol lands.

**Contract:** answer measured questions from these TSVs (or the CLI over them), cite the
row you read, and never fill a gap with general VistA knowledge. This card is the
orientation — read it instead of re-exploring the export tree.

Companion source: the **vdocs gold corpus** (`~/data/vdocs/`) holds what the VA
*documentation says*. vista-meta holds what the system *measurably is*. When they
conflict, report both sides labeled `documented:` vs `measured:` — do not reconcile
silently.

## Provenance (pin this in answers)

| Field | Value |
|---|---|
| release | `{tag}` (`schema_version: {record["schema_version"]}`) |
| content_hash | `{record["content_hash"]}` |
| db_state_fingerprint | `{record["db_state_fingerprint"]}` |
| extracted | {record["extraction_timestamp"]}, engine `{record["engine"]}`, image `{record["engine_image"]}` |
| manifest | `docs/releases/data-v1.manifest.json` (in-repo record; per-file sha256) |
| schema contract | `docs/reference/schema-v1-normalization-spec.md` |

**Scope caveats (state these when they matter):**
- Measured on the **VEHU demo instance** — `record_count` and data-bearing counts reflect
  VEHU's demo data, not any production site. Structure (DD, routines, options, RPCs) is
  the shipped VistA code base; record volumes are not.
- The routine census contains only **11 `%`-routines** (`is_percent_routine=Y`) — Kernel
  `%`-utilities largely live outside the extracted source tree, so call edges *into* them
  are visible but their own rows/edges mostly are not.
- XINDEX outputs are cross-validated against our parser in `xindex-validation.tsv`; when
  a per-routine claim is load-bearing, check its `callees_agreement_ratio` there.

## Query paths (in order of preference)

1. **CLI** — `~/projects/vista-meta/bin/vista-meta <verb>` (not on `$PATH`):
   {verbs}.
2. **TSVs directly** — `vista/export/{{data-model,code-model}}/*.tsv`, tab-separated,
   header row, deterministic sort. Fine for `awk -F'\\t'` single-file lookups.
3. **Joins** — load into in-memory SQLite (no build step; first row becomes column
   names when the table doesn't pre-exist):
   ```bash
{_indent(SQLITE_RECIPE, "   ")}
   ```
   Or generate the one-file projection: `make meta-db` →
   `dist/vista-meta-data-v1.db` (all tables typed + the entity bridge + join
   views `v_rpc_impl`, `v_routine_global_piks`, `v_rpc_data_piks`,
   `v_package_overview`, …). The TSVs stay canonical; the db is derived.

## Data dictionary

### data-model/ (PIKS classification — 100% file coverage: auto + triage + subfile inheritance)

{_dictionary_table(export_dir, "data-model")}

**PIKS in one line each** (full guide: `docs/guides/piks-analysis-guide.md`):
**P** Patient — clinical data about identified individuals (PHI). **I** Institution —
facilities, staff (File 200), schedules, assets. **K** Knowledge — terminologies, code
tables, templates, rules. **S** System — Kernel/FileMan plumbing, menus, queues, config.

### code-model/ (per-routine intelligence)

{_dictionary_table(export_dir, "code-model")}

## Join keys

- **`routine_name`** — routines* ↔ routine-calls (`caller_routine`/`callee_routine`) ↔
  routine-globals ↔ rpcs ↔ options ↔ vista-file-9-8 ↔ xindex-*.
- **`package`** — every code-model TSV; `package-namespace.tsv` maps it to
  namespace/prefixes and to **`app_code`/`vdl_id`**, which join to vdocs hits
  (`vdocs search` results carry `app_code`).
- **`file_number`** — files ↔ piks ↔ field-piks ↔ package-data;
  `field-piks.pointer_target` is itself a file_number (the pointer graph).
- **`TAG^ROUTINE`** — rpcs/options/protocol-calls (`tag`+`routine_name`) ↔
  routine-calls (`callee_tag`+`callee_routine`).
- **Global names** — `routine-globals.global_name` is bare (`DPT`); `files.global_root`
  is a global reference (may be empty, may carry `^`/subscripts) — normalize before
  joining.

- **vdocs entities** — the generated bridge `bridge/entity-bridge.tsv` maps every
  vdocs `data-v1` entity (`<type>:<canonical_name>`) to its vista-meta row
  (`vista_tsv` + `vista_key_column`=`vista_key_value`, with `join_method` /
  `join_confidence`; `undetermined` is legal). Dual release pins + measured join
  rates: `bridge/entity-bridge.meta.json`.

The full FK registry (every declared edge, machine-readable) lives in
`ai-manifest.json` under `join_keys`.

## Recipes

```bash
{AWK_RECIPES}
```

## Citation contract

Cite every measured claim as:

> **vista-meta {tag}** · `<tsv path>` · `<key>=<value>` — *or* the exact CLI command run.

Example: *"ORWPT SELECT is served by SELECT^ORWPT"* →
**vista-meta {tag}** · `code-model/rpcs.tsv` · `name=ORWPT SELECT`.

If no row answers the question, the correct answer is
**"not measured in vista-meta {tag}"** — say so and stop; do not substitute
general knowledge.
"""


def _indent(text: str, prefix: str) -> str:
    return "\n".join(prefix + ln for ln in text.splitlines())


def emit(export_dir: Path, record: dict) -> None:
    (export_dir / CARD_NAME).write_text(
        render_card(export_dir, record), encoding="utf-8")
    (export_dir / MANIFEST_NAME).write_text(
        render_manifest(build_manifest_doc(export_dir, record)),
        encoding="utf-8")


def check(export_dir: Path, record: dict) -> list[str]:
    errors = []
    live = content_hash.compute(export_dir)
    if live != record["content_hash"]:
        errors.append(
            f"content_hash drift: live {live[:16]}… != release "
            f"{record['content_hash'][:16]}… — the TSVs changed since "
            f"{record['tag']}; cut a new release (and record) before "
            "regenerating the card")
    expected = ((CARD_NAME, render_card(export_dir, record)),
                (MANIFEST_NAME,
                 render_manifest(build_manifest_doc(export_dir, record))))
    for name, want in expected:
        p = export_dir / name
        if not p.exists():
            errors.append(f"{name}: missing — run 'make ai-card'")
        elif p.read_text(encoding="utf-8") != want:
            errors.append(f"{name}: stale (differs from regeneration) — "
                          "run 'make ai-card'")
    return errors


def main(argv: list[str]) -> int:
    record = json.loads(RECORD_JSON.read_text(encoding="utf-8"))
    if argv == ["--check"]:
        errors = check(EXPORT_DIR, record)
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        print("ai-card check: " + ("FAIL" if errors else
                                   "PASS (card ≡ regeneration, pin ≡ "
                                   f"{record['tag']} manifest)"))
        return 1 if errors else 0
    emit(EXPORT_DIR, record)
    n_rows = sum(row_count(EXPORT_DIR / s.model / n)
                 for n, s in schema_v1.FILES.items())
    print(f"{CARD_NAME} + {MANIFEST_NAME}: 24 tables, {n_rows:,} rows, "
          f"pinned to {record['tag']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
