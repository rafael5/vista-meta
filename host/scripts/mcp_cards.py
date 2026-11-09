#!/usr/bin/env python3
# Plan: docs/proposals/routine-and-package-cards.md

"""Routine card, package interface card and keyed listings for the MCP
server — stdlib only, composed from meta.db's existing tables at query
time.

Measured 2026-11-09 over 446 sessions: agents read routine source by
hand 1,315 times (44 % of their knowledge context) for answers this
model already holds — the call graph, the bindings, the globals, the
tags. A card hands them over in one call, bounded so that a routine
with ten thousand callers stays readable.

Source text is read from the host copy of the VistA-M tree
(`vista/vista-m-host/`, filled by `make sync-routines`); it never goes
into meta.db. When the tree is absent the card still carries every
measured part and says why the text is missing.
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import schema_v1
from build_meta_db import table_name

# Bounds — each list is cut here, with its full count and what was cut.
CAP_CALLERS = 25            # caller rows shown, heaviest first
CAP_CALLER_PACKAGES = 20    # packages the remaining callers are summed into
CAP_BY_TAG = 30             # per-tag caller counts on a routine card
CAP_LIST = 40               # callees, globals, RPCs, options, protocols
CAP_TAGS = 150              # labels listed on a routine card
CAP_TAG_LINES = 80          # lines of a tag's text
CAP_CALL_SITES = 10         # TAG+n sites shown per caller row
CAP_PACKAGE_LIST = 30       # a package's RPCs, options, protocols
CAP_ENTRY_POINTS = 25       # a package's cross-package entry points
LISTING_DEFAULT_ROWS = 100
LISTING_MAX_ROWS = 500

TSV_OF = {table_name(n): f"{s.model}/{n}" for n, s in schema_v1.FILES.items()}
TSV_OF["entity_bridge"] = "bridge/entity-bridge.tsv"

CONTAINER_ROOT = "/opt/VistA-M/"

# ROUTINE, ^ROUTINE, TAG^ROUTINE, $$TAG^ROUTINE
_NAME = re.compile(r"^(?:\$\$)?(?:([%A-Za-z0-9]+)?\^)?([%A-Za-z0-9]+)$")
_LABEL = re.compile(r"^([%A-Za-z0-9]+)(?:\(([^)]*)\))?")

CALL_SITES_NOTE = (
    "call_sites: the TAG+n lines in the caller where XINDEX recorded "
    "this reference (code-model/xindex-xrefs.tsv, location_list); "
    "absent (null) where XINDEX did not index the caller or keyed the "
    "reference differently — absent means not measured, not no call. "
    f"At most {CAP_CALL_SITES} per row; call_sites_more counts the rest.")
# routine_calls row → the "ROUTINE [$$]TAG" key XINDEX files the reference
# under (a bare `D ^ROUTINE` is "ROUTINE " with an empty tag).
_XREF_KEY = ("c.callee_routine || ' ' || CASE WHEN c.kind = 'func' "
             "THEN '$$' ELSE '' END || COALESCE(c.callee_tag, '')")
PER_ROUTINE_NOTE = ("measured for the whole routine, not per tag — the "
                    "tag's text shows its own calls and references")

CARD_TOOLS = [
    {
        "name": "routine_card",
        "description":
            "Everything measured about one routine, or one tag, in a "
            "single call — use it instead of reading or grepping the "
            "source. name: ROUTINE, ^ROUTINE or TAG^ROUTINE (any case, "
            "a leading $$ is fine). Returns the routines_comprehensive "
            "row; the source (a tag's lines with TAG+n offsets, formal "
            "parameters and opening comments, or a routine's labels with "
            "line numbers) with its host path and line range; callers "
            "(narrowed to the tag, with package and ref_count); callees; "
            "globals; bound RPCs, options and protocols; the vdocs "
            "counterpart. Every part carries its citation; long lists "
            "are cut with their full count and say what was cut.",
        "inputSchema": {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        },
    },
    {
        "name": "package_card",
        "description":
            "A package's measured interfaces in one call. name: the "
            "package name (any case, e.g. 'clinical reminders') or a "
            "namespace prefix (e.g. PXRM). Returns its RPCs, options and "
            "protocols (registered to the package or implemented by its "
            "routines) and the entry points other packages actually call "
            "— routine_calls rows whose callee is in the package and "
            "whose caller is not, grouped by TAG^ROUTINE with the number "
            "of calling packages.",
        "inputSchema": {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        },
    },
    {
        "name": "listing",
        "description":
            "Keyed listings, paged. kind: rpc (RPCs whose name starts "
            "with key, e.g. ORWPT) | option (options whose name starts "
            "with key) | field (the fields of FileMan file number key, "
            "with PIKS, in field order). Returns the full count and "
            "whether the page was truncated.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "kind": {"type": "string",
                         "enum": ["field", "option", "rpc"]},
                "key": {"type": "string"},
                "max_rows": {"type": "integer", "minimum": 1,
                             "maximum": LISTING_MAX_ROWS,
                             "description": f"Page size (default "
                                            f"{LISTING_DEFAULT_ROWS})"},
                "offset": {"type": "integer", "minimum": 0},
            },
            "required": ["kind", "key"],
        },
    },
]


class CardInputError(ValueError):
    """A malformed card request — the server reports it as an input
    error, never as "not measured"."""


def _quote(value) -> str:
    return "NULL" if value is None else "'" + str(value).replace("'", "''") + "'"


def _with_literals(where: str, params) -> str:
    """The WHERE clause with its parameters written in, so the hint can
    be pasted into `query` as it stands."""
    if isinstance(params, dict):
        return re.sub(r":(\w+)", lambda m: _quote(params[m.group(1)]), where)
    values = iter(params)
    return re.sub(r"\?", lambda m: _quote(next(values)), where)


# ── source text ──────────────────────────────────────────────────────
def host_relative(source_path: str | None) -> Path | None:
    """`/opt/VistA-M/Packages/...` → `Packages/...`; the %-routines in
    `o/` and `r/` are synced into `PercentRoutines/`."""
    if not source_path or not source_path.startswith(CONTAINER_ROOT):
        return None
    rest = source_path[len(CONTAINER_ROOT):]
    if rest.startswith("Packages/"):
        return Path(rest)
    if rest.startswith(("o/", "r/")):
        return Path("PercentRoutines") / Path(rest).name
    return None


def parse_labels(lines: list[str]) -> list[dict]:
    """Each label line (code in column one) with its 1-based line,
    formal parameters and the comment on the label line itself."""
    labels = []
    for i, line in enumerate(lines, 1):
        if not line or line[0] in " \t;":
            continue
        m = _LABEL.match(line)
        if not m:
            continue
        rest = line[m.end():].lstrip()
        labels.append({
            "tag": m.group(1), "line": i,
            "formal_parameters": [p.strip() for p in
                                  (m.group(2) or "").split(",")
                                  if p.strip()],
            "comment": rest[1:].strip() if rest.startswith(";") else "",
        })
    return labels


def tag_extent(lines: list[str], labels: list[dict],
               tag: dict) -> tuple[int, int]:
    """First and last 1-based line of a tag: up to the next label."""
    later = [lb["line"] for lb in labels if lb["line"] > tag["line"]]
    return tag["line"], (later[0] - 1 if later else len(lines))


def opening_comments(lines: list[str], tag: dict) -> list[str]:
    out = [tag["comment"]] if tag["comment"] else []
    for line in lines[tag["line"]:]:
        stripped = line.strip()
        if not stripped.startswith(";"):
            break
        text = stripped[1:].strip()
        if text:
            out.append(text)
    return out


def _find_label(labels: list[dict], tag: str) -> dict | None:
    exact = [lb for lb in labels if lb["tag"] == tag]
    folded = [lb for lb in labels if lb["tag"].upper() == tag.upper()]
    return (exact or folded or [None])[0]


def _compact_label(lb: dict) -> dict:
    out = {"tag": lb["tag"], "line": lb["line"]}
    if lb["formal_parameters"]:
        out["formal_parameters"] = lb["formal_parameters"]
    if lb["comment"]:
        out["comment"] = lb["comment"]
    return out


# ── cards ────────────────────────────────────────────────────────────
class Cards:
    def __init__(self, con: sqlite3.Connection, release: str,
                 source_root: Path, display_root: str):
        self.con = con
        self.release = release
        self.source_root = source_root
        self.display_root = display_root

    def not_measured(self, what: str) -> str:
        return (f"not measured in vista-meta {self.release} ({what}) — "
                "report this as the answer; do not substitute general "
                "knowledge.")

    def cite(self, table: str, key: str) -> str:
        return f"vista-meta {self.release} · {TSV_OF[table]} · {key}"

    def _dicts(self, sql: str, params=()) -> list[dict]:
        cur = self.con.execute(sql, params)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]

    def _scalar(self, sql: str, params=()):
        return self.con.execute(sql, params).fetchone()[0]

    def _part(self, table: str, key: str, columns: str, where: str,
              params, order: str, cap: int, note: str = "") -> dict:
        count = self._scalar(f"SELECT COUNT(*) FROM {table} WHERE {where}",
                             params)
        rows = self._dicts(f"SELECT {columns} FROM {table} WHERE {where} "
                           f"ORDER BY {order} LIMIT {cap}", params)
        part = {"citation": self.cite(table, key), "count": count,
                "rows": rows}
        if count > cap:
            part["cut"] = (f"showing {cap} of {count} rows; the rest: "
                           f"`query` {table} WHERE "
                           f"{_with_literals(where, params)}")
        if note:
            part["note"] = note
        return part

    # ── routine card ────────────────────────────────────────────────
    def routine_card(self, name: str) -> dict | str:
        m = _NAME.match(name.strip())
        if not m:
            raise CardInputError(
                f"name {name!r} is not ROUTINE, ^ROUTINE or TAG^ROUTINE "
                "(e.g. XLFDT or FMTE^XLFDT)")
        tag_asked, routine_asked = m.group(1), m.group(2)
        found = self._dicts(
            "SELECT * FROM routines_comprehensive "
            "WHERE routine_name = ? COLLATE NOCASE "
            "ORDER BY routine_name = ? DESC LIMIT 1",
            (routine_asked, routine_asked))
        if not found:
            return self.not_measured(
                f"routine routine_name={routine_asked!r}")
        row = found[0]
        routine = row["routine_name"]
        source, tag = self._source(row, tag_asked)
        if tag_asked and tag is None:
            labels = source.get("measured_tags") or [
                t["tag"] for t in source.get("tags", [])]
            return self.not_measured(
                f"tag {tag_asked!r} is not a label of {routine}; its "
                f"labels: {', '.join(labels[:60])}")
        card = {
            "card": "routine",
            "name": f"{tag}^{routine}" if tag else routine,
            "routine": {
                "citation": self.cite("routines_comprehensive",
                                      f"routine_name={routine}"),
                "row": row},
            "source": source,
            "callers": self._callers(routine, tag),
        }
        card.update(self._outbound(routine, tag))
        card.update(self._bindings(routine, tag))
        card["documented"] = self._part(
            "entity_bridge", f"entity_id=routine:{routine}",
            "entity_id, mention_count, vista_key_value, join_method, "
            "join_confidence",
            "entity_type = 'routine' AND (vista_key_value = ? "
            "OR canonical_name = ?)", (routine, routine), "entity_id",
            CAP_LIST)
        return card

    def _source(self, row: dict, tag_asked: str | None
                ) -> tuple[dict, str | None]:
        """The source part, and the tag as spelled in the routine."""
        rel = host_relative(row["source_path"])
        part: dict = {"root": self.display_root}
        if rel is not None:
            part["path"] = rel.as_posix()
        reason = self._unavailable(rel)
        if reason:
            part["text_unavailable"] = reason
            measured = [t for (t,) in self.con.execute(
                "SELECT tag FROM xindex_tags WHERE routine_name = ? "
                "ORDER BY tag", (row["routine_name"],))]
            part["measured_tags"] = measured
            if not tag_asked:
                return part, None
            hit = ([t for t in measured if t == tag_asked]
                   or [t for t in measured
                       if t.upper() == tag_asked.upper()])
            if hit:
                part["tag"] = hit[0]
            return part, (hit[0] if hit else None)
        lines = (self.source_root / rel).read_text(
            encoding="utf-8", errors="replace").splitlines()
        labels = parse_labels(lines)
        if not tag_asked:
            part["lines"] = f"1-{len(lines)}"
            part["tags"] = [_compact_label(lb) for lb in labels[:CAP_TAGS]]
            if len(labels) > CAP_TAGS:
                part["cut"] = (f"showing {CAP_TAGS} of {len(labels)} "
                               "labels")
            return part, None
        label = _find_label(labels, tag_asked)
        if label is None:
            part["tags"] = [_compact_label(lb) for lb in labels]
            return part, None
        first, last = tag_extent(lines, labels, label)
        body = lines[first - 1:last]
        tag = label["tag"]
        part.update({
            "tag": tag, "lines": f"{first}-{last}",
            "formal_parameters": label["formal_parameters"],
            "opening_comments": opening_comments(lines, label),
            "text": [f"{tag}+{n}: {text}"
                     for n, text in enumerate(body[:CAP_TAG_LINES])],
        })
        if len(body) > CAP_TAG_LINES:
            part["cut"] = (f"showing {tag}+0..{tag}+{CAP_TAG_LINES - 1} "
                           f"of {len(body)} lines; the rest is lines "
                           f"{first + CAP_TAG_LINES}-{last} of the file")
        return part, tag

    def _unavailable(self, rel: Path | None) -> str:
        if not self.source_root.is_dir():
            return (f"source text unavailable: the host tree "
                    f"{self.display_root} is absent — `make sync-routines` "
                    "fills it from the running container")
        if rel is None:
            return ("source text unavailable: the routine's source_path "
                    "has no host counterpart")
        if not (self.source_root / rel).is_file():
            return (f"source text unavailable: {rel.as_posix()} is not in "
                    f"the host tree {self.display_root} — re-run "
                    "`make sync-routines`")
        return ""

    def _callers(self, routine: str, tag: str | None) -> dict:
        where, params = "callee_routine = ?", [routine]
        key = f"callee_routine={routine}"
        if tag:
            # `D ^ROUTINE` enters at the first label, which is the
            # routine's own name; routine_calls stores it tagless.
            where += (" AND (callee_tag = ? OR callee_tag IS NULL)"
                      if tag == routine else " AND callee_tag = ?")
            params.append(tag)
            key += f", callee_tag={tag}"
        count, refs, packages = self.con.execute(
            "SELECT COUNT(*), COALESCE(SUM(ref_count), 0), "
            f"COUNT(DISTINCT caller_package) FROM routine_calls "
            f"WHERE {where}", params).fetchone()
        order = "ref_count DESC, caller_routine, callee_tag, kind"
        rows = self._dicts(
            "SELECT caller_routine, caller_package, callee_tag, kind, "
            "ref_count, x.location_list AS call_sites FROM ("
            "SELECT * FROM routine_calls "
            f"WHERE {where} ORDER BY {order} LIMIT {CAP_CALLERS}) c "
            "LEFT JOIN xindex_xrefs x ON x.routine_name = "
            f"c.caller_routine AND x.ref = {_XREF_KEY} "
            f"ORDER BY {order}", params)
        for row in rows:
            sites = (row["call_sites"] or "").split(",")
            if len(sites) > CAP_CALL_SITES:
                row["call_sites"] = ",".join(sites[:CAP_CALL_SITES])
                row["call_sites_more"] = len(sites) - CAP_CALL_SITES
        part = {
            "citation": self.cite("routine_calls", key),
            "count": count, "refs": refs, "calling_packages": packages,
            "rows": rows,
            "call_sites": CALL_SITES_NOTE,
        }
        if not tag:
            part["by_tag"] = self._dicts(
                "SELECT callee_tag, COUNT(*) AS rows, COUNT(DISTINCT "
                "caller_package) AS calling_packages, SUM(ref_count) AS "
                f"refs FROM routine_calls WHERE {where} GROUP BY "
                f"callee_tag ORDER BY rows DESC, callee_tag "
                f"LIMIT {CAP_BY_TAG}", params)
        if count > CAP_CALLERS:
            self._sum_rest_by_package(part, where, params, order, count)
        return part

    def _sum_rest_by_package(self, part: dict, where: str, params,
                             order: str, count: int) -> None:
        groups = self._dicts(
            f"WITH ranked AS (SELECT caller_package, ref_count, "
            f"ROW_NUMBER() OVER (ORDER BY {order}) AS rn "
            f"FROM routine_calls WHERE {where}) "
            "SELECT caller_package AS package, COUNT(*) AS rows, "
            f"SUM(ref_count) AS refs FROM ranked WHERE rn > {CAP_CALLERS} "
            "GROUP BY caller_package ORDER BY refs DESC, package", params)
        shown, unlisted = (groups[:CAP_CALLER_PACKAGES],
                           groups[CAP_CALLER_PACKAGES:])
        part["rest_by_package"] = shown
        cut = (f"showing the {CAP_CALLERS} heaviest of {count} caller "
               f"rows; the other {count - CAP_CALLERS} are summed by "
               f"package in rest_by_package")
        if unlisted:
            part["rest_packages_unlisted"] = len(unlisted)
            part["rest_rows_unlisted"] = sum(g["rows"] for g in unlisted)
            part["rest_refs_unlisted"] = sum(g["refs"] for g in unlisted)
            cut += (f" (the {len(shown)} heaviest packages; "
                    f"{len(unlisted)} more are only counted)")
        part["cut"] = cut

    def _outbound(self, routine: str, tag: str | None) -> dict:
        note = PER_ROUTINE_NOTE if tag else ""
        return {
            "callees": self._part(
                "routine_calls", f"caller_routine={routine}",
                "callee_tag, callee_routine, kind, ref_count",
                "caller_routine = ?", (routine,),
                "ref_count DESC, callee_routine, callee_tag", CAP_LIST,
                note),
            "globals": self._part(
                "routine_globals", f"routine_name={routine}",
                "global_name, ref_count", "routine_name = ?", (routine,),
                "ref_count DESC, global_name", CAP_LIST, note),
        }

    def _bindings(self, routine: str, tag: str | None) -> dict:
        tag_sql, tag_key = ("", "") if not tag else (" AND tag = ?",
                                                     f", tag={tag}")
        params = (routine, tag) if tag else (routine,)
        return {
            "rpcs": self._part(
                "rpcs", f"routine_name={routine}{tag_key}",
                "name, tag, return_type_label, availability, "
                "inactive_label", f"routine_name = ?{tag_sql}", params,
                "name", CAP_LIST),
            "options": self._part(
                "options", f"routine_name={routine}{tag_key}",
                "name, menu_text, type, tag", f"routine_name = ?{tag_sql}",
                params, "name", CAP_LIST),
            "protocols": self._part(
                "protocol_calls",
                f"callee_routine={routine}"
                + (f", callee_tag={tag}" if tag else ""),
                "protocol_name, protocol_package, action_kind, callee_tag, "
                "call_kind", "callee_routine = ?"
                + (" AND callee_tag = ?" if tag else ""), params,
                "protocol_name, action_kind", CAP_LIST),
        }

    # ── package card ────────────────────────────────────────────────
    def _resolve_package(self, name: str) -> dict | None:
        rows = self._dicts("SELECT * FROM package_namespace")
        upper = name.upper()
        for test in (lambda r: (r["package"] or "").upper() == upper,
                     lambda r: (r["package_name"] or "").upper() == upper,
                     lambda r: (r["namespace"] or "").upper() == upper,
                     lambda r: upper in [
                         p.strip().upper()
                         for p in (r["prefixes"] or "").split(",")
                         if p.strip() and not p.strip().startswith("!")]):
            hits = [r for r in rows if test(r)]
            if hits:
                return hits[0]
        return None

    def package_card(self, name: str) -> dict | str:
        name = name.strip()
        if not name:
            raise CardInputError("name is empty; give a package name or "
                                 "a namespace prefix")
        ns = self._resolve_package(name)
        if ns is None:
            return self.not_measured(
                f"package or namespace prefix {name!r}")
        pkg, pkg_name = ns["package"], ns["package_name"]
        overview = self._dicts(
            "SELECT * FROM v_package_overview WHERE package = ?", (pkg,))
        in_pkg = ("SELECT routine_name FROM routines_comprehensive "
                  "WHERE package = :p")
        params = {"p": pkg, "pn": pkg_name}
        owned = ("package_dir = :p OR package = :pn COLLATE NOCASE")
        return {
            "card": "package",
            "package": {"citation": self.cite("packages", f"package={pkg}"),
                        "row": overview[0] if overview else ns},
            "rpcs": self._part(
                "rpcs", f"package_dir={pkg}, or routine_name in the package",
                "name, tag, routine_name, return_type_label, "
                "inactive_label",
                f"{owned} OR routine_name IN ({in_pkg})", params, "name",
                CAP_PACKAGE_LIST),
            "options": self._part(
                "options",
                f"package_dir={pkg}, or routine_name in the package",
                "name, menu_text, type, tag, routine_name",
                f"{owned} OR routine_name IN ({in_pkg})", params, "name",
                CAP_PACKAGE_LIST),
            "protocols": self._part(
                "protocols",
                f"package_dir={pkg}, or an action calling the package",
                "name, item_text, type",
                f"{owned} OR name IN (SELECT protocol_name FROM "
                f"protocol_calls WHERE callee_routine IN ({in_pkg}))",
                params, "name", CAP_PACKAGE_LIST),
            "entry_points": self._entry_points(pkg, in_pkg),
        }

    def _entry_points(self, pkg: str, in_pkg: str) -> dict:
        where = (f"callee_routine IN ({in_pkg}) "
                 "AND caller_package IS NOT :p")
        total, packages = self.con.execute(
            "SELECT COUNT(DISTINCT COALESCE(callee_tag, '') || '^' || "
            "callee_routine), COUNT(DISTINCT caller_package) "
            f"FROM routine_calls WHERE {where}", {"p": pkg}).fetchone()
        rows = self._dicts(
            "SELECT COALESCE(callee_tag, '') || '^' || callee_routine "
            "AS entry_point, COUNT(DISTINCT caller_package) AS "
            "calling_packages, COUNT(*) AS caller_rows, SUM(ref_count) "
            f"AS refs FROM routine_calls WHERE {where} "
            "GROUP BY callee_tag, callee_routine "
            "ORDER BY calling_packages DESC, refs DESC, entry_point "
            f"LIMIT {CAP_ENTRY_POINTS}", {"p": pkg})
        part = {"citation": self.cite("routine_calls",
                                      f"callee package={pkg}"),
                "count": total, "calling_packages": packages, "rows": rows}
        if total > CAP_ENTRY_POINTS:
            part["cut"] = (f"showing the {CAP_ENTRY_POINTS} most widely "
                           f"called of {total} entry points")
        return part

    # ── listings ────────────────────────────────────────────────────
    def listing(self, kind: str, key: str, max_rows: int,
                offset: int) -> dict | str:
        key = key.strip()
        if not key:
            raise CardInputError("key is empty; give a name prefix or a "
                                 "file number")
        if kind == "field":
            table, cite_key = "field_piks", f"file_number={key}"
            columns = ("field_number, field_name, data_type, file_piks, "
                       "pointer_target, ref_piks, cross_piks, "
                       "sensitivity_flag")
            where, params = "file_number = ?", (key,)
            order = "CAST(field_number AS REAL), field_number"
        else:
            table = {"rpc": "rpcs", "option": "options"}[kind]
            cite_key = f"name={key.upper()}*"
            columns = {
                "rpc": "name, tag, routine_name, return_type_label, "
                       "availability, inactive_label, package",
                "option": "name, menu_text, type, tag, routine_name, "
                          "package"}[kind]
            escaped = (key.replace("\\", "\\\\").replace("%", "\\%")
                       .replace("_", "\\_"))
            where, params = "name LIKE ? ESCAPE '\\'", (escaped + "%",)
            order = "name"
        count = self._scalar(f"SELECT COUNT(*) FROM {table} WHERE {where}",
                             params)
        if count == 0:
            return self.not_measured(f"{kind} {cite_key}")
        rows = self._dicts(
            f"SELECT {columns} FROM {table} WHERE {where} ORDER BY {order} "
            f"LIMIT {max_rows} OFFSET {offset}", params)
        out = {"citation": self.cite(table, cite_key), "count": count,
               "offset": offset, "rows": rows,
               "truncated": offset + len(rows) < count}
        if kind == "field":
            out["file_name"] = self._scalar(
                "SELECT file_name FROM files WHERE file_number = ?", (key,))
        return out
