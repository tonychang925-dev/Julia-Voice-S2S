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
import re
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
    for name in ("run_tests", "launch_experiment.sh", "entrypoint", "namespace.py"):
        p = release_root / "experiment" / name
        p.chmod(p.stat().st_mode | stat.S_IXUSR)
    (release_root / "manifest.json").write_text(json.dumps(
        {"source_commit": FAKE_SHA, "archive_name": "none.tar.gz", "archive_sha256": "deadbeef",
         "file_count": 0, "files": []}, indent=2))
    return release_root


# The launcher defaults EXPERIMENT_PYTHON to the target's absolute interpreter,
# which does not exist here. Tests override it explicitly; the default itself is
# asserted separately.
def _launcher_env() -> dict[str, str]:
    return {"EXPERIMENT_PYTHON": sys.executable}


def test_launcher_dry_run_plans_an_experiment_namespace(tmp_path):
    release_root = _stage_launcher(tmp_path, "exp-0123456-20260101_000000")
    r = _run(["sh", str(release_root / "experiment" / "launch_experiment.sh"),
              "--expected-sha", FAKE_SHA, "--dry-run"], env=_launcher_env())
    assert r.returncode == 0, r.stdout + r.stderr
    assert "DRY RUN" in r.stdout
    assert "run/exp-0123456" in r.stdout
    assert "logs/exp-0123456" in r.stdout
    assert "tmp/exp-0123456" in r.stdout
    assert "--tts" in r.stdout and "elevenlabs" in r.stdout
    assert "never printed" in r.stdout, "the launcher must state that secret values are not printed"


def test_launcher_plan_references_only_artifact_owned_things(tmp_path):
    """The plan must name the artifact's own entrypoint and the declared
    interpreter, and must not reach for PATH, a console script, or production."""
    release_root = _stage_launcher(tmp_path, "exp-0123456-20260101_000000")
    r = _run(["sh", str(release_root / "experiment" / "launch_experiment.sh"),
              "--expected-sha", FAKE_SHA, "--dry-run"], env=_launcher_env())
    assert r.returncode == 0, r.stdout + r.stderr

    assert str(release_root / "experiment" / "entrypoint") in r.stdout
    assert sys.executable in r.stdout
    assert "interpreter" in r.stdout
    for forbidden in ("releases/current", "manual-",
                      "/root/miniconda3/bin/speech-to-speech", "/opt/julia", "/etc/julia"):
        assert forbidden not in r.stdout, f"plan references {forbidden}"

    # A generic scratch path must not appear. Tokenised rather than substring-
    # matched, because the repository namespace legitimately contains
    # /root/julia_voice_v2/tmp/exp-<sha> and a naive "/tmp/" search would flag it.
    tokens = re.findall(r"[/\w.\-]+", r.stdout)
    generic = [t for t in tokens if t == "/tmp" or t.startswith("/tmp/")]
    assert not generic, f"plan references a generic scratch path: {generic}"


def test_launcher_refuses_a_golden_release(tmp_path):
    release_root = _stage_launcher(tmp_path, "manual-a500f55-20260824_145318")
    r = _run(["sh", str(release_root / "experiment" / "launch_experiment.sh"),
              "--expected-sha", FAKE_SHA, "--dry-run"], env=_launcher_env())
    assert r.returncode == 65
    assert "REFUSED" in r.stderr


def test_launcher_refuses_the_current_symlink(tmp_path):
    target = _stage_launcher(tmp_path, "exp-0123456-20260101_000000")
    current = tmp_path / "releases" / "current"
    current.symlink_to(target)
    r = _run(["sh", str(current / "experiment" / "launch_experiment.sh"),
              "--expected-sha", FAKE_SHA, "--dry-run"], env=_launcher_env())
    assert r.returncode == 65
    assert "current" in r.stderr


def test_launcher_refuses_when_the_declared_interpreter_is_absent(tmp_path):
    release_root = _stage_launcher(tmp_path, "exp-0123456-20260101_000000")
    r = _run(["sh", str(release_root / "experiment" / "launch_experiment.sh"),
              "--expected-sha", FAKE_SHA, "--dry-run"],
             env={"EXPERIMENT_PYTHON": str(tmp_path / "no-such-python")})
    assert r.returncode == 69
    assert "not executable" in r.stderr


