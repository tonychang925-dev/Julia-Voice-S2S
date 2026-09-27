from __future__ import annotations

import importlib
import sys
import types
from types import SimpleNamespace


def _import_chat_module():
    nltk = types.ModuleType("nltk")
    nltk.sent_tokenize = lambda text: [text]
    nltk.data = types.ModuleType("nltk.data")
    nltk.data.find = lambda *_args, **_kwargs: "stub"
    sys.modules.setdefault("nltk", nltk)
    import s2s

    sys.modules.setdefault("speech_to_speech", s2s)
    return importlib.import_module("speech_to_speech.LLM.chat_completions_language_model")


class _FakeCreate:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(choices=[])


class _FakeClient:
    def __init__(self):
        self.create = _FakeCreate()
        self.chat = SimpleNamespace(completions=self.create)

    def with_options(self, **_kwargs):
        return self


def _handler(mod, monkeypatch, **setup_kwargs):
    base_module = importlib.import_module(
        "speech_to_speech.LLM.base_openai_compatible_language_model"
    )
    monkeypatch.setattr(base_module, "OpenAI", lambda **_kwargs: _FakeClient())
    return mod.ChatCompletionsApiModelHandler(
        stop_event=None,
        queue_in=None,
        queue_out=None,
        setup_kwargs={
            "model_name": "baseline",
            "base_url": "http://127.0.0.1:18089/v1",
            "api_key": "test",
            **setup_kwargs,
        },
    )


def test_warmup_uses_legacy_non_canonical_chat_request(monkeypatch):
    mod = _import_chat_module()
    handler = _handler(mod, monkeypatch)

    assert len(handler.client.chat.completions.calls) == 1
    request = handler.client.chat.completions.calls[0]
    assert request["model"] == "baseline"
    assert request["messages"] == [
        {"role": "system", "content": "You are a helpful assistant"},
        {"role": "user", "content": "Hello"},
    ]
    serialized = str(request)
    assert "conversation_id" not in serialized
    assert "turn_id" not in serialized
    assert "voice_trace_id" not in serialized


def test_disabled_warmup_constructs_client_without_provider_request(monkeypatch):
    mod = _import_chat_module()
    handler = _handler(mod, monkeypatch, warmup_enabled=False)

    assert handler.model_name == "baseline"
    assert handler.client.chat.completions.calls == []


def test_real_request_identity_augmentation_is_unchanged():
    mod = _import_chat_module()
    handler = object.__new__(mod.ChatCompletionsApiModelHandler)
    runtime_config = SimpleNamespace(
        session=SimpleNamespace(metadata={"conversation_id": "conv-A"})
    )

    augmented = handler._augment_request_optional_kwargs(
        runtime_config,
        {"_voice_trace_id": "turn-A"},
    )

    assert augmented[mod._SESSION_EXTRA_BODY_KEY] == {
        "conversation_id": "conv-A",
        "voice_trace_id": "turn-A",
        "turn_id": "turn-A",
    }


def test_cli_disable_warmup_reaches_real_handler_setup(monkeypatch):
    import s2s

    sys.modules.setdefault("speech_to_speech", s2s)
    pipeline = importlib.import_module("speech_to_speech.s2s_pipeline")
    sys.argv = [
        "prog",
        "--llm_backend",
        "chat-completions",
        "--no_responses_api_warmup_enabled",
    ]
    parsed = pipeline.parse_arguments()
    pipeline.prepare_all_args(
        parsed.module_kwargs,
        parsed.whisper_stt_handler_kwargs,
        parsed.paraformer_stt_handler_kwargs,
        parsed.faster_whisper_stt_handler_kwargs,
        parsed.mlx_audio_whisper_stt_handler_kwargs,
        parsed.parakeet_tdt_stt_handler_kwargs,
        parsed.elevenlabs_scribe_stt_handler_kwargs,
        parsed.language_model_handler_kwargs,
        parsed.responses_api_language_model_handler_kwargs,
        parsed.chat_tts_handler_kwargs,
        parsed.facebook_mms_tts_handler_kwargs,
        parsed.pocket_tts_handler_kwargs,
        parsed.kokoro_tts_handler_kwargs,
        parsed.qwen3_tts_handler_kwargs,
        parsed.elevenlabs_tts_handler_kwargs,
    )
    handler_module = importlib.import_module("speech_to_speech.LLM.chat_completions_language_model")
    base_module = importlib.import_module(
        "speech_to_speech.LLM.base_openai_compatible_language_model"
    )
    monkeypatch.setattr(base_module, "OpenAI", lambda **_kwargs: _FakeClient())
    handler = pipeline.get_llm_handler(
        parsed.module_kwargs,
        None,
        None,
        None,
        parsed.language_model_handler_kwargs,
        parsed.responses_api_language_model_handler_kwargs,
    )

    assert isinstance(handler, handler_module.ChatCompletionsApiModelHandler)
    assert handler.warmup_enabled is False
    assert handler.client.chat.completions.calls == []


def test_disabled_startup_warmup_does_not_suppress_runtime_errors(monkeypatch):
    mod = _import_chat_module()
    handler = _handler(mod, monkeypatch, warmup_enabled=False)

    def fail_request(_api_input, _optional_kwargs):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(handler, "_serialize", lambda _chat: [{"role": "user", "content": "hello"}])
    monkeypatch.setattr(handler, "_request", fail_request)
    base_module = importlib.import_module(
        "speech_to_speech.LLM.base_openai_compatible_language_model"
    )
    turn = base_module._Turn(
        language_code=None,
        gen=None,
        runtime_config=SimpleNamespace(),
        response=SimpleNamespace(),
        turn_id="turn-A",
        turn_revision=0,
        speech_stopped_at_s=None,
        wants_audio=False,
        voice_trace_id="turn-A",
    )

    active_chat = SimpleNamespace(image_message_ids=lambda: set())
    outputs = list(handler._generate(active_chat, object(), turn, {}))
    end = outputs[-1]

    assert end.turn_id == "turn-A"
    assert end.turn_revision == 0
    assert end.error == "Language model generation failed: provider unavailable"
