#!/usr/bin/env python3
# W2b of the machine-friendly-exports umbrella: the meta.db projection.
# Plan: docs/historical/machine-friendly-exports.md

"""Generate the SQLite projection of the data release.

  dist/vista-meta-data-v1.db   one typed table per schema_v1 TSV
                               + entity_bridge (when emitted)
                               + a `meta` pins table
                               + the canonical join views

The TSVs remain the model of record — this database is a derived,
regenerable dist artifact (gitignored, like the tarballs) for
consumers that want one attachable file instead of 24 imports: the
dual-source corpus-researcher agent today, an MCP server later (W4c).
Column types come from schema_v1 (int→INTEGER, float→REAL, everything
else TEXT; blank=NULL, matching the TSV null convention — booleans
stay Y/N text). The views encode the four code↔data join paths the
project README describes, including the global_root normalization
(`^DPT(` → `DPT`) needed to join files.tsv to routine-globals.tsv.

Gate: --check verifies the built db against the live tree — pin
(meta.content_hash ≡ release record ≡ live TSVs), per-table row
counts, and that every view still executes.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import content_hash
import schema_v1

PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXPORT_DIR = PROJECT_ROOT / "vista/export"
RECORD_JSON = PROJECT_ROOT / "docs/releases/data-v1.manifest.json"
OUT_DB = PROJECT_ROOT / "dist/vista-meta-data-v1.db"
BRIDGE_TSV = "bridge/entity-bridge.tsv"

BRIDGE_COLUMNS = (
    ("entity_id", "TEXT"), ("entity_type", "TEXT"),
    ("canonical_name", "TEXT"), ("mention_count", "INTEGER"),
    ("vista_tsv", "TEXT"), ("vista_key_column", "TEXT"),
    ("vista_key_value", "TEXT"), ("join_method", "TEXT"),
    ("join_confidence", "TEXT"),
)

_SQL_TYPES = {"int": "INTEGER", "float": "REAL"}

# `^DPT(` / `^%ZOSF(` / `^DIC` → the bare token routine-globals uses.
_GLOBAL_KEY = ("CASE WHEN instr(ltrim(f.global_root,'^'),'(') > 0 "
               "THEN substr(ltrim(f.global_root,'^'),1,"
               "instr(ltrim(f.global_root,'^'),'(')-1) "
               "ELSE ltrim(f.global_root,'^') END")

VIEWS: dict[str, str] = {
    # RPC → implementing routine + its measured metrics
    "v_rpc_impl":
        "SELECT r.name AS rpc, r.tag, r.routine_name, rc.package,\n"
        "       rc.line_count, rc.in_degree, rc.out_degree\n"
        "FROM rpcs r\n"
        "LEFT JOIN routines_comprehensive rc USING (routine_name)",
    # Option → implementing routine
    "v_option_impl":
        "SELECT o.name AS option_name, o.menu_text, o.tag,\n"
        "       o.routine_name, rc.package\n"
        "FROM options o\n"
        "LEFT JOIN routines_comprehensive rc USING (routine_name)",
    # FileMan file keyed by its bare global token, with PIKS
    "v_global_file_piks":
        f"SELECT f.file_number, f.file_name, {_GLOBAL_KEY} AS global_key,\n"
        "       p.piks, p.piks_confidence, p.piks_source\n"
        "FROM files f JOIN piks p USING (file_number)\n"
        "WHERE f.global_root IS NOT NULL AND f.global_root != ''",
    # Join path 1: routine → global → FileMan file → PIKS
    "v_routine_global_piks":
        "SELECT rg.routine_name, rg.package, rg.global_name,\n"
        "       rg.ref_count, g.file_number, g.file_name, g.piks\n"
        "FROM routine_globals rg\n"
        "JOIN v_global_file_piks g ON g.global_key = rg.global_name",
    # Join path 3 (transitive): RPC → routine → global → PIKS
    "v_rpc_data_piks":
        "SELECT r.name AS rpc, r.routine_name, t.global_name,\n"
        "       t.file_number, t.file_name, t.piks\n"
        "FROM rpcs r JOIN v_routine_global_piks t USING (routine_name)",
    # Join path 2: package → namespace/app_code + PIKS distribution
    "v_package_overview":
        "SELECT p.package, n.namespace, n.prefixes, n.app_code, n.vdl_id,\n"
        "       p.routine_count, p.total_lines, s.p_files, s.i_files,\n"
        "       s.k_files, s.s_files\n"
        "FROM packages p\n"
        "LEFT JOIN package_namespace n USING (package)\n"
        "LEFT JOIN package_piks_summary s USING (package)",
}

INDEXES = (
    "CREATE INDEX idx_routine_calls_callee ON routine_calls "
    "(callee_routine)",
    "CREATE INDEX idx_routine_globals_global ON routine_globals "
    "(global_name)",
    "CREATE INDEX idx_rpcs_name ON rpcs (name)",
    "CREATE INDEX idx_options_name ON options (name)",
    "CREATE INDEX idx_bridge_key ON entity_bridge (vista_key_value)",
)


def table_name(tsv_name: str) -> str:
    return tsv_name[:-4].replace("-", "_").replace(".", "_")


def _create_sql(spec: schema_v1.FileSpec) -> str:
    cols = ", ".join(
        f'"{c}" {_SQL_TYPES.get(spec.effective_type(c), "TEXT")}'
        for c in spec.columns)
    pk = f', PRIMARY KEY ({", ".join(spec.pk)})' if spec.pk else ""
    return f"CREATE TABLE {table_name(spec.name)} ({cols}{pk})"


def _typed(spec: schema_v1.FileSpec, col: str, value: str):
    if value == "":
        return None
    t = spec.effective_type(col)
    if t == "int":
        return int(value)
    if t == "float":
        return float(value)
    return value


def _tsv_rows(path: Path) -> list[list[str]]:
    lines = path.read_text(encoding="utf-8").split("\n")
    return [ln.split("\t") for ln in lines[1:] if ln]


def _load_bridge(con: sqlite3.Connection, export_dir: Path) -> None:
    cols = ", ".join(f'"{c}" {t}' for c, t in BRIDGE_COLUMNS)
    con.execute(f"CREATE TABLE entity_bridge ({cols}, "
                "PRIMARY KEY (entity_id))")
    path = export_dir / BRIDGE_TSV
    if not path.exists():
        return
    rows = [[None if v == "" else (int(v) if c == "mention_count" else v)
             for (c, _), v in zip(BRIDGE_COLUMNS, r)]
            for r in _tsv_rows(path)]
    con.executemany(
        f"INSERT INTO entity_bridge VALUES "
        f"({','.join('?' * len(BRIDGE_COLUMNS))})", rows)


def build(export_dir: Path, out_path: Path, record: dict) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.unlink(missing_ok=True)
    con = sqlite3.connect(out_path)
    try:
        for name, spec in sorted(schema_v1.FILES.items()):
            con.execute(_create_sql(spec))
            rows = [[_typed(spec, c, v)
                     for c, v in zip(spec.columns, r)]
                    for r in _tsv_rows(export_dir / spec.model / name)]
            con.executemany(
                f"INSERT INTO {table_name(name)} VALUES "
                f"({','.join('?' * len(spec.columns))})", rows)
        _load_bridge(con, export_dir)
        con.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT)")
        con.executemany("INSERT INTO meta VALUES (?, ?)", [
            ("artifact", "vista-meta-meta-db"),
            ("tag", record["tag"]),
            ("schema_version", str(record["schema_version"])),
            ("content_hash", record["content_hash"]),
            ("db_state_fingerprint", record["db_state_fingerprint"]),
            ("extraction_timestamp", record["extraction_timestamp"]),
            ("generated_by", "host/scripts/build_meta_db.py"),
            ("canonical_format",
             "TSV (this database is a generated projection)"),
        ])
        for name, body in VIEWS.items():
            con.execute(f"CREATE VIEW {name} AS\n{body}")
        for idx in INDEXES:
            con.execute(idx)
        con.commit()
    finally:
        con.close()


def check(export_dir: Path, db_path: Path, record: dict) -> list[str]:
    if not db_path.exists():
        return [f"{db_path.name}: missing — run 'make meta-db'"]
    errors = []
    live = content_hash.compute(export_dir)
    if live != record["content_hash"]:
        errors.append(f"content_hash drift: live {live[:16]}… != record "
                      f"{record['content_hash'][:16]}…")
    con = sqlite3.connect(db_path)
    try:
        meta = dict(con.execute("SELECT key, value FROM meta").fetchall())
        if meta.get("content_hash") != record["content_hash"]:
            errors.append("pin mismatch: db meta content_hash != release "
                          "record — rebuild ('make meta-db')")
        for name, spec in sorted(schema_v1.FILES.items()):
            want = len(_tsv_rows(export_dir / spec.model / name))
            got = con.execute(
                f"SELECT COUNT(*) FROM {table_name(name)}").fetchone()[0]
            if got != want:
                errors.append(f"row count mismatch ({table_name(name)}): "
                              f"db {got} != tsv {want}")
        bridge_path = export_dir / BRIDGE_TSV
        if bridge_path.exists():
            want = len(_tsv_rows(bridge_path))
            got = con.execute(
                "SELECT COUNT(*) FROM entity_bridge").fetchone()[0]
            if got != want:
                errors.append(f"row count mismatch (entity_bridge): "
                              f"db {got} != tsv {want}")
        for view in VIEWS:
            try:
                con.execute(f"SELECT COUNT(*) FROM {view}")
            except sqlite3.Error as e:
                errors.append(f"view {view} broken: {e}")
    finally:
        con.close()
    return errors


def main(argv: list[str]) -> int:
    record = json.loads(RECORD_JSON.read_text(encoding="utf-8"))
    if argv == ["--check"]:
        errors = check(EXPORT_DIR, OUT_DB, record)
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        print("meta-db check: " + ("FAIL" if errors else
                                   f"PASS (≡ TSVs, pinned {record['tag']})"))
        return 1 if errors else 0
    build(EXPORT_DIR, OUT_DB, record)
    con = sqlite3.connect(OUT_DB)
    try:
        n_tables = con.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table'"
        ).fetchone()[0]
        n_rows = sum(
            con.execute(f"SELECT COUNT(*) FROM {table_name(n)}").fetchone()[0]
            for n in schema_v1.FILES)
    finally:
        con.close()
    print(f"{OUT_DB.relative_to(PROJECT_ROOT)}: {n_tables} tables "
          f"({n_rows:,} rows) + {len(VIEWS)} views, pinned to "
          f"{record['tag']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
