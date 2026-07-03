#!/usr/bin/env python3
# V5 of the producer-contracts plan: the data fingerprint.
# Plan: docs/proposals/producer-contracts-implementation-plan.md § V5

"""Compute the schema_version 1 content_hash (data identity).

Normative recipe (plan § V5 — the recipe is the contract, F13):
content_hash = sha256 over the LF-joined lines
"<filename>\t<sha256(file-bytes)>", filenames included and sorted
bytewise. Scope = the 24 data TSVs of schema_v1 ONLY — the typed
column manifest, fidelity.json and manifest.json are excluded, so a
meta-only correction does not move data identity (bundle-level
integrity is bundle_sha256's job, V7).

Mirrors vdocs' corpus_content_hash role: two emissions with equal
content_hash carry byte-identical data. Computed on demand, never
persisted standalone — V7 embeds it in manifest.json.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import schema_v1

PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXPORT_DIR = PROJECT_ROOT / "vista/export"


def manifest_lines(files: dict[str, bytes]) -> list[str]:
    """The recipe's per-file lines, bytewise-sorted by filename."""
    return [f"{name}\t{hashlib.sha256(files[name]).hexdigest()}"
            for name in sorted(files)]


def content_hash(files: dict[str, bytes]) -> str:
    joined = "\n".join(manifest_lines(files))
    return hashlib.sha256(joined.encode("ascii")).hexdigest()


def read_data_tsvs(export_dir: Path) -> dict[str, bytes]:
    """The 24 in-scope files; a missing file is an error, not a skip."""
    return {name: (export_dir / spec.model / name).read_bytes()
            for name, spec in schema_v1.FILES.items()}


def compute(export_dir: Path) -> str:
    return content_hash(read_data_tsvs(export_dir))


def main(argv: list[str]) -> int:
    if argv == ["--lines"]:
        for line in manifest_lines(read_data_tsvs(EXPORT_DIR)):
            print(line)
        return 0
    print(compute(EXPORT_DIR))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
