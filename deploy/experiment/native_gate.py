#!/usr/bin/env python3
"""Repository-owned native deployment gate (VOICE-EL-P0D-1, Workstream E).

Runs the deployment-critical assertions for an ElevenLabs experiment release
**on the target**, using nothing but the Python standard library plus whatever
the release and the interpreter already provide.

Why stdlib-only
---------------
The server has no pytest, and VOICE SERVER IMMUTABILITY RULE v1 forbids
installing one there. Rather than shipping the whole development test framework
to production, the deployment-critical assertions are extracted here into a
lightweight runner that is itself a build product of the repository. The server
executes this file and nothing else::

    <artifact>/run_tests --expected-sha <sha> --release-root <path>

What it does NOT do
-------------------
No network. Anything that needs a live ElevenLabs connection belongs to the
runtime gate (P0D live phase) and must never be faked here as native validation.

Gate order matters: the import locus is attested second and a failure there
aborts the run immediately, because every later gate imports the pipeline and
would otherwise validate the wrong body of code.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import platform
import sys
import threading
from queue import Queue
from typing import Any, Callable

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import locus  # noqa: E402  (repository-owned sibling module)


EXIT_OK = 0
EXIT_GATE_FAILED = 4
EXIT_LOCUS_REFUSED = 3


# ── helpers ───────────────────────────────────────────────────────────────


def _result(gate_id: str, name: str, ok: bool, detail: str = "") -> dict[str, Any]:
    return {"id": gate_id, "name": name, "ok": bool(ok), "detail": detail}


def _read_json(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ── namespace precondition (Workstream B) ─────────────────────────────────


def check_namespace(env: dict[str, str]) -> dict[str, Any]:
    """The runner refuses to operate outside a repository-defined namespace.

    Specifically it refuses a generic temp root: writing scratch state to
    /tmp root is what the aborted P0D did, and rule 9 exists to prevent it.
    """
    tmp_root = env.get("EXPERIMENT_TMP_ROOT", "")
    problems = []
    if not tmp_root:
        problems.append("EXPERIMENT_TMP_ROOT is not set")
    else:
        real = os.path.realpath(tmp_root)
        if real in ("/tmp", "/var/tmp", "/"):
            problems.append(f"EXPERIMENT_TMP_ROOT must not be a generic scratch root ({real})")
        if not os.path.basename(real).startswith("exp-"):
            problems.append(f"EXPERIMENT_TMP_ROOT must be an experiment namespace (got {real})")
    for var in ("EXPERIMENT_RUN_ROOT", "EXPERIMENT_LOG_ROOT"):
        if not env.get(var):
            problems.append(f"{var} is not set")
    return _result("NAMESPACE", "repository-defined experiment namespace",
                   not problems, "; ".join(problems) or f"tmp root = {tmp_root}")


# ── G1 ────────────────────────────────────────────────────────────────────


def gate_g1_manifest_sha(release_root: str, expected_sha: str) -> dict[str, Any]:
    manifest_path = os.path.join(release_root, "manifest.json")
    if not os.path.isfile(manifest_path):
        return _result("G1", "exact manifest SHA", False, f"no manifest at {manifest_path}")
    manifest = _read_json(manifest_path)
    actual = manifest.get("source_commit")
    if actual != expected_sha:
        return _result("G1", "exact manifest SHA", False, f"expected {expected_sha}, manifest says {actual}")

    archive_name = manifest.get("archive_name", "")
    archive_path = os.path.join(release_root, archive_name)
    if os.path.isfile(archive_path):
        on_disk = _sha256_file(archive_path)
        if on_disk != manifest.get("archive_sha256"):
            return _result("G1", "exact manifest SHA", False,
                           f"archive SHA mismatch: manifest {manifest.get('archive_sha256')} vs on-disk {on_disk}")
        detail = f"source_commit={actual[:12]} archive_sha verified"
    else:
        detail = f"source_commit={actual[:12]} (archive not retained beside the release)"
    return _result("G1", "exact manifest SHA", True, detail)


# ── G2 ────────────────────────────────────────────────────────────────────


def gate_g2_import_locus(release_root: str) -> dict[str, Any]:
    r = locus.attest(release_root)
    detail = f"actual={r['actual'] or '<unresolved>'} classification={r['classification']}"
    if r.get("detail"):
        detail += f" detail={r['detail']}"
    return _result("G2", "exact import locus", r["ok"], detail)


# ── G3 ────────────────────────────────────────────────────────────────────


def gate_g3_required_imports(modules: list[str] | None = None) -> dict[str, Any]:
    mods = modules or [
        "numpy",
        "torch",
        "websockets",
        "openai",
        "speech_to_speech.TTS.elevenlabs_tts_handler",
        "speech_to_speech.s2s_pipeline",
    ]
    missing = []
    for name in mods:
        try:
            importlib.import_module(name)
        except Exception as exc:  # noqa: BLE001
            missing.append(f"{name} ({type(exc).__name__})")
    return _result("G3", "required Python imports", not missing, "missing: " + ", ".join(missing) if missing else "all importable")


# ── G4 ────────────────────────────────────────────────────────────────────


def gate_g4_websockets_compat(ws_min: int, ws_max_exclusive: int) -> dict[str, Any]:
    try:
        ws = importlib.import_module("websockets")
    except Exception as exc:  # noqa: BLE001
        return _result("G4", "websockets compatibility visibility", False, f"cannot import websockets: {exc}")

    raw = getattr(ws, "__version__", "0")
    try:
        major = int(str(raw).split(".")[0])
    except ValueError:
        return _result("G4", "websockets compatibility visibility", False, f"unparsable version {raw!r}")

    ok = ws_min <= major < ws_max_exclusive
    detail = f"websockets {raw} (declared compatible: >={ws_min},<{ws_max_exclusive})"
    if not ok:
        detail += " — OUTSIDE the declared compatibility envelope"
    return _result("G4", "websockets compatibility visibility", ok, detail)


# ── G5 / G6 — provider selection ──────────────────────────────────────────


def _parse(argv: list[str]) -> Any:
    pipeline = importlib.import_module("speech_to_speech.s2s_pipeline")
    original = sys.argv
    sys.argv = ["gate", *argv]
    try:
        return pipeline, pipeline.parse_arguments()
    finally:
        sys.argv = original


def gate_g5_elevenlabs_selectable() -> dict[str, Any]:
    try:
        _, args = _parse(["--tts", "elevenlabs"])
    except BaseException as exc:  # noqa: BLE001 - argparse exits on bad values
        return _result("G5", "--tts elevenlabs available", False, f"{type(exc).__name__}: {exc}")
    ok = args.module_kwargs.tts == "elevenlabs"
    return _result("G5", "--tts elevenlabs available", ok, f"parsed tts={args.module_kwargs.tts!r}")


def gate_g6_qwen3_default() -> dict[str, Any]:
    try:
        _, default_args = _parse([])
        _, explicit = _parse(["--tts", "qwen3"])
    except BaseException as exc:  # noqa: BLE001
        return _result("G6", "qwen3 remains available and default", False, f"{type(exc).__name__}: {exc}")
    ok = default_args.module_kwargs.tts == "qwen3" and explicit.module_kwargs.tts == "qwen3"
    return _result("G6", "qwen3 remains available and default", ok,
                   f"default={default_args.module_kwargs.tts!r} explicit={explicit.module_kwargs.tts!r}")


# ── shared: build the realtime unit with only the model stages stubbed ────


def _prepare(tts: str) -> tuple[Any, Any]:
    pipeline, args = _parse(["--mode", "realtime", "--tts", tts])
    pipeline.prepare_all_args(
        args.module_kwargs,
        args.whisper_stt_handler_kwargs,
        args.paraformer_stt_handler_kwargs,
        args.faster_whisper_stt_handler_kwargs,
        args.mlx_audio_whisper_stt_handler_kwargs,
        args.parakeet_tdt_stt_handler_kwargs,
        args.language_model_handler_kwargs,
        args.responses_api_language_model_handler_kwargs,
        args.chat_tts_handler_kwargs,
        args.facebook_mms_tts_handler_kwargs,
        args.pocket_tts_handler_kwargs,
        args.kokoro_tts_handler_kwargs,
        args.qwen3_tts_handler_kwargs,
        args.elevenlabs_tts_handler_kwargs,
    )
    return pipeline, args


class _Stage:
    """Stand-in for a model-loading stage; this gate never loads weights."""

    def __init__(self, *a, **k):
        self.queue_in = k.get("queue_in")
        self.queue_out = k.get("queue_out")

    def run(self):
        pass

    def stop(self):
        pass


_FAKE_UNIT_HANDLERS: list[Any] = []


def gate_g7_handler_construction() -> dict[str, Any]:
    try:
        pipeline, args = _prepare("elevenlabs")
        handler_cls = importlib.import_module("speech_to_speech.TTS.elevenlabs_tts_handler").ElevenLabsTTSHandler
        handler = handler_cls(
            threading.Event(),
            queue_in=Queue(),
            queue_out=Queue(),
            setup_args=(threading.Event(),),
            setup_kwargs=vars(args.elevenlabs_tts_handler_kwargs),
        )
    except Exception as exc:  # noqa: BLE001
        return _result("G7", "ElevenLabs handler construction", False, f"{type(exc).__name__}: {exc}")
    ok = handler.output_format == "pcm_16000"
    return _result("G7", "ElevenLabs handler construction", ok,
                   f"{type(handler).__name__} output_format={handler.output_format}")


def gate_g8_realtime_call_contract() -> dict[str, Any]:
    """build_pipeline(realtime) must forward the ElevenLabs kwargs to the unit builder."""
    try:
        pipeline, args = _prepare("elevenlabs")
        captured: dict[str, Any] = {}

        class _FakeUnit:
            handlers: list[Any] = []

        def spy(**kwargs):
            captured.update(kwargs)
            return _FakeUnit()

        original = pipeline._build_realtime_pipeline_unit
        pipeline._build_realtime_pipeline_unit = spy
        try:
            pipeline.build_pipeline(
                args.module_kwargs,
                args.socket_receiver_kwargs,
                args.socket_sender_kwargs,
                args.websocket_streamer_kwargs,
                args.vad_handler_kwargs,
                args.whisper_stt_handler_kwargs,
                args.faster_whisper_stt_handler_kwargs,
                args.paraformer_stt_handler_kwargs,
                args.mlx_audio_whisper_stt_handler_kwargs,
                args.parakeet_tdt_stt_handler_kwargs,
                args.language_model_handler_kwargs,
                args.responses_api_language_model_handler_kwargs,
                args.chat_tts_handler_kwargs,
                args.facebook_mms_tts_handler_kwargs,
                args.pocket_tts_handler_kwargs,
                args.kokoro_tts_handler_kwargs,
                args.qwen3_tts_handler_kwargs,
                args.elevenlabs_tts_handler_kwargs,
                pipeline.initialize_queues_and_events(),
            )
        finally:
            pipeline._build_realtime_pipeline_unit = original
    except Exception as exc:  # noqa: BLE001
        return _result("G8", "realtime caller/callee wiring", False, f"{type(exc).__name__}: {exc}")

    ok = captured.get("elevenlabs_tts_handler_kwargs") is args.elevenlabs_tts_handler_kwargs
    return _result("G8", "realtime caller/callee wiring", ok,
                   "elevenlabs_tts_handler_kwargs forwarded by identity" if ok
                   else f"not forwarded; keys={sorted(k for k in captured if k.endswith('_kwargs'))}")


def gate_g9_cancel_injection() -> dict[str, Any]:
    """The realtime unit must inject the unit's CancelScope into the handler."""
    try:
        pipeline, args = _prepare("elevenlabs")
        handler_cls = importlib.import_module("speech_to_speech.TTS.elevenlabs_tts_handler").ElevenLabsTTSHandler

        class _SentinelTracker:
            pass

        original_vad = pipeline.VADHandler
        original_stt = pipeline.get_stt_handler
        original_llm = pipeline.get_llm_handler
        original_tracker = pipeline.SpeculativeTurnTracker
        pipeline.VADHandler = lambda *a, **k: _Stage()
        pipeline.get_stt_handler = lambda *a, **k: _Stage()
        pipeline.get_llm_handler = lambda *a, **k: _Stage()
        pipeline.SpeculativeTurnTracker = _SentinelTracker
        try:
            unit = pipeline._build_realtime_pipeline_unit(
                index=0,
                stop_event=threading.Event(),
                module_kwargs=args.module_kwargs,
                vad_handler_kwargs=args.vad_handler_kwargs,
                whisper_stt_handler_kwargs=args.whisper_stt_handler_kwargs,
                faster_whisper_stt_handler_kwargs=args.faster_whisper_stt_handler_kwargs,
                paraformer_stt_handler_kwargs=args.paraformer_stt_handler_kwargs,
                mlx_audio_whisper_stt_handler_kwargs=args.mlx_audio_whisper_stt_handler_kwargs,
                parakeet_tdt_stt_handler_kwargs=args.parakeet_tdt_stt_handler_kwargs,
                language_model_handler_kwargs=args.language_model_handler_kwargs,
                responses_api_language_model_handler_kwargs=args.responses_api_language_model_handler_kwargs,
                chat_tts_handler_kwargs=args.chat_tts_handler_kwargs,
                facebook_mms_tts_handler_kwargs=args.facebook_mms_tts_handler_kwargs,
                pocket_tts_handler_kwargs=args.pocket_tts_handler_kwargs,
                kokoro_tts_handler_kwargs=args.kokoro_tts_handler_kwargs,
                qwen3_tts_handler_kwargs=args.qwen3_tts_handler_kwargs,
                elevenlabs_tts_handler_kwargs=args.elevenlabs_tts_handler_kwargs,
            )
        finally:
            pipeline.VADHandler = original_vad
            pipeline.get_stt_handler = original_stt
            pipeline.get_llm_handler = original_llm
            pipeline.SpeculativeTurnTracker = original_tracker
    except Exception as exc:  # noqa: BLE001
        return _result("G9", "CancelScope / tracker injection", False, f"{type(exc).__name__}: {exc}")

    handlers = [h for h in unit.handlers if isinstance(h, handler_cls)]
    if len(handlers) != 1:
        return _result("G9", "CancelScope / tracker injection", False, f"expected 1 handler, found {len(handlers)}")
    handler = handlers[0]
    scope_ok = handler.cancel_scope is unit.cancel_scope and handler.cancel_scope is not None
    tracker_ok = isinstance(handler.speculative_turns, _SentinelTracker)
    ok = scope_ok and tracker_ok
    return _result("G9", "CancelScope / tracker injection", ok,
                   f"cancel_scope wired={scope_ok} tracker injected={tracker_ok}")


