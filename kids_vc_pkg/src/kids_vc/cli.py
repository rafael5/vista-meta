"""CLI entry point — thin wrapper over the implementation's main()."""

from __future__ import annotations

import sys

from ._impl import _main


def main() -> int:
    return _main(sys.argv[1:])


if __name__ == "__main__":
    sys.exit(main())
