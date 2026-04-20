#!/usr/bin/env python3
# Corpus round-trip harness for kids_vc.py.
# Phase 8f: validate kids-vc against every .KID file in WorldVistA/VistA master.
# Spec: docs/kids-vc-guide.md §6.3

"""Fetch every .KID file from WorldVistA/VistA master and run kids_vc.roundtrip.

Reports pass/fail stats + first N failures with details so you know
exactly which real-world patches surface edge cases kids-vc doesn't
yet handle.

Usage:
  fetch_kids_corpus.py                          # fetch + test (default cache: /tmp/kids-corpus)
  fetch_kids_corpus.py --cache-dir DIR          # custom cache directory
  fetch_kids_corpus.py --max-fail-samples N     # how many failure details to print
  fetch_kids_corpus.py --limit N                # only try first N files (quick check)
  fetch_kids_corpus.py --no-fetch               # use cached files only, skip download

Outputs a report TSV at <cache-dir>/results.tsv with one row per file:
  path<TAB>status<TAB>subscripts<TAB>error

Network: one GitHub API request (tree listing) + N raw.githubusercontent.com
fetches per .KID. Raw fetches aren't rate-limited; only the API call is.
Cache dir is populated on first run; subsequent runs reuse unless --fresh.
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

_here = Path(__file__).resolve().parent
sys.path.insert(0, str(_here))
import kids_vc  # noqa: E402

GITHUB_TREE_API = (
    "https://api.github.com/repos/WorldVistA/VistA/git/trees/master?recursive=1"
)
RAW_PREFIX = "https://raw.githubusercontent.com/WorldVistA/VistA/master/"

USER_AGENT = "kids-vc-corpus-harness/0.1"


def _http_get(url: str, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def list_kid_paths() -> list[str]:
    """Query GitHub's tree API and return all paths ending in .KID or .kid."""
    print(f"[1/3] Listing repository tree via GitHub API...", flush=True)
    raw = _http_get(GITHUB_TREE_API)
    data = json.loads(raw)
    if data.get("truncated"):
        print("  WARNING: tree listing is truncated (>100k entries). "
              "Results may be incomplete.", file=sys.stderr)
    paths = [
        entry["path"]
        for entry in data.get("tree", [])
        if entry.get("type") == "blob"
        and (entry["path"].lower().endswith(".kid")
             or entry["path"].lower().endswith(".kids"))
    ]
    print(f"  Found {len(paths):,} .KID files in master tree.")
    return paths


def cache_path_for(path: str, cache_dir: Path) -> Path:
    """Deterministic cache filename — flattens the repo path to a safe name."""
    # Replace slashes and spaces to keep filesystem-friendly
    safe = path.replace("/", "_").replace(" ", "-")
    return cache_dir / safe


