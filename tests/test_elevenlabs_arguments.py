"""VOICE-EL-P0B — provider-selection / argument-surface tests (no runtime deps).

Deliberately dependency-light: these run under the default interpreter, where
`tests/test_elevenlabs_wiring.py` (which needs torch/transformers/openai) skips.
Together the two files cover P0B in both environments.
"""

from __future__ import annotations

import importlib
import sys
import types
from dataclasses import fields
from typing import get_args, get_type_hints

import pytest


def _imports():
    nltk = types.ModuleType("nltk")
    nltk.sent_tokenize = lambda text: [text]  # noqa: E731
    sys.modules.setdefault("nltk", nltk)
    import s2s

    sys.modules.setdefault("speech_to_speech", s2s)
    return types.SimpleNamespace(
        module_args=importlib.import_module("speech_to_speech.arguments_classes.module_arguments"),
        el_args=importlib.import_module("speech_to_speech.arguments_classes.elevenlabs_tts_arguments"),
        handler=importlib.import_module("speech_to_speech.TTS.elevenlabs_tts_handler"),
    )


# ═══════════════════════════════════════════════════════════════════════════
# A1 — the provider is a first-class member of the --tts choice set
# ═══════════════════════════════════════════════════════════════════════════


def test_a1_tts_literal_contains_elevenlabs_and_still_contains_the_old_providers():
    M = _imports()
    hint = get_type_hints(M.module_args.ModuleArguments)["tts"]
    # Optional[Literal[...]] -> (Literal[...], NoneType)
    literal = get_args(hint)[0]
    members = set(get_args(literal))

    assert "elevenlabs" in members
    assert {"chatTTS", "facebookMMS", "pocket", "kokoro", "qwen3"} <= members, (
        "the existing provider set must not shrink"
    )


def test_a2_default_provider_remains_qwen3():
    M = _imports()
    assert M.module_args.ModuleArguments().tts == "qwen3"
    assert M.module_args.ModuleArguments(tts="elevenlabs").tts == "elevenlabs"


# ═══════════════════════════════════════════════════════════════════════════
# A3 — the argument surface, and the secret never being a CLI value
# ═══════════════════════════════════════════════════════════════════════════


def test_a3_elevenlabs_arguments_expose_the_expected_surface():
    M = _imports()
    names = {f.name for f in fields(M.el_args.ElevenLabsTTSHandlerArguments)}
    assert names == {
        "elevenlabs_api_key_env",
        "elevenlabs_voice_id",
        "elevenlabs_model_id",
        "elevenlabs_output_format",
        "elevenlabs_ws_url",
        "elevenlabs_connect_timeout_s",
        "elevenlabs_recv_poll_s",
    }


def test_a4_api_key_is_referenced_by_env_var_name_only_never_as_a_value():
    M = _imports()
    names = {f.name for f in fields(M.el_args.ElevenLabsTTSHandlerArguments)}
    assert not any(n.endswith("_api_key") for n in names), (
        "a CLI field holding the key itself would leak it into argv / `ps`"
    )
    assert "elevenlabs_api_key_env" in names


def test_a5_defaults_match_the_measured_contract():
    M = _imports()
    a = M.el_args.ElevenLabsTTSHandlerArguments()
    assert a.elevenlabs_model_id == "eleven_v3_conversational"
    assert a.elevenlabs_output_format == "pcm_16000", "measured mono S16LE @16k — no resampling"
    assert a.elevenlabs_api_key_env == "ELEVENLABS_API_KEY"


def test_a6_handler_setup_accepts_the_renamed_argument_names():
    """The rename_args contract, asserted without importing s2s_pipeline.

    rename_args(prefix="elevenlabs") strips the prefix from every field, so the
    handler must accept those stripped names (plus the injected gen_kwargs).
    """
    import inspect

    M = _imports()
    stripped = {
        f.name[len("elevenlabs_") :] for f in fields(M.el_args.ElevenLabsTTSHandlerArguments)
    }
    accepted = set(inspect.signature(M.handler.ElevenLabsTTSHandler.setup).parameters)

    missing = stripped - accepted
    assert not missing, f"handler.setup() cannot accept the renamed kwargs: {sorted(missing)}"
    assert "gen_kwargs" in accepted, "rename_args always injects gen_kwargs"


def test_a7_output_rate_matches_the_pipeline_rate():
    M = _imports()
    assert M.handler.PIPELINE_SR == 16000
    assert M.handler.BLOCK_BYTES == 1024, "512 samples of int16 mono"


if __name__ == "__main__":  # pragma: no cover
    sys.exit(pytest.main([__file__, "-q"]))
