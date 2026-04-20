"""kids-vc — version-control tool for VistA KIDS distribution files.

Public API re-exported from the underlying implementation. The source-of-
truth modules live in `host/scripts/kids_vc.py` and `host/scripts/
zwr_merge.py` in the vista-meta project; this package vendors them by
path-insert so there's no code duplication.

Usage:
  from kids_vc import parse_kid, decompose_build, canonicalize_iens
  from kids_vc.merge import merge as zwr_merge

Or via CLI:
  kids-vc parse <kid>
  kids-vc decompose <kid> <dir>
  kids-vc assemble <dir> <kid>
  kids-vc roundtrip <kid>
  kids-vc canonicalize <decomposed-dir>

  kids-vc-merge <base> <ours> <theirs>   (git merge driver)
"""

from __future__ import annotations

__version__ = "0.1.0"

from ._impl import (
    parse_kid,
    decompose_build,
    assemble_build,
    canonicalize_iens,
    canonicalize_routine_line2,
    roundtrip,
    WELL_KNOWN_FILES,
    # Private helpers — needed by kids_vc.merge (zwr_merge imports these)
    _parse_zwr_line,
    _format_subscript,
    _zwr_line,
    _sort_key,
)

__all__ = [
    "__version__",
    "parse_kid",
    "decompose_build",
    "assemble_build",
    "canonicalize_iens",
    "canonicalize_routine_line2",
    "roundtrip",
    "WELL_KNOWN_FILES",
]
