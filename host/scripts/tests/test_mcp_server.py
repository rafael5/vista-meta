#!/usr/bin/env python3
"""TDD for mcp_server.py — machine-friendly-exports W4c.

A stdlib-only MCP stdio server over the meta.db projection: JSON-RPC
2.0, newline-delimited, tools = query (read-only SQL) / lookup /
bridge / orientation / routine_card / package_card / listing. Every lookup answer carries the release-pinned
citation; SQL is SELECT/WITH-only against a read-only connection.

Run: python3 host/scripts/tests/test_mcp_server.py
"""

from __future__ import annotations

import json
import sys
import tempfile
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
        self.assertEqual(names, {"query", "lookup", "bridge", "orientation",
                                 "routine_card", "package_card", "listing"})
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


# ── routine card / package card / listing ────────────────────────────
# A small world: ORWPT (Order Entry) is called by DGREG (Registration)
# and ORQQ (Order Entry); XLFDT (Kernel) is called by 60 routines across
# 30 packages so the card has to bound itself.

_ZZ_CALLERS = [
    {"caller_routine": f"ZZ{i:03d}", "caller_package": f"Pkg {i % 30:02d}",
     "callee_tag": "FMTE", "callee_routine": "XLFDT", "kind": "func",
     "ref_count": str(i + 1)}
    for i in range(60)]

CARD_ROWS = {
    "routines-comprehensive.tsv": [
        {"routine_name": "ORQQ", "package": "Order Entry",
         "source_path": "/opt/VistA-M/Packages/Order Entry/Routines/ORQQ.m"},
        {"routine_name": "XLFDT", "package": "Kernel",
         "source_path": "/opt/VistA-M/Packages/Kernel/Routines/XLFDT.m"},
        {"routine_name": "DGREG", "package": "Registration",
         "source_path": "/opt/VistA-M/Packages/Registration/Routines/"
                        "DGREG.m"},
        {"routine_name": "%DT", "package": "VA FileMan",
         "source_path": "/opt/VistA-M/o/_DT.m"},
    ],
    "packages.tsv": [{"package": "Kernel"}, {"package": "Registration"}],
    "package-namespace.tsv": [
        {"package": "Kernel", "package_name": "KERNEL", "namespace": "XU",
         "prefixes": "XU,XLF,!XLFZ"},
        {"package": "Registration", "package_name": "REGISTRATION",
         "namespace": "DG", "prefixes": "DG"},
    ],
    "routine-calls.tsv": [
        {"caller_routine": "DGREG", "caller_package": "Registration",
         "callee_tag": "SELECT", "callee_routine": "ORWPT", "kind": "do",
         "ref_count": "2"},
        {"caller_routine": "DGREG", "caller_package": "Registration",
         "callee_tag": "NOW", "callee_routine": "XLFDT", "kind": "func",
         "ref_count": "3"},
        {"caller_routine": "ORQQ", "caller_package": "Order Entry",
         "callee_tag": "SELECT", "callee_routine": "ORWPT", "kind": "do",
         "ref_count": "1"},
        {"caller_routine": "ORQQ", "caller_package": "Order Entry",
         "callee_tag": "LIST", "callee_routine": "ORWPT", "kind": "do",
         "ref_count": "1"},
        {"caller_routine": "ORWPT", "caller_package": "Order Entry",
         "callee_tag": "NOW", "callee_routine": "XLFDT", "kind": "func",
         "ref_count": "1"},
        {"caller_routine": "ORWPT", "caller_package": "Order Entry",
         "callee_tag": "", "callee_routine": "DIC", "kind": "do",
         "ref_count": "4"},
    ] + _ZZ_CALLERS,
    "rpcs.tsv": [
        {"ien": "2", "name": "ORWPT LIST", "tag": "LIST",
         "routine_name": "ORWPT"},
        {"ien": "3", "name": "XUS SIGNON", "tag": "SIGN",
         "routine_name": "XUSRB", "package": "KERNEL",
         "package_dir": "Kernel"},
    ],
    "options.tsv": [
        {"ien": "2", "name": "ORWPT MENU", "menu_text": "Patient menu",
         "tag": "SELECT", "routine_name": "ORWPT",
         "package_dir": "Order Entry"},
    ],
    "protocols.tsv": [
        {"ien": "2", "name": "ORWPT EVENT", "item_text": "Patient event",
         "package": "ORDER ENTRY", "package_dir": "Order Entry"},
    ],
    "protocol-calls.tsv": [
        {"protocol_name": "ORWPT EVENT", "action_kind": "entry",
         "callee_tag": "SELECT", "callee_routine": "ORWPT",
         "call_kind": "do", "ref_count": "1"},
        {"protocol_name": "ORWPT OTHER", "action_kind": "entry",
         "callee_tag": "LIST", "callee_routine": "ORWPT",
         "call_kind": "do", "ref_count": "1"},
    ],
    "xindex-tags.tsv": [
        {"routine_name": "ORWPT", "tag": "ORWPT"},
        {"routine_name": "ORWPT", "tag": "SELECT"},
        {"routine_name": "ORWPT", "tag": "LIST"},
    ],
    "field-piks.tsv": [
        {"file_number": "2", "field_number": ".02", "field_name": "SEX"},
        {"file_number": "2", "field_number": ".01", "field_name": "NAME"},
        {"file_number": "2", "field_number": ".1", "field_name": "WARD"},
        {"file_number": "52", "field_number": ".01", "field_name": "RX #"},
    ],
}

