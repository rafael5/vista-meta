#!/usr/bin/env python3
# V7 of the producer-contracts plan: the release step → data-v1.
# Plan: docs/proposals/producer-contracts-implementation-plan.md § V7

"""Assemble (and publish) the vista-meta data-v1 release bundle.

Layout (all under dist/, gitignored):
  vista-meta-data-v1.tar.gz            the bundle: 24 TSVs + meta/ +
                                       the IN-BUNDLE manifest.json
  vista-meta-data-v1.manifest.json     the STANDALONE manifest =
                                       in-bundle fields + bundle_sha256
                                       + raw_archive_sha256 (F5: a
                                       manifest inside the tarball
                                       cannot hash the tarball)
  vista-meta-data-v1-raw.tar.gz        the raw extraction
                                       intermediates (F7/T0c: any
                                       re-emission runs from the
                                       archive, never a live engine)
  SHA256SUMS                           sha256sum -c checkable

Everything is deterministic: file mtimes are pinned to the R3
extraction timestamp, tar entries are sorted, gzip carries no
timestamp — re-assembling the same tree yields byte-identical assets.

Steps (--publish): assert clean tree + HEAD pushed (else
source_commit lies, F16), validate the tree, assemble, create the
GitHub Release tagged data-v1, then record the standalone manifest
in-repo (docs/releases/) so later asset tampering is detectable.
"""

from __future__ import annotations

import gzip
import hashlib
import io
import json
import subprocess
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path

import content_hash
import schema_v1
import validate_export

PROJECT_ROOT = Path(__file__).resolve().parents[2]
EXPORT_DIR = PROJECT_ROOT / "vista/export"
DIST_DIR = PROJECT_ROOT / "dist"
RECORD_JSON = PROJECT_ROOT / "docs/releases/data-v1.manifest.json"

TAG = "data-v1"
ARTIFACT = "vista-meta-data"
BUNDLE_ROOT = "vista-meta-data-v1"
BUNDLE_NAME = "vista-meta-data-v1.tar.gz"
STANDALONE_NAME = "vista-meta-data-v1.manifest.json"
RAW_NAME = "vista-meta-data-v1-raw.tar.gz"
SUMS_NAME = "SHA256SUMS"

META_FILES = ("meta/column-manifest.json", "meta/fidelity.json")


def payload_paths(export_dir: Path) -> dict[str, Path]:
    """Bundle payload, keyed by in-bundle relpath (manifest excluded)."""
    rels = {f"{spec.model}/{name}": export_dir / spec.model / name
            for name, spec in schema_v1.FILES.items()}
    rels.update({rel: export_dir / rel for rel in META_FILES})
    return dict(sorted(rels.items()))


def sidecar_epoch(sidecar: dict) -> int:
    ts = sidecar["extraction_timestamp"].replace("Z", "+00:00")
    return int(datetime.fromisoformat(ts).timestamp())


