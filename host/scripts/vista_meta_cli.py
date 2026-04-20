#!/usr/bin/env python3
# Spec: docs/vista-developers-guide.md §Tier-1 — collapse toolchain friction
#
# vista-meta CLI: package overview (pkg) + AI context pack (context).
# Reads only the code-model TSVs under vista/export/code-model/ and the
# synced VistA-M snapshot under vista/vista-m-host/. No container needed.

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CODE_MODEL = ROOT / "vista" / "export" / "code-model"
DATA_MODEL = ROOT / "vista" / "export" / "data-model"
VISTA_M = ROOT / "vista" / "vista-m-host" / "Packages"

csv.field_size_limit(2**24)


# ── Package resolution ───────────────────────────────────────────────

def _known_packages() -> list[str]:
    path = CODE_MODEL / "packages.tsv"
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        return [row["package"] for row in reader]


def resolve_package(query: str) -> str:
    """Resolve a user-supplied name/prefix/substring to one canonical package.

    Matching cascade: exact → case-insensitive exact → case-insensitive
    substring → namespace prefix (most routines starting with <query> wins).
    Raises SystemExit with a helpful message on ambiguity or miss.
    """
    pkgs = _known_packages()
    if not pkgs:
        sys.exit(f"No packages.tsv at {CODE_MODEL}. Run `make inventory`.")

    if query in pkgs:
        return query
    ci = [p for p in pkgs if p.lower() == query.lower()]
    if len(ci) == 1:
        return ci[0]
    sub = [p for p in pkgs if query.lower() in p.lower()]
    if len(sub) == 1:
        return sub[0]
    if len(sub) > 1:
        sys.exit("Ambiguous package name. Candidates:\n  " + "\n  ".join(sub))

    prefix_pkg = _infer_package_from_prefix(query.upper())
    if prefix_pkg:
        return prefix_pkg

    hint = ", ".join(sorted(pkgs)[:5])
    sys.exit(f"No package matching '{query}'. Examples: {hint}, ...")


def _infer_package_from_prefix(prefix: str) -> str | None:
    path = CODE_MODEL / "routines-comprehensive.tsv"
    if not path.exists():
        return None
    counts: Counter[str] = Counter()
    with path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            if row["routine_name"].startswith(prefix):
                counts[row["package"]] += 1
    if not counts:
        return None
    top, n = counts.most_common(1)[0]
    total = sum(counts.values())
    if n / total < 0.4:
        return None
    return top


def dominant_prefix(pkg: str) -> tuple[str | None, float]:
    """Infer the namespace prefix — most-common 2-4-char prefix of routine names."""
    path = CODE_MODEL / "routines-comprehensive.tsv"
    if not path.exists():
        return None, 0.0
    counts: Counter[str] = Counter()
    total = 0
    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            if row["package"] != pkg:
                continue
            name = row["routine_name"]
            if not name or name.startswith("%"):
                continue
            total += 1
            for k in (4, 3, 2):
                if len(name) >= k:
                    counts[name[:k]] += 1
    if total == 0 or not counts:
        return None, 0.0
    best = None
    best_frac = 0.0
    for pfx, n in counts.items():
        frac = n / total
        if frac > best_frac and frac >= 0.5:
            best, best_frac = pfx, frac
    return best, best_frac


# ── Table loaders ────────────────────────────────────────────────────

def _rows_matching(path: Path, col: str, value: str) -> list[dict]:
    if not path.exists():
        return []
    out = []
    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            if row.get(col) == value:
                out.append(row)
    return out


def package_manifest(pkg: str) -> dict | None:
    rows = _rows_matching(CODE_MODEL / "package-manifest.tsv", "package", pkg)
    return rows[0] if rows else None


def package_fm_files(pkg: str) -> list[dict]:
    rows = _rows_matching(CODE_MODEL / "package-data.tsv", "package", pkg)
    seen: dict[str, dict] = {}
    for r in rows:
        if r.get("kind") != "file":
            continue
        fn = r.get("file_number", "")
        if fn and fn not in seen:
            seen[fn] = r
    return sorted(seen.values(), key=lambda r: float(r["file_number"] or 0))