ORWPT_M = """\
ORWPT ;SLC/KCM - Patient selection ;05/01/2020
 ;;3.0;ORDER ENTRY/RESULTS REPORTING;**1**;Dec 17, 1997;Build 5
 Q
 ;
SELECT(ORY,DFN) ;Select a patient
 ; Returns the patient's demographics in ORY.
 ; DFN: patient IEN
 N X
 S X=$$NOW^XLFDT
 S ORY=$P(^DPT(DFN,0),U)
 Q
 ;
LIST(ORY) ; list patients
 D ^DIC
 Q
"""


def _source_tree() -> Path:
    root = Path(tempfile.mkdtemp())
    d = root / "Packages/Order Entry/Routines"
    d.mkdir(parents=True)
    (d / "ORWPT.m").write_text(ORWPT_M, encoding="utf-8")
    (root / "PercentRoutines").mkdir()
    (root / "PercentRoutines/_DT.m").write_text(
        "%DT ;SFISC/GFT-DATE/TIME UTILITY\n ;;22.2;VA FileMan\n Q\n",
        encoding="utf-8")
    return root


def _card_handler(source_root=None):
    root = make_tree(extra_rows=CARD_ROWS)
    with (root / "bridge/entity-bridge.tsv").open("a") as f:
        f.write("routine:ORWPT\troutine\tORWPT\t12\t"
                "code-model/routines.tsv\troutine_name\tORWPT\t"
                "exact-name-ci\thigh\n")
    db = root / "meta.db"
    bmd.build(root, db, make_record(root))
    return srv.Handler(db, source_root=source_root or _source_tree())


def card(handler, name, args):
    resp = call_tool(handler, name, args)
    return resp, tool_text(resp)


