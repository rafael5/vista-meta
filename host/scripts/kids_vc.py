#!/usr/bin/env python3
# Phase 8a of kids-vc initiative — a Python successor to XPDK2VC.
# Spec: docs/kids-vc-guide.md
# Design source: github.com/shabiel XPDK2VC (Apache 2) — structure faithfully
# ported; diff-stability refinements added (patch-list canonicalization).

"""Parse, decompose, assemble, and round-trip-verify VistA KIDS distribution files.

KIDS (Kernel Installation & Distribution System) is VistA's package-and-
deploy mechanism. A `.KID` file bundles routines, FileMan DD changes,
options, protocols, RPCs, pre/post-install routines, etc. as one
monolithic unit. This tool decomposes `.KID` files into per-component
text files suitable for git, and re-assembles per-component files back
to `.KID` for deployment.

Usage:
  kids_vc.py parse <kid-file>                      — parse, print summary
  kids_vc.py decompose <kid-file> <output-dir>     — split into components
  kids_vc.py assemble <input-dir> <output-kid>     — reassemble from components
  kids_vc.py roundtrip <kid-file>                  — parse → decompose → assemble → diff

Exit status 0 on success. Round-trip compares semantic equivalence
(after canonicalization), not byte-for-byte — by design, canonicalization
strips volatile fields (build number, patch list) from routine line 2.

MVP scope (Phase 8a): handles Build, Package, EnvironmentCheck, PreInit,
PostInstall, RequiredBuild, InstallQuestions, Routines, KRN (Kernel
components). FIA (FileMan files), DATA, GLO (global builds) are
recognized but emitted as single flat .zwr files without further
decomposition. Future phases will add DD-embedded MUMPS extraction
and ZWR merge drivers.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Parser — port of XPDK2V1's state machine
# ---------------------------------------------------------------------------

# Matches a subscript line like `"BLD",1,0)` or `"KRN",19,12345,0)` or
# `"^DD",999,.01,0)`. The line is the TAIL of a $NA reference (no leading
# global root). KIDS uses caret-prefixed section names like ^DD, ^DIC for
# FileMan DD/DIC data.
SUBSCRIPT_RE = re.compile(r'^"\^?[A-Z]')


def _strip_cr(line: str) -> str:
    return line.rstrip("\r\n")


def _parse_subscript_line(line: str) -> tuple:
    """Parse a KIDS subscript line like `"KRN",19,12345,0)` into a tuple.

    Strings are returned as str; integers are returned as int.
    Trailing `)` is dropped.
    """
    assert line.endswith(")"), f"subscript line must end with ): {line!r}"
    inner = line[:-1]
    parts: list[Any] = []
    i = 0
    n = len(inner)
    while i < n:
        c = inner[i]
        if c == '"':
            # quoted string — find closing quote (handle "" escape)
            j = i + 1
            buf = []
            while j < n:
                if inner[j] == '"':
                    if j + 1 < n and inner[j + 1] == '"':
                        buf.append('"')
                        j += 2
                        continue
                    break
                buf.append(inner[j])
                j += 1
            parts.append("".join(buf))
            i = j + 1
        elif c == ",":
            i += 1
        else:
            # numeric or dotted-numeric
            j = i
            while j < n and inner[j] not in ",":
                j += 1
            token = inner[i:j]
            parts.append(int(token) if token.isdigit() else _coerce_num(token))
            i = j
    return tuple(parts)


def _coerce_num(s: str) -> Any:
    """FileMan file numbers are decimals like 9.8, 8989.51. Coerce properly."""
    try:
        if "." in s:
            return float(s) if s.replace(".", "").isdigit() else s
        return int(s)
    except ValueError:
        return s


def _format_subscript(subs: tuple) -> str:
    """Inverse of _parse_subscript_line. Produces `"KRN",19,12345,0)` form."""
    pieces = []
    for s in subs:
        if isinstance(s, str):
            escaped = s.replace('"', '""')
            pieces.append(f'"{escaped}"')
        else:
            # render floats without trailing zeros
            if isinstance(s, float) and s.is_integer():
                pieces.append(str(int(s)))
            else:
                pieces.append(str(s))
    return ",".join(pieces) + ")"


def parse_kid(path: Path) -> dict:
    """Parse a KIDS file. Returns {install_names: [...], builds: {name: {subs: value}}}.

    State machine matches XPDK2V1:
      BEGIN → KIDSSS → INSTLNM → ZERO → CONTENT → (loop back to INSTLNM on new build) → END.
    """
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        raw_lines = [_strip_cr(ln) for ln in fh]

    result = {"install_names": [], "builds": {}}
    state = "BEGIN"
    i = 0
    current_build: str | None = None

    while i < len(raw_lines):
        line = raw_lines[i]
        if state == "BEGIN":
            # Skip header preamble (first two lines per XPDK2V1 BEGIN state).
            i += 2
            state = "KIDSSS"
            continue
        if state == "KIDSSS":
            if not line.startswith("**KIDS**:"):
                i += 1
                continue
            payload = line[len("**KIDS**:"):]
            for name in payload.split("^"):
                if name:
                    result["install_names"].append(name)
                    result["builds"][name] = {}
            i += 1
            # skip optional blank line
            if i < len(raw_lines) and raw_lines[i] == "":
                i += 1
            state = "INSTLNM"
            continue
        if state == "INSTLNM":
            if not line.startswith("**INSTALL NAME**"):
                i += 1
                continue
            i += 1
            if i >= len(raw_lines):
                break
            current_build = raw_lines[i]
            if current_build not in result["builds"]:
                result["builds"][current_build] = {}
            i += 1
            state = "CONTENT"
            continue
        if state == "CONTENT":
            if line == "**END**":
                i += 1
                continue
            if line == "**INSTALL NAME**":
                state = "INSTLNM"
                continue
            if line.startswith("$END KID") or line.startswith("$END TXT"):
                i += 1
                continue
            if line.startswith("$KID") or line.startswith("$TXT"):
                i += 1
                continue
            if not SUBSCRIPT_RE.match(line):
                i += 1
                continue
            # Pair: subscript line + value line.
            if i + 1 >= len(raw_lines):
                break
            subs = _parse_subscript_line(line)
            value = raw_lines[i + 1]
            assert current_build is not None
            result["builds"][current_build][subs] = value
            i += 2
            continue
        i += 1

    return result


# ---------------------------------------------------------------------------
# Decomposer — port of XPDK2VC's per-component dispatcher
# ---------------------------------------------------------------------------

# Top-level KIDS sections that map to a single .zwr file (GENOUT in XPDK2VC).
SIMPLE_SECTIONS = {
    "BLD": "Build.zwr",
    "PKG": "Package.zwr",
    "VER": "KernelFMVersion.zwr",
    "PRE": "EnvironmentCheck.zwr",
    "INI": "PreInit.zwr",
    "INIT": "PostInstall.zwr",
    "MBREQ": "RequiredBuild.zwr",
    "QUES": "InstallQuestions.zwr",
    "TEMP": "TransportGlobal.zwr",
}

# Legal path-sanitization — XPDK2VC replaces these with "-".
UNSAFE_PATH_CHARS = re.compile(r'[\\/:!@#$%^&*()?<>" ]')


def _sanitize(name: str) -> str:
    return UNSAFE_PATH_CHARS.sub("-", name).strip("-") or "unnamed"


def _patch_descriptor_to_dir(desc: str) -> str:
    """VMTEST*1.0*1 → VMTEST_1.0_1 (XPDK2VC's PD4FS convention)."""
    return desc.replace("*", "_")


def canonicalize_routine_line2(line2: str) -> str:
    """Apply diff-stability transforms to a routine's ;; version line.

    XPDK2VC's fix: strip pieces 7+ (build number / "Build N").
    kids-vc's extension: also strip piece 4 (patch list) and piece 5 (date).

    Keeps: ;;VERSION;PACKAGE;;;
    Drops: ;;VERSION;PACKAGE;**20,27,48**;Apr 25, 1995;Build 3
    """
    parts = line2.split(";")
    # parts[0]="" parts[1]="" parts[2]=VERSION parts[3]=PACKAGE
    # parts[4]=**patches** parts[5]=date parts[6]=Build N ...
    if len(parts) < 4:
        return line2
    keep = parts[:4]
    keep.append("")  # piece 5 canonicalized to empty (patch list removed)
    keep.append("")  # piece 6 canonicalized to empty (build date removed)
    return ";".join(keep)


def _zwr_line(subs: tuple, value: str) -> str:
    """Render one subscript=value pair as a ZWR-format line."""
    # ZWR-style string literal: double-quote, escape embedded " as "".
    escaped = value.replace('"', '""')
    return f'{_format_subscript(subs)}="{escaped}"'


def _ien_substitute(subs: tuple, position: int, replacement: str = "IEN") -> tuple:
    """Replace the subscript at `position` with `replacement`.

    Per XPDK2VC's `SUBNAME` — stabilizes IEN-dependent subscripts so the
    same entity produces the same key across VistA instances.
    """
    if position >= len(subs):
        return subs
    return subs[:position] + (replacement,) + subs[position + 1:]


def decompose_build(build: dict, out_dir: Path) -> None:
    """Decompose one build's parsed data into per-component files under out_dir.

    MVP: NO IEN substitution — subscripts are preserved exactly. Diff-stability
    for line 2 of routines (canonicalization) IS applied. Phase 8b will add
    principled IEN substitution with round-trip-safe restoration.
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    # Bucket by top-level section.
    sections: dict[str, dict[tuple, str]] = {}
    for subs, value in build.items():
        section = subs[0] if subs and isinstance(subs[0], str) else "UNKNOWN"
        sections.setdefault(section, {})[subs] = value

    # Simple GENOUT-style sections → one .zwr each. No IEN substitution.
    for section, filename in SIMPLE_SECTIONS.items():
        if section not in sections:
            continue
        path = out_dir / filename
        with path.open("w", encoding="utf-8") as fh:
            for subs in sorted(sections[section], key=_sort_key):
                fh.write(_zwr_line(subs, sections[section][subs]) + "\n")

    # Routines: two files per routine (.header + .m) with line-2 canonicalization.
    # Plus a ROUTINES_INDEX.zwr for the ("RTN",) count and any other shape.
    if "RTN" in sections:
        rtn_dir = out_dir / "Routines"
        rtn_dir.mkdir(exist_ok=True)
        routines = _group_routines(sections["RTN"])
        # non-per-routine RTN subscripts (e.g. ("RTN",) count line)
        misc = {s: v for s, v in sections["RTN"].items() if len(s) < 2}
        if misc:
            with (rtn_dir / "_index.zwr").open("w", encoding="utf-8") as fh:
                for s in sorted(misc, key=_sort_key):
                    fh.write(_zwr_line(s, misc[s]) + "\n")
        for name, body in routines.items():
            header = body.get("header", "")
            (rtn_dir / f"{name}.header").write_text(header + "\n", encoding="utf-8")
            m_lines = []
            for line_no, content in sorted(body["lines"].items()):
                if line_no == 2:
                    content = canonicalize_routine_line2(content)
                m_lines.append(content)
            # Use "line\n" per line (empty file if no lines) so 0-line
            # routines round-trip correctly (don't phantom-produce an
            # empty line 1 on read-back).
            (rtn_dir / f"{name}.m").write_text(
                "".join(line + "\n" for line in m_lines), encoding="utf-8"
            )

    # ORD — ORD.zwr at top level (not per-file; ORD's structure is
    # ORD,<precedence>,<filenum>,0 and KIDS expects them together).
    if "ORD" in sections:
        with (out_dir / "ORD.zwr").open("w", encoding="utf-8") as fh:
            for subs in sorted(sections["ORD"], key=_sort_key):
                fh.write(_zwr_line(subs, sections["ORD"][subs]) + "\n")

    # KRN — per-file subdirectories containing FileHeader + per-entry files.
    if "KRN" in sections:
        # Split into file-headers, per-entry bodies, and cross-refs
        krn_by_file: dict[Any, dict[tuple, str]] = {}
        krn_non_numeric: dict[tuple, str] = {}  # e.g., ("KRN","B","OPTION",19)
        for subs, value in sections["KRN"].items():
            if len(subs) < 3:
                krn_non_numeric[subs] = value
                continue
            fnum = subs[1]
            if not isinstance(fnum, (int, float)):
                krn_non_numeric[subs] = value
                continue
            krn_by_file.setdefault(fnum, {})[subs] = value

        if krn_non_numeric:
            krn_dir = out_dir / "KRN"
            krn_dir.mkdir(exist_ok=True)
            with (krn_dir / "_misc.zwr").open("w", encoding="utf-8") as fh:
                for subs in sorted(krn_non_numeric, key=_sort_key):
                    fh.write(_zwr_line(subs, krn_non_numeric[subs]) + "\n")

        for fnum, file_contents in krn_by_file.items():
            file_name = _resolve_kernel_file_name(fnum, sections["KRN"])
            file_dir = out_dir / "KRN" / _sanitize(file_name)
            file_dir.mkdir(parents=True, exist_ok=True)

            # Headers: IEN=0 node + any non-integer-IEN cross-refs
            header_subs = {s: v for s, v in file_contents.items()
                           if len(s) >= 3 and
                              (s[2] == 0 or not isinstance(s[2], int))}
            if header_subs:
                with (file_dir / "FileHeader.zwr").open("w", encoding="utf-8") as fh:
                    for s in sorted(header_subs, key=_sort_key):
                        fh.write(_zwr_line(s, header_subs[s]) + "\n")

            # Per-entry groups (integer IEN > 0)
            by_ien: dict[int, dict[tuple, str]] = {}
            for subs, value in file_contents.items():
                if len(subs) < 3:
                    continue
                ien = subs[2]
                if not isinstance(ien, int) or ien == 0:
                    continue
                by_ien.setdefault(ien, {})[subs] = value

            # Names-first pass: derive an entry name per IEN, then detect
            # collisions and suffix with IEN for disambiguation. File 8989.5
            # (PARAMETER) is the canonical collision case — its zero-node
            # piece 1 is a storage spec (e.g. "516;DIC(9.4,") shared across
            # entries; the meaningful name lives in piece 2 (parameter name)
            # plus piece 3 (instance #). Collision fallback covers all such.
            def _entry_zero_node(ec: dict[tuple, str]) -> str:
                first_subs = next(iter(ec))
                zn = ec.get((*first_subs[:3], 0), "")
                if zn:
                    return zn
                for s, v in ec.items():
                    if len(s) == 4 and s[3] == 0:
                        return v
                return ""

            def _derive_name(ien: int, ec: dict[tuple, str]) -> str:
                zn = _entry_zero_node(ec)
                if not zn:
                    return f"ien-{ien}"
                # Heuristic: if piece 1 looks like a storage spec
                # (contains ";" and "(" and ends with ","), prefer piece 2.
                p = zn.split("^")
                if p and (";" in p[0] and "(" in p[0] and p[0].endswith(",")):
                    return p[1] if len(p) > 1 else p[0]
                return p[0]

            # Derive name per IEN, then check collisions on the SANITIZED
            # form (which is what becomes the filename). Two entries like
            # "LBRY FUNDING" and "LBRY FUNDING ??" both sanitize to
            # "LBRY-FUNDING" — would overwrite without this.
            sanitized_names: dict[int, str] = {
                ien: _sanitize(_derive_name(ien, ec))
                for ien, ec in by_ien.items()
            }
            name_counts: dict[str, int] = {}
            for n in sanitized_names.values():
                name_counts[n] = name_counts.get(n, 0) + 1

            for ien, entry_contents in by_ien.items():
                name = sanitized_names[ien]
                if name_counts[name] > 1:
                    name = f"{name}__ien{ien}"
                entry_file = file_dir / f"{name}.zwr"
                with entry_file.open("w", encoding="utf-8") as fh:
                    for s in sorted(entry_contents, key=_sort_key):
                        fh.write(_zwr_line(s, entry_contents[s]) + "\n")

    # FIA (FileMan file DD) — one DD.zwr per file, in Files/<num>+<name>/
    # Co-locate ^DD, ^DIC security, IX (indexes), KEY/KEYPTR, and PGL when present.
    # DATA + FRV* (seed data + reverse-value nodes) go to Data.zwr alongside.
    fia_files: dict[Any, str] = {}  # fnum → file name
    for subs, value in sections.get("FIA", {}).items():
        # The `("FIA", fnum)` bare node carries the name as its value.
        if len(subs) == 2:
            fia_files[subs[1]] = value

    fileman_sections = {"FIA", "^DD", "^DIC", "SEC", "UP", "IX", "KEY", "KEYPTR",
                         "PGL", "DATA", "FRV1", "FRVL", "FRV1K"}

    # Track which fileman-section subscripts we've consumed; unclaimed ones
    # must still be emitted (bug found at scale — some real patches have
    # SEC entries keyed by ("SEC","^DIC",fnum,...) where subs[1] is a
    # string, not a file number). Anything not consumed by per-file
    # decomposition gets written to a dedicated fallback file per section.
    consumed: set[tuple] = set()

    def _matches_file(subs: tuple, fnum: Any) -> bool:
        """Does this subs belong to file `fnum`? Scan positions 1 and 2 so
        we catch both `(SEC, fnum, ...)` and `(SEC, "^DIC", fnum, ...)`
        shapes commonly seen in real WorldVistA patches."""
        if len(subs) < 2:
            return False
        if subs[1] == fnum:
            return True
        if len(subs) >= 3 and subs[2] == fnum:
            return True
        return False

    if fia_files:
        files_root = out_dir / "Files"
        files_root.mkdir(exist_ok=True)
        for fnum, fname in fia_files.items():
            safe_name = _sanitize(fname) or f"file-{fnum}"
            file_dir = files_root / f"{fnum}+{safe_name}"
            file_dir.mkdir(exist_ok=True)
            dd_pairs: list[tuple[tuple, str]] = []
            data_pairs: list[tuple[tuple, str]] = []
            for section in fileman_sections:
                sec_data = sections.get(section, {})
                for subs in list(sec_data.keys()):
                    if not _matches_file(subs, fnum):
                        continue
                    target = data_pairs if section in ("DATA", "FRV1", "FRVL", "FRV1K") else dd_pairs
                    target.append((subs, sec_data[subs]))
                    consumed.add(subs)
            if dd_pairs:
                with (file_dir / "DD.zwr").open("w", encoding="utf-8") as fh:
                    for s, v in sorted(dd_pairs, key=lambda kv: _sort_key(kv[0])):
                        fh.write(_zwr_line(s, v) + "\n")
                _extract_dd_code(dd_pairs, file_dir / "DD-code")
            if data_pairs:
                with (file_dir / "Data.zwr").open("w", encoding="utf-8") as fh:
                    for s, v in sorted(data_pairs, key=lambda kv: _sort_key(kv[0])):
                        fh.write(_zwr_line(s, v) + "\n")

    # Unclaimed fileman-section entries — patches reference files not
    # in their own FIA set (common when patching another package's file
    # shared-ownership). Emit under Files/_unclaimed.zwr so nothing is lost.
    unclaimed_fm: list[tuple[tuple, str]] = []
    for section in fileman_sections:
        for subs, value in sections.get(section, {}).items():
            if subs not in consumed:
                unclaimed_fm.append((subs, value))
    if unclaimed_fm:
        files_root = out_dir / "Files"
        files_root.mkdir(exist_ok=True)
        with (files_root / "_unclaimed.zwr").open("w", encoding="utf-8") as fh:
            for s, v in sorted(unclaimed_fm, key=lambda kv: _sort_key(kv[0])):
                fh.write(_zwr_line(s, v) + "\n")

    # Catch-all for any TOP-LEVEL section we don't recognize at all.
    known = set(SIMPLE_SECTIONS.keys()) | {"RTN", "ORD", "KRN"} | fileman_sections
    unknown_sections = set(sections.keys()) - known
    if unknown_sections:
        misc = out_dir / "_misc.zwr"
        with misc.open("w", encoding="utf-8") as fh:
            for section in sorted(unknown_sections):
                for s in sorted(sections[section], key=_sort_key):
                    fh.write(_zwr_line(s, sections[section][s]) + "\n")


def _sort_key(subs: tuple) -> tuple:
    """Stable sort key tolerating mixed str/int subscripts."""
    return tuple((type(s).__name__, s) for s in subs)


def _group_routines(rtn_section: dict[tuple, str]) -> dict[str, dict]:
    """Group RTN subscripts by routine name."""
    routines: dict[str, dict] = {}
    for subs, value in rtn_section.items():
        # Shapes: ("RTN",) | ("RTN", name) | ("RTN", name, n, 0)
        if len(subs) < 2:
            continue
        name = subs[1]
        r = routines.setdefault(name, {"header": "", "lines": {}})
        if len(subs) == 2:
            r["header"] = value
        elif len(subs) == 4:
            r["lines"][subs[2]] = value
    return routines


def _group_krn_entries(krn_section: dict[tuple, str]) -> dict[tuple, list[tuple]]:
    """Group KRN subscripts by (file_number, ien). Mirrors XPDK2VC's
    `F IEN=0:0 S IEN=$O(...) Q:'IEN` — IEN=0 is the file header, skipped
    from per-entry export (goes into FileHeader.zwr instead)."""
    groups: dict[tuple, list[tuple]] = {}
    for subs in krn_section:
        if len(subs) < 3:
            continue
        fnum, ien = subs[1], subs[2]
        if not isinstance(ien, int) or ien == 0:
            continue
        groups.setdefault((fnum, ien), []).append(subs)
    return groups


def _krn_file_headers(krn_section: dict[tuple, str]) -> dict[Any, dict[tuple, str]]:
    """Return {fnum: {subs: value}} for file-header nodes (IEN=0 and B-xref)."""
    out: dict[Any, dict[tuple, str]] = {}
    for subs, value in krn_section.items():
        if len(subs) < 3:
            continue
        fnum, ien = subs[1], subs[2]
        if isinstance(ien, int) and ien == 0:
            out.setdefault(fnum, {})[subs] = value
        elif not isinstance(ien, int):
            # cross-references like "B" index
            out.setdefault(fnum, {})[subs] = value
    return out


# Well-known FileMan file-number → presentable name map.
# Covers the files commonly referenced in KIDS KRN/FIA sections.
# Source: FileMan DD conventions + VistA package namespaces.
WELL_KNOWN_FILES: dict[float | int, str] = {
    # Kernel UI
    0.4: "PRINT-TEMPLATE",
    0.401: "SORT-TEMPLATE",
    0.402: "INPUT-TEMPLATE",
    0.403: "FORM",
    0.404: "BLOCK",
    # Kernel core
    3.7: "DEVICE",
    3.8: "MAIL-GROUP",
    3.9: "MAIL-MESSAGE",
    9.2: "HELP-FRAME",
    9.4: "PACKAGE",
    9.6: "KIDS-BUILD",
    9.7: "KIDS-INSTALL",
    9.8: "ROUTINE",
    19: "OPTION",
    19.1: "SECURITY-KEY",
    19.2: "OPTION-SCHEDULING",
    # OE/RR / CPRS
    100: "ORDER",
    101: "PROTOCOL",
    101.41: "DIALOG",
    # Person / registration
    200: "NEW-PERSON",
    2: "PATIENT",
    # HL7
    771: "HL7-APPLICATION",
    870: "HL-LOGICAL-LINK",
    871: "HL-FILE-EVENT",
    872: "HL-LOWER-LEVEL-PROTOCOL",
    # Parameters
    8989.51: "PARAMETER-DEFINITION",
    8989.52: "PARAMETER-TEMPLATE",
    # RPCs
    8993: "RPC-BROKER-SUBSCRIBER",
    8994: "REMOTE-PROCEDURE",
}


def _extract_dd_code(dd_pairs: list[tuple[tuple, str]], out_dir: Path) -> None:
    """Extract MUMPS code embedded in ^DD nodes as per-field .m annotation files.

    DD-embedded MUMPS lives in four places:
    - `^DD(file, field, 0)` piece 5   → input transform
    - `^DD(file, field, 9)`           → computed-field expression
    - `^DD(file, field, 1, xref, 1)`  → cross-reference SET logic
    - `^DD(file, field, 1, xref, 2)`  → cross-reference KILL logic

    Emits `<field>.<kind>.m` files — one per non-trivial code piece.
    These are informational; DD.zwr remains authoritative for round-trip.

    A code piece is "trivial" if it's empty, bare "Q", bare ";", or
    a single-char noop — we skip those to avoid noise.
    """
    emitted: list[Path] = []
    out_dir_created = False

    def _is_trivial(code: str) -> bool:
        c = code.strip()
        return c in ("", "Q", "K", "D", ";") or (len(c) <= 2 and not any(ch in c for ch in "=<>+-_"))

    def _emit(field: Any, kind: str, code: str) -> None:
        nonlocal out_dir_created
        if _is_trivial(code):
            return
        if not out_dir_created:
            out_dir.mkdir(parents=True, exist_ok=True)
            out_dir_created = True
        safe_field = _sanitize(str(field)) or "unnamed"
        path = out_dir / f"{safe_field}.{kind}.m"
        path.write_text(code + "\n", encoding="utf-8")
        emitted.append(path)

    # FileMan DD piece-2 type codes that identify a field 0-node.
    # Includes compound codes (RF = required free text, RFX = required free
    # text with MUMPS transform, FJ5 = free text justified 5, etc.).
    FIELD_TYPE_RE = re.compile(r'^[A-Z][A-Z0-9]*$')

    def _is_field_zero_node(subs: tuple, value: str) -> bool:
        """A field 0-node has subs[-1]==0 and its value starts with
        NAME^TYPE^... where TYPE is an uppercase type code."""
        if subs[-1] != 0 or len(subs) < 4:
            return False
        pieces = value.split("^")
        if len(pieces) < 5:
            return False
        type_code = pieces[1]
        # strip trailing quote-rule marker like ' and suffix digits
        type_clean = re.match(r"^[A-Z]+", type_code)
        return bool(type_clean)

    for subs, value in dd_pairs:
        if len(subs) < 2 or subs[0] != "^DD":
            continue

        # Field zero-node (definition). Works for both top-level and subfile.
        if _is_field_zero_node(subs, value):
            field_pretty = ".".join(str(s) for s in subs[2:-1])
            pieces = value.split("^")
            field_type = pieces[1]
            if field_type.startswith("C"):
                # Computed field — join pieces 5+ to preserve caret-refs.
                code = "^".join(pieces[4:])
                _emit(field_pretty, "computed", code)
            elif pieces[4]:
                _emit(field_pretty, "input-transform", pieces[4])
            continue

        # Cross-reference code: (^DD, ..., field, 1, xref_ien, {1,2})
        # Last 3 subscripts are (1, xref_ien, code_kind).
        if (len(subs) >= 6 and subs[-1] in (1, 2)
                and isinstance(subs[-2], int) and subs[-2] > 0
                and subs[-3] == 1):
            kind = "xref-set" if subs[-1] == 1 else "xref-kill"
            xref_ien = subs[-2]
            field_pretty = ".".join(str(s) for s in subs[2:-3])
            _emit(f"{field_pretty}.xref-{xref_ien}", kind, value)
            continue

        # Computed-field word-processing code: (^DD, ..., field, 9, N, 0)
        if (len(subs) >= 6 and subs[-1] == 0 and isinstance(subs[-2], int)
                and subs[-3] == 9):
            field_pretty = ".".join(str(s) for s in subs[2:-3])
            _emit(field_pretty, "computed-wp", value)
            continue

    # Write an index so readers know what was extracted
    if emitted:
        index = out_dir / "_README.md"
        index.write_text(
            "# DD-embedded MUMPS code annotations\n\n"
            "These `.m` files are EXTRACTIONS of MUMPS code found inside the\n"
            "FileMan ^DD nodes in `../DD.zwr`. They are **informational** —\n"
            "`DD.zwr` is authoritative for KIDS round-trip.\n\n"
            "Use these files to diff / blame / review the embedded code in a\n"
            "human-readable form. Any change you want reflected in the KIDS\n"
            "build must be made in the DD.zwr source (the assembler only\n"
            "reads DD.zwr).\n\n"
            "Filename convention: `<field>.<kind>.m` where kind ∈\n"
            "{input-transform, computed, xref-set, xref-kill}.\n",
            encoding="utf-8"
        )


def _resolve_kernel_file_name(fnum: Any, krn_section: dict[tuple, str] | None = None) -> str:
    """Map a file number to a presentable directory name.

    Exact match against WELL_KNOWN_FILES. Falls back to `file-<n>`.
    KIDS sections don't ship the FileMan file name; we'd have to look it
    up in the real FileMan DD, which isn't in the KIDS file itself.
    """
    if fnum in WELL_KNOWN_FILES:
        return WELL_KNOWN_FILES[fnum]
    return f"file-{fnum}"


# ---------------------------------------------------------------------------
# Assembler — reverse direction (per-component files → .KID text)
# ---------------------------------------------------------------------------

def assemble_build(in_dir: Path, install_name: str) -> list[tuple[tuple, str]]:
    """Read per-component files under in_dir and reconstruct (subs, value) pairs.

    MVP: no IEN substitution, so no IEN restoration needed.
    """
    pairs: list[tuple[tuple, str]] = []

    def _read_zwr(path: Path) -> list[tuple[tuple, str]]:
        rows = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            subs, value = _parse_zwr_line(line)
            rows.append((subs, value))
        return rows

    # Simple sections
    for section, filename in SIMPLE_SECTIONS.items():
        path = in_dir / filename
        if path.exists():
            pairs.extend(_read_zwr(path))

    # Routines: _index.zwr (for ("RTN",) count etc.) + per-routine .header+.m
    rtn_dir = in_dir / "Routines"
    if rtn_dir.exists():
        idx_path = rtn_dir / "_index.zwr"
        if idx_path.exists():
            pairs.extend(_read_zwr(idx_path))
        for m_path in sorted(rtn_dir.glob("*.m")):
            name = m_path.stem
            header_path = rtn_dir / f"{name}.header"
            header = header_path.read_text(encoding="utf-8").rstrip("\n") if header_path.exists() else ""
            pairs.append((("RTN", name), header))
            m_lines = m_path.read_text(encoding="utf-8").splitlines()
            for idx, content in enumerate(m_lines, start=1):
                pairs.append((("RTN", name, idx, 0), content))

    # ORD (top-level, single file)
    ord_path = in_dir / "ORD.zwr"
    if ord_path.exists():
        pairs.extend(_read_zwr(ord_path))

    # KRN
    krn_root = in_dir / "KRN"
    if krn_root.exists():
        misc_path = krn_root / "_misc.zwr"
        if misc_path.exists():
            pairs.extend(_read_zwr(misc_path))
        for file_dir in sorted(krn_root.iterdir()):
            if not file_dir.is_dir():
                continue
            hdr = file_dir / "FileHeader.zwr"
            if hdr.exists():
                pairs.extend(_read_zwr(hdr))
            for entry_path in sorted(file_dir.glob("*.zwr")):
                if entry_path.name in ("FileHeader.zwr",):
                    continue
                pairs.extend(_read_zwr(entry_path))

    # FIA (FileMan files) — Files/<num>+<name>/DD.zwr + Data.zwr
    # Plus Files/_unclaimed.zwr for entries not assignable to any file.
    files_root = in_dir / "Files"
    if files_root.exists():
        unclaimed = files_root / "_unclaimed.zwr"
        if unclaimed.exists():
            pairs.extend(_read_zwr(unclaimed))
        for file_dir in sorted(files_root.iterdir()):
            if not file_dir.is_dir():
                continue
            dd = file_dir / "DD.zwr"
            if dd.exists():
                pairs.extend(_read_zwr(dd))
            data = file_dir / "Data.zwr"
            if data.exists():
                pairs.extend(_read_zwr(data))

    # Catch-all misc
    misc_path = in_dir / "_misc.zwr"
    if misc_path.exists():
        pairs.extend(_read_zwr(misc_path))

    return pairs


def _parse_zwr_line(line: str) -> tuple[tuple, str]:
    """Parse a ZWR line like `"BLD",1,0)="..."` into (subs, value)."""
    paren = line.index(")=")
    subs_text = line[:paren + 1]
    value_text = line[paren + 2:]
    subs = _parse_subscript_line(subs_text)
    if value_text.startswith('"') and value_text.endswith('"'):
        inner = value_text[1:-1].replace('""', '"')
        return subs, inner
    return subs, value_text


def _ien_restore(subs: tuple, placeholder: str, restore: int) -> tuple:
    return tuple(restore if s == placeholder else s for s in subs)


def write_kid(install_names: list[str], builds_pairs: dict[str, list[tuple[tuple, str]]],
              out_path: Path) -> None:
    """Serialize builds back to KIDS text format."""
    lines = [
        "KIDS Distribution saved by kids_vc.py",
        "kids-vc reassembled output",
        f"**KIDS**:{'^'.join(install_names)}^",
        "",
    ]
    for name in install_names:
        lines.append("**INSTALL NAME**")
        lines.append(name)
        for subs, value in builds_pairs.get(name, []):
            lines.append(_format_subscript(subs))
            lines.append(value)
    lines.append("**END**")
    lines.append("**END**")
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Round-trip comparison
# ---------------------------------------------------------------------------

def _canonical_pairs(build: dict) -> list[tuple[tuple, str]]:
    """Canonicalize a parsed build for comparison: apply the same transforms
    decompose applies, so round-trip equality is after canonicalization."""
    out: list[tuple[tuple, str]] = []
    for subs, value in sorted(build.items(), key=lambda kv: _sort_key(kv[0])):
        if len(subs) >= 4 and subs[0] == "RTN" and subs[2] == 2 and subs[3] == 0:
            value = canonicalize_routine_line2(value)
        out.append((subs, value))
    return out


def roundtrip(kid_path: Path) -> int:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        decomp_dir = tmp_dir / "decomposed"
        reassembled = tmp_dir / "reassembled.kid"

        parsed1 = parse_kid(kid_path)
        for name, build in parsed1["builds"].items():
            decompose_build(build, decomp_dir / _patch_descriptor_to_dir(name) / "KIDComponents")

        builds_pairs = {}
        for name in parsed1["install_names"]:
            build_dir = decomp_dir / _patch_descriptor_to_dir(name) / "KIDComponents"
            builds_pairs[name] = assemble_build(build_dir, name)

        write_kid(parsed1["install_names"], builds_pairs, reassembled)
        parsed2 = parse_kid(reassembled)

        canon1 = {name: _canonical_pairs(b) for name, b in parsed1["builds"].items()}
        canon2 = {name: _canonical_pairs(b) for name, b in parsed2["builds"].items()}

        if canon1 == canon2:
            print(f"roundtrip OK: {kid_path.name}")
            print(f"  builds:     {len(parsed1['builds'])}")
            print(f"  pairs:      {sum(len(b) for b in parsed1['builds'].values())}")
            print(f"  canonicalized equality verified")
            return 0
        # Diff report
        print(f"roundtrip FAIL: {kid_path.name}", file=sys.stderr)
        for name in parsed1["install_names"]:
            a = canon1.get(name, [])
            b = canon2.get(name, [])
            if a != b:
                print(f"  build {name}: {len(a)} → {len(b)} pairs", file=sys.stderr)
                for x, y in zip(a, b):
                    if x != y:
                        print(f"    - {x!r}", file=sys.stderr)
                        print(f"    + {y!r}", file=sys.stderr)
                        break
        return 1


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _cmd_parse(args: argparse.Namespace) -> int:
    p = parse_kid(Path(args.kid_file))
    print(f"install_names: {p['install_names']}")
    for name, build in p["builds"].items():
        print(f"  build {name}: {len(build)} subscripts")
        sections: dict[str, int] = {}
        for subs in build:
            sec = subs[0] if subs else "UNKNOWN"
            sections[sec] = sections.get(sec, 0) + 1
        for sec, cnt in sorted(sections.items()):
            print(f"    {sec:<8} {cnt}")
    return 0


def _cmd_decompose(args: argparse.Namespace) -> int:
    out = Path(args.output_dir)
    if out.exists():
        shutil.rmtree(out)
    parsed = parse_kid(Path(args.kid_file))
    for name, build in parsed["builds"].items():
        decompose_build(build, out / _patch_descriptor_to_dir(name) / "KIDComponents")
    print(f"decomposed to {out}")
    return 0


def _cmd_assemble(args: argparse.Namespace) -> int:
    in_dir = Path(args.input_dir)
    out = Path(args.output_kid)
    install_names = []
    builds_pairs: dict[str, list[tuple[tuple, str]]] = {}
    for build_dir in sorted(in_dir.iterdir()):
        if not build_dir.is_dir():
            continue
        kid_components = build_dir / "KIDComponents"
        if not kid_components.exists():
            continue
        # recover install name from directory name (e.g., VMTEST_1.0_1 → VMTEST*1.0*1)
        name_parts = build_dir.name.split("_")
        if len(name_parts) >= 3:
            install_name = f"{name_parts[0]}*{'.'.join(name_parts[1:-1])}*{name_parts[-1]}"
        else:
            install_name = build_dir.name
        install_names.append(install_name)
        builds_pairs[install_name] = assemble_build(kid_components, install_name)
    write_kid(install_names, builds_pairs, out)
    print(f"assembled {out}")
    return 0


def _cmd_roundtrip(args: argparse.Namespace) -> int:
    return roundtrip(Path(args.kid_file))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="kids-vc — KIDS version control tool")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("parse", help="Parse a .KID file and summarize")
    sp.add_argument("kid_file")
    sp.set_defaults(fn=_cmd_parse)

    sd = sub.add_parser("decompose", help="Split .KID into per-component files")
    sd.add_argument("kid_file")
    sd.add_argument("output_dir")
    sd.set_defaults(fn=_cmd_decompose)

    sa = sub.add_parser("assemble", help="Reassemble per-component files to .KID")
    sa.add_argument("input_dir")
    sa.add_argument("output_kid")
    sa.set_defaults(fn=_cmd_assemble)

    sr = sub.add_parser("roundtrip", help="decompose → assemble → compare")
    sr.add_argument("kid_file")
    sr.set_defaults(fn=_cmd_roundtrip)

    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
