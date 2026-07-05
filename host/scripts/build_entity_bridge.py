#!/usr/bin/env python3
# W3 of the machine-friendly-exports umbrella: the vdocs entity bridge.
# Plan: docs/historical/machine-friendly-exports.md

"""Emit the vdocs↔vista-meta entity bridge from two pinned releases.

  vista/export/bridge/entity-bridge.tsv        one row per vdocs entity
  vista/export/bridge/entity-bridge.meta.json  both pins + measured rates

Inputs are RELEASES, never live state: the vdocs data-v1 bundle
(unpacked at dist/peers/vdocs-data-v1 by `make peer-fetch`, sha256-
verified against docs/releases/data-v1-peers.json) and the vista-meta
TSVs (gate-verified ≡ docs/releases/data-v1.manifest.json). Every
entity gets exactly one row; `undetermined` is legal and *reported* —
rates are floors (regression tripwires), never faked coverage.

Join tiers mirror vdocs' D2.5 methodology (uppercase-exact against a
named vocabulary column, kernel/entity_quality.py there):
  high      — an authoritative vocabulary exists (the four shared
              vocabularies of schema_v1.SHARED_VOCABULARIES)
  moderate  — positive-only vocabulary: a match is evidence, absence
              is not (routine-globals is code-derived; namespace
              prefixes are curated)
  undetermined — no vista-meta vocabulary for the type, or no match

Gate: --check verifies (a) live content_hash ≡ the vista-meta release
pin, (b) the bridge meta's TWO fingerprints ≡ the in-repo pin records
(this extends Gate R to the bridge), (c) per-type rates recounted from
the committed TSV ≡ meta and ≥ their floors, and (d) when the peer
bundle is present, committed artifacts ≡ full regeneration.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path

import content_hash
import schema_v1

PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXPORT_DIR = PROJECT_ROOT / "vista/export"
BRIDGE_DIR_NAME = "bridge"
TSV_NAME = "entity-bridge.tsv"
META_NAME = "entity-bridge.meta.json"
RECORD_JSON = PROJECT_ROOT / "docs/releases/data-v1.manifest.json"
PEERS_JSON = PROJECT_ROOT / "docs/releases/data-v1-peers.json"
PEER_DIR = PROJECT_ROOT / "dist/peers/vdocs-data-v1"
PEER_KEY = "vdocs-data:data-v1"

COLUMNS = ("entity_id", "entity_type", "canonical_name", "mention_count",
           "vista_tsv", "vista_key_column", "vista_key_value",
           "join_method", "join_confidence")


@dataclass(frozen=True)
class BridgeSpec:
    vocabulary: str        # "<file>.tsv:<column>" (schema_v1 basename)
    method: str            # join_method label on a successful match
    confidence: str        # "high" | "moderate"
    status: str            # "floor-verified" | "positive-only"


BRIDGES: dict[str, BridgeSpec] = {
    "fileman_file": BridgeSpec("files.tsv:file_number",
                               "exact-key", "high", "floor-verified"),
    "rpc": BridgeSpec("rpcs.tsv:name",
                      "exact-name-ci", "high", "floor-verified"),
    "routine": BridgeSpec("routines.tsv:routine_name",
                          "exact-name-ci", "high", "floor-verified"),
    "option": BridgeSpec("options.tsv:name",
                         "exact-name-ci", "high", "floor-verified"),
    "global": BridgeSpec("routine-globals.tsv:global_name",
                         "global-caret-strip-ci", "moderate",
                         "positive-only"),
    "package_namespace": BridgeSpec("package-namespace.tsv:package",
                                    "namespace-ci", "moderate",
                                    "positive-only"),
}

# Regression tripwires on the measured rates — red-line only on
# regression, never on the known ceiling. The four floor-verified
# floors mirror vdocs' registries/entity-quality.yaml (this emitter
# reproduces its measured rates exactly: 0.8526 / 0.7296 / 0.5791).
# The two positive-only floors sit just under the rates measured on
# the first real emission (2026-07-05, vdocs pin 54a26e07…):
# global 0.076 (routine-globals is code-derived, absence ≠ invalid),
# package_namespace 0.9474 (18/19; DGPM is not among Registration's
# declared prefixes in package-namespace.tsv).
FLOORS: dict[str, float] = {
    "fileman_file": 0.80,
    "rpc": 0.65,
    "routine": 0.50,
    "option": 0.95,
    "global": 0.05,
    "package_namespace": 0.90,
}

# Types vdocs ships that have no vista-meta vocabulary at all.
NO_VOCABULARY_TYPES = ("build", "hl7_segment", "mail_group")


def _read_column(export_dir: Path, name: str, column: str) -> list[str]:
    spec = schema_v1.spec_for(name)
    path = export_dir / spec.model / name
    lines = path.read_text(encoding="utf-8").split("\n")
    i = lines[0].split("\t").index(column)
    return [row[i] for row in (ln.split("\t") for ln in lines[1:] if ln)
            if row[i]]


def _vocab_map(values: list[str]) -> dict[str, str]:
    """upper(value) → original value; bytewise-min original on dups."""
    out: dict[str, str] = {}
    for v in sorted(values):
        out.setdefault(v.upper(), v)
    return out


def _namespace_maps(export_dir: Path) -> tuple[dict[str, str],
                                               dict[str, str]]:
    """upper(namespace) → package, upper(prefix) → package.
    `!`-prefixed tokens in `prefixes` are exclusion markers, skipped."""
    spec = schema_v1.spec_for("package-namespace.tsv")
    path = export_dir / spec.model / "package-namespace.tsv"
    lines = path.read_text(encoding="utf-8").split("\n")
    header = lines[0].split("\t")
    i_pkg = header.index("package")
    i_ns = header.index("namespace")
    i_pre = header.index("prefixes")
    ns_map: dict[str, str] = {}
    prefix_map: dict[str, str] = {}
    for row in sorted(ln.split("\t") for ln in lines[1:] if ln):
        if row[i_ns]:
            ns_map.setdefault(row[i_ns].upper(), row[i_pkg])
        for tok in row[i_pre].split(","):
            tok = tok.strip()
            if tok and not tok.startswith("!"):
                prefix_map.setdefault(tok.upper(), row[i_pkg])
    return ns_map, prefix_map


def read_entities(peer_dir: Path) -> list[tuple[str, str, str, int]]:
    con = sqlite3.connect(peer_dir / "index.db")
    try:
        rows = con.execute(
            "SELECT entity_id, type, canonical_name, mention_count "
            "FROM entities ORDER BY entity_id").fetchall()
    finally:
        con.close()
    return [(r[0], r[1], r[2], int(r[3] or 0)) for r in rows]


def _unjoined(eid: str, etype: str, name: str, mentions: int) -> dict:
    return {"entity_id": eid, "entity_type": etype, "canonical_name": name,
            "mention_count": mentions, "vista_tsv": "",
            "vista_key_column": "", "vista_key_value": "",
            "join_method": "none", "join_confidence": "undetermined"}


def build_rows(export_dir: Path, peer_dir: Path) -> list[dict]:
    vocabs: dict[str, dict[str, str]] = {}
    for etype, bspec in BRIDGES.items():
        if etype == "package_namespace":
            continue
        fname, column = bspec.vocabulary.split(":")
        vocabs[etype] = _vocab_map(_read_column(export_dir, fname, column))
    ns_map, prefix_map = _namespace_maps(export_dir)

    rows = []
    for eid, etype, name, mentions in read_entities(peer_dir):
        bspec = BRIDGES.get(etype)
        if bspec is None:
            rows.append(_unjoined(eid, etype, name, mentions))
            continue
        fname, column = bspec.vocabulary.split(":")
        model = schema_v1.spec_for(fname).model
        if etype == "package_namespace":
            key = name.upper()
            pkg = ns_map.get(key)
            method = "namespace-ci"
            if pkg is None:
                pkg = prefix_map.get(key)
                method = "prefix-ci"
            if pkg is None:
                rows.append(_unjoined(eid, etype, name, mentions))
                continue
            rows.append({"entity_id": eid, "entity_type": etype,
                         "canonical_name": name, "mention_count": mentions,
                         "vista_tsv": f"{model}/{fname}",
                         "vista_key_column": column,
                         "vista_key_value": pkg, "join_method": method,
                         "join_confidence": bspec.confidence})
            continue
        lookup = name.upper()
        if etype == "global" and lookup.startswith("^"):
            lookup = lookup[1:]
        hit = vocabs[etype].get(lookup)
        if hit is None:
            rows.append(_unjoined(eid, etype, name, mentions))
            continue
        rows.append({"entity_id": eid, "entity_type": etype,
                     "canonical_name": name, "mention_count": mentions,
                     "vista_tsv": f"{model}/{fname}",
                     "vista_key_column": column, "vista_key_value": hit,
                     "join_method": bspec.method,
                     "join_confidence": bspec.confidence})
    return sorted(rows, key=lambda r: r["entity_id"])


def _rates(rows: list[dict]) -> dict[str, dict]:
    types: dict[str, dict] = {}
    seen = {r["entity_type"] for r in rows}
    for etype in sorted(set(BRIDGES) | set(NO_VOCABULARY_TYPES) | seen):
        of_type = [r for r in rows if r["entity_type"] == etype]
        joined = sum(1 for r in of_type if r["join_method"] != "none")
        count = len(of_type)
        bspec = BRIDGES.get(etype)
        types[etype] = {
            "status": bspec.status if bspec else "no-vocabulary",
            "vocabulary": bspec.vocabulary if bspec else "",
            "confidence": bspec.confidence if bspec else "undetermined",
            "count": count,
            "joined": joined,
            "rate": round(joined / count, 4) if count else 1.0,
            "floor": FLOORS.get(etype, 0.0),
        }
    return types


def build_meta(rows: list[dict], peers_record: dict,
               release_record: dict) -> dict:
    peer = peers_record["peers"][PEER_KEY]
    return {
        "artifact": "vista-meta-entity-bridge",
        "schema_version": 1,
        "generated_by": "host/scripts/build_entity_bridge.py",
        "columns": list(COLUMNS),
        "pins": {
            "vista_meta": {"artifact": "vista-meta-data",
                           "tag": release_record["tag"],
                           "content_hash": release_record["content_hash"]},
            "vdocs": {"artifact": "vdocs-data", "tag": "data-v1",
                      "corpus_content_hash": peer["corpus_content_hash"],
                      "bundle_sha256": peer["bundle_sha256"],
                      "release": peer.get("release", "")},
        },
        "counts": {
            "entities": len(rows),
            "joined": sum(1 for r in rows if r["join_method"] != "none"),
        },
        "types": _rates(rows),
    }


def render_tsv(rows: list[dict]) -> str:
    lines = ["\t".join(COLUMNS)]
    lines += ["\t".join(str(r[c]) for c in COLUMNS) for r in rows]
    return "\n".join(lines) + "\n"


def render_meta(doc: dict) -> str:
    return json.dumps(doc, indent=2, sort_keys=True) + "\n"


def verify_peer(peer_dir: Path, peers_record: dict) -> list[str]:
    """The unpacked bundle must BE the pinned release (bridge-staleness
    risk): its manifest's corpus_content_hash ≡ the peers record's."""
    manifest = json.loads(
        (peer_dir / "manifest.json").read_text(encoding="utf-8"))
    pinned = peers_record["peers"][PEER_KEY]["corpus_content_hash"]
    if manifest["corpus_content_hash"] != pinned:
        return [f"peer manifest mismatch: unpacked bundle has "
                f"corpus_content_hash {manifest['corpus_content_hash'][:16]}…"
                f" but the pin record says {pinned[:16]}… — re-run "
                "'make peer-fetch'"]
    return []


def emit(export_dir: Path, peer_dir: Path, peers_record: dict,
         release_record: dict) -> None:
    for e in verify_peer(peer_dir, peers_record):
        sys.exit(f"ERROR: {e}")
    rows = build_rows(export_dir, peer_dir)
    out_dir = export_dir / BRIDGE_DIR_NAME
    out_dir.mkdir(exist_ok=True)
    (out_dir / TSV_NAME).write_text(render_tsv(rows), encoding="utf-8")
    (out_dir / META_NAME).write_text(
        render_meta(build_meta(rows, peers_record, release_record)),
        encoding="utf-8")


def _recount(tsv_text: str) -> dict[str, tuple[int, int]]:
    """(count, joined) per type from a committed bridge TSV."""
    lines = tsv_text.split("\n")
    header = lines[0].split("\t")
    i_type = header.index("entity_type")
    i_method = header.index("join_method")
    out: dict[str, tuple[int, int]] = {}
    for row in (ln.split("\t") for ln in lines[1:] if ln):
        c, j = out.get(row[i_type], (0, 0))
        out[row[i_type]] = (c + 1, j + (row[i_method] != "none"))
    return out


def check(export_dir: Path, peer_dir: Path | None, peers_record: dict,
          release_record: dict,
          floors: dict[str, float] = FLOORS) -> list[str]:
    errors = []
    live = content_hash.compute(export_dir)
    if live != release_record["content_hash"]:
        errors.append(
            f"content_hash drift: live {live[:16]}… != release "
            f"{release_record['content_hash'][:16]}… — the TSVs changed "
            f"since {release_record['tag']}; the bridge's vista-meta side "
            "is no longer the pinned release")

    tsv_path = export_dir / BRIDGE_DIR_NAME / TSV_NAME
    meta_path = export_dir / BRIDGE_DIR_NAME / META_NAME
    if not tsv_path.exists() or not meta_path.exists():
        return errors + [f"{TSV_NAME} / {META_NAME}: missing — run "
                         "'make bridge'"]
    meta = json.loads(meta_path.read_text(encoding="utf-8"))

    # Gate R extension: both fingerprints must match the pin records.
    peer_pin = peers_record["peers"][PEER_KEY]
    if (meta["pins"]["vista_meta"]["content_hash"]
            != release_record["content_hash"]):
        errors.append("pin mismatch (vista_meta): bridge meta != "
                      "docs/releases/data-v1.manifest.json")
    if (meta["pins"]["vdocs"]["corpus_content_hash"]
            != peer_pin["corpus_content_hash"]
            or meta["pins"]["vdocs"]["bundle_sha256"]
            != peer_pin["bundle_sha256"]):
        errors.append("pin mismatch (vdocs): bridge meta != "
                      "docs/releases/data-v1-peers.json")

    # Rates: recount from the committed TSV, compare to meta, gate floors.
    recount = _recount(tsv_path.read_text(encoding="utf-8"))
    for etype, t in meta["types"].items():
        count, joined = recount.get(etype, (0, 0))
        rate = round(joined / count, 4) if count else 1.0
        if (count, joined, round(t["rate"], 4)) != (t["count"], t["joined"],
                                                    rate):
            errors.append(f"rate mismatch ({etype}): meta says "
                          f"{t['joined']}/{t['count']}, TSV recount says "
                          f"{joined}/{count} — stale, run 'make bridge'")
        floor = floors.get(etype, 0.0)
        if t.get("floor") != floor:
            errors.append(f"floor drift ({etype}): meta {t.get('floor')} != "
                          f"declared {floor} — regenerate")
        if rate < floor:
            errors.append(f"floor regression ({etype}): measured {rate} < "
                          f"floor {floor}")

    # Full regeneration diff — only when the pinned peer input is present.
    if peer_dir is not None and peer_dir.exists():
        errors += verify_peer(peer_dir, peers_record)
        if not errors:
            rows = build_rows(export_dir, peer_dir)
            if tsv_path.read_text(encoding="utf-8") != render_tsv(rows):
                errors.append(f"{TSV_NAME}: stale (differs from "
                              "regeneration) — run 'make bridge'")
            want_meta = render_meta(
                build_meta(rows, peers_record, release_record))
            if meta_path.read_text(encoding="utf-8") != want_meta:
                errors.append(f"{META_NAME}: stale (differs from "
                              "regeneration) — run 'make bridge'")
    return errors


def main(argv: list[str]) -> int:
    release_record = json.loads(RECORD_JSON.read_text(encoding="utf-8"))
    peers_record = json.loads(PEERS_JSON.read_text(encoding="utf-8"))
    if argv == ["--check"]:
        peer = PEER_DIR if PEER_DIR.exists() else None
        errors = check(EXPORT_DIR, peer, peers_record, release_record)
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        scope = ("full" if peer else
                 "pins+rates only — peer bundle absent, run "
                 "'make peer-fetch' for the regeneration diff")
        print(f"entity-bridge check ({scope}): "
              + ("FAIL" if errors else "PASS"))
        return 1 if errors else 0
    if not PEER_DIR.exists():
        sys.exit("ERROR: dist/peers/vdocs-data-v1 not found — run "
                 "'make peer-fetch' first")
    emit(EXPORT_DIR, PEER_DIR, peers_record, release_record)
    meta = json.loads((EXPORT_DIR / BRIDGE_DIR_NAME / META_NAME)
                      .read_text(encoding="utf-8"))
    for etype, t in sorted(meta["types"].items()):
        print(f"  {etype:<18} {t['joined']:>5}/{t['count']:<5} "
              f"rate {t['rate']:<7} floor {t['floor']:<5} [{t['status']}]")
    print(f"{TSV_NAME}: {meta['counts']['joined']}/"
          f"{meta['counts']['entities']} entities joined")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