class TestRoutineCard(unittest.TestCase):
    def setUp(self):
        self.h = _card_handler()

    def routine(self, name):
        resp, text = card(self.h, "routine_card", {"name": name})
        self.assertFalse(resp["result"]["isError"], text)
        return json.loads(text), text

    def test_routine_card_carries_every_part_with_its_citation(self):
        c, _ = self.routine("ORWPT")
        cite = "vista-meta data-v1 · code-model/"
        self.assertEqual(c["routine"]["citation"],
                         cite + "routines-comprehensive.tsv · "
                                "routine_name=ORWPT")
        self.assertEqual(c["routine"]["row"]["package"], "Order Entry")
        self.assertEqual(c["callers"]["citation"],
                         cite + "routine-calls.tsv · callee_routine=ORWPT")
        self.assertEqual(c["callees"]["citation"],
                         cite + "routine-calls.tsv · caller_routine=ORWPT")
        self.assertEqual(c["globals"]["citation"],
                         cite + "routine-globals.tsv · routine_name=ORWPT")
        self.assertEqual(c["rpcs"]["citation"],
                         cite + "rpcs.tsv · routine_name=ORWPT")
        self.assertEqual(c["options"]["citation"],
                         cite + "options.tsv · routine_name=ORWPT")
        self.assertEqual(c["protocols"]["citation"],
                         cite + "protocol-calls.tsv · callee_routine=ORWPT")
        self.assertEqual(c["documented"]["citation"],
                         "vista-meta data-v1 · bridge/entity-bridge.tsv · "
                         "entity_id=routine:ORWPT")

    def test_routine_card_rows(self):
        c, _ = self.routine("ORWPT")
        callers = {(r["caller_routine"], r["caller_package"], r["callee_tag"],
                    r["ref_count"]) for r in c["callers"]["rows"]}
        self.assertEqual(callers, {("DGREG", "Registration", "SELECT", 2),
                                   ("ORQQ", "Order Entry", "SELECT", 1),
                                   ("ORQQ", "Order Entry", "LIST", 1)})
        self.assertEqual(c["callers"]["count"], 3)
        callees = {(r["callee_tag"], r["callee_routine"])
                   for r in c["callees"]["rows"]}
        self.assertEqual(callees, {("NOW", "XLFDT"), (None, "DIC")})
        self.assertEqual([r["global_name"] for r in c["globals"]["rows"]],
                         ["DPT"])
        self.assertEqual(sorted(r["name"] for r in c["rpcs"]["rows"]),
                         ["ORWPT LIST", "ORWPT SELECT"])
        self.assertIn("ORWPT MENU",
                      [r["name"] for r in c["options"]["rows"]])
        self.assertEqual(sorted(r["protocol_name"]
                                for r in c["protocols"]["rows"]),
                         ["ORWPT EVENT", "ORWPT OTHER"])
        self.assertEqual(c["documented"]["rows"][0]["join_confidence"],
                         "high")

    def test_routine_card_lists_tags_with_line_numbers(self):
        c, _ = self.routine("ORWPT")
        tags = [(t["tag"], t["line"]) for t in c["source"]["tags"]]
        self.assertEqual(tags, [("ORWPT", 1), ("SELECT", 5), ("LIST", 13)])
        self.assertEqual(c["source"]["tags"][1]["formal_parameters"],
                         ["ORY", "DFN"])
        self.assertEqual(c["source"]["path"],
                         "Packages/Order Entry/Routines/ORWPT.m")
        self.assertEqual(c["source"]["lines"], "1-15")

    def test_tag_card_gives_the_tags_text_with_offsets(self):
        c, _ = self.routine("SELECT^ORWPT")
        src = c["source"]
        self.assertEqual(src["tag"], "SELECT")
        self.assertEqual(src["lines"], "5-12")
        self.assertEqual(src["formal_parameters"], ["ORY", "DFN"])
        self.assertEqual(src["opening_comments"], [
            "Select a patient",
            "Returns the patient's demographics in ORY.",
            "DFN: patient IEN"])
        self.assertEqual(src["text"][0],
                         "SELECT+0: SELECT(ORY,DFN) ;Select a patient")
        self.assertEqual(src["text"][4], "SELECT+4:  S X=$$NOW^XLFDT")
        self.assertEqual(len(src["text"]), 8)

    def test_tag_card_narrows_callers_and_bindings_to_the_tag(self):
        c, _ = self.routine("SELECT^ORWPT")
        self.assertEqual(c["callers"]["citation"],
                         "vista-meta data-v1 · code-model/routine-calls.tsv"
                         " · callee_routine=ORWPT, callee_tag=SELECT")
        self.assertEqual(sorted(r["caller_routine"]
                                for r in c["callers"]["rows"]),
                         ["DGREG", "ORQQ"])
        self.assertEqual([r["name"] for r in c["rpcs"]["rows"]],
                         ["ORWPT SELECT"])
        self.assertEqual([r["name"] for r in c["options"]["rows"]],
                         ["ORWPT MENU"])
        self.assertEqual([r["protocol_name"] for r in c["protocols"]["rows"]],
                         ["ORWPT EVENT"])
        # what it calls and the globals are measured per routine, not tag
        self.assertIn("whole routine", c["callees"]["note"])
        self.assertIn("whole routine", c["globals"]["note"])

    def test_name_forms_match_in_any_case(self):
        c, _ = self.routine("$$select^orwpt")
        self.assertEqual(c["source"]["tag"], "SELECT")
        c, _ = self.routine("^orwpt")
        self.assertEqual(c["routine"]["row"]["routine_name"], "ORWPT")

    def test_call_sites_are_stated_unmeasured(self):
        c, _ = self.routine("ORWPT")
        self.assertIn("TAG+n call sites: not measured",
                      c["callers"]["note"])

    def test_percent_routine_maps_to_the_percent_tree(self):
        c, _ = self.routine("%DT")
        self.assertEqual(c["source"]["path"], "PercentRoutines/_DT.m")

    def test_absent_source_tree_still_returns_the_measured_parts(self):
        h = _card_handler(source_root=Path(tempfile.mkdtemp()) / "nope")
        resp, text = card(h, "routine_card", {"name": "SELECT^ORWPT"})
        self.assertFalse(resp["result"]["isError"])
        c = json.loads(text)
        self.assertIn("unavailable", c["source"]["text_unavailable"])
        self.assertIn("make sync-routines", c["source"]["text_unavailable"])
        self.assertEqual(len(c["callers"]["rows"]), 2)
        # tags still come from the measured xindex_tags
        self.assertIn("SELECT", c["source"]["measured_tags"])

    def test_routine_file_missing_from_tree_says_so(self):
        c, _ = self.routine("XLFDT")
        self.assertIn("not in the host tree",
                      c["source"]["text_unavailable"])

    def test_heavily_called_routine_is_bounded_and_says_what_it_cut(self):
        c, text = self.routine("XLFDT")
        callers = c["callers"]
        self.assertEqual(callers["count"], 62)
        self.assertEqual(len(callers["rows"]), srv.CAP_CALLERS)
        self.assertEqual(callers["calling_packages"], 32)
        self.assertIn("cut", callers)
        rest = callers["rest_by_package"]
        self.assertLessEqual(len(rest), srv.CAP_CALLER_PACKAGES)
        shown = sum(r["ref_count"] for r in callers["rows"])
        self.assertEqual(shown + sum(r["refs"] for r in rest)
                         + callers.get("rest_refs_unlisted", 0),
                         callers["refs"])
        # highest ref_count first
        self.assertEqual(callers["rows"][0]["caller_routine"], "ZZ059")
        by_tag = {r["callee_tag"]: r["rows"] for r in callers["by_tag"]}
        self.assertEqual(by_tag, {"FMTE": 60, "NOW": 2})

    def test_unknown_routine_or_tag_is_not_measured(self):
        resp, text = card(self.h, "routine_card", {"name": "ZZNOPE"})
        self.assertFalse(resp["result"]["isError"])
        self.assertIn("not measured in vista-meta data-v1", text)
        resp, text = card(self.h, "routine_card", {"name": "NOPE^ORWPT"})
        self.assertFalse(resp["result"]["isError"])
        self.assertIn("not measured", text)
        self.assertIn("SELECT", text)  # names the labels it does have

    def test_empty_name_is_an_input_error(self):
        for name in ("", "  ", "TAG^", "A^B^C"):
            resp, _ = card(self.h, "routine_card", {"name": name})
            self.assertTrue(resp["result"]["isError"], name)