def test_launcher_defaults_to_the_target_absolute_interpreter():
    ns = (PAYLOAD / "namespace.env").read_text(encoding="utf-8")
    assert "/root/miniconda3/bin/python" in ns
    assert "EXPERIMENT_PYTHON=${EXPERIMENT_PYTHON:-/root/miniconda3/bin/python}" in ns


def test_launcher_does_not_reuse_production_ports_or_paths():
    text = LAUNCHER.read_text(encoding="utf-8")
    assert "8765" not in text and "7860" not in text, "ports come from namespace.env, never hardcoded"
    assert "julia-voice-supervisor" not in text
    assert "supervisorctl" not in text
    assert "speech-to-speech" not in text, "no site-packages console script"


def test_launcher_never_invokes_python_via_path():
    """P0D-0 proved the target's non-interactive PATH has no python3."""
    text = LAUNCHER.read_text(encoding="utf-8")
    assert "python3 " not in text and "`python3" not in text
    assert '"$PY"' in text, "every interpreter invocation goes through the declared absolute path"


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
    assert modes["experiment/entrypoint"] & 0o111
    # everything else must stay 644, exactly as before this capability existed.
    # The experiment layout nests the application tree under release/.
    assert modes["release/speech_to_speech/s2s_pipeline.py"] & 0o777 == 0o644
    assert modes["experiment/namespace.env"] & 0o777 == 0o644


# ═══════════════════════════════════════════════════════════════════════════
# R1 — namespace materialization (the shared implementation)
# ═══════════════════════════════════════════════════════════════════════════


def _namespaces():
    return _load_module(PAYLOAD / "namespace.py", "ns_materialize")


def test_templates_materialize_into_concrete_roots():
    ns = _namespaces()
    result = ns.concrete_for_release(str(NAMESPACE_ENV),
                                     "/root/julia_voice_v2/releases/exp-0123456-20260101_000000",
                                     FAKE_SHA)
    assert result["missing_templates"] == []
    assert result["unresolved"] == [], f"placeholders left unresolved: {result['unresolved']}"
    assert result["roots"]["EXPERIMENT_RUN_ROOT"] == "/root/julia_voice_v2/run/exp-0123456"
    assert result["roots"]["EXPERIMENT_LOG_ROOT"] == "/root/julia_voice_v2/logs/exp-0123456"
    assert result["roots"]["EXPERIMENT_TMP_ROOT"] == "/root/julia_voice_v2/tmp/exp-0123456"


def test_stamp_is_recovered_from_the_release_directory_name():
    """Both consumers must derive the same roots from the same on-disk facts,
    not from two independent clocks."""
    ns = _namespaces()
    a = ns.concrete_for_release(str(NAMESPACE_ENV), "/root/julia_voice_v2/releases/exp-0123456-20260101_000000", FAKE_SHA)
    b = ns.concrete_for_release(str(NAMESPACE_ENV), "/root/julia_voice_v2/releases/exp-0123456-20260101_000000", FAKE_SHA)
    assert a["stamp"] == b["stamp"] == "20260101_000000"
    assert a["roots"] == b["roots"]


def test_materialized_namespace_satisfies_the_gate_precondition(tmp_path):
    """The value the gate checks must be the value the launcher creates."""
    ns = _namespaces()
    gate = _load_module(PAYLOAD / "native_gate.py", "native_gate_materialized")
    result = ns.concrete_for_release(str(NAMESPACE_ENV),
                                     "/root/julia_voice_v2/releases/exp-0123456-20260101_000000",
                                     FAKE_SHA)
    check = gate.check_namespace(dict(result["concrete"], **result["roots"]))
    assert check["ok"] is True, check["detail"]