def package_rpcs(pkg: str) -> list[dict]:
    path = CODE_MODEL / "rpcs.tsv"
    if not path.exists():
        return []
    manifest = {r["routine_name"] for r in _rows_matching(
        CODE_MODEL / "routines-comprehensive.tsv", "package", pkg)}
    out = []
    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            if row.get("routine") in manifest:
                out.append(row)
    return out


def package_options(pkg: str) -> list[dict]:
    return _rows_matching(
        CODE_MODEL / "options.tsv", "package", pkg.upper())


def package_protocols(pkg: str) -> list[dict]:
    return _rows_matching(
        CODE_MODEL / "protocols.tsv", "package", pkg.upper())


def package_routines(pkg: str) -> list[dict]:
    path = CODE_MODEL / "routines-comprehensive.tsv"
    rows = _rows_matching(path, "package", pkg)
    rows.sort(key=lambda r: int(r.get("in_degree") or 0), reverse=True)
    return rows


def package_globals(pkg: str) -> list[tuple[str, int]]:
    path = CODE_MODEL / "routine-globals.tsv"
    if not path.exists():
        return []
    totals: Counter[str] = Counter()
    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            if row.get("package") == pkg:
                totals[row["global_name"]] += int(row.get("ref_count") or 0)
    return totals.most_common()


def package_inbound(pkg: str, limit: int = 10) -> list[dict]:
    rows = _rows_matching(
        CODE_MODEL / "package-edge-matrix.tsv", "dest_package", pkg)
    rows = [r for r in rows if r["source_package"] != pkg]
    rows.sort(key=lambda r: int(r.get("call_edges") or 0), reverse=True)
    return rows[:limit]


def package_outbound(pkg: str, limit: int = 10) -> list[dict]:
    rows = _rows_matching(
        CODE_MODEL / "package-edge-matrix.tsv", "source_package", pkg)
    rows = [r for r in rows if r["dest_package"] != pkg]
    rows.sort(key=lambda r: int(r.get("call_edges") or 0), reverse=True)
    return rows[:limit]


# ── pkg command ──────────────────────────────────────────────────────

def cmd_pkg(args: argparse.Namespace) -> int:
    pkg = resolve_package(args.name)
    m = package_manifest(pkg)
    prefix, pfrac = dominant_prefix(pkg)
    files = package_fm_files(pkg)
    rpcs = package_rpcs(pkg)
    opts = package_options(pkg)
    prots = package_protocols(pkg)
    routines = package_routines(pkg)
    glbls = package_globals(pkg)
    inbound = package_inbound(pkg)
    outbound = package_outbound(pkg)

    print(f"PACKAGE  {pkg}")
    if prefix:
        print(f"PREFIX   {prefix}  ({pfrac * 100:.0f}% of routines)")
    else:
        print("PREFIX   (no dominant prefix — likely multi-namespace)")

    print()
    print(f"Routines         {len(routines):>6}"
          + (f"  lines {m['total_lines']:>10}" if m else ""))
    if m:
        print(f"PIKS files       P={m['p_files']} I={m['i_files']} "
              f"K={m['k_files']} S={m['s_files']}   "
              f"(of {m['files_shipped']} FM files shipped)")
    print(f"FM files owned   {len(files):>6}")
    print(f"RPCs exposed     {len(rpcs):>6}")
    print(f"Options (pkg=)   {len(opts):>6}")
    print(f"Protocols (pkg=) {len(prots):>6}")
    print(f"Globals touched  {len(glbls):>6}  (distinct)")

    if files:
        print()
        print("FILEMAN FILES OWNED")
        for r in files[:20]:
            print(f"  {r['file_number']:>8}  {r['entity_name']}")
        if len(files) > 20:
            print(f"  ... and {len(files) - 20} more")

    if glbls:
        print()
        print("TOP GLOBALS (by total ref count)")
        for name, n in glbls[:10]:
            print(f"  ^{name:<16}  {n:>6}")

    if rpcs:
        print()
        print("RPCs EXPOSED (top 10 by name)")
        for r in sorted(rpcs, key=lambda r: r["name"])[:10]:
            tag = r.get("tag") or ""
            rt = r.get("routine") or ""
            entry = f"{tag}^{rt}" if tag else rt
            print(f"  {r['name']:<34}  {entry}")
        if len(rpcs) > 10:
            print(f"  ... and {len(rpcs) - 10} more")

    if inbound:
        print()
        print("TOP INBOUND (other packages calling INTO this one)")
        for r in inbound:
            print(f"  {r['source_package']:<36}  {int(r['call_edges']):>6} edges")

    if outbound:
        print()
        print("TOP OUTBOUND (this package calling OUT to others)")
        for r in outbound:
            print(f"  {r['dest_package']:<36}  {int(r['call_edges']):>6} edges")

    if routines:
        print()
        print("ENTRY-POINT CANDIDATES (top 10 by in-degree)")
        for r in routines[:10]:
            marks = []
            if int(r.get("rpc_count") or 0) > 0:
                marks.append(f"RPC×{r['rpc_count']}")
            if int(r.get("option_count") or 0) > 0:
                marks.append(f"OPT×{r['option_count']}")
            tag = " ".join(marks) or "-"
            print(f"  {r['routine_name']:<14}  in={r['in_degree']:>4}  "
                  f"out={r['out_degree']:>4}  lines={r['line_count']:>5}  {tag}")

    return 0