# ── G10 ───────────────────────────────────────────────────────────────────


def gate_g10_pcm_contract() -> dict[str, Any]:
    try:
        mod = importlib.import_module("speech_to_speech.TTS.elevenlabs_tts_handler")
    except Exception as exc:  # noqa: BLE001
        return _result("G10", "pcm_16000 output contract", False, f"{type(exc).__name__}: {exc}")
    checks = {"PIPELINE_SR": mod.PIPELINE_SR, "DEFAULT_OUTPUT_FORMAT": mod.DEFAULT_OUTPUT_FORMAT,
              "BLOCK_BYTES": mod.BLOCK_BYTES}
    ok = checks["PIPELINE_SR"] == 16000 and checks["DEFAULT_OUTPUT_FORMAT"] == "pcm_16000" and checks["BLOCK_BYTES"] == 1024
    return _result("G10", "pcm_16000 output contract", ok, f"{checks} (expect 16000 / pcm_16000 / 1024)")


# ── runner ────────────────────────────────────────────────────────────────


def run_gates(release_root: str, expected_sha: str, env: dict[str, str] | None = None,
              up_to: str | None = None) -> dict[str, Any]:
    env = dict(os.environ if env is None else env)
    ws_min = int(env.get("EXPERIMENT_WEBSOCKETS_MIN", "12"))
    ws_max = int(env.get("EXPERIMENT_WEBSOCKETS_MAX_EXCLUSIVE", "16"))

    gates: list[dict[str, Any]] = [check_namespace(env)]
    gates.append(gate_g1_manifest_sha(release_root, expected_sha))
    gates.append(gate_g2_import_locus(release_root))

    refused = not gates[-1]["ok"]
    if refused:
        return {"release_root": release_root, "expected_sha": expected_sha,
                "refused": True, "gates": gates}

    remaining: list[tuple[str, Callable[[], dict[str, Any]]]] = [
        ("G3", lambda: gate_g3_required_imports()),
        ("G4", lambda: gate_g4_websockets_compat(ws_min, ws_max)),
        ("G5", gate_g5_elevenlabs_selectable),
        ("G6", gate_g6_qwen3_default),
        ("G7", gate_g7_handler_construction),
        ("G8", gate_g8_realtime_call_contract),
        ("G9", gate_g9_cancel_injection),
        ("G10", gate_g10_pcm_contract),
    ]
    for gate_id, fn in remaining:
        if up_to and gate_id > up_to:
            break
        try:
            gates.append(fn())
        except Exception as exc:  # noqa: BLE001 - a gate that raises is a failed gate
            gates.append(_result(gate_id, gate_id, False, f"unexpected {type(exc).__name__}: {exc}"))

    return {"release_root": release_root, "expected_sha": expected_sha,
            "refused": False, "gates": gates}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Native deployment gate for an experiment release.")
    parser.add_argument("--release-root", required=True)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    report = run_gates(args.release_root, args.expected_sha)

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print("NATIVE DEPLOYMENT GATE")
        print(f"  release  : {report['release_root']}")
        print(f"  expected : {report['expected_sha']}")
        print(f"  python   : {sys.version.split()[0]} on {platform.system()} {platform.machine()}")
        print("")
        for g in report["gates"]:
            print(f"  [{'PASS' if g['ok'] else 'FAIL'}] {g['id']:9s} {g['name']}")
            if g["detail"]:
                print(f"            {g['detail']}")

    if report["refused"]:
        print("\nREFUSED: import locus is not the experiment release; later gates not run.", file=sys.stderr)
        return EXIT_LOCUS_REFUSED

    failed = [g["id"] for g in report["gates"] if not g["ok"]]
    if failed:
        print(f"\nGATE FAILED: {', '.join(failed)}", file=sys.stderr)
        print("RESULT = DEPLOYMENT_ARTIFACT_INCOMPLETE — return to the repository. "
              "Do NOT repair on the server.", file=sys.stderr)
        return EXIT_GATE_FAILED

    print("\nALL GATES PASS")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