class TestPackageCard(unittest.TestCase):
    def setUp(self):
        self.h = _card_handler()

    def package(self, name):
        resp, text = card(self.h, "package_card", {"name": name})
        self.assertFalse(resp["result"]["isError"], text)
        return json.loads(text), text

    def test_package_card_by_name_in_any_case(self):
        c, _ = self.package("order entry")
        self.assertEqual(c["package"]["citation"],
                         "vista-meta data-v1 · code-model/packages.tsv · "
                         "package=Order Entry")
        self.assertEqual(sorted(r["name"] for r in c["rpcs"]["rows"]),
                         ["ORWPT LIST", "ORWPT SELECT"])
        self.assertIn("ORWPT MENU",
                      [r["name"] for r in c["options"]["rows"]])
        self.assertEqual([r["name"] for r in c["protocols"]["rows"]],
                         ["ORWPT EVENT"])
        self.assertTrue(c["rpcs"]["citation"].startswith(
            "vista-meta data-v1 · code-model/rpcs.tsv · "))

    def test_entry_points_are_called_from_other_packages_only(self):
        c, _ = self.package("Order Entry")
        eps = c["entry_points"]
        self.assertEqual(eps["citation"],
                         "vista-meta data-v1 · code-model/routine-calls.tsv"
                         " · callee package=Order Entry")
        # SELECT^ORWPT is called from Registration; LIST^ORWPT only from
        # its own package, so it is not an interface
        self.assertEqual(eps["rows"], [{
            "entry_point": "SELECT^ORWPT", "calling_packages": 1,
            "caller_rows": 1, "refs": 2}])

    def test_package_by_namespace_or_prefix(self):
        c, _ = self.package("or")
        self.assertEqual(c["package"]["row"]["package"], "Order Entry")
        c, _ = self.package("XLF")
        self.assertEqual(c["package"]["row"]["package"], "Kernel")
        self.assertEqual(c["entry_points"]["rows"][0]["entry_point"],
                         "FMTE^XLFDT")
        self.assertEqual(c["entry_points"]["rows"][0]["calling_packages"],
                         30)
        self.assertEqual([r["name"] for r in c["rpcs"]["rows"]],
                         ["XUS SIGNON"])

    def test_a_cut_list_names_a_query_that_runs_as_written(self):
        import mcp_cards
        saved, mcp_cards.CAP_PACKAGE_LIST = mcp_cards.CAP_PACKAGE_LIST, 1
        try:
            c, _ = self.package("Order Entry")
        finally:
            mcp_cards.CAP_PACKAGE_LIST = saved
        cut = c["rpcs"]["cut"]
        self.assertIn("showing 1 of 2 rows", cut)
        where = cut.split("WHERE ", 1)[1]
        resp = call_tool(self.h, "query", {
            "sql": f"SELECT COUNT(*) AS n FROM rpcs WHERE {where}"})
        self.assertFalse(resp["result"]["isError"], tool_text(resp))
        self.assertEqual(json.loads(tool_text(resp))["rows"], [{"n": 2}])

    def test_excluded_prefix_and_unknown_are_not_measured(self):
        for name in ("XLFZ", "No Such Package"):
            resp, text = card(self.h, "package_card", {"name": name})
            self.assertFalse(resp["result"]["isError"])
            self.assertIn("not measured", text)


