#!/usr/bin/env python3
"""TDD for mcp_server.py — machine-friendly-exports W4c.

A stdlib-only MCP stdio server over the meta.db projection: JSON-RPC
2.0, newline-delimited, tools = query (read-only SQL) / lookup /
bridge / orientation. Every lookup answer carries the release-pinned
citation; SQL is SELECT/WITH-only against a read-only connection.

Run: python3 host/scripts/tests/test_mcp_server.py
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(SCRIPTS_DIR / "tests"))

import build_meta_db as bmd  # noqa: E402
import mcp_server as srv  # noqa: E402
from test_build_meta_db import make_record, make_tree  # noqa: E402


def _fixture_handler():
    root = make_tree()
    db = root / "meta.db"
    bmd.build(root, db, make_record(root))
    return srv.Handler(db)


def req(handler, method, params=None, id=1):
    msg = {"jsonrpc": "2.0", "method": method, "id": id}
    if params is not None:
        msg["params"] = params
    return handler.handle(msg)


def call_tool(handler, name, args):
    return req(handler, "tools/call", {"name": name, "arguments": args})


def tool_text(resp):
    return resp["result"]["content"][0]["text"]


class TestProtocol(unittest.TestCase):
    def setUp(self):
        self.h = _fixture_handler()

    def test_initialize(self):
        resp = req(self.h, "initialize",
                   {"protocolVersion": "2024-11-05", "capabilities": {},
                    "clientInfo": {"name": "t", "version": "0"}})
        r = resp["result"]
        self.assertEqual(r["protocolVersion"], srv.PROTOCOL_VERSION)
        self.assertIn("tools", r["capabilities"])
        self.assertEqual(r["serverInfo"]["name"], "vista-meta")

    def test_initialized_notification_gets_no_response(self):
        self.assertIsNone(self.h.handle(
            {"jsonrpc": "2.0", "method": "notifications/initialized"}))

    def test_ping(self):
        self.assertEqual(req(self.h, "ping")["result"], {})

    def test_tools_list(self):
        tools = req(self.h, "tools/list")["result"]["tools"]
        names = {t["name"] for t in tools}
        self.assertEqual(names, {"query", "lookup", "bridge", "orientation"})
        for t in tools:
            self.assertIn("inputSchema", t)
            self.assertIn("description", t)

    def test_unknown_method_is_jsonrpc_error(self):
        resp = req(self.h, "resources/list")
        self.assertEqual(resp["error"]["code"], -32601)

    def test_unknown_notification_silently_ignored(self):
        self.assertIsNone(self.h.handle(
            {"jsonrpc": "2.0", "method": "notifications/cancelled"}))

    def test_unknown_tool_is_invalid_params(self):
        resp = call_tool(self.h, "nope", {})
        self.assertEqual(resp["error"]["code"], -32602)


class TestTools(unittest.TestCase):
    def setUp(self):
        self.h = _fixture_handler()

    def test_query_select_returns_rows(self):
        resp = call_tool(self.h, "query", {
            "sql": "SELECT rpc, routine_name FROM v_rpc_impl"})
        self.assertFalse(resp["result"]["isError"])
        rows = json.loads(tool_text(resp))
        self.assertEqual(rows["rows"],
                         [{"rpc": "ORWPT SELECT", "routine_name": "ORWPT"}])

    def test_query_rejects_non_select(self):
        resp = call_tool(self.h, "query", {"sql": "DELETE FROM rpcs"})
        self.assertTrue(resp["result"]["isError"])
        self.assertIn("SELECT", tool_text(resp))

    def test_query_write_blocked_by_readonly_connection(self):
        # even a sneaky statement that passes the prefix check cannot write
        resp = call_tool(self.h, "query", {
            "sql": "WITH x AS (SELECT 1) INSERT INTO rpcs SELECT * FROM x"})
        self.assertTrue(resp["result"]["isError"])

    def test_query_row_cap(self):
        resp = call_tool(self.h, "query", {
            "sql": "SELECT * FROM field_piks", "max_rows": 0})
        self.assertTrue(resp["result"]["isError"])
        resp = call_tool(self.h, "query", {
            "sql": "SELECT tag FROM xindex_tags", "max_rows": 1})
        self.assertEqual(len(json.loads(tool_text(resp))["rows"]), 1)

    def test_query_unknown_column_lists_the_tables_columns(self):
        # 15 of 112 query calls in 45 days failed on a guessed column name;
        # the error names the real ones so the retry needs no extra call.
        resp = call_tool(self.h, "query", {"sql": "SELECT rpc_name FROM rpcs"})
        self.assertTrue(resp["result"]["isError"])
        text = tool_text(resp)
        self.assertIn("no such column: rpc_name", text)
        self.assertIn("rpcs columns: ien, name, tag, routine_name,", text)

    def test_query_unknown_column_lists_every_joined_table(self):
        resp = call_tool(self.h, "query", {
            "sql": "SELECT r.nope FROM rpcs r "
                   "JOIN routines t ON r.routine_name = t.name"})
        text = tool_text(resp)
        self.assertLess(text.index("rpcs columns:"),
                        text.index("routines columns:"))
        self.assertNotIn("files columns:", text)

    def test_lookup_rpc_carries_citation(self):
        resp = call_tool(self.h, "lookup",
                         {"kind": "rpc", "key": "ORWPT SELECT"})
        text = tool_text(resp)
        self.assertIn("ORWPT", text)
        self.assertIn("vista-meta data-v1 · code-model/rpcs.tsv · "
                      "name=ORWPT SELECT", text)

    def test_lookup_file_includes_piks(self):
        text = tool_text(call_tool(self.h, "lookup",
                                   {"kind": "file", "key": "2"}))
        self.assertIn("PATIENT", text)
        self.assertIn('"piks": "P"', text)

    def test_lookup_miss_says_not_measured(self):
        text = tool_text(call_tool(self.h, "lookup",
                                   {"kind": "routine", "key": "ZZNOPE"}))
        self.assertIn("not measured in vista-meta data-v1", text)

    def test_lookup_bad_kind_is_error(self):
        resp = call_tool(self.h, "lookup", {"kind": "widget", "key": "x"})
        self.assertTrue(resp["result"]["isError"])

    def test_lookup_key_matches_in_any_case(self):
        # Measured 2026-11-09: `package "CLINICAL REMINDERS"` answered
        # "not measured" while the row exists as `Clinical Reminders`.
        text = tool_text(call_tool(self.h, "lookup",
                                   {"kind": "package", "key": "ORDER ENTRY"}))
        self.assertIn("package=Order Entry", text)
        text = tool_text(call_tool(self.h, "lookup",
                                   {"kind": "routine", "key": " orwpt "}))
        self.assertIn("routine_name=ORWPT", text)

    def test_lookup_without_a_key_is_an_input_error_not_a_miss(self):
        # Measured 2026-11-09: `{"kind": "routine", "name": "DGSEC"}` was
        # answered "not measured" — a malformed call stated as a fact.
        for args in ({"kind": "routine", "name": "DGSEC"},
                     {"kind": "routine"},
                     {"kind": "routine", "key": "  "}):
            resp = call_tool(self.h, "lookup", args)
            self.assertTrue(resp["result"]["isError"], args)
            self.assertNotIn("not measured", tool_text(resp))

    def test_undeclared_argument_is_named_with_the_declared_ones(self):
        resp = call_tool(self.h, "lookup",
                         {"kind": "routine", "name": "DGSEC"})
        text = tool_text(resp)
        self.assertIn("'name'", text)
        self.assertIn("kind, key", text)
        resp = call_tool(self.h, "query",
                         {"sql": "SELECT 1", "limit": 5})
        self.assertTrue(resp["result"]["isError"])
        self.assertIn("'limit'", tool_text(resp))

    def test_missing_required_argument_is_named(self):
        resp = call_tool(self.h, "query", {})
        self.assertTrue(resp["result"]["isError"])
        self.assertIn("needs sql", tool_text(resp))

    def test_arguments_must_be_an_object(self):
        resp = req(self.h, "tools/call",
                   {"name": "lookup", "arguments": ["routine", "ORWPT"]})
        self.assertTrue(resp["result"]["isError"])

    def test_bridge_lookup(self):
        text = tool_text(call_tool(self.h, "bridge",
                                   {"entity_id": "rpc:ORWPT SELECT"}))
        self.assertIn("exact-name-ci", text)
        self.assertIn("ORWPT SELECT", text)

    def test_orientation_carries_pin_and_surface(self):
        text = tool_text(call_tool(self.h, "orientation", {}))
        self.assertIn(self.h.meta["content_hash"], text)
        self.assertIn("v_rpc_data_piks", text)
        self.assertIn("entity_bridge", text)
        self.assertIn("not measured in vista-meta data-v1", text)

    def test_orientation_lists_every_relations_columns(self):
        # Measured 2026-11-09: 15 of 113 query calls failed on a guessed
        # column; the columns belong where the first query is written.
        text = tool_text(call_tool(self.h, "orientation", {}))
        self.assertIn("rpcs: ien, name, tag, routine_name,", text)
        self.assertIn("v_rpc_impl: rpc,", text)
        relations = [n for (n,) in self.h.con.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table','view')")]
        for rel in relations:
            self.assertIn(f"\n  {rel}: ", text, rel)

    def test_orientation_cross_points_to_the_vdocs_peer(self):
        text = tool_text(call_tool(self.h, "orientation", {}))
        self.assertIn("vdocs serve-mcp", text)
        self.assertIn("documented:", text)
        self.assertIn("measured:", text)


class TestStdioFraming(unittest.TestCase):
    def test_serve_lines_roundtrip(self):
        h = _fixture_handler()
        lines = [
            json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                        "params": {"protocolVersion": "2024-11-05"}}),
            json.dumps({"jsonrpc": "2.0",
                        "method": "notifications/initialized"}),
            "not json at all",
            json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}),
        ]
        out = list(srv.serve_lines(h, iter(lines)))
        replies = [json.loads(o) for o in out]
        ids = [r.get("id") for r in replies]
        self.assertIn(1, ids)
        self.assertIn(2, ids)
        # malformed line → parse error, id null, loop survives
        self.assertTrue(any(r.get("error", {}).get("code") == -32700
                            for r in replies))


if __name__ == "__main__":
    unittest.main()
