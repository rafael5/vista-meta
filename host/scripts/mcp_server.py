#!/usr/bin/env python3
# W4c of the machine-friendly-exports umbrella: the MCP front door.
# Plan: docs/historical/machine-friendly-exports.md

"""MCP stdio server over the meta.db projection — stdlib only.

Speaks MCP's stdio transport (newline-delimited JSON-RPC 2.0):
`initialize` / `tools/list` / `tools/call`, four tools:

  query        read-only SQL (SELECT/WITH only) over the 26 tables +
               6 join views, row-capped
  lookup       keyed lookup (rpc / option / routine / file / package /
               global) with the release-pinned citation line
  bridge       vdocs entity_id → its vista-meta row (the W3 bridge)
  orientation  provenance pins + query surface + citation contract

The database is the generated dist projection (`make meta-db`); on
startup the server builds/rebuilds it when missing or stale, so
`python3 host/scripts/mcp_server.py` is self-sufficient. The
connection is read-only (`mode=ro`) — the SELECT/WITH prefix check is
UX, the read-only mode is the guarantee. Wire into a harness via the
repo's `.mcp.json`.
"""

from __future__ import annotations

import json
import re
import sqlite3
import sys
from pathlib import Path

import build_meta_db

PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "vista-meta", "version": "1.0.0"}

MAX_ROWS_CEILING = 500
DEFAULT_MAX_ROWS = 50

_SELECT_ONLY = re.compile(r"^\s*(select|with)\b", re.IGNORECASE)

# kind → (queryable relation, key column, citable TSV, citation key column)
LOOKUP_KINDS = {
    "rpc": ("rpcs", "name", "code-model/rpcs.tsv", "name"),
    "option": ("options", "name", "code-model/options.tsv", "name"),
    "routine": ("routines_comprehensive", "routine_name",
                "code-model/routines-comprehensive.tsv", "routine_name"),
    "file": ("files", "file_number", "data-model/files.tsv",
             "file_number"),
    "package": ("v_package_overview", "package", "code-model/packages.tsv",
                "package"),
    "global": ("v_global_file_piks", "global_key", "data-model/files.tsv",
               "file_number"),
}

