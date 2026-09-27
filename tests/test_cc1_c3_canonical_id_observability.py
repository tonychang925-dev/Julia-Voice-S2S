from __future__ import annotations

import importlib
import sys
import types
from types import SimpleNamespace


def _alias_package():
    nltk = types.ModuleType("nltk")
    nltk.sent_tokenize = lambda text: [text]
    sys.modules.setdefault("nltk", nltk)
    import s2s

    sys.modules.setdefault("speech_to_speech", s2s)


def _imports():
    _alias_package()
    return {
        "chat": importlib.import_module("speech_to_speech.LLM.chat_completions_language_model"),
        "runtime": importlib.import_module("speech_to_speech.api.openai_realtime.runtime_config"),
        "realtime": importlib.import_module("openai.types.realtime"),
    }


class _StrictCreate:
    def __init__(self):
        self.kwargs = None

    def create(
        self,
        *,
        model,
        messages,
        stream,
        extra_body,
        timeout,
        temperature=None,
        stream_options=None,
    ):
        self.kwargs = {
            "model": model,
            "messages": messages,
            "stream": stream,
            "extra_body": extra_body,
            "timeout": timeout,
            "temperature": temperature,
            "stream_options": stream_options,
        }
        return {"ok": True}


class _StrictClient:
    def __init__(self):
        self.create = _StrictCreate()
        self.chat = SimpleNamespace(completions=self.create)


def _apply_session_update(raw_session: dict):
    mods = _imports()
    event = mods["realtime"].SessionUpdateEvent.model_validate(
        {"type": "session.update", "session": raw_session}
    )
    cfg = mods["runtime"].RuntimeConfig()
    cfg.apply_session_update(event.session)
    return mods, cfg


def _brain_request_from_runtime_config(cfg, voice_trace_id: str = "trace-c3"):
    cm = _imports()["chat"]
    handler = object.__new__(cm.ChatCompletionsApiModelHandler)
    optional = {"temperature": 0.1, "_voice_trace_id": voice_trace_id}
    augmented = handler._augment_request_optional_kwargs(cfg, optional)
    client = _StrictClient()
    cm._request_chat_completions(
        client=client,
        model_name="julia-brain",
        messages=[{"role": "user", "content": "hello"}],
        stream=False,
        extra_body=None,
        timeout=30,
        optional_kwargs=augmented,
    )
    return cm, client.create.kwargs


def test_cc1_c3_session_update_to_brain_request_preserves_canonical_conversation_id(caplog):
    mods, cfg = _apply_session_update(
        {
            "type": "realtime",
            "instructions": "voice test",
            "audio": {"output": {"voice": "Aiden"}},
            "metadata": {"conversation_id": "conv-cc1-c3"},
        }
    )

    assert cfg.session.metadata == {"conversation_id": "conv-cc1-c3"}

    with caplog.at_level("INFO"):
        cm, kwargs = _brain_request_from_runtime_config(cfg, voice_trace_id="voice-trace-c3")

    assert kwargs["extra_body"] == {
        "conversation_id": "conv-cc1-c3",
        "voice_trace_id": "voice-trace-c3",
    }
    assert "conversation_id" not in kwargs
    assert "voice_trace_id" not in kwargs
    assert "turn_id" not in kwargs
    assert cm._SESSION_EXTRA_BODY_KEY not in kwargs
    assert any(
        "CC1_BRAIN_REQUEST conversation_id=conv-cc1-c3 voice_trace_id=voice-trace-c3" in rec.message
        for rec in caplog.records
    )


def test_cc1_c3_missing_session_metadata_keeps_conversation_id_absent(caplog):
    _mods, cfg = _apply_session_update(
        {
            "type": "realtime",
            "instructions": "voice test",
            "audio": {"output": {"voice": "Aiden"}},
        }
    )

    assert getattr(cfg.session, "metadata", None) is None

    with caplog.at_level("INFO"):
        _cm, kwargs = _brain_request_from_runtime_config(cfg, voice_trace_id="voice-trace-only")

    assert kwargs["extra_body"] == {"voice_trace_id": "voice-trace-only"}
    assert "conversation_id" not in kwargs["extra_body"]
    assert "turn_id" not in kwargs["extra_body"]
    assert any(
        "CC1_BRAIN_REQUEST conversation_id=EMPTY voice_trace_id=voice-trace-only" in rec.message
        for rec in caplog.records
    )
