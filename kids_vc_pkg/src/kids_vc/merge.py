"""ZWR 3-way merge — re-export from host/scripts/zwr_merge.py."""

from __future__ import annotations

from importlib import util as _importlib_util
from pathlib import Path


def _find_impl() -> Path:
    cur = Path(__file__).resolve().parent
    vendored = cur / "_vendored" / "zwr_merge.py"
    if vendored.exists():
        return vendored
    for _ in range(8):
        candidate = cur / "host" / "scripts" / "zwr_merge.py"
        if candidate.exists():
            return candidate
        cur = cur.parent
    raise ImportError("zwr_merge.py source not found")


_impl_path = _find_impl()
_spec = _importlib_util.spec_from_file_location("_zwr_merge_impl", _impl_path)
_impl = _importlib_util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_impl)

merge = _impl.merge
main = _impl.main


if __name__ == "__main__":
    import sys
    sys.exit(main())
