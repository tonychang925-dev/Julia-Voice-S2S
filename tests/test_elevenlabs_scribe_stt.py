from __future__ import annotations

import sys
import types
from queue import Empty, Queue
from threading import Event
from types import SimpleNamespace

import numpy as np
import pytest

import s2s

sys.modules["speech_to_speech"] = s2s

from speech_to_speech.STT import provider_factory
from speech_to_speech.STT.elevenlabs_scribe_handler import (
    ElevenLabsScribeSTTHandler,
    ScribeAuthenticationError,
    ScribeRateLimitError,
    float_pcm_to_pcm16_le,
)
from speech_to_speech.pipeline.messages import (
    PartialTranscription,
    Transcription,
    VADAudio,
)


class FakeScribeStream:
    def __init__(self, events: list[dict] | None = None) -> None:
        self.events = list(events or [])
        self.connected = False
        self.closed = False
        self.sent: list[tuple[bytes, bool]] = []

    def connect(self) -> None:
        self.connected = True

    def send_audio(self, audio: bytes, *, commit: bool) -> None:
        self.sent.append((audio, commit))

    def receive(self, timeout_s: float) -> dict | None:
        if not self.events:
            if timeout_s == 0:
                return None
            raise Empty
        return self.events.pop(0)

    def close(self) -> None:
        self.closed = True


def build_handler(stream: FakeScribeStream) -> ElevenLabsScribeSTTHandler:
    return ElevenLabsScribeSTTHandler(
        Event(),
        queue_in=Queue(),
        queue_out=Queue(),
        setup_kwargs={
            "api_key": "test-key",
            "model_id": "scribe_v2_realtime",
            "language_code": "zh",
            "audio_format": "pcm_16000",
            "commit_strategy": "manual",
            "keyterms": ["Julia"],
            "response_timeout_s": 0.01,
            "stream_factory": lambda **kwargs: stream,
        },
    )


def audio(mode: str, turn_id: str = "turn-a", revision: int = 2) -> VADAudio:
    return VADAudio(
        audio=np.array([0.0, 0.5], dtype=np.float32),
        mode=mode,
        turn_id=turn_id,
        turn_revision=revision,
    )


def test_factory_selects_scribe_without_whisper_imports(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for module_name in ("faster_whisper", "ctranslate2"):
        blocked = types.ModuleType(module_name)
        blocked.__getattr__ = lambda name, module=module_name: (_ for _ in ()).throw(
            AssertionError(f"{module} imported on Scribe path")
        )
        monkeypatch.setitem(sys.modules, module_name, blocked)
    monkeypatch.delitem(sys.modules, "s2s.STT.faster_whisper_handler", raising=False)

    handler = provider_factory.create_stt_provider(
        provider_factory.STTHandlerContext(
            stop_event=Event(),
            queue_in=Queue(),
            queue_out=Queue(),
            speculative_turns=None,
            module_kwargs=SimpleNamespace(stt="elevenlabs-scribe"),
            provider_kwargs={
                "elevenlabs_scribe_stt_handler_kwargs": SimpleNamespace(
                    api_key="test-key",
                    stream_factory=lambda **kwargs: FakeScribeStream(),
                )
            },
        )
    )

    assert isinstance(handler, ElevenLabsScribeSTTHandler)


def test_pcm_conversion_boundaries() -> None:
    converted = float_pcm_to_pcm16_le(np.array([-2.0, -1.0, 0.0, 0.5, 1.0, 2.0]))

    assert converted == b"\x01\x80\x01\x80\x00\x00\x00\x40\xff\x7f\xff\x7f"


def test_partial_transcript_preserves_turn_identity() -> None:
    stream = FakeScribeStream(
        [{"message_type": "partial_transcript", "text": " 你好 "}]
    )
    handler = build_handler(stream)

    output = list(handler.process(audio("progressive")))

    assert isinstance(output[0], PartialTranscription)
    assert output[0].text == "你好"
    assert output[0].turn_id == "turn-a"
    assert output[0].turn_revision == 2


def test_manual_commit_maps_committed_transcript_and_preserves_identity() -> None:
    stream = FakeScribeStream(
        [
            {
                "message_type": "committed_transcript",
                "text": "你好，我是 Julia。",
                "language_code": "zh",
            }
        ]
    )
    handler = build_handler(stream)

    output = list(handler.process(audio("final")))

    assert stream.sent[0][1] is True
    assert isinstance(output[0], Transcription)
    assert output[0].text == "你好，我是 Julia。"
    assert output[0].turn_id == "turn-a"
    assert output[0].turn_revision == 2


def test_late_transcript_is_not_promoted(monkeypatch: pytest.MonkeyPatch) -> None:
    handler = build_handler(FakeScribeStream())
    handler.speculative_turns = SimpleNamespace(
        is_latest_after_pending_reopen=lambda turn_id, revision: False
    )
    output = Transcription(text="late", turn_id="turn-a", turn_revision=2)

    assert handler.should_emit_output(output) is False


@pytest.mark.parametrize(
    ("event", "expected_error"),
    [
        (
            {"message_type": "auth_error", "error": "invalid key"},
            ScribeAuthenticationError,
        ),
        ({"message_type": "rate_limited", "error": "slow down"}, ScribeRateLimitError),
    ],
)
def test_provider_failures_are_typed_without_transcript(
    event: dict, expected_error: type
) -> None:
    stream = FakeScribeStream([event])
    handler = build_handler(stream)

    with pytest.raises(expected_error):
        list(handler.process(audio("progressive")))


def test_socket_close_is_connection_failure() -> None:
    stream = FakeScribeStream(
        [{"message_type": "__stream_closed__", "error": "closed"}]
    )
    handler = build_handler(stream)

    with pytest.raises(Exception, match="closed"):
        list(handler.process(audio("progressive")))
