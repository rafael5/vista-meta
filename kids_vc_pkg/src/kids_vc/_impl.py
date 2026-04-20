"""Implementation re-export from host/scripts/kids_vc.py.

Finds the source-of-truth module by walking up from this package's
install location. Works in editable install (pip install -e .) where
the parent vista-meta repo is accessible, and in source checkouts.

For pip install from a sdist/wheel, the source is vendored into this
package (see build step in pyproject.toml).
"""

from __future__ import annotations

import sys
from importlib import util as _importlib_util
from pathlib import Path


def _find_impl() -> Path:
    """Locate kids_vc.py source-of-truth. Search order:
    1. Vendored next to this file (for wheel installs)
    2. Upward from this file looking for host/scripts/kids_vc.py
    3. Error with diagnostic
    """
    vendored = Path(__file__).parent / "_vendored" / "kids_vc.py"
    if vendored.exists():
        return vendored
    # Walk up to find host/scripts/kids_vc.py
    cur = Path(__file__).resolve().parent
    for _ in range(8):
        candidate = cur / "host" / "scripts" / "kids_vc.py"
        if candidate.exists():
            return candidate
        cur = cur.parent
    raise ImportError(
        "Could not locate kids_vc.py source. "
        "Expected either _vendored/kids_vc.py alongside this package, or "
        "a parent directory containing host/scripts/kids_vc.py."
    )


_impl_path = _find_impl()
_spec = _importlib_util.spec_from_file_location("_kids_vc_impl", _impl_path)
_impl = _importlib_util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_impl)

# Re-export public API
parse_kid = _impl.parse_kid
decompose_build = _impl.decompose_build
assemble_build = _impl.assemble_build
canonicalize_iens = _impl.canonicalize_iens
canonicalize_routine_line2 = _impl.canonicalize_routine_line2
roundtrip = _impl.roundtrip
WELL_KNOWN_FILES = _impl.WELL_KNOWN_FILES
_main = _impl.main  # for the CLI entry point

# Re-export private helpers that zwr_merge needs (it imports from kids_vc)
_parse_zwr_line = _impl._parse_zwr_line
_format_subscript = _impl._format_subscript
_zwr_line = _impl._zwr_line
_sort_key = _impl._sort_key