# ── context command ──────────────────────────────────────────────────

def _routine_source_path(pkg: str, name: str) -> Path | None:
    rp = VISTA_M / pkg / "Routines" / f"{name}.m"
    return rp if rp.exists() else None


def cmd_context(args: argparse.Namespace) -> int:
    pkg = resolve_package(args.name)
    max_bytes = args.bytes
    with_source = args.with_source
    picked = set(r.strip() for r in (args.routines or "").split(",") if r.strip())

    out = sys.stdout
    def w(s: str = "") -> None:
        out.write(s + "\n")

    # Header + summary (re-uses pkg-style info, slightly compressed)
    w(f"# VistA package context — {pkg}")
    w(f"# Generated by vista-meta context; root = {ROOT}")
    w()
    m = package_manifest(pkg)
    prefix, pfrac = dominant_prefix(pkg)
    files = package_fm_files(pkg)
    rpcs = package_rpcs(pkg)
    opts = package_options(pkg)
    prots = package_protocols(pkg)
    routines = package_routines(pkg)
    glbls = package_globals(pkg)
    inbound = package_inbound(pkg)
    outbound = package_outbound(pkg)

    w("## Summary")
    if prefix:
        w(f"- Namespace prefix: {prefix} ({pfrac * 100:.0f}% of routines)")
    w(f"- Routines: {len(routines)}")
    if m:
        w(f"- FM files shipped: {m['files_shipped']} "
          f"(P={m['p_files']} I={m['i_files']} "
          f"K={m['k_files']} S={m['s_files']})")
    w(f"- RPCs exposed: {len(rpcs)}")
    w(f"- Options (package=): {len(opts)}")
    w(f"- Protocols (package=): {len(prots)}")
    w(f"- Distinct globals touched: {len(glbls)}")
    w()

    if files:
        w("## FileMan files owned")
        for r in files:
            w(f"- {r['file_number']}  {r['entity_name']}")
        w()

    if rpcs:
        w("## RPCs exposed")
        for r in sorted(rpcs, key=lambda r: r["name"]):
            tag = r.get("tag") or ""
            rt = r.get("routine") or ""
            entry = f"{tag}^{rt}" if tag else rt
            w(f"- {r['name']} -> {entry}")
        w()

    if inbound:
        w("## Top inbound callers")
        for r in inbound:
            w(f"- {r['source_package']} — {r['call_edges']} call edges")
        w()
    if outbound:
        w("## Top outbound callees")
        for r in outbound:
            w(f"- {r['dest_package']} — {r['call_edges']} call edges")
        w()

    w("## Routines inventory (ranked by in-degree)")
    for r in routines:
        line2 = r.get("version_line") or ""
        w(f"- {r['routine_name']}  "
          f"(in={r['in_degree']}, out={r['out_degree']}, "
          f"lines={r['line_count']})  {line2}")
    w()

    if not (with_source or picked):
        w("## No source included")
        w("Re-run with --with-source for budgeted full source, or "
          "--routines R1,R2 for specific routines.")
        return 0

    source_names = picked or [r["routine_name"] for r in routines]
    w("## Routine source")
    w()
    emitted = 0
    skipped: list[str] = []
    for name in source_names:
        p = _routine_source_path(pkg, name)
        if p is None:
            skipped.append(name)
            continue
        body = p.read_text(encoding="utf-8", errors="replace")
        block = f"### {name}.m\n```mumps\n{body}\n```\n\n"
        if emitted + len(block) > max_bytes and not picked:
            remaining = len(source_names) - source_names.index(name)
            w(f"### (truncated — {remaining} more routines omitted; "
              f"budget {max_bytes} bytes exceeded)")
            break
        out.write(block)
        emitted += len(block)

    if skipped:
        w()
        w(f"## Skipped (no source found under vista/vista-m-host/): "
          f"{len(skipped)} routines")
    w()
    w(f"# Context bytes emitted (source section): ~{emitted}")
    return 0