def test_namespace_cli_shell_format_is_eval_safe(tmp_path):
    r = _run([sys.executable, str(PAYLOAD / "namespace.py"),
              "--namespace-env", str(NAMESPACE_ENV),
              "--release-root", "/root/julia_voice_v2/releases/exp-0123456-20260101_000000",
              "--sha", FAKE_SHA, "--format", "shell"])
    assert r.returncode == 0, r.stderr
    lines = [ln for ln in r.stdout.splitlines() if ln.strip()]
    assert len(lines) == 3
    for line in lines:
        assert line.startswith(("EXPERIMENT_RUN_ROOT=", "EXPERIMENT_LOG_ROOT=", "EXPERIMENT_TMP_ROOT="))
        assert " " not in line, "an eval'd assignment must not contain unquoted spaces"
    # and the shell must actually be able to consume it
    check = subprocess.run(
        ["sh", "-c",
         f'eval "$({sys.executable!s} {PAYLOAD / "namespace.py"} --namespace-env {NAMESPACE_ENV} '
         f'--release-root /root/julia_voice_v2/releases/exp-0123456-20260101_000000 '
         f'--sha {FAKE_SHA} --format shell)"; echo "$EXPERIMENT_RUN_ROOT"'],
        capture_output=True, text=True)
    assert check.stdout.strip() == "/root/julia_voice_v2/run/exp-0123456"


# ═══════════════════════════════════════════════════════════════════════════
# R1 — the real artifact, executed end to end
# ═══════════════════════════════════════════════════════════════════════════


def _build_and_extract(tmp_path: Path) -> tuple[Path, str]:
    tracked = subprocess.run(["git", "ls-files", "--error-unmatch", "deploy/experiment/run_tests"],
                             cwd=REPO, capture_output=True, text=True)
    if tracked.returncode != 0:
        pytest.skip("experiment payload is not committed yet; the builder reads commits, not the worktree")

    builder = _load_module(BUILDER, "builder_e2e")
    out = tmp_path / "out"
    out.mkdir()
    archive, manifest = builder.build_artifact(out, experiment=True)
    sha = manifest["source_commit"]

    release_root = tmp_path / "releases" / f"exp-{sha[:7]}-20260101_000000"
    release_root.mkdir(parents=True)
    subprocess.run(["tar", "-xzf", str(archive), "-C", str(release_root)], check=True)
    shutil.copy(out / "manifest.json", release_root / "manifest.json")
    return release_root, sha


def test_real_artifact_has_the_expected_layout(tmp_path):
    release_root, _sha = _build_and_extract(tmp_path)
    assert (release_root / "release" / "speech_to_speech" / "__init__.py").is_file()
    assert (release_root / "release" / "frontend" / "main.js").is_file()
    assert (release_root / "experiment" / "run_tests").is_file()
    assert (release_root / "manifest.json").is_file()


def test_real_artifact_native_gate_passes_namespace_and_locus(tmp_path):
    """The whole point of R1: the built artifact's own runner, run from a clean
    directory with no PYTHONPATH, must reach and pass NAMESPACE, G1 and G2.

    Nothing from the repository working tree and nothing from an installed
    speech_to_speech may satisfy this — the only importable copy is the one
    inside the extracted artifact.
    """
    release_root, sha = _build_and_extract(tmp_path)

    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    r = subprocess.run([sys.executable, str(release_root / "experiment" / "run_tests"),
                        "--expected-sha", sha],
                       capture_output=True, text=True, env=env, cwd=str(tmp_path))

    assert r.returncode != 3, f"runner refused: {r.stdout}\n{r.stderr}"
    assert "[PASS] NAMESPACE" in r.stdout, r.stdout
    assert "[PASS] G1" in r.stdout, r.stdout
    assert "[PASS] G2" in r.stdout, r.stdout
    # the attested locus is inside the extracted artifact, not site-packages
    assert str(release_root / "release") in r.stdout, r.stdout


def test_real_artifact_runner_uses_the_interpreter_it_was_given(tmp_path):
    """The runner reports the interpreter it is executing under, so the runtime
    evidence names the real one rather than assuming PATH resolved something."""
    release_root, sha = _build_and_extract(tmp_path)
    r = subprocess.run([sys.executable, str(release_root / "experiment" / "run_tests"),
                        "--expected-sha", sha],
                       capture_output=True, text=True,
                       env={k: v for k, v in os.environ.items() if k != "PYTHONPATH"},
                       cwd=str(tmp_path))
    assert f"interpreter    : {sys.executable}" in r.stdout, r.stdout