class TestListing(unittest.TestCase):
    def setUp(self):
        self.h = _card_handler()

    def listing(self, args):
        resp, text = card(self.h, "listing", args)
        self.assertFalse(resp["result"]["isError"], text)
        return json.loads(text)

    def test_rpcs_by_prefix_in_any_case(self):
        out = self.listing({"kind": "rpc", "key": "orwpt"})
        self.assertEqual([r["name"] for r in out["rows"]],
                         ["ORWPT LIST", "ORWPT SELECT"])
        self.assertEqual(out["count"], 2)
        self.assertEqual(out["citation"],
                         "vista-meta data-v1 · code-model/rpcs.tsv · "
                         "name=ORWPT*")

    def test_options_by_prefix(self):
        out = self.listing({"kind": "option", "key": "ORWPT"})
        self.assertEqual([r["name"] for r in out["rows"]], ["ORWPT MENU"])

    def test_fields_of_a_file_in_field_order(self):
        out = self.listing({"kind": "field", "key": "2"})
        self.assertEqual([r["field_number"] for r in out["rows"]],
                         [".01", ".02", ".1"])
        self.assertEqual(out["file_name"], "PATIENT")
        self.assertEqual(out["citation"],
                         "vista-meta data-v1 · data-model/field-piks.tsv · "
                         "file_number=2")

    def test_paging_and_truncation(self):
        out = self.listing({"kind": "field", "key": "2", "max_rows": 2})
        self.assertEqual(len(out["rows"]), 2)
        self.assertTrue(out["truncated"])
        self.assertEqual(out["count"], 3)
        out = self.listing({"kind": "field", "key": "2", "max_rows": 2,
                            "offset": 2})
        self.assertEqual([r["field_number"] for r in out["rows"]], [".1"])
        self.assertFalse(out["truncated"])

    def test_no_rows_is_not_measured_and_bad_input_is_an_error(self):
        resp, text = card(self.h, "listing", {"kind": "rpc", "key": "ZZQ"})
        self.assertFalse(resp["result"]["isError"])
        self.assertIn("not measured", text)
        for args in ({"kind": "widget", "key": "x"},
                     {"kind": "rpc", "key": " "},
                     {"kind": "rpc", "key": "OR", "max_rows": 0}):
            resp, _ = card(self.h, "listing", args)
            self.assertTrue(resp["result"]["isError"], args)


class TestCardsInOrientation(unittest.TestCase):
    def test_orientation_points_at_the_cards(self):
        text = tool_text(call_tool(_card_handler(), "orientation", {}))
        for tool in ("routine_card", "package_card", "listing"):
            self.assertIn(tool, text)


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