# ── where / callers (symbol jumping) ─────────────────────────────────

def _parse_ref(ref: str) -> tuple[str, str]:
    """Parse TAG^ROUTINE / ^ROUTINE / ROUTINE into (tag, routine)."""
    ref = ref.strip()
    if "^" in ref:
        tag, routine = ref.split("^", 1)
        return tag, routine
    return "", ref


def _routine_source(routine: str) -> tuple[str, Path] | tuple[None, None]:
    path = CODE_MODEL / "routines-comprehensive.tsv"
    if not path.exists():
        return None, None
    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            if row["routine_name"] == routine:
                src = row.get("source_path") or ""
                pkg = row.get("package") or ""
                if src:
                    # source_path is the in-container path; map to host
                    host = src.replace("/opt/VistA-M/", "vista/vista-m-host/")
                    return pkg, ROOT / host
    return None, None


def _tag_line(path: Path, tag: str) -> int | None:
    """Return 1-based line number of `tag` at column 0, else None."""
    if not path.exists():
        return None
    try:
        with path.open(encoding="utf-8", errors="replace") as f:
            for i, line in enumerate(f, start=1):
                if not line or line[0] in (" ", "\t", ";"):
                    continue
                head = line.rstrip("\n")
                name = head.split("(")[0].split(" ")[0].split("\t")[0]
                if name == tag:
                    return i
    except OSError:
        return None
    return None