# ═══════════════════════════════════════════════════════════════════════════
# R1 — no dependence on PATH
# ═══════════════════════════════════════════════════════════════════════════


def _coreutils_only_path(tmp_path: Path) -> str:
    """A PATH with the shell utilities the launcher legitimately needs, and
    deliberately without any interpreter — the situation P0D-0 measured on the
    target's non-interactive shell."""
    bindir = tmp_path / "coreutils"
    bindir.mkdir()
    for tool in ("dirname", "basename", "grep", "sed", "date", "cut", "tr", "cat", "mkdir", "env"):
        found = shutil.which(tool)
        if found:
            (bindir / tool).symlink_to(found)
    return str(bindir)


def test_launcher_works_without_an_interpreter_on_path(tmp_path):
    release_root = _stage_launcher(tmp_path, "exp-0123456-20260101_000000")
    path = _coreutils_only_path(tmp_path)
    assert shutil.which("python3", path=path) is None, "precondition: no interpreter on the test PATH"

    r = subprocess.run(
        ["/bin/sh", str(release_root / "experiment" / "launch_experiment.sh"),
         "--expected-sha", FAKE_SHA, "--dry-run"],
        capture_output=True, text=True,
        env={"PATH": path, "EXPERIMENT_PYTHON": sys.executable, "HOME": str(tmp_path)},
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert "DRY RUN" in r.stdout


# ═══════════════════════════════════════════════════════════════════════════
# R1 — the runtime entrypoint is artifact-owned and valid
# ═══════════════════════════════════════════════════════════════════════════


def test_entrypoint_is_shipped_executable_with_the_payload(tmp_path):
    release_root, _sha = _build_and_extract(tmp_path)
    entry = release_root / "experiment" / "entrypoint"
    assert entry.is_file()
    assert entry.stat().st_mode & 0o111, "the entrypoint must be executable in the artifact"
    assert entry.read_text(encoding="utf-8").strip(), "empty entrypoint"


def test_entrypoint_runs_the_pipeline_main_and_passes_arguments_through(tmp_path):
    """Proves the entrypoint is a valid runtime entry without needing torch:
    a stub speech_to_speech package stands in for the release and records what
    it was called with."""
    stub_root = tmp_path / "stub"
    pkg = stub_root / "speech_to_speech"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("__version__ = 'stub'\n")
    (pkg / "s2s_pipeline.py").write_text(textwrap.dedent(
        """
        import json, os, sys
        def main():
            with open(os.environ["STUB_RECORD"], "w") as fh:
                json.dump(sys.argv[1:], fh)
        """
    ))

    record = tmp_path / "record.json"
    r = subprocess.run([sys.executable, str(PAYLOAD / "entrypoint"),
                        "--mode", "realtime", "--tts", "elevenlabs"],
                       capture_output=True, text=True,
                       env={"PYTHONPATH": str(stub_root), "STUB_RECORD": str(record), "PATH": ""})

    assert r.returncode == 0, r.stdout + r.stderr
    assert json.loads(record.read_text()) == ["--mode", "realtime", "--tts", "elevenlabs"]
    assert "[experiment-entrypoint] speech_to_speech = " in r.stdout, "provenance must be emitted"


def test_entrypoint_is_a_direct_import_not_an_indirect_launch():
    """Assert the mechanism, not the vocabulary: the file must call the pipeline
    entry in-process rather than shelling out to a launcher it does not own."""
    text = (PAYLOAD / "entrypoint").read_text(encoding="utf-8")
    assert "from speech_to_speech.s2s_pipeline import main" in text
    assert "pipeline_main()" in text
    assert "subprocess" not in text, "no shelling out"
    assert "os.system" not in text
    assert "console_scripts" not in text


def test_manifest_records_the_runtime_program_and_layout(tmp_path):
    builder = _load_module(BUILDER, "builder_layout")
    meta = builder._experiment_metadata(PAYLOAD, "abc", [])
    assert meta["runtime_program"] == "experiment/entrypoint"
    assert meta["layout"]["extract_into"] == "<release_root>"
    assert meta["layout"]["release_tree"] == "release/"


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
