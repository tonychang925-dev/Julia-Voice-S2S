from __future__ import annotations

import importlib
import sys
import types
from types import SimpleNamespace


def _import_chat_module():
    # Local repo package directory is `s2s`, while deployed/imported package name
    # is `speech_to_speech`. Tests alias only in-process; no environment mutation.
    nltk = types.ModuleType("nltk")
    nltk.sent_tokenize = lambda text: [text]
    sys.modules.setdefault("nltk", nltk)
    import s2s
    sys.modules.setdefault("speech_to_speech", s2s)
    return importlib.import_module("speech_to_speech.LLM.chat_completions_language_model")


def _import_base_module():
    _import_chat_module()
    return importlib.import_module("speech_to_speech.LLM.base_openai_compatible_language_model")


class _FakeCreate:
    def __init__(self):
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return {"ok": True}


class _FakeClient:
    def __init__(self):
        self.create = _FakeCreate()
        self.chat = SimpleNamespace(completions=self.create)


def test_rmd3a_t03_t04_conversation_id_is_extra_body_not_sdk_kwarg():
    mod = _import_chat_module()
    handler = object.__new__(mod.ChatCompletionsApiModelHandler)
    runtime_config = SimpleNamespace(session=SimpleNamespace(metadata={"conversation_id": " conv-A "}))

    optional = {"temperature": 0.2}
    augmented = handler._augment_request_optional_kwargs(runtime_config, optional)
    assert optional == {"temperature": 0.2}
    assert augmented is not optional
    assert augmented[mod._SESSION_EXTRA_BODY_KEY] == {"conversation_id": "conv-A"}

    client = _FakeClient()
    mod._request_chat_completions(
        client=client,
        model_name="julia-brain",
        messages=[{"role": "user", "content": "hello"}],
        stream=False,
        extra_body=None,
        timeout=30,
        optional_kwargs=augmented,
    )
    kwargs = client.create.kwargs
    assert kwargs["extra_body"] == {"conversation_id": "conv-A"}
    assert "conversation_id" not in kwargs
    assert mod._SESSION_EXTRA_BODY_KEY not in kwargs
    assert kwargs["temperature"] == 0.2


def test_rmd3a_t05_static_extra_body_survives_and_is_not_mutated():
    mod = _import_chat_module()
    client = _FakeClient()
    static_extra_body = {"thinking": {"type": "disabled"}}
    optional = {mod._SESSION_EXTRA_BODY_KEY: {"conversation_id": "conv-B"}}

    mod._request_chat_completions(
        client=client,
        model_name="julia-brain",
        messages=[],
        stream=True,
        extra_body=static_extra_body,
        timeout=30,
        optional_kwargs=optional,
    )

    assert static_extra_body == {"thinking": {"type": "disabled"}}
    assert client.create.kwargs["extra_body"] == {
        "thinking": {"type": "disabled"},
        "conversation_id": "conv-B",
    }
    assert client.create.kwargs["stream_options"] == {"include_usage": True}


def test_rmd3a_t06_missing_or_empty_metadata_keeps_request_unchanged():
    mod = _import_chat_module()
    handler = object.__new__(mod.ChatCompletionsApiModelHandler)
    original = {"tools": []}

    assert handler._augment_request_optional_kwargs(
        SimpleNamespace(session=SimpleNamespace(metadata={})), original
    ) is original
    assert handler._augment_request_optional_kwargs(
        SimpleNamespace(session=SimpleNamespace(metadata={"conversation_id": "  "})), original
    ) is original

    client = _FakeClient()
    mod._request_chat_completions(
        client=client,
        model_name="julia-brain",
        messages=[],
        stream=False,
        extra_body=None,
        timeout=30,
        optional_kwargs=original,
    )
    assert client.create.kwargs["extra_body"] is None
    assert "conversation_id" not in client.create.kwargs


def test_rmd3a_t07_base_openai_compatible_hook_is_noop_for_other_handlers():
    base = _import_base_module()

    class OtherHandler(base.BaseOpenAICompatibleHandler):
        def warmup(self): pass
        def _build_compaction_generate_fn(self): pass
        def _serialize(self, active_chat): pass
        def _request(self, api_input, optional_kwargs): pass
        def _iter_stream_events(self, api_response): return iter(())
        def _iter_response_events(self, api_response): return iter(())
        def _build_optional_kwargs(self, req_tools, req_tool_choice): return {}

    handler = object.__new__(OtherHandler)
    optional = {"temperature": 0.1}
    assert handler._augment_request_optional_kwargs(SimpleNamespace(), optional) is optional
