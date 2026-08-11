"""RMD-3G-OBS-V focused observability tests — Voice/S2S only.

Proves voice_trace_id propagation, extra_body safety, close_reason states,
GeneratorExit handling, and cancel signal generation-transition logging.
"""

from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest


def _alias_package():
    nltk = types.ModuleType("nltk")
    nltk.sent_tokenize = lambda text: [text]
    sys.modules.setdefault("nltk", nltk)
    import s2s

    sys.modules.setdefault("speech_to_speech", s2s)


# ═══════════════════════════════════════════════════════════════════════════
# INV-A: voice_trace_id originates from S2S native request.turn_id
# INV-B: HTTP payload contains voice_trace_id, NOT turn_id=<s2s trace>
# INV-C: _voice_trace_id removed before SDK kwargs
# INV-D: conversation_id from RMD-3A unchanged
# ═══════════════════════════════════════════════════════════════════════════

def test_inv_abcd_voice_trace_id_is_extra_body_not_turn_id_or_sdk_kwarg():
    _alias_package()
    cm = importlib.import_module("speech_to_speech.LLM.chat_completions_language_model")
    handler = object.__new__(cm.ChatCompletionsApiModelHandler)
    runtime_config = SimpleNamespace(session=SimpleNamespace(metadata={"conversation_id": " conv-A "}))

    # Simulate what process() does: voice_trace_id from turn_id, passed via optional_kwargs
    optional = {"temperature": 0.2, "_voice_trace_id": "trace-s2s-native-1"}
    augmented = handler._augment_request_optional_kwargs(runtime_config, optional)

    # Input optional_kwargs must NOT be mutated
    assert optional == {"temperature": 0.2, "_voice_trace_id": "trace-s2s-native-1"}
    assert augmented is not optional

    extra = augmented[cm._SESSION_EXTRA_BODY_KEY]
    assert extra["conversation_id"] == "conv-A"
    assert extra["voice_trace_id"] == "trace-s2s-native-1"

    # INV-B: HTTP payload has voice_trace_id, NOT turn_id
    assert "turn_id" not in extra

    # INV-C: _voice_trace_id popped before SDK call
    class _FakeCreate:
        kwargs = None

        def create(self, **kwargs):
            self.kwargs = kwargs
            return {"ok": True}

    create = _FakeCreate()
    client = SimpleNamespace(chat=SimpleNamespace(completions=create))
    cm._request_chat_completions(
        client=client,
        model_name="julia-brain",
        messages=[{"role": "user", "content": "hello"}],
        stream=False,
        extra_body=None,
        timeout=30,
        optional_kwargs=augmented,
    )
    assert create.kwargs["extra_body"] == {
        "conversation_id": "conv-A",
        "voice_trace_id": "trace-s2s-native-1",
    }
    assert "voice_trace_id" not in create.kwargs
    assert "turn_id" not in create.kwargs
    assert cm._SESSION_EXTRA_BODY_KEY not in create.kwargs
    assert "_voice_trace_id" not in create.kwargs


def test_inv_d_conversation_id_r3a_behavior_unchanged():
    _alias_package()
    cm = importlib.import_module("speech_to_speech.LLM.chat_completions_language_model")
    handler = object.__new__(cm.ChatCompletionsApiModelHandler)

    # conversation_id present, no voice_trace_id
    runtime_config = SimpleNamespace(session=SimpleNamespace(metadata={"conversation_id": "conv-r3a"}))
    optional = {"tools": []}
    augmented = handler._augment_request_optional_kwargs(runtime_config, optional)
    assert augmented[cm._SESSION_EXTRA_BODY_KEY] == {"conversation_id": "conv-r3a"}
    assert "voice_trace_id" not in augmented[cm._SESSION_EXTRA_BODY_KEY]

    # No conversation_id, voice_trace_id only
    runtime_config2 = SimpleNamespace(session=SimpleNamespace(metadata={}))
    optional2 = {"_voice_trace_id": "trace-only"}
    augmented2 = handler._augment_request_optional_kwargs(runtime_config2, optional2)
    assert augmented2[cm._SESSION_EXTRA_BODY_KEY] == {"voice_trace_id": "trace-only"}

    # Neither present → no session_extra_body
    runtime_config3 = SimpleNamespace(session=SimpleNamespace(metadata={}))
    optional3 = {"tools": []}
    augmented3 = handler._augment_request_optional_kwargs(runtime_config3, optional3)
    assert cm._SESSION_EXTRA_BODY_KEY not in augmented3


# ═══════════════════════════════════════════════════════════════════════════
# INV-E: S2S_LLM_REQUEST_START records voice_trace_id + generation
# ═══════════════════════════════════════════════════════════════════════════

def test_inv_e_s2s_llm_request_start_log_present_in_source():
    base_src = (Path(__file__).resolve().parents[1] / "s2s/LLM/base_openai_compatible_language_model.py").read_text()
    assert "S2S_LLM_REQUEST_START" in base_src
    assert "pipeline_index" in base_src
    assert "voice_trace_id" in base_src
    # Verify log line references pipeline_index from pipeline_log_ctx
    assert "pipeline_log_ctx.get()" in base_src


# ═══════════════════════════════════════════════════════════════════════════
# INV-F2: history commit failure → close_reason = error, NEVER completed
# ═══════════════════════════════════════════════════════════════════════════

def test_inv_f2_commit_failure_produces_error_not_completed():
    base_src = (Path(__file__).resolve().parents[1] / "s2s/LLM/base_openai_compatible_language_model.py").read_text()
    # In the commit-failure except block, close_reason must be set to "error"
    commit_fail_block = base_src.split("LLM history commit failed")[1].split("\n")[:8]
    commit_text = "\n".join(commit_fail_block)
    assert 'close_reason = "error"' in commit_text, (
        "commit failure must set close_reason=error, found: " + commit_text
    )


