"""VOICE-EL-P0B — provider-selector wiring tests.

These tests import `speech_to_speech.s2s_pipeline`, which pulls the full runtime
dependency set (torch, transformers, openai, nltk resources). Where that set is
absent the whole module skips rather than silently passing — see the guard
below. The pure-argument tests that need none of it live in
`tests/test_elevenlabs_arguments.py`.

The important assertion here is `test_w5_*`: prepare_all_args()'s rename step
produces the kwargs dict that is splatted into the handler's setup(). That
contract is invisible to type checkers and static analysis, and its violation
is exactly what broke the first wiring attempt (`gen_kwargs` was injected by
rename_args but the handler's setup() did not accept it).
"""

from __future__ import annotations

import importlib
import importlib.util
import inspect
import sys
import types
from queue import Queue
from threading import Event

import pytest

# The full pipeline needs the runtime dependency set; skip cleanly where absent.
pytest.importorskip("torch", reason="s2s_pipeline requires the full runtime dependency set")
pytest.importorskip("openai", reason="s2s_pipeline requires the full runtime dependency set")


_Qwen3_needs_mlx = sys.platform == "darwin" and importlib.util.find_spec("mlx_audio") is None
qwen3_constructible = pytest.mark.skipif(
    _Qwen3_needs_mlx,
    reason="Qwen3 TTS selects the mlx-audio backend on Apple Silicon, which is not installed here; "
    "this path runs on the Linux/GPU target and in any environment with mlx-audio present",
)


def _alias_package():
    nltk = types.ModuleType("nltk")
    nltk.sent_tokenize = lambda text: [text]  # noqa: E731
    nltk.data = types.ModuleType("nltk.data")
    nltk.data.find = lambda *a, **k: "stub"  # satisfy module-level resource probe
    nltk.download = lambda *a, **k: True
    sys.modules.setdefault("nltk", nltk)
    import s2s

    sys.modules.setdefault("speech_to_speech", s2s)


def _pipeline():
    _alias_package()
    return importlib.import_module("speech_to_speech.s2s_pipeline")


def _parse(argv):
    P = _pipeline()
    sys.argv = ["prog", *argv]
    return P, P.parse_arguments()


def _prepared(tts):
    """Full argument-preparation path, exactly as main() runs it."""
    P, args = _parse(["--tts", tts])
    P.prepare_all_args(
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
    return P, args


def _build(P, args):
    return P.get_tts_handler(
        args.module_kwargs,
        Event(),
        Queue(),
        Queue(),
        Event(),
        args.chat_tts_handler_kwargs,
        args.facebook_mms_tts_handler_kwargs,
        args.pocket_tts_handler_kwargs,
        args.kokoro_tts_handler_kwargs,
        args.qwen3_tts_handler_kwargs,
        args.elevenlabs_tts_handler_kwargs,
    )


# ═══════════════════════════════════════════════════════════════════════════
# W1-W3 — provider selection parses
# ═══════════════════════════════════════════════════════════════════════════


def test_w1_tts_elevenlabs_is_accepted_by_the_real_cli_parser():
    _, args = _parse(["--tts", "elevenlabs"])
    assert args.module_kwargs.tts == "elevenlabs"


def test_w2_default_provider_is_unchanged_qwen3():
    _, args = _parse([])
    assert args.module_kwargs.tts == "qwen3"


def test_w3_unknown_provider_is_still_rejected():
    P = _pipeline()
    sys.argv = ["prog", "--tts", "not-a-provider"]
    with pytest.raises(SystemExit):
        P.parse_arguments()


# ═══════════════════════════════════════════════════════════════════════════
# W4 — dispatch returns the right handler for each provider
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    ("tts", "expected"),
    [
        pytest.param("qwen3", "Qwen3TTSHandler", marks=qwen3_constructible),
        ("elevenlabs", "ElevenLabsTTSHandler"),
    ],
)
def test_w4_get_tts_handler_dispatches_by_provider(tts, expected):
    P, args = _prepared(tts)
    handler = _build(P, args)
    assert type(handler).__name__ == expected


# ═══════════════════════════════════════════════════════════════════════════
# W5 — the rename -> setup() kwargs contract
#
# prepare_all_args() -> rename_args() strips the provider prefix and injects
# `gen_kwargs`; that dict is splatted into setup(). Nothing in the type system
# ties the two together, so assert the containment explicitly for every
# provider. This is the regression test for the `gen_kwargs` defect.
# ═══════════════════════════════════════════════════════════════════════════


def _setup_params(handler_class):
    return set(inspect.signature(handler_class.setup).parameters)


@pytest.mark.parametrize(
    ("tts", "args_attr", "module_path", "class_name"),
    [
        ("qwen3", "qwen3_tts_handler_kwargs", "speech_to_speech.TTS.qwen3_tts_handler", "Qwen3TTSHandler"),
        (
            "elevenlabs",
            "elevenlabs_tts_handler_kwargs",
            "speech_to_speech.TTS.elevenlabs_tts_handler",
            "ElevenLabsTTSHandler",
        ),
    ],
)
def test_w5_renamed_kwargs_are_all_accepted_by_handler_setup(tts, args_attr, module_path, class_name):
    _, args = _prepared(tts)
    produced = set(vars(getattr(args, args_attr)))
    accepted = _setup_params(getattr(importlib.import_module(module_path), class_name))

    unexpected = produced - accepted
    assert not unexpected, (
        f"{tts}: prepare_all_args produces kwargs that {class_name}.setup() does not accept: "
        f"{sorted(unexpected)} — this is exactly the class of wiring defect that must not ship"
    )


