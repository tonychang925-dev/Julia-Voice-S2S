import json
import logging
import sys
import types

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
import s2s
if "nltk" not in sys.modules:
    nltk = types.ModuleType("nltk")
    nltk.sent_tokenize = lambda text: [text]
    sys.modules["nltk"] = nltk

sys.modules.setdefault("speech_to_speech", s2s)

from speech_to_speech.baseHandler import BaseHandler
from speech_to_speech.LLM.chat_completions_language_model import _request_chat_completions
from speech_to_speech.pipeline.latency import LatencyRecorder
from speech_to_speech.pipeline.messages import AudioOutput, TTSInput


def test_recorder_preserves_monotonic_order_and_correlation(caplog):
    recorder = LatencyRecorder()
    with caplog.at_level(logging.INFO, logger="julia.voice.latency"):
        recorder.emit("T0_USER_LAST_SPEECH_FRAME", turn_id="turn-1", turn_revision=2)
        recorder.emit("T1_VAD_SPEECH_END", turn_id="turn-1", turn_revision=2)
        recorder.emit("T14_FIRST_AUDIO_SENT_TO_CLIENT", turn_id="turn-1", turn_revision=2)
        summary = recorder.finish(turn_id="turn-1", turn_revision=2)

    assert summary is not None
    assert summary["turn_id"] == "turn-1"
    assert summary["speech_end_to_vad_ms"] >= 0
    event_messages = [line for line in caplog.messages if line.startswith("LATENCY_EVENT ")]
    records = [json.loads(line.removeprefix("LATENCY_EVENT ")) for line in event_messages]
    assert all(record["turn_id"] == "turn-1" for record in records)
    assert [record["monotonic_ns"] for record in records] == sorted(
        record["monotonic_ns"] for record in records
    )


def test_missing_optional_stages_do_not_crash():
    recorder = LatencyRecorder()
    recorder.emit("T0_USER_LAST_SPEECH_FRAME", turn_id="turn-missing", turn_revision=1)
    assert recorder.finish(turn_id="turn-missing", turn_revision=1) is None


def test_audio_payload_is_unchanged_by_instrumentation():
    handler = object.__new__(BaseHandler)
    source = TTSInput(text="ignored", turn_id="turn-a", turn_revision=1, cancel_generation=7)
    output = handler.output_for_queue(b"pcm", source)
    assert isinstance(output, AudioOutput)
    assert output.audio == b"pcm"
    assert output.turn_id == "turn-a"


def test_provider_request_kwargs_are_unchanged_by_trace_revision():
    calls = []

    class Client:
        class chat:
            class completions:
                @staticmethod
                def create(**kwargs):
                    calls.append(kwargs)
                    return "response"

    optional = {"_session_extra_body": {"_turn_revision": 4, "turn_id": "turn-a"}}
    result = _request_chat_completions(
        client=Client(),
        model_name="model-a",
        messages=[{"role": "user", "content": "hello"}],
        stream=True,
        extra_body=None,
        timeout=1,
        optional_kwargs=optional,
    )
    assert result == "response"
    assert calls[0]["model"] == "model-a"
    assert "_turn_revision" not in calls[0]["extra_body"]
