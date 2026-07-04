#!/usr/bin/env python3
"""Dead-link gate for the docs tree.

Two surfaces, both must be clean:
1. Markdown relative links in CLAUDE.md, README.md, TODO.md, docs/**/*.md —
   every non-URL target must exist on disk (anchors stripped).
2. Code citations (`# Spec: docs/...` / `# Plan: docs/...`) across the build
   surface — the cited doc path must exist relative to the repo root.

Exit 0 = clean; exit 1 = prints every dead reference. Run via `make docs-check`.
"""

from __future__ import annotations

import re
import sys
from urllib.parse import unquote
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Runtime-generated trees (gitignored; synced from the container). Docs may
# legitimately link into them: verify the target when the tree exists locally,
# skip when it doesn't (e.g. a clean CI checkout — the link is "pending sync",
# not dead).
RUNTIME_ROOTS = [ROOT / "vista" / "vista-m-host"]

MD_LINK = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)\)")
CITE = re.compile(r"[#;]\s*(?:Spec|Plan):\s*(docs/[A-Za-z0-9/_.\-]+\.md)")

# Code surfaces that carry `# Spec:` / `# Plan:` provenance headers.
CITE_GLOBS = [
    "host/scripts/*.py",
    "bin/*",
    "docker/*",
    "vista/dev-r/*.m",
    "vista/scripts/**/*",
    "tests/**/*",
    "Makefile",
    ".env.example",
    ".gitignore",
]


def md_files() -> list[Path]:
    files = [ROOT / "CLAUDE.md", ROOT / "README.md", ROOT / "TODO.md"]
    files += sorted((ROOT / "docs").rglob("*.md"))
    return [f for f in files if f.is_file()]


def check_markdown() -> list[str]:
    errors = []
    r_exists_cache: dict[int, bool] = {}
    for f in md_files():
        for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            for target in MD_LINK.findall(line):
                if target.startswith(("http://", "https://", "mailto:", "#", "~", "<")):
                    continue
                path = unquote(target.split("#", 1)[0])
                if not path:
                    continue
                if path.startswith("/"):  # container-absolute paths in ADRs — not repo files
                    continue
                resolved = (f.parent / path).resolve()
                if any(r in resolved.parents or resolved == r for r in RUNTIME_ROOTS):
                    if not r_exists_cache.setdefault(0, RUNTIME_ROOTS[0].exists()):
                        continue
                if not resolved.exists():
                    errors.append(f"{f.relative_to(ROOT)}:{n} → {target}")
    return errors


def check_citations() -> list[str]:
    errors = []
    seen: set[Path] = set()
    for pattern in CITE_GLOBS:
        for f in ROOT.glob(pattern):
            if not f.is_file() or f in seen or f.stat().st_size > 2_000_000:
                continue
            seen.add(f)
            try:
                text = f.read_text(encoding="utf-8")
            except (UnicodeDecodeError, PermissionError):
                continue
            for n, line in enumerate(text.splitlines(), 1):
                for cited in CITE.findall(line):
                    if not (ROOT / cited).is_file():
                        errors.append(f"{f.relative_to(ROOT)}:{n} → {cited}")
    return errors


def main() -> int:
    md = check_markdown()
    cites = check_citations()
    for label, errs in (("markdown links", md), ("code citations", cites)):
        if errs:
            print(f"DEAD {label} ({len(errs)}):")
            for e in errs:
                print(f"  {e}")
    if md or cites:
        return 1
    print("docs-check: clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
