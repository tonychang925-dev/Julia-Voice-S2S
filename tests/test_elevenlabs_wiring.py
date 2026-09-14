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
# W7 — cancel_scope / speculative_turns reach the new handler
# ═══════════════════════════════════════════════════════════════════════════


def test_w7_realtime_unit_injects_cancel_scope_into_elevenlabs_kwargs():
    """The realtime builder mutates each TTS kwargs object with cancel_scope and
    speculative_turns before building handlers. If the new provider is missing
    from that loop, cancellation silently becomes inert in production."""
    P = _pipeline()
    source = inspect.getsource(P._build_realtime_pipeline_unit)
    assert "elevenlabs_tts_kw" in source, "elevenlabs must be in the vars(kw) injection loop"
