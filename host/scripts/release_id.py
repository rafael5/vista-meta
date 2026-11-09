#!/usr/bin/env python3
# ADR-047: the data release — schema_version 1, tagged releases.

"""The data release this tree is cut as — the only place its tag lives.

The tag's major number follows the schema (ADR-047: a column change is
a v2 break); a re-extraction under the same schema takes a minor number
(data-v1 → data-v1.1). Each release keeps its own in-repo records, so
earlier records stay byte-identical to their published assets.

`python3 host/scripts/release_id.py` prints the tag, for the Makefile.
"""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

TAG = "data-v1"
ARTIFACT = "vista-meta-data"
STEM = f"{ARTIFACT}-{TAG.removeprefix('data-')}"   # vista-meta-data-v1

RELEASES_DIR = PROJECT_ROOT / "docs/releases"
RECORD_JSON = RELEASES_DIR / f"{TAG}.manifest.json"
PEERS_JSON = RELEASES_DIR / f"{TAG}-peers.json"
DERIVED_JSON = RELEASES_DIR / f"{TAG}-derived.json"

if __name__ == "__main__":
    print(TAG)
