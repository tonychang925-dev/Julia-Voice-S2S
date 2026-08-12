#!/usr/bin/env python3
"""Deterministic S2S release builder.

Builds a reproducible tar.gz artifact from an approved source commit.
Controls all archive metadata so two builds from the same commit produce
byte-identical archives.

Usage:
  python3 scripts/build_s2s_release.py <output_dir>

Output:
  <output_dir>/speech_to_speech-obs-<commit_short>.tar.gz
  <output_dir>/manifest.json
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
S2S_DIR = REPO_ROOT / "s2s"
FRONTEND_DIR = REPO_ROOT / "frontend"


def git_commit() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True
    ).strip()


def build_artifact(output_dir: Path) -> tuple[Path, dict]:
    """Build the deterministic release artifact. Returns (archive_path, manifest)."""
    commit = git_commit()
    commit_short = commit[:7]
    archive_name = f"speech_to_speech-obs-{commit_short}.tar.gz"
    archive_path = output_dir / archive_name

    output_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="s2s_build_") as tmp:
        tmpdir = Path(tmp)
        pkg_dir = tmpdir / "speech_to_speech"
        frontend_dir = tmpdir / "frontend"
        shutil.copytree(S2S_DIR, pkg_dir, symlinks=False)
        shutil.copytree(FRONTEND_DIR, frontend_dir, symlinks=False)

        # ---- Deterministic metadata ----
        FIXED_MTIME = 1758076800  # 2026-08-11 00:00:00 UTC
        FIXED_UID = 0
        FIXED_GID = 0
        FIXED_UNAME = ""
        FIXED_GNAME = ""

        # Manifest entries collected during tar assembly below

        # Reset directory permissions deterministically
        for root, dirs, files in os.walk(pkg_dir, topdown=False):
            dirs.sort()
            files.sort()
            for d in dirs:
                dp = Path(root) / d
                dp.chmod(0o755)
            for f in files:
                fp = Path(root) / f
                fp.chmod(0o644)
            rp = Path(root)
            rp.chmod(0o755)
            os.utime(rp, (FIXED_MTIME, FIXED_MTIME))

        # Build tar with explicit control
        import gzip, io

        # Walk BOTH directories for manifest
        all_entries = []
        _walk_and_collect(pkg_dir, tmpdir, all_entries, mtime=FIXED_MTIME,
                         uid=FIXED_UID, gid=FIXED_GID, uname=FIXED_UNAME, gname=FIXED_GNAME)
        _walk_and_collect(frontend_dir, tmpdir, all_entries, mtime=FIXED_MTIME,
                         uid=FIXED_UID, gid=FIXED_GID, uname=FIXED_UNAME, gname=FIXED_GNAME)
        all_entries.sort(key=lambda e: e["path"])

        # Build tar in memory first to control ordering
        tar_buffer = io.BytesIO()
        with tarfile.open(fileobj=tar_buffer, mode="w", format=tarfile.PAX_FORMAT) as tar:
            # Add the top-level directories first
            for top_name in ["speech_to_speech", "frontend"]:
                top = tarfile.TarInfo(name=top_name)
                top.type = tarfile.DIRTYPE
                top.mode = 0o755
                top.uid = FIXED_UID
                top.gid = FIXED_GID
                top.uname = FIXED_UNAME
                top.gname = FIXED_GNAME
                top.mtime = FIXED_MTIME
                tar.addfile(top)

            # Add all directories with sorted paths for determinism
            dirs_seen = {"speech_to_speech"}
            for entry in all_entries:
                if entry["type"] != "directory":
                    continue
                if entry["path"] in dirs_seen:
                    continue
                dirs_seen.add(entry["path"])
                info = tarfile.TarInfo(name=entry["path"])
                info.type = tarfile.DIRTYPE
                info.mode = 0o755
                info.uid = FIXED_UID
                info.gid = FIXED_GID
                info.uname = FIXED_UNAME
                info.gname = FIXED_GNAME
                info.mtime = FIXED_MTIME
                tar.addfile(info)

            # Add all regular files with sorted paths for determinism
            for entry in all_entries:
                if entry["type"] != "file":
                    continue
                src = tmpdir / entry["path"]
                info = tar.gettarinfo(
                    name=str(src),
                    arcname=entry["path"],
                )
                info.uid = FIXED_UID
                info.gid = FIXED_GID
                info.uname = FIXED_UNAME
                info.gname = FIXED_GNAME
                info.mtime = FIXED_MTIME
                info.mode = 0o644

                with open(src, "rb") as fh:
                    tar.addfile(info, fh)

        # Gzip with deterministic mtime=0
        tar_bytes = tar_buffer.getvalue()
        with gzip.GzipFile(filename="", mode="wb", mtime=0, fileobj=open(archive_path, "wb"), compresslevel=6) as gz:
            gz.write(tar_bytes)

        # Compute archive SHA
        archive_sha = _sha256_file(archive_path)

        # Build complete manifest from archive
        complete_manifest = _manifest_from_archive(archive_path)

        fw_main = frontend_dir / "main.js"
        fw_ws = frontend_dir / "ws" / "s2s-ws-client.js"
        manifest = {
            "source_commit": commit,
            "archive_name": archive_name,
            "archive_sha256": archive_sha,
            "file_count": len(complete_manifest),
            "frontend_main_sha": _sha256_file(fw_main) if fw_main.exists() else None,
            "frontend_ws_sha": _sha256_file(fw_ws) if fw_ws.exists() else None,
            "files": complete_manifest,
        }

        manifest_path = output_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True))

        return archive_path, manifest


def _walk_and_collect(
    pkg_dir: Path,
    base_dir: Path,
    entries: list,
    mtime: int,
    uid: int,
    gid: int,
    uname: str,
    gname: str,
) -> None:
    """Walk package directory, fix metadata, collect manifest entries."""
    for root, dirs, files in sorted(os.walk(pkg_dir)):
        dirs.sort()
        files.sort()

        # Skip __pycache__, .DS_Store, macOS metadata
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        files = [f for f in files if f != ".DS_Store" and not f.startswith("._")]

        rp = Path(root)
        for d in dirs:
            dp = rp / d
            dp.chmod(0o755)
            os.utime(dp, (mtime, mtime))
            rel = str(dp.relative_to(base_dir))
            entries.append(
                {
                    "path": rel,
                    "type": "directory",
                    "mode": "755",
                    "sha256": None,
                }
            )

        for f in files:
            fp = rp / f
            fp.chmod(0o644)
            os.utime(fp, (mtime, mtime))
            rel = str(fp.relative_to(base_dir))
            sha = _sha256_file(fp)
            entries.append(
                {
                    "path": rel,
                    "type": "file",
                    "mode": "644",
                    "size": fp.stat().st_size,
                    "sha256": sha,
                }
            )


def _manifest_from_archive(archive_path: Path) -> list[dict]:
    """Extract complete manifest from a built archive."""
    entries = []
    with tarfile.open(archive_path, "r:gz") as tar:
        for info in sorted(tar.getmembers(), key=lambda i: i.name):
            entry = {
                "path": info.name,
                "type": "directory" if info.isdir() else "file",
                "mode": stat.filemode(info.mode)[-3:],
                "size": info.size,
            }
            if info.isfile():
                fh = tar.extractfile(info)
                if fh:
                    entry["sha256"] = hashlib.sha256(fh.read()).hexdigest()
                else:
                    entry["sha256"] = None
            else:
                entry["sha256"] = None
            entries.append(entry)
    return entries


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


if __name__ == "__main__":
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/tmp/s2s_release")
    arc_path, manifest = build_artifact(output)
    print(f"Artifact: {arc_path}")
    print(f"SHA256:   {manifest['archive_sha256']}")
    print(f"Files:    {manifest['file_count']}")
    print(f"Manifest: {output / 'manifest.json'}")