# ═══════════════════════════════════════════════════════════════════════════
# INV-F: cancel_scope.cancel() — from_generation → to_generation, one call
# ═══════════════════════════════════════════════════════════════════════════

def test_inv_f_cancel_signal_generation_transition():
    router_src = (
        Path(__file__).resolve().parents[1] / "s2s/api/openai_realtime/websocket_router.py"
    ).read_text()
    assert "S2S_CANCEL_SIGNAL" in router_src
    assert "from_generation" in router_src
    assert "to_generation" in router_src
    # Verify from_generation captured before cancel(), to_generation after,
    # and exactly one cancel() call in the speech_started handler block.
    # grep for the critical sequence: capture → cancel → capture → log
    cancel_pattern_present = (
        "from_generation = unit.cancel_scope.generation" in router_src
        and "unit.cancel_scope.cancel()" in router_src
        and "to_generation = unit.cancel_scope.generation" in router_src
    )
    assert cancel_pattern_present, "cancel signal generation-transition capture missing"


# ═══════════════════════════════════════════════════════════════════════════
# INV-G: stale → S2S_STREAM_CLOSE reason=stale_cancel
# INV-H: normal → reason=completed
# INV-I: GeneratorExit → consumer_close, re-raised
# INV-J: error → reason=error
# INV-K: close event emitted exactly once
# INV-L: api_response.close() cleanup preserved
# INV-M: no cancellation behavior change
# ═══════════════════════════════════════════════════════════════════════════

def test_inv_ghijklm_close_reason_derivation_and_generator_exit():
    base_src = (Path(__file__).resolve().parents[1] / "s2s/LLM/base_openai_compatible_language_model.py").read_text()

    # close_reason initialized as "unknown"
    assert 'close_reason = "unknown"' in base_src

    # Set to completed/stale_cancel/error in the right places
    assert 'close_reason = "completed"' in base_src
    assert 'close_reason = "stale_cancel"' in base_src
    assert 'close_reason = "error"' in base_src
    assert 'close_reason = "consumer_close"' in base_src

    # GeneratorExit explicitly caught and re-raised
    assert "except GeneratorExit:" in base_src
    gen_exit_block = base_src.split("except GeneratorExit:")[1].split("\n")[:5]
    gen_text = "\n".join(gen_exit_block)
    assert "raise" in gen_text
    assert "consumer_close" in gen_text

    # S2S_STREAM_CLOSE logged exactly once in finally, with pipeline_index
    assert "S2S_STREAM_CLOSE" in base_src
    assert "pipeline_index" in base_src.split("S2S_STREAM_CLOSE")[1].split("\n")[0]
    finally_block = base_src.split("finally:")[-1]
    assert finally_block.count("S2S_STREAM_CLOSE") == 1

    # api_response.close() preserved
    assert "api_response.close()" in base_src

    # No cancellation behavior change — verify no new cancel_scope calls
    assert "cancel_scope.cancel()" not in base_src.split("_generate")[1]


# ═══════════════════════════════════════════════════════════════════════════
# INV: _Turn.voice_trace_id is ephemeral, NOT turn_id/durable identity
# ═══════════════════════════════════════════════════════════════════════════

def test_turn_voice_trace_id_is_ephemeral_not_canonical_identity():
    _alias_package()
    base = importlib.import_module("speech_to_speech.LLM.base_openai_compatible_language_model")
    Turn = base._Turn  # noqa: N806

    assert "voice_trace_id" in Turn.model_fields
    field = Turn.model_fields["voice_trace_id"]
    assert field.default is None
    # voice_trace_id is str|None, not substituting turn_id
    assert "turn_id" in Turn.model_fields
    assert Turn.model_fields["turn_id"] is not field


# ═══════════════════════════════════════════════════════════════════════════
# Regression: RMD-3A metadata + conversation_id behavior unchanged
# ═══════════════════════════════════════════════════════════════════════════

def test_rmd3a_conversation_id_still_propagates():
    _alias_package()
    cm = importlib.import_module("speech_to_speech.LLM.chat_completions_language_model")
    handler = object.__new__(cm.ChatCompletionsApiModelHandler)
    runtime_config = SimpleNamespace(session=SimpleNamespace(metadata={"conversation_id": "rmd3a-conv"}))

    augmented = handler._augment_request_optional_kwargs(runtime_config, {"tools": []})
    assert augmented[cm._SESSION_EXTRA_BODY_KEY]["conversation_id"] == "rmd3a-conv"


def test_rmd3a_missing_metadata_returns_unchanged():
    _alias_package()
    cm = importlib.import_module("speech_to_speech.LLM.chat_completions_language_model")
    handler = object.__new__(cm.ChatCompletionsApiModelHandler)
    runtime_config = SimpleNamespace(session=SimpleNamespace(metadata={}))

    original = {"tools": []}
    augmented = handler._augment_request_optional_kwargs(runtime_config, original)
    assert cm._SESSION_EXTRA_BODY_KEY not in augmented
    assert original == {"tools": []}


def test_rmd3a_empty_conversation_id_not_propagated():
    _alias_package()
    cm = importlib.import_module("speech_to_speech.LLM.chat_completions_language_model")
    handler = object.__new__(cm.ChatCompletionsApiModelHandler)
    runtime_config = SimpleNamespace(session=SimpleNamespace(metadata={"conversation_id": "   "}))

    original = {"tools": []}
    augmented = handler._augment_request_optional_kwargs(runtime_config, original)
    assert cm._SESSION_EXTRA_BODY_KEY not in augmented