TOOLS = [
    {
        "name": "query",
        "description":
            "Read-only SQL (SELECT/WITH only) over the vista-meta measured "
            "model: 24 schema_v1 tables (rpcs, options, routines, files, "
            "piks, routine_calls, routine_globals, packages, xindex_*, …), "
            "entity_bridge, and join views v_rpc_impl / v_option_impl / "
            "v_global_file_piks / v_routine_global_piks / v_rpc_data_piks / "
            "v_package_overview. Call `orientation` first if unsure.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "sql": {"type": "string",
                        "description": "A single SELECT/WITH statement"},
                "max_rows": {"type": "integer", "minimum": 1,
                             "maximum": MAX_ROWS_CEILING,
                             "description": f"Row cap (default "
                                            f"{DEFAULT_MAX_ROWS})"},
            },
            "required": ["sql"],
        },
    },
    {
        "name": "lookup",
        "description":
            "Keyed lookup with a release-pinned citation. kind: rpc | "
            "option | routine | file (FileMan number, incl. PIKS) | "
            "package | global (bare name, e.g. DPT).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "kind": {"type": "string",
                         "enum": sorted(LOOKUP_KINDS)},
                "key": {"type": "string"},
            },
            "required": ["kind", "key"],
        },
    },
    {
        "name": "bridge",
        "description":
            "Map a vdocs data-v1 entity onto its vista-meta row via the "
            "generated entity bridge. Pass entity_id "
            "('<type>:<canonical_name>', e.g. 'rpc:ORWPT SELECT') or name "
            "(+ optional type). join_confidence 'undetermined' means no "
            "measured counterpart — report it, don't treat it as an error.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "entity_id": {"type": "string"},
                "name": {"type": "string"},
                "type": {"type": "string"},
            },
        },
    },
    {
        "name": "orientation",
        "description":
            "The front door: release provenance pins, the queryable "
            "tables/views, and the citation contract. Call once per "
            "session before querying.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


class ToolError(Exception):
    """Tool-execution failure — returned as isError content, not a
    JSON-RPC error (the call itself was well-formed)."""


def _rows_to_dicts(cursor, rows) -> list[dict]:
    cols = [d[0] for d in cursor.description]
    return [dict(zip(cols, r)) for r in rows]


class Handler:
    def __init__(self, db_path: Path):
        self.con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        self.meta = dict(self.con.execute(
            "SELECT key, value FROM meta").fetchall())
        self.tag = self.meta.get("tag", "data-v1")

    # ── tools ─────────────────────────────────────────────────────
    def tool_query(self, args: dict) -> str:
        sql = args.get("sql", "")
        max_rows = args.get("max_rows", DEFAULT_MAX_ROWS)
        if (not isinstance(max_rows, int)
                or not 1 <= max_rows <= MAX_ROWS_CEILING):
            raise ToolError(f"max_rows must be 1..{MAX_ROWS_CEILING}")
        if not _SELECT_ONLY.match(sql):
            raise ToolError("only a single SELECT/WITH statement is "
                            "allowed (the connection is read-only)")
        try:
            cur = self.con.execute(sql)
            rows = cur.fetchmany(max_rows + 1)
        except sqlite3.Error as e:
            raise ToolError(f"sqlite: {e}") from e
        truncated = len(rows) > max_rows
        rows = rows[:max_rows]
        return json.dumps({
            "columns": [d[0] for d in cur.description],
            "rows": _rows_to_dicts(cur, rows),
            "row_count": len(rows),
            "truncated": truncated,
            "release": self.tag,
        }, indent=1, ensure_ascii=False)

    def tool_lookup(self, args: dict) -> str:
        kind, key = args.get("kind", ""), args.get("key", "")
        if kind not in LOOKUP_KINDS:
            raise ToolError(f"kind must be one of {sorted(LOOKUP_KINDS)}")
        relation, column, tsv, cite_col = LOOKUP_KINDS[kind]
        if kind == "file":
            sql = ("SELECT f.*, p.piks, p.piks_confidence, p.piks_source "
                   "FROM files f LEFT JOIN piks p USING (file_number) "
                   "WHERE f.file_number = ?")
        else:
            sql = f"SELECT * FROM {relation} WHERE {column} = ?"
        cur = self.con.execute(sql, (key,))
        rows = _rows_to_dicts(cur, cur.fetchmany(MAX_ROWS_CEILING))
        if not rows:
            return (f"not measured in vista-meta {self.tag} "
                    f"({kind} {column}={key!r}) — report this as the "
                    "answer; do not substitute general knowledge.")
        cite_val = rows[0].get(cite_col, key)
        citation = (f"vista-meta {self.tag} · {tsv} · "
                    f"{cite_col}={cite_val}")
        return json.dumps({"rows": rows, "citation": citation}, indent=1, ensure_ascii=False)

    def tool_bridge(self, args: dict) -> str:
        if args.get("entity_id"):
            cur = self.con.execute(
                "SELECT * FROM entity_bridge WHERE entity_id = ?",
                (args["entity_id"],))
        elif args.get("name"):
            sql = "SELECT * FROM entity_bridge WHERE canonical_name = ?"
            params = [args["name"]]
            if args.get("type"):
                sql += " AND entity_type = ?"
                params.append(args["type"])
            cur = self.con.execute(sql, params)
        else:
            raise ToolError("pass entity_id, or name (+ optional type)")
        rows = _rows_to_dicts(cur, cur.fetchmany(MAX_ROWS_CEILING))
        if not rows:
            return ("no such entity in the vdocs data-v1 index "
                    "(the bridge covers every vdocs entity — an absent "
                    "row means the entity_id/name is wrong)")
        return json.dumps({"rows": rows}, indent=1, ensure_ascii=False)

    def tool_orientation(self, args: dict) -> str:
        kinds = dict(self.con.execute(
            "SELECT name, type FROM sqlite_master "
            "WHERE type IN ('table','view') ORDER BY name").fetchall())
        tables = sorted(n for n, t in kinds.items() if t == "table")
        views = sorted(n for n, t in kinds.items() if t == "view")
        return (
            f"vista-meta — the measured model of VistA "
            f"(release {self.tag}, schema_version "
            f"{self.meta.get('schema_version')})\n\n"
            f"Provenance pins (state in answers):\n"
            f"  content_hash: {self.meta.get('content_hash')}\n"
            f"  db_state_fingerprint: "
            f"{self.meta.get('db_state_fingerprint')}\n"
            f"  extracted: {self.meta.get('extraction_timestamp')}\n"
            f"  canonical format: {self.meta.get('canonical_format')}\n\n"
            f"Tables: {', '.join(tables)}\n\n"
            f"Join views: {', '.join(views)}\n\n"
            "Citation contract — cite every measured claim as:\n"
            f"  vista-meta {self.tag} · <tsv path> · <key>=<value>\n"
            "(the `lookup` tool returns this line ready-made). If no row "
            "answers the question, the correct answer is \"not measured "
            f"in vista-meta {self.tag}\" — say so and stop.\n\n"
            "Full orientation card: vista/export/AI-CARD.md; per-TSV "
            "catalog: vista/export/ai-manifest.json."
        )

    # ── JSON-RPC routing ──────────────────────────────────────────
    def _call_tool(self, msg_id, params: dict) -> dict:
        name = params.get("name", "")
        tool = {"query": self.tool_query, "lookup": self.tool_lookup,
                "bridge": self.tool_bridge,
                "orientation": self.tool_orientation}.get(name)
        if tool is None:
            return _error(msg_id, -32602, f"unknown tool {name!r}")
        try:
            text = tool(params.get("arguments") or {})
            is_error = False
        except ToolError as e:
            text, is_error = str(e), True
        return _result(msg_id, {
            "content": [{"type": "text", "text": text}],
            "isError": is_error,
        })

    def handle(self, msg: dict) -> dict | None:
        method = msg.get("method", "")
        msg_id = msg.get("id")
        is_notification = "id" not in msg
        if method == "initialize":
            return _result(msg_id, {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": SERVER_INFO,
                "instructions":
                    "Measured VistA facts only — call `orientation` first, "
                    "cite every claim, and answer \"not measured\" when no "
                    "row matches.",
            })
        if method == "ping":
            return _result(msg_id, {})
        if method == "tools/list":
            return _result(msg_id, {"tools": TOOLS})
        if method == "tools/call":
            return self._call_tool(msg_id, msg.get("params") or {})
        if is_notification:
            return None  # notifications/* — nothing to say
        return _error(msg_id, -32601, f"method {method!r} not supported")


def _result(msg_id, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


def _error(msg_id, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": msg_id,
            "error": {"code": code, "message": message}}


def serve_lines(handler: Handler, lines) -> "iter[str]":
    """Transport-agnostic loop: JSON lines in → JSON lines out."""
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError as e:
            yield json.dumps(_error(None, -32700, f"parse error: {e}"))
            continue
        resp = handler.handle(msg)
        if resp is not None:
            yield json.dumps(resp)


def ensure_db() -> Path:
    """Build (or rebuild) the projection when missing or stale — the
    server must be startable from a fresh clone with one command."""
    record = json.loads(
        build_meta_db.RECORD_JSON.read_text(encoding="utf-8"))
    db = build_meta_db.OUT_DB
    if not db.exists() or build_meta_db.check(
            build_meta_db.EXPORT_DIR, db, record):
        print(f"mcp_server: (re)building {db.name} …", file=sys.stderr)
        build_meta_db.build(build_meta_db.EXPORT_DIR, db, record)
    return db


def main() -> int:
    handler = Handler(ensure_db())
    for out in serve_lines(handler, sys.stdin):
        print(out, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