def fetch_to_cache(paths: list[str], cache_dir: Path, fetch: bool) -> list[Path]:
    """Ensure each path is downloaded. Returns list of local paths in order."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    local_paths: list[Path] = []
    fetched = 0
    cached = 0
    failed = 0
    for i, path in enumerate(paths, start=1):
        local = cache_path_for(path, cache_dir)
        if local.exists() and local.stat().st_size > 0:
            local_paths.append(local)
            cached += 1
            continue
        if not fetch:
            # Skip missing files when --no-fetch
            failed += 1
            continue
        url = RAW_PREFIX + urllib.parse.quote(path)
        try:
            content = _http_get(url)
            local.write_bytes(content)
            local_paths.append(local)
            fetched += 1
        except urllib.error.URLError as e:
            print(f"  fetch failed: {path} — {e}", file=sys.stderr)
            failed += 1
        if i % 50 == 0:
            print(f"  [{i}/{len(paths)}] fetched={fetched} cached={cached} "
                  f"failed={failed}", flush=True)
    print(f"[2/3] Download: {fetched} fetched, {cached} from cache, "
          f"{failed} failed.")
    return local_paths


def run_roundtrip(local_path: Path) -> tuple[str, int, str]:
    """Return (status, subscript_count, error_text).

    status ∈ {"PASS", "PARSE_FAIL", "ROUNDTRIP_FAIL", "EXCEPTION"}
    """
    # Capture stdout/stderr to avoid spam
    buf = io.StringIO()
    orig_stdout, orig_stderr = sys.stdout, sys.stderr
    sys.stdout = sys.stderr = buf
    try:
        try:
            parsed = kids_vc.parse_kid(local_path)
        except Exception as e:
            return "PARSE_FAIL", 0, f"{type(e).__name__}: {e}"
        subs_count = sum(len(b) for b in parsed["builds"].values())
        try:
            rc = kids_vc.roundtrip(local_path)
        except Exception as e:
            tb = traceback.format_exc(limit=3)
            return "EXCEPTION", subs_count, f"{type(e).__name__}: {e}\n{tb}"
        if rc == 0:
            return "PASS", subs_count, ""
        output = buf.getvalue()
        return "ROUNDTRIP_FAIL", subs_count, output[-500:]
    finally:
        sys.stdout, sys.stderr = orig_stdout, orig_stderr


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--cache-dir", type=Path, default=Path("/tmp/kids-corpus"))
    p.add_argument("--max-fail-samples", type=int, default=5)
    p.add_argument("--limit", type=int, default=0,
                   help="only test the first N files (0 = no limit)")
    p.add_argument("--no-fetch", action="store_true",
                   help="use cached files only, skip HTTP downloads")
    args = p.parse_args(argv)

    try:
        all_paths = list_kid_paths()
    except Exception as e:
        print(f"Failed to list repository tree: {e}", file=sys.stderr)
        return 2

    if args.limit > 0:
        all_paths = all_paths[: args.limit]
        print(f"  Limiting to first {args.limit} files.")

    local_paths = fetch_to_cache(all_paths, args.cache_dir, fetch=not args.no_fetch)

    print(f"[3/3] Running round-trip on {len(local_paths):,} files...", flush=True)
    results: list[tuple[str, str, int, str]] = []
    status_counts: dict[str, int] = {}
    start = time.time()
    for i, local in enumerate(local_paths, start=1):
        # Recover the original repo path from the flattened filename
        status, count, err = run_roundtrip(local)
        results.append((local.name, status, count, err))
        status_counts[status] = status_counts.get(status, 0) + 1
        if i % 100 == 0:
            elapsed = time.time() - start
            rate = i / elapsed if elapsed else 0
            print(f"  [{i}/{len(local_paths)}] "
                  f"{' '.join(f'{k}={v}' for k,v in status_counts.items())} "
                  f"— {rate:.1f}/s", flush=True)

    elapsed = time.time() - start

    # Write TSV report
    report = args.cache_dir / "results.tsv"
    with report.open("w", encoding="utf-8") as fh:
        fh.write("filename\tstatus\tsubscripts\terror\n")
        for name, status, count, err in results:
            err_oneline = err.replace("\t", " ").replace("\n", " | ")[:300]
            fh.write(f"{name}\t{status}\t{count}\t{err_oneline}\n")

    # Summary
    total = len(results)
    passed = status_counts.get("PASS", 0)
    pass_pct = 100 * passed / total if total else 0
    total_subs = sum(c for _, _, c, _ in results)
    print()
    print(f"=== CORPUS ROUND-TRIP SUMMARY ===")
    print(f"  files tested:     {total:,}")
    print(f"  elapsed:          {elapsed:.1f}s ({total/elapsed:.1f} files/s)")
    print(f"  total subscripts: {total_subs:,}")
    for status, cnt in sorted(status_counts.items()):
        marker = "✓" if status == "PASS" else "✗"
        print(f"  {marker} {status:<16} {cnt:>5,}  ({100*cnt/total:.2f}%)")
    print(f"  pass rate:        {pass_pct:.2f}%")
    print(f"  report:           {report}")

    # Sample failures
    fails = [r for r in results if r[1] != "PASS"]
    if fails and args.max_fail_samples > 0:
        print()
        print(f"=== FIRST {min(args.max_fail_samples, len(fails))} FAILURES ===")
        for name, status, count, err in fails[: args.max_fail_samples]:
            print(f"\n--- [{status}] {name} ({count} subs) ---")
            print(err[:400] if err else "(no error detail)")

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