def cmd_where(args: argparse.Namespace) -> int:
    tag, routine = _parse_ref(args.ref)
    pkg, src = _routine_source(routine)
    if not src:
        sys.exit(f"Routine {routine!r} not found in routines-comprehensive.tsv")
    if not src.exists():
        sys.exit(f"Source not synced: {src}\n  Run `make sync-routines`.")

    lineno = 1
    if tag:
        found = _tag_line(src, tag)
        if found is None:
            sys.exit(f"Tag {tag!r} not found in {src}")
        lineno = found

    # Emit a clickable path:line and a quick snippet
    rel = src.relative_to(ROOT)
    print(f"{rel}:{lineno}   (package: {pkg})")
    try:
        with src.open(encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        start = max(0, lineno - 1)
        end = min(len(lines), lineno + 5)
        for i in range(start, end):
            marker = ">" if i == lineno - 1 else " "
            print(f"{marker} {i + 1:>5}  {lines[i].rstrip()}")
    except OSError:
        pass
    return 0


def cmd_callers(args: argparse.Namespace) -> int:
    tag, routine = _parse_ref(args.ref)
    path = CODE_MODEL / "routine-calls.tsv"
    if not path.exists():
        sys.exit(f"{path} missing. Run `make routine-calls`.")

    matches: list[dict] = []
    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            if row["callee_routine"] != routine:
                continue
            if tag and row["callee_tag"] != tag:
                continue
            matches.append(row)

    if not matches:
        print(f"No callers found for {args.ref}")
        return 0

    # Group by caller_routine
    callers: dict[str, dict] = {}
    for r in matches:
        key = r["caller_name"]
        agg = callers.setdefault(key, {"package": r["caller_package"],
                                       "tags": Counter(), "total": 0})
        agg["tags"][r["callee_tag"]] += int(r["ref_count"])
        agg["total"] += int(r["ref_count"])

    # Sort by total ref count desc
    ordered = sorted(callers.items(), key=lambda kv: kv[1]["total"],
                     reverse=True)

    print(f"Callers of {args.ref}: {len(ordered)} routines, "
          f"{sum(r['total'] for _, r in ordered)} total refs")
    limit = args.limit
    shown = 0
    for name, agg in ordered:
        if shown >= limit:
            print(f"  ... and {len(ordered) - shown} more (use --limit to see more)")
            break
        tag_summary = ", ".join(
            f"{t}×{n}" for t, n in agg["tags"].most_common())
        print(f"  {name:<14} [{agg['package'][:28]:<28}]  {tag_summary}")
        shown += 1
    return 0


# ── new-test (M-Unit skeleton generator) ─────────────────────────────

import re


def _public_tags(src: Path) -> list[str]:
    """Return column-0 alphabetic labels after line 1 (the routine header)."""
    tags: list[str] = []
    try:
        with src.open(encoding="utf-8", errors="replace") as f:
            for i, line in enumerate(f, start=1):
                if i == 1:
                    continue
                if not line or line[0] in (" ", "\t", ";"):
                    continue
                m = re.match(r"^([A-Za-z%][A-Za-z0-9]*)", line)
                if m:
                    tags.append(m.group(1))
    except OSError:
        pass
    seen: set[str] = set()
    return [t for t in tags if not (t in seen or seen.add(t))]


def cmd_new_test(args: argparse.Namespace) -> int:
    target = args.routine
    pkg, src = _routine_source(target)
    if not src or not src.exists():
        sys.exit(f"Routine {target!r} not found in synced corpus. "
                 f"Run `make sync-routines`.")

    tags = _public_tags(src)
    # Truncate test routine name to 8 chars (MUMPS limit)
    test_name = ("T" + target)[:8]

    from datetime import date
    out: list[str] = []
    pkg_u = (pkg or "UNKNOWN").upper()
    out.append(f"{test_name} ;SITE/AUTHOR - M-Unit tests for {target} "
               f";{date.today().isoformat()}")
    out.append(f" ;;1.0;{pkg_u};;")
    out.append(" Q")
    out.append(" ;")
    out.append("STARTUP Q")
    out.append(" ;")
    out.append("SHUTDOWN Q")
    out.append(" ;")

    if not tags:
        out.append(f"T1 ; @TEST {target} has no public tags — edit this stub")
        out.append(" D SUCCEED^%ut")
        out.append(" Q")
        out.append(" ;")
    else:
        for idx, tag in enumerate(tags, start=1):
            # Test tag is T<N>; description names the target tag.
            out.append(f"T{idx} ; @TEST exercise {tag}^{target}")
            out.append(" ; TODO: set up fixture / inputs")
            out.append(f" ; D {tag}^{target}")
            out.append(" D SUCCEED^%ut")
            out.append(" Q")
            out.append(" ;")

    text = "\n".join(out) + "\n"
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
        print(f"Wrote {args.output}  ({len(tags)} test stub(s))")
    else:
        sys.stdout.write(text)
    return 0


# ── lint (doc-comment discipline) ────────────────────────────────────

DOC_TAG_RE = re.compile(r";\s*@(summary|param|returns|deprecated|test)\b",
                        re.IGNORECASE)


def lint_file(path: Path) -> list[str]:
    """Return list of lint issues. Empty list = clean."""
    issues: list[str] = []
    try:
        lines = path.read_text(encoding="utf-8",
                               errors="replace").splitlines()
    except OSError as e:
        return [f"{path}: read error: {e}"]

    for i, raw in enumerate(lines):
        if i == 0:
            continue
        if not raw or raw[0] in (" ", "\t", ";"):
            continue
        m = re.match(r"^([A-Za-z%][A-Za-z0-9]*)", raw)
        if not m:
            continue
        tag = m.group(1)

        # STARTUP/SHUTDOWN and purely numeric labels are structural,
        # not user-facing — skip doc-comment requirement.
        if tag in ("STARTUP", "SHUTDOWN"):
            continue

        # Walk backwards collecting contiguous comment lines
        docs: list[str] = []
        j = i - 1
        while j >= 0 and lines[j].lstrip().startswith(";"):
            docs.append(lines[j])
            j -= 1
        # Trailing ';' marker comments after a tag also count
        trailing = raw.split(";", 1)[1] if ";" in raw else ""
        if trailing:
            docs.append(";" + trailing)

        has_summary = any(DOC_TAG_RE.search(d) for d in docs)
        if not has_summary:
            issues.append(f"{path}:{i + 1}: tag {tag!r} has no "
                          f"@summary/@test doc block")
    return issues


def cmd_lint(args: argparse.Namespace) -> int:
    any_issue = False
    for a in args.paths:
        p = Path(a)
        if p.is_dir():
            files = list(p.rglob("*.m"))
        elif p.is_file():
            files = [p]
        else:
            print(f"skip: {p}", file=sys.stderr)
            continue
        for f in files:
            for issue in lint_file(f):
                print(issue)
                any_issue = True
    return 1 if any_issue else 0


# ── CLI entry ────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="vista-meta",
        description="VistA package overview + AI context pack.")
    sub = p.add_subparsers(dest="cmd", required=True)

    pp = sub.add_parser("pkg", help="Print a package overview")
    pp.add_argument("name", help="Package name, substring, or namespace prefix")
    pp.set_defaults(func=cmd_pkg)

    pc = sub.add_parser("context", help="Emit an AI-oriented context pack")
    pc.add_argument("name", help="Package name, substring, or namespace prefix")
    pc.add_argument("--with-source", action="store_true",
                    help="Include full routine source (budgeted)")
    pc.add_argument("--routines", default="",
                    help="Comma-separated routine names; implies source")
    pc.add_argument("--bytes", type=int, default=200_000,
                    help="Byte budget for the source section (default 200000)")
    pc.set_defaults(func=cmd_context)

    pw = sub.add_parser("where", help="Jump to a tag: TAG^ROUTINE or ROUTINE")
    pw.add_argument("ref", help="TAG^ROUTINE, ^ROUTINE, or just ROUTINE")
    pw.set_defaults(func=cmd_where)

    pcl = sub.add_parser("callers",
                         help="List callers of TAG^ROUTINE (or all tags if TAG omitted)")
    pcl.add_argument("ref", help="TAG^ROUTINE, ^ROUTINE, or just ROUTINE")
    pcl.add_argument("--limit", type=int, default=30,
                     help="Max callers to show (default 30)")
    pcl.set_defaults(func=cmd_callers)

    pnt = sub.add_parser("new-test",
                         help="Generate an M-Unit test skeleton for ROUTINE")
    pnt.add_argument("routine", help="Target routine name (e.g. PSOVCC1)")
    pnt.add_argument("-o", "--output",
                     help="Write to file (default: stdout)")
    pnt.set_defaults(func=cmd_new_test)

    pl = sub.add_parser("lint",
                        help="Check public tags for @summary doc blocks")
    pl.add_argument("paths", nargs="+", help="Files or directories")
    pl.set_defaults(func=cmd_lint)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
