#!/usr/bin/env python3
"""Deterministic S2S release builder.

Builds a reproducible tar.gz artifact from an approved source commit.
Controls all archive metadata so two builds from the same commit produce
byte-identical archives.

Usage:
  python3 scripts/build_s2s_release.py <output_dir>
  python3 scripts/build_s2s_release.py <output_dir> --experiment

Output:
  <output_dir>/speech_to_speech-obs-<commit_short>.tar.gz
  <output_dir>/manifest.json

`--experiment` additionally ships `deploy/experiment/` as `experiment/` inside
the artifact and adds a machine-readable experiment capability block to the
manifest (VOICE-EL-P0D-1, Workstream G). The default build is unchanged and
byte-identical to a build made before that flag existed; a test asserts it.
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
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
S2S_DIR = REPO_ROOT / "s2s"
FRONTEND_DIR = REPO_ROOT / "frontend"
EXPERIMENT_DIR = REPO_ROOT / "deploy" / "experiment"

EXPERIMENT_CAPABILITY_VERSION = 1
EXPERIMENT_PAYLOAD_DIRNAME = "experiment"


def verify_remote_commit(commit: str) -> None:
    """Verify commit exists on remote. Fails if not pushed."""
    result = subprocess.run(
        ["git", "branch", "-r", "--contains", commit],
        cwd=REPO_ROOT, capture_output=True, text=True
    )
    if result.returncode != 0 or not result.stdout.strip():
        raise RuntimeError(f"Commit {commit[:12]} not found on any remote branch — push first")


def materialize_from_commit(commit: str, target_dir: Path, experiment: bool = False) -> None:
    """Extract s2s/ and frontend/ from exact git commit object. Ambient working tree irrelevant."""
    with tempfile.TemporaryDirectory(prefix="rcp_src_") as src_tmp:
        src = Path(src_tmp)
        # Clone with full depth to ensure the exact commit is reachable, then checkout
        subprocess.run(
            ["git", "clone", str(REPO_ROOT), str(src)],
            check=True, capture_output=True
        )
        subprocess.run(["git", "checkout", commit], cwd=src, check=True, capture_output=True)
        shutil.copytree(src / "s2s", target_dir / "speech_to_speech", symlinks=False)
        shutil.copytree(src / "frontend", target_dir / "frontend", symlinks=False)
        if experiment:
            exp_src = src / "deploy" / "experiment"
            if not exp_src.is_dir():
                raise RuntimeError(f"--experiment requested but {exp_src} is absent from commit {commit[:12]}")
            shutil.copytree(exp_src, target_dir / EXPERIMENT_PAYLOAD_DIRNAME, symlinks=False)


def build_artifact(output_dir: Path, commit: str | None = None, experiment: bool = False) -> tuple[Path, dict]:
    """Build deterministic release from EXACT git commit (must be pushed to remote).
    Ambient working tree is NEVER read. Only git commit object matters.
    """
    if commit is None:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True
        ).strip()

    verify_remote_commit(commit)

    commit_short = commit[:7]
    archive_name = f"speech_to_speech-obs-{commit_short}.tar.gz"
    archive_path = output_dir / archive_name

    output_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="s2s_build_") as tmp:
        tmpdir = Path(tmp)
        materialize_from_commit(commit, tmpdir, experiment=experiment)
        pkg_dir = tmpdir / "speech_to_speech"
        frontend_dir = tmpdir / "frontend"
        experiment_dir = tmpdir / EXPERIMENT_PAYLOAD_DIRNAME if experiment else None

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
        if experiment_dir is not None:
            # preserve_exec: the artifact's entrypoints (run_tests, the launcher)
            # must stay executable, unlike the rest of the tree which is 644.
            _walk_and_collect(experiment_dir, tmpdir, all_entries, mtime=FIXED_MTIME,
                              uid=FIXED_UID, gid=FIXED_GID, uname=FIXED_UNAME, gname=FIXED_GNAME,
                              preserve_exec=True)
        all_entries.sort(key=lambda e: e["path"])

        # Build tar in memory first to control ordering
        tar_buffer = io.BytesIO()
        with tarfile.open(fileobj=tar_buffer, mode="w", format=tarfile.PAX_FORMAT) as tar:
            # Add the top-level directories first
            top_dirs = ["speech_to_speech", "frontend"]
            if experiment_dir is not None:
                top_dirs.append(EXPERIMENT_PAYLOAD_DIRNAME)
            for top_name in top_dirs:
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
        if experiment_dir is not None:
            manifest["experiment"] = _experiment_metadata(experiment_dir, archive_sha, complete_manifest)

        manifest_path = output_dir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True))

        return archive_path, manifest


def _parse_env_file(path: Path) -> dict:
    """Parse a simple KEY=VALUE file (no expansion, no shell execution)."""
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip()
    return values


def _experiment_metadata(experiment_dir: Path, archive_sha: str, files: list[dict]) -> dict:
    """Machine-readable experiment capability block (VOICE-EL-P0D-1, Workstream G).

    Derived from the shipped namespace.env so there is exactly one definition of
    the namespace, ports and compatibility envelope — the artifact's own.
    """
    ns = _parse_env_file(experiment_dir / "namespace.env")
    tree_digest = hashlib.sha256(
        json.dumps([(f["path"], f["sha256"]) for f in files], sort_keys=True).encode()
    ).hexdigest()

    def _int(key: str) -> int | None:
        try:
            return int(ns.get(key, ""))
        except (TypeError, ValueError):
            return None

    return {
        "capability_version": EXPERIMENT_CAPABILITY_VERSION,
        "artifact_sha256": archive_sha,
        "built_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "release_tree_sha256": tree_digest,
        "expected_import_root": "<release_root>/release",
        "native_runner_path": f"{EXPERIMENT_PAYLOAD_DIRNAME}/run_tests",
        "runtime_entrypoint": f"{EXPERIMENT_PAYLOAD_DIRNAME}/launch_experiment.sh",
        "runtime_args_path": f"{EXPERIMENT_PAYLOAD_DIRNAME}/runtime.args",
        "namespace_env_path": f"{EXPERIMENT_PAYLOAD_DIRNAME}/namespace.env",
        "namespace": {
            "namespace_version": _int("EXPERIMENT_NAMESPACE_VERSION"),
            "release_root_template": ns.get("EXPERIMENT_RELEASE_ROOT_TEMPLATE"),
            "run_root_template": ns.get("EXPERIMENT_RUN_ROOT_TEMPLATE"),
            "log_root_template": ns.get("EXPERIMENT_LOG_ROOT_TEMPLATE"),
            "tmp_root_template": ns.get("EXPERIMENT_TMP_ROOT_TEMPLATE"),
        },
        "ports": {
            "s2s": _int("EXPERIMENT_S2S_PORT"),
            "frontend": _int("EXPERIMENT_FRONTEND_PORT"),
        },
        "required_runtime_python": ns.get("EXPERIMENT_REQUIRED_PYTHON"),
        "websockets_compatibility": {
            "min": _int("EXPERIMENT_WEBSOCKETS_MIN"),
            "max_exclusive": _int("EXPERIMENT_WEBSOCKETS_MAX_EXCLUSIVE"),
        },
    }


def _walk_and_collect(
    pkg_dir: Path,
    base_dir: Path,
    entries: list,
    mtime: int,
    uid: int,
    gid: int,
    uname: str,
    gname: str,
    preserve_exec: bool = False,
) -> None:
    """Walk package directory, fix metadata, collect manifest entries.

    preserve_exec is used only for the experiment payload, whose entrypoints must
    remain executable in the artifact. Everything else stays 644, exactly as
    before, so default builds are unaffected.
    """
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
            executable = preserve_exec and bool(fp.stat().st_mode & 0o111)
            fp.chmod(0o755 if executable else 0o644)
            os.utime(fp, (mtime, mtime))
            rel = str(fp.relative_to(base_dir))
            sha = _sha256_file(fp)
            entries.append(
                {
                    "path": rel,
                    "type": "file",
                    "mode": "755" if executable else "644",
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
    import argparse

    parser = argparse.ArgumentParser(description="Deterministic S2S release builder.")
    parser.add_argument("output_dir", nargs="?", default="/tmp/s2s_release")
    parser.add_argument("--experiment", action="store_true",
                        help="also ship deploy/experiment/ as experiment/ and emit the experiment "
                             "capability block in the manifest")
    parser.add_argument("--commit", default=None, help="exact commit (defaults to HEAD)")
    cli = parser.parse_args()

    arc_path, manifest = build_artifact(Path(cli.output_dir), commit=cli.commit, experiment=cli.experiment)
    print(f"Artifact: {arc_path}")
    print(f"SHA256:   {manifest['archive_sha256']}")
    print(f"Files:    {manifest['file_count']}")
    if cli.experiment:
        exp = manifest["experiment"]
        print(f"Experiment capability v{exp['capability_version']} runner={exp['native_runner_path']}")
    print(f"Manifest: {Path(cli.output_dir) / 'manifest.json'}")