def build_manifest(export_dir: Path, sidecar: dict,
                   source_commit: str) -> dict:
    return {
        "artifact": ARTIFACT,
        "tag": TAG,
        "schema_version": 1,
        "content_hash": content_hash.compute(export_dir),
        "source_commit": source_commit,
        "engine": sidecar["engine"],
        "engine_image": sidecar["engine_image"],
        "engine_image_id": sidecar["engine_image_id"],
        "container_id": sidecar["container_id"],
        "extraction_timestamp": sidecar["extraction_timestamp"],
        "db_state_fingerprint": sidecar["db_state_fingerprint"],
        "extraction_source_commit": sidecar["source_commit"],
        "files": {
            rel: {"sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                  "bytes": p.stat().st_size}
            for rel, p in payload_paths(export_dir).items()},
    }


def standalone_manifest(in_bundle: dict, bundle_sha256: str,
                        raw_archive_sha256: str) -> dict:
    return {**in_bundle,
            "bundle_sha256": bundle_sha256,
            "raw_archive_sha256": raw_archive_sha256}


def render(doc: dict) -> str:
    return json.dumps(doc, indent=2, sort_keys=True) + "\n"


def _write_targz(out_path: Path, entries: list[tuple[str, bytes]],
                 mtime: int) -> str:
    """Deterministic tar.gz: sorted entries, pinned metadata,
    timestamp-free gzip. Returns the archive's sha256."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tf:
        for name, data in sorted(entries):
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mtime = mtime
            info.mode = 0o644
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            tf.addfile(info, io.BytesIO(data))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("wb") as f:
        with gzip.GzipFile(filename="", mode="wb", fileobj=f,
                           mtime=0) as gz:
            gz.write(buf.getvalue())
    return hashlib.sha256(out_path.read_bytes()).hexdigest()


def write_bundle(export_dir: Path, manifest_doc: dict,
                 out_path: Path) -> str:
    entries = [(f"{BUNDLE_ROOT}/{rel}", p.read_bytes())
               for rel, p in payload_paths(export_dir).items()]
    entries.append((f"{BUNDLE_ROOT}/manifest.json",
                    render(manifest_doc).encode("utf-8")))
    # the manifest carries extraction_timestamp, same key as the sidecar
    return _write_targz(out_path, entries, mtime=sidecar_epoch(manifest_doc))


def write_raw_archive(raw_dir: Path, out_path: Path, mtime: int) -> str:
    entries = [(f"{BUNDLE_ROOT}-raw/{p.name}", p.read_bytes())
               for p in sorted(raw_dir.iterdir()) if p.is_file()]
    return _write_targz(out_path, entries, mtime=mtime)


def sha256sums(paths: list[Path]) -> str:
    return "".join(
        f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n"
        for p in paths)


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=PROJECT_ROOT,
                          capture_output=True, text=True,
                          check=True).stdout.strip()


def assert_releasable() -> str:
    """F16: source_commit must not lie. Returns the release commit."""
    if _git("status", "--porcelain"):
        sys.exit("ERROR: working tree not clean — commit or stash first")
    head = _git("rev-parse", "HEAD")
    upstream = _git("rev-parse", "@{upstream}")
    if head != upstream:
        sys.exit(f"ERROR: HEAD {head[:12]} != upstream {upstream[:12]} — "
                 "push first (source_commit must be fetchable)")
    report = validate_export.validate(EXPORT_DIR)
    if report.errors:
        for e in report.errors:
            print(f"ERROR: {e}", file=sys.stderr)
        sys.exit("ERROR: validate failed — not releasable")
    return head


def assemble() -> dict:
    head = assert_releasable()
    sidecar = json.loads(
        (EXPORT_DIR / "raw/extraction.json").read_text(encoding="utf-8"))
    manifest = build_manifest(EXPORT_DIR, sidecar, head)

    DIST_DIR.mkdir(exist_ok=True)
    bundle_sha = write_bundle(EXPORT_DIR, manifest,
                              DIST_DIR / BUNDLE_NAME)
    raw_sha = write_raw_archive(EXPORT_DIR / "raw",
                                DIST_DIR / RAW_NAME,
                                sidecar_epoch(sidecar))
    standalone = standalone_manifest(manifest, bundle_sha, raw_sha)
    (DIST_DIR / STANDALONE_NAME).write_text(render(standalone),
                                            encoding="utf-8")
    (DIST_DIR / SUMS_NAME).write_text(
        sha256sums([DIST_DIR / BUNDLE_NAME,
                    DIST_DIR / STANDALONE_NAME,
                    DIST_DIR / RAW_NAME]), encoding="utf-8")
    for n in (BUNDLE_NAME, RAW_NAME, STANDALONE_NAME, SUMS_NAME):
        print(f"dist/{n}: {(DIST_DIR / n).stat().st_size} bytes")
    print(f"bundle_sha256: {bundle_sha}")
    print(f"content_hash:  {manifest['content_hash']}")
    return standalone


def publish(standalone: dict) -> None:
    subprocess.run(
        ["gh", "release", "create", TAG,
         str(DIST_DIR / BUNDLE_NAME),
         str(DIST_DIR / STANDALONE_NAME),
         str(DIST_DIR / RAW_NAME),
         str(DIST_DIR / SUMS_NAME),
         "--title", f"vista-meta {TAG}",
         "--notes",
         f"schema_version 1 data release.\n\n"
         f"content_hash: `{standalone['content_hash']}`\n"
         f"bundle_sha256: `{standalone['bundle_sha256']}`\n"
         f"engine: {standalone['engine']} "
         f"({standalone['engine_image']}), db_state_fingerprint "
         f"`{standalone['db_state_fingerprint'][:16]}…`\n\n"
         f"Verify: `sha256sum -c SHA256SUMS`, then compare against the "
         f"in-repo record `docs/releases/{RECORD_JSON.name}`."],
        cwd=PROJECT_ROOT, check=True)
    RECORD_JSON.parent.mkdir(parents=True, exist_ok=True)
    RECORD_JSON.write_text(render(standalone), encoding="utf-8")
    print(f"published {TAG}; in-repo record written to "
          f"{RECORD_JSON.relative_to(PROJECT_ROOT)} — commit it now")


def main(argv: list[str]) -> int:
    standalone = assemble()
    if argv == ["--publish"]:
        publish(standalone)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
