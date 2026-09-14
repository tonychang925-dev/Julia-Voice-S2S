"""VOICE-EL-P0D-1 — deployment safety infrastructure tests.

Covers the repository-owned pieces that let an experiment reach a GPU server
without anyone editing, installing or improvising on that server:

  * the immutability rule is present and normative in governance docs
  * the artifact payload never installs, never patches, never writes /tmp root
  * the experimental namespace contract is repository-defined
  * the import-locus gate fails closed on every wrong locus
  * the native gate refuses to run when the locus is wrong
  * the release builder emits the experiment capability block
  * the experimental launcher refuses the Golden release

These run locally / in CI only. Nothing here touches a server.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import stat
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
PAYLOAD = REPO / "deploy" / "experiment"
LOCUS = PAYLOAD / "locus.py"
RUN_TESTS = PAYLOAD / "run_tests"
LAUNCHER = PAYLOAD / "launch_experiment.sh"
NAMESPACE_ENV = PAYLOAD / "namespace.env"
RULE_DOC = REPO / "docs" / "authority" / "SERVER_IMMUTABILITY_RULE_v1.md"
BUILDER = REPO / "scripts" / "build_s2s_release.py"

FAKE_SHA = "0123456789abcdef0123456789abcdef01234567"


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _fake_release(root: Path, *, release_name: str, package: bool = True) -> Path:
    """Build a fake release layout: <root>/releases/<name>/release/..."""
    release_root = root / "releases" / release_name
    tree = release_root / "release"
    tree.mkdir(parents=True)
    if package:
        pkg = tree / "speech_to_speech"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("__version__ = 'fake'\n")
    return release_root


def _run(cmd: list[str], env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    merged = dict(os.environ)
    merged.pop("PYTHONPATH", None)
    if env:
        merged.update(env)
    return subprocess.run(cmd, capture_output=True, text=True, env=merged)


# ═══════════════════════════════════════════════════════════════════════════
# Immutability rule is present and normative
# ═══════════════════════════════════════════════════════════════════════════


def test_rule_doc_exists_and_carries_all_ten_points():
    assert RULE_DOC.is_file(), "the immutability rule must be a repository document"
    text = RULE_DOC.read_text(encoding="utf-8")

    for marker in (
        "Repository = Source Authority",
        "Server     = Runtime Evidence",
        "DEPLOYMENT_ARTIFACT_INCOMPLETE",
    ):
        assert marker in text

    # every one of the ten numbered statements must be present
    for fragment in (
        "not a development environment",
        "authored, edited, patched, or repaired on the server",
        "installed or modified on the server",
        "reviewed repository commit",
        "exact Git SHA",
        "immutable repository-built artifacts",
        "repository/artifact defect",
        "fixed locally, committed, reviewed, rebuilt, and redeployed",
        "explicitly defined run/log/cache locations",
        "evidence, not source authority",
    ):
        assert fragment in text, f"rule is missing its statement about: {fragment}"


def test_authority_index_points_at_the_rule():
    index = (REPO / "docs" / "authority" / "CURRENT_AUTHORITY.md").read_text(encoding="utf-8")
    assert "SERVER_IMMUTABILITY_RULE_v1.md" in index
    assert "DEPLOYMENT_ARTIFACT_INCOMPLETE" in index


# ═══════════════════════════════════════════════════════════════════════════
# The payload never installs, patches, or writes generic scratch
# ═══════════════════════════════════════════════════════════════════════════

FORBIDDEN_PATTERNS = [
    "pip install",
    "pip3 install",
    "conda install",
    "apt-get install",
    "apt install",
    "sed -i",
    "git cherry-pick",
    "yum install",
]


@pytest.mark.parametrize("path", sorted(p for p in PAYLOAD.rglob("*") if p.is_file()))
def test_payload_contains_no_forbidden_operations(path):
    text = path.read_text(encoding="utf-8", errors="ignore")
    lowered = text.lower()
    offenders = [p for p in FORBIDDEN_PATTERNS if p in lowered]
    assert not offenders, f"{path.name} contains forbidden operation(s): {offenders}"


@pytest.mark.parametrize("path", sorted(p for p in PAYLOAD.rglob("*") if p.is_file()))
def test_payload_never_writes_generic_tmp_paths(path):
    """A bare /tmp/... write is what the aborted P0D did; rule 9 forbids it."""
    for lineno, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        assert '"/tmp/' not in stripped and "'/tmp/" not in stripped, (
            f"{path.name}:{lineno} writes a generic /tmp path: {stripped}"
        )


# ═══════════════════════════════════════════════════════════════════════════
# Namespace contract
# ═══════════════════════════════════════════════════════════════════════════


def _namespace() -> dict[str, str]:
    values = {}
    for line in NAMESPACE_ENV.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        values[k.strip()] = v.strip()
    return values


def test_namespace_defines_all_four_roots_and_template_shape():
    ns = _namespace()
    for key in ("EXPERIMENT_RELEASE_ROOT_TEMPLATE", "EXPERIMENT_RUN_ROOT_TEMPLATE",
                "EXPERIMENT_LOG_ROOT_TEMPLATE", "EXPERIMENT_TMP_ROOT_TEMPLATE"):
        assert ns.get(key), f"{key} must be repository-defined"
        assert "%SHA%" in ns[key]
        assert ns[key].startswith("/root/julia_voice_v2/"), "experiments live inside the deployment root"
        assert not ns[key].startswith("/tmp")


def test_namespace_ports_do_not_collide_with_production():
    ns = _namespace()
    assert ns["EXPERIMENT_S2S_PORT"] != "8765", "must not collide with the production S2S port"
    assert ns["EXPERIMENT_FRONTEND_PORT"] != "7860", "must not collide with the production frontend port"


def test_namespace_never_targets_the_golden_current_symlink():
    ns = _namespace()
    for key, value in ns.items():
        if key.endswith("_TEMPLATE"):
            assert "releases/current" not in value


def test_gate_refuses_generic_tmp_root_and_accepts_experiment_namespace(tmp_path):
    gate = _load_module(PAYLOAD / "native_gate.py", "native_gate_ns")

    bad = gate.check_namespace({"EXPERIMENT_TMP_ROOT": "/tmp", "EXPERIMENT_RUN_ROOT": "/x", "EXPERIMENT_LOG_ROOT": "/y"})
    assert bad["ok"] is False and "/tmp" in bad["detail"]

    unset = gate.check_namespace({})
    assert unset["ok"] is False

    good = gate.check_namespace({
        "EXPERIMENT_TMP_ROOT": "/root/julia_voice_v2/tmp/exp-abc1234",
        "EXPERIMENT_RUN_ROOT": "/root/julia_voice_v2/run/exp-abc1234",
        "EXPERIMENT_LOG_ROOT": "/root/julia_voice_v2/logs/exp-abc1234",
    })
    assert good["ok"] is True, good["detail"]


# ═══════════════════════════════════════════════════════════════════════════
# Import-locus gate — fails closed on every wrong locus
# ═══════════════════════════════════════════════════════════════════════════


def test_locus_passes_for_the_expected_release(tmp_path):
    release_root = _fake_release(tmp_path, release_name="exp-0123456-20260101_000000")
    r = _run([sys.executable, str(LOCUS), "--expected-release-root", str(release_root)],
             env={"PYTHONPATH": str(release_root / "release")})
    assert r.returncode == 0, r.stdout + r.stderr
    assert "PASS" in r.stdout


def test_locus_fails_for_a_different_experiment_release(tmp_path):
    expected = _fake_release(tmp_path, release_name="exp-aaaaaaa-20260101_000000")
    other = _fake_release(tmp_path, release_name="exp-bbbbbbb-20260101_000000")
    r = _run([sys.executable, str(LOCUS), "--expected-release-root", str(expected)],
             env={"PYTHONPATH": str(other / "release")})
    assert r.returncode == 3
    assert "other-experiment-release" in r.stdout


def test_locus_fails_for_a_golden_release(tmp_path):
    expected = _fake_release(tmp_path, release_name="exp-aaaaaaa-20260101_000000")
    golden = _fake_release(tmp_path, release_name="manual-a500f55-20260824_145318")
    r = _run([sys.executable, str(LOCUS), "--expected-release-root", str(expected)],
             env={"PYTHONPATH": str(golden / "release")})
    assert r.returncode == 3
    assert "named-release" in r.stdout


def test_locus_fails_for_site_packages(tmp_path):
    expected = _fake_release(tmp_path, release_name="exp-aaaaaaa-20260101_000000")
    site = tmp_path / "python3.10" / "site-packages"
    pkg = site / "speech_to_speech"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("__version__ = 'installed'\n")

    r = _run([sys.executable, str(LOCUS), "--expected-release-root", str(expected)],
             env={"PYTHONPATH": str(site)})
    assert r.returncode == 3
    assert "site-packages" in r.stdout
    assert "FATAL" in r.stderr


def test_locus_fails_when_the_package_cannot_be_imported(tmp_path):
    expected = _fake_release(tmp_path, release_name="exp-aaaaaaa-20260101_000000", package=False)
    r = _run([sys.executable, str(LOCUS), "--expected-release-root", str(expected)])
    assert r.returncode == 3


def test_locus_prints_both_expected_and_actual(tmp_path):
    expected = _fake_release(tmp_path, release_name="exp-aaaaaaa-20260101_000000")
    other = _fake_release(tmp_path, release_name="exp-bbbbbbb-20260101_000000")
    r = _run([sys.executable, str(LOCUS), "--expected-release-root", str(expected)],
             env={"PYTHONPATH": str(other / "release")})
    assert str(expected / "release") in r.stdout
    assert str(other / "release") in r.stdout


# ═══════════════════════════════════════════════════════════════════════════
# The runner refuses to execute against a wrong locus
# ═══════════════════════════════════════════════════════════════════════════


def _stage_run_tests(tmp_path: Path, release_name: str, *, package: bool) -> Path:
    """Lay out <tmp>/releases/<name>/{manifest.json,experiment/,release/}."""
    release_root = _fake_release(tmp_path, release_name=release_name, package=package)
    shutil.copytree(PAYLOAD, release_root / "experiment")
    (release_root / "manifest.json").write_text(json.dumps(
        {"source_commit": FAKE_SHA, "archive_name": "none.tar.gz", "archive_sha256": "deadbeef",
         "file_count": 0, "files": []}, indent=2))
    entry = release_root / "experiment" / "run_tests"
    entry.chmod(entry.stat().st_mode | stat.S_IXUSR)
    return release_root


def test_runner_refuses_when_the_release_does_not_own_the_import(tmp_path):
    """Deliberately wrong locus: the release tree has no package, so the import
    resolves to a decoy elsewhere on the path. The runner must refuse."""
    release_root = _stage_run_tests(tmp_path, "exp-0123456-20260101_000000", package=False)
    decoy = tmp_path / "decoy"
    pkg = decoy / "speech_to_speech"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("__version__ = 'decoy'\n")

    r = _run([sys.executable, str(release_root / "experiment" / "run_tests"),
              "--expected-sha", FAKE_SHA], env={"PYTHONPATH": str(decoy)})
    assert r.returncode == 3, r.stdout + r.stderr
    assert "REFUSED" in r.stderr


def test_runner_reports_manifest_sha_mismatch(tmp_path):
    release_root = _stage_run_tests(tmp_path, "exp-0123456-20260101_000000", package=True)
    r = _run([sys.executable, str(release_root / "experiment" / "run_tests"),
              "--expected-sha", "f" * 40], env={"PYTHONPATH": str(release_root / "release")})
    # G1 fails first; the locus gate passes because run_tests prepends the release
    assert r.returncode == 4, r.stdout + r.stderr
    assert "G1" in r.stdout and "FAIL" in r.stdout


# ═══════════════════════════════════════════════════════════════════════════
# Experimental launcher
# ═══════════════════════════════════════════════════════════════════════════


def _stage_launcher(tmp_path: Path, release_name: str) -> Path:
    release_root = _fake_release(tmp_path, release_name=release_name, package=True)
    shutil.copytree(PAYLOAD, release_root / "experiment")
    for name in ("run_tests", "launch_experiment.sh"):
        p = release_root / "experiment" / name
        p.chmod(p.stat().st_mode | stat.S_IXUSR)
    return release_root


def test_launcher_dry_run_plans_an_experiment_namespace(tmp_path):
    release_root = _stage_launcher(tmp_path, "exp-0123456-20260101_000000")
    r = _run(["sh", str(release_root / "experiment" / "launch_experiment.sh"),
              "--expected-sha", FAKE_SHA, "--dry-run"])
    assert r.returncode == 0, r.stdout + r.stderr
    assert "DRY RUN" in r.stdout
    assert "releases/exp-0123456" in r.stdout
    assert "run/exp-0123456" in r.stdout
    assert "logs/exp-0123456" in r.stdout
    assert "tmp/exp-0123456" in r.stdout
    assert "--tts" in r.stdout and "elevenlabs" in r.stdout
    assert "never printed" in r.stdout, "the launcher must state that secret values are not printed"


def test_launcher_refuses_a_golden_release(tmp_path):
    release_root = _stage_launcher(tmp_path, "manual-a500f55-20260824_145318")
    r = _run(["sh", str(release_root / "experiment" / "launch_experiment.sh"),
              "--expected-sha", FAKE_SHA, "--dry-run"])
    assert r.returncode == 65
    assert "REFUSED" in r.stderr


def test_launcher_refuses_the_current_symlink(tmp_path):
    target = _stage_launcher(tmp_path, "exp-0123456-20260101_000000")
    current = tmp_path / "releases" / "current"
    current.symlink_to(target)
    r = _run(["sh", str(current / "experiment" / "launch_experiment.sh"),
              "--expected-sha", FAKE_SHA, "--dry-run"])
    assert r.returncode == 65
    assert "current" in r.stderr


def test_launcher_does_not_reuse_production_ports_or_paths():
    text = LAUNCHER.read_text(encoding="utf-8")
    assert "8765" not in text and "7860" not in text, "ports come from namespace.env, never hardcoded"
    assert "julia-voice-supervisor" not in text
    assert "supervisorctl" not in text


# ═══════════════════════════════════════════════════════════════════════════
# Builder — experiment capability block
# ═══════════════════════════════════════════════════════════════════════════


def test_builder_emits_the_experiment_capability_block(tmp_path):
    builder = _load_module(BUILDER, "builder_p0d1")
    meta = builder._experiment_metadata(PAYLOAD, "abc123", [{"path": "x", "sha256": "y"}])

    assert meta["capability_version"] == builder.EXPERIMENT_CAPABILITY_VERSION
    assert meta["artifact_sha256"] == "abc123"
    assert meta["native_runner_path"] == "experiment/run_tests"
    assert meta["runtime_entrypoint"] == "experiment/launch_experiment.sh"
    assert meta["expected_import_root"] == "<release_root>/release"
    assert meta["namespace"]["release_root_template"].endswith("exp-%SHA%-%STAMP%")
    assert meta["ports"]["s2s"] == 8865 and meta["ports"]["frontend"] == 7960
    assert meta["websockets_compatibility"] == {"min": 12, "max_exclusive": 16}
    assert "ELEVENLABS_API_KEY" not in json.dumps(meta), "no secret material in the manifest"


def test_builder_refuses_experiment_when_the_payload_is_absent_from_the_commit(tmp_path):
    """A build-time fail-closed: no payload in the commit => no experiment artifact."""
    builder = _load_module(BUILDER, "builder_p0d1_absent")
    with pytest.raises(RuntimeError, match="--experiment requested"):
        builder.materialize_from_commit("a500f55bbd8d24a8a86ca103c6d52ff2fb332b77", tmp_path / "x", experiment=True)


def test_experiment_artifact_keeps_its_entrypoints_executable(tmp_path):
    """End-to-end: the built artifact must contain runnable entrypoints.

    The server executes `<artifact>/run_tests`, so a 644 file there is a broken
    artifact. This regressed once — the tar assembler hardcoded mode 644 and
    silently discarded the preserved bit — so it is asserted against the real
    built archive rather than against the helper that is supposed to set it.
    """
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", "deploy/experiment/run_tests"],
        cwd=REPO, capture_output=True, text=True,
    )
    if tracked.returncode != 0:
        pytest.skip("experiment payload is not committed yet; the builder reads commits, not the worktree")

    builder = _load_module(BUILDER, "builder_p0d1_mode")
    out = tmp_path / "out"
    archive, _manifest = builder.build_artifact(out, experiment=True)

    import tarfile

    with tarfile.open(archive, "r:gz") as tar:
        modes = {m.name: m.mode for m in tar.getmembers()}

    assert modes["experiment/run_tests"] & 0o111, f"run_tests is not executable: {oct(modes['experiment/run_tests'])}"
    assert modes["experiment/launch_experiment.sh"] & 0o111
    # everything else must stay 644, exactly as before this capability existed
    assert modes["speech_to_speech/s2s_pipeline.py"] & 0o777 == 0o644
    assert modes["experiment/namespace.env"] & 0o777 == 0o644


def test_builder_signature_defaults_to_non_experiment():
    import inspect

    builder = _load_module(BUILDER, "builder_p0d1_sig")
    assert inspect.signature(builder.build_artifact).parameters["experiment"].default is False


# ═══════════════════════════════════════════════════════════════════════════
# websockets compatibility envelope is declared and enforced
# ═══════════════════════════════════════════════════════════════════════════


HANDLER = REPO / "s2s" / "TTS" / "elevenlabs_tts_handler.py"


def test_handler_uses_no_version_specific_connect_kwargs():
    """The transport must not depend on a keyword that moved between releases.

    `websockets.connect` takes `extra_headers` on 12.x and `additional_headers`
    from 13.x. The handler sidesteps the split entirely by authenticating with a
    message field, so neither name may appear.
    """
    source = HANDLER.read_text(encoding="utf-8")
    assert "additional_headers" not in source, "13.x-only kwarg would break websockets 12"
    assert "extra_headers" not in source, "12.x-only kwarg would break websockets 15"
    assert "xi-api-key" not in source.lower(), "auth travels as a message field, not an HTTP header"


@pytest.mark.filterwarnings("ignore::DeprecationWarning")
def test_websockets_connect_returns_a_wait_for_compatible_awaitable():
    """The handler does `asyncio.wait_for(<module>.connect(url), timeout=...)`.

    That is only legal if connect() returns an awaitable — true on 12.x (the
    legacy Connect object) and on 13+ (the asyncio client). Assert the shape
    without ever dialling, so this runs under either version.
    """
    import asyncio
    import inspect

    import websockets

    obj = websockets.connect("wss://example.invalid/never-dialed")
    try:
        assert inspect.isawaitable(obj) or asyncio.iscoroutine(obj), (
            f"websockets {websockets.__version__} connect() is not awaitable; "
            "asyncio.wait_for would reject it"
        )
    finally:
        close = getattr(obj, "close", None)
        if callable(close):
            close()


def test_handler_close_calls_are_argument_free():
    """close() signatures drifted across websockets releases; the handler must
    call it with no arguments so both ends of the envelope accept it."""
    source = HANDLER.read_text(encoding="utf-8")
    assert ".close()" in source
    assert ".close(code" not in source and ".close(1000" not in source


def test_gate_enforces_the_declared_websockets_envelope():
    """The gate must be able to REJECT, not merely report."""
    gate = _load_module(PAYLOAD / "native_gate.py", "native_gate_ws")

    import websockets

    major = int(websockets.__version__.split(".")[0])

    inside = gate.gate_g4_websockets_compat(12, 16)
    assert inside["ok"] is True, inside["detail"]
    assert 12 <= major < 16, f"local websockets {websockets.__version__} is outside the declared envelope"

    # an envelope that excludes the installed version must fail closed
    outside = gate.gate_g4_websockets_compat(9000, 9001)
    assert outside["ok"] is False
    assert "OUTSIDE" in outside["detail"]