def test_w5b_elevenlabs_kwargs_carry_the_expected_names_after_rename():
    _, args = _prepared("elevenlabs")
    produced = set(vars(args.elevenlabs_tts_handler_kwargs))
    assert "gen_kwargs" in produced, "rename_args injects gen_kwargs; setup() must accept it"
    assert {"api_key_env", "voice_id", "model_id", "output_format", "ws_url"} <= produced
    assert not any(name.startswith("elevenlabs_") for name in produced), "prefix must be stripped"


# ═══════════════════════════════════════════════════════════════════════════
# W6 — the handler is actually instantiable through the real selector
# ═══════════════════════════════════════════════════════════════════════════


def test_w6_elevenlabs_handler_instantiates_through_the_selector():
    P, args = _prepared("elevenlabs")
    handler = _build(P, args)
    assert handler.output_format == "pcm_16000"
    assert handler.model_id == "eleven_v3_conversational"
    assert handler.gen_kwargs == {}


@qwen3_constructible
def test_w6b_qwen3_handler_still_instantiates_unchanged():
    P, args = _prepared("qwen3")
    handler = _build(P, args)
    assert handler.blocksize == 512, "existing qwen3 default must not move"


# ═══════════════════════════════════════════════════════════════════════════
# R1 — the realtime pool caller/callee contract
#
# A source-string assertion lived here previously. It passed on a candidate where
# build_pipeline() did NOT pass elevenlabs_tts_handler_kwargs to
# _build_realtime_pipeline_unit(), which is a TypeError on the production
# topology. Source inspection cannot see a missing call argument. These tests
# exercise the call instead.
# ═══════════════════════════════════════════════════════════════════════════


class _FakeUnit:
    """Stand-in for a PipelineUnit; only `.handlers` is read by build_pipeline."""

    def __init__(self):
        self.handlers: list[Any] = []


def _call_build_pipeline(P, args, queues_and_events):
    return P.build_pipeline(
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
        queues_and_events,
    )


def test_r1_build_pipeline_realtime_forwards_elevenlabs_kwargs_to_the_unit_builder(monkeypatch):
    """build_pipeline(mode=realtime) must hand the ElevenLabs argument object to
    _build_realtime_pipeline_unit. The callee requires it, so a missing kwarg is
    a TypeError on the real topology — this asserts the call, not the source."""
    P = _pipeline()
    # Must go through prepare_all_args(): build_llm_proxy_config() indexes the
    # post-rename keys, exactly as main() orders it.
    _, args = _prepared("elevenlabs")
    assert args.module_kwargs.mode == "realtime"

    captured: dict[str, Any] = {}

    def spy(**kwargs):
        captured.update(kwargs)
        return _FakeUnit()

    monkeypatch.setattr(P, "_build_realtime_pipeline_unit", spy)
    _call_build_pipeline(P, args, P.initialize_queues_and_events())

    assert "elevenlabs_tts_handler_kwargs" in captured, (
        "build_pipeline(realtime) dropped elevenlabs_tts_handler_kwargs — "
        "the real _build_realtime_pipeline_unit would raise TypeError here"
    )
    assert captured["elevenlabs_tts_handler_kwargs"] is args.elevenlabs_tts_handler_kwargs


def test_r1_realtime_unit_really_constructs_the_elevenlabs_handler(monkeypatch):
    """Real _build_realtime_pipeline_unit -> real _build_pipeline_handlers ->
    real get_tts_handler -> a real ElevenLabsTTSHandler, with cancel_scope wired.

    Only the model-loading stages (VAD / STT / LLM) are stubbed: they need model
    weights that this machine does not have. The TTS dispatch under test is real.
    """
    import speech_to_speech.TTS.elevenlabs_tts_handler as el

    P = _pipeline()
    _, args = _prepared("elevenlabs")

    monkeypatch.setattr(P, "VADHandler", lambda *a, **k: _FakeUnit())
    monkeypatch.setattr(P, "get_stt_handler", lambda *a, **k: _FakeUnit())
    monkeypatch.setattr(P, "get_llm_handler", lambda *a, **k: _FakeUnit())

    # Sentinel tracker so the injection can be proven by type, not by `is not None`:
    # _build_realtime_pipeline_unit constructs it internally, so there is no other
    # handle on the same instance.
    class _SentinelTracker:
        pass

    monkeypatch.setattr(P, "SpeculativeTurnTracker", _SentinelTracker)

    unit = P._build_realtime_pipeline_unit(
        index=0,
        stop_event=__import__("threading").Event(),
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

    tts_handlers = [h for h in unit.handlers if isinstance(h, el.ElevenLabsTTSHandler)]
    assert len(tts_handlers) == 1, f"expected exactly one ElevenLabs handler, got {unit.handlers}"
    handler = tts_handlers[0]

    # Behavioural replacement for the removed source-string check: the realtime
    # builder must have injected the unit's CancelScope (and the tracker) into the
    # new provider, or cancellation would be silently inert in production.
    assert handler.cancel_scope is unit.cancel_scope
    assert isinstance(handler.speculative_turns, _SentinelTracker)
    assert handler.output_format == "pcm_16000"

