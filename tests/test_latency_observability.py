import json
import logging
import sys
import types
import time
from threading import Event

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
from speech_to_speech.pipeline.speculative_turns import SpeculativeTurnTracker
from speech_to_speech.pipeline.messages import AudioOutput, TTSInput
from speech_to_speech.VAD.vad_handler import VADHandler


def test_recorder_preserves_monotonic_order_and_correlation(caplog):
    recorder = LatencyRecorder()
    with caplog.at_level(logging.INFO, logger="julia.voice.latency"):
        recorder.emit("INPUT_LAST_SPEECH_FRAME", turn_id="turn-1", turn_revision=2)
        recorder.emit("VAD_SOFT_END", turn_id="turn-1", turn_revision=2)
        recorder.emit("T14_FIRST_AUDIO_SENT_TO_CLIENT", turn_id="turn-1", turn_revision=2)
        summary = recorder.finish(turn_id="turn-1", turn_revision=2)

    assert summary is not None
    assert summary["turn_id"] == "turn-1"
    assert summary["input_last_speech_to_vad_soft_end_ms"] >= 0
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


def test_latency_events_persist_complete_structured_timeline(tmp_path):
    event_path = tmp_path / "latency-events.jsonl"
    recorder = LatencyRecorder(event_path=event_path)

    recorder.emit(
        "INPUT_LAST_SPEECH_FRAME",
        turn_id="turn-1",
        turn_revision=2,
        conversation_id="conversation-1",
        voice_trace_id="trace-1",
        monotonic_ns=100,
    )
    recorder.emit("BRAIN_REQUEST_SENT", turn_id="turn-1", turn_revision=2, monotonic_ns=200)

    records = [json.loads(line) for line in event_path.read_text().splitlines()]
    assert [record["event"] for record in records] == [
        "INPUT_LAST_SPEECH_FRAME",
        "BRAIN_REQUEST_SENT",
    ]
    assert all(
        record["conversation_id"] == "conversation-1"
        and record["turn_id"] == "turn-1"
        and record["turn_revision"] == 2
        and record["voice_trace_id"] == "trace-1"
        and isinstance(record["timestamp_ns"], int)
        and isinstance(record["monotonic_ns"], int)
        for record in records
    )


def test_audio_payload_is_unchanged_by_instrumentation():
    handler = object.__new__(BaseHandler)
    source = TTSInput(text="ignored", turn_id="turn-a", turn_revision=1, cancel_generation=7)
    output = handler.output_for_queue(b"pcm", source)
    assert isinstance(output, AudioOutput)
    assert output.audio == b"pcm"
    assert output.turn_id == "turn-a"


def test_vad_instrumentation_executes_before_audio_dispatch():
    class SilentIterator:
        triggered = False
        buffer = []

        def __call__(self, _audio):
            return None

    handler = object.__new__(VADHandler)
    handler.should_listen = Event()
    handler.should_listen.set()
    handler.iterator = SilentIterator()
    handler._apply_runtime_turn_detection = lambda _runtime_config: None
    handler._discard_expired_pending_short_segment = lambda: None
    handler._uses_realtime_turn_handling = lambda: False
    handler._process_normal = lambda _vad_output, _runtime_config: iter(())
    handler._log_chunks = 0
    handler._total_samples = 0
    handler._last_log_time = time.time()

    assert list(handler.process(b"\x00" * 512)) == []


def test_smart_turn_decision_details_preserve_policy_without_inference(caplog):
    handler = object.__new__(VADHandler)
    handler.smart_turn_analyzer = None
    handler._current_turn_id = "turn-a"
    handler._current_turn_revision = 1
    handler.speculative_reopen_ms = 800

    with caplog.at_level(logging.INFO, logger="julia.voice.latency"):
        grace_ms, processing_delay_ms = handler._smart_turn_timing_ms(None)

    assert (grace_ms, processing_delay_ms) == (800, 0)
    records = [json.loads(line.removeprefix("LATENCY_EVENT ")) for line in caplog.messages if line.startswith("LATENCY_EVENT ")]
    decision = next(record for record in records if record["event"] == "SMART_TURN_DECISION_COMPLETE")
    assert decision["turn_decision"] == "disabled"


def test_grace_start_and_expiry_are_observed_with_configured_duration(caplog):
    tracker = SpeculativeTurnTracker()
    tracker.observe("turn-a", 1)

    with caplog.at_level(logging.INFO, logger="julia.voice.latency"):
        tracker.start_reopen_grace("turn-a", 1, 0.002)
        time.sleep(0.003)
        assert tracker.try_is_latest_after_reopen_grace("turn-a", 1) is True

    records = [json.loads(line.removeprefix("LATENCY_EVENT ")) for line in caplog.messages if line.startswith("LATENCY_EVENT ")]
    records = [record for record in records if record["event"] in {"TURN_GRACE_STARTED", "TURN_GRACE_EXPIRED"}]
    assert [record["event"] for record in records] == ["TURN_GRACE_STARTED", "TURN_GRACE_EXPIRED"]
    assert records[0]["turn_grace_ms"] == 2.0
    assert records[0]["monotonic_ns"] <= records[1]["monotonic_ns"]


def test_committed_turn_does_not_fabricate_grace_start(caplog):
    tracker = SpeculativeTurnTracker()
    tracker.observe("turn-a", 1)
    tracker.commit("turn-a", 1)

    with caplog.at_level(logging.INFO, logger="julia.voice.latency"):
        tracker.start_reopen_grace("turn-a", 1, 0.001)

    assert not [line for line in caplog.messages if "TURN_GRACE_STARTED" in line]


def test_reopen_increments_structured_vad_counter(caplog):
    handler = object.__new__(VADHandler)
    handler._current_turn_id = "turn-a"
    handler._current_turn_revision = 0
    handler._turn_reopen_counts = {}
    handler.speculative_turns = None
    handler._current_conversation_id = "conversation-a"

    with caplog.at_level(logging.INFO, logger="julia.voice.latency"):
        reopened = handler._reopen_current_turn()
        reopened_again = handler._reopen_current_turn()

    assert reopened == ("turn-a", 1, True)
    assert reopened_again == ("turn-a", 2, True)
    records = [json.loads(line.removeprefix("LATENCY_EVENT ")) for line in caplog.messages if '"event":"VAD_REOPEN_COUNT"' in line]
    assert [record["reopen_count"] for record in records] == [1, 2]
    assert [record["turn_revision"] for record in records] == [1, 2]
    assert all(record["conversation_id"] == "conversation-a" for record in records)


def test_brain_event_is_emitted_at_provider_dispatch_and_kwargs_remain_unchanged(caplog):
    calls = []
    observed_events = []

    class Client:
        class chat:
            class completions:
                @staticmethod
                def create(**kwargs):
                    observed_events.extend(
                        line
                        for line in caplog.messages
                        if line.startswith('LATENCY_EVENT {"event":"BRAIN_REQUEST_SENT"')
                    )
                    calls.append(kwargs)
                    return "response"

    optional = {"_session_extra_body": {"_turn_revision": 4, "turn_id": "turn-a"}}
    with caplog.at_level(logging.INFO, logger="julia.voice.latency"):
        result = _request_chat_completions(
            client=Client(),
            model_name="model-a",
            messages=[{"role": "user", "content": "hello"}],
            stream=True,
            extra_body={"conversation_id": "conversation-a"},
            timeout=1,
            optional_kwargs=optional,
        )
    assert result == "response"
    assert observed_events
    record = json.loads(observed_events[0].removeprefix("LATENCY_EVENT "))
    assert record["event"] == "BRAIN_REQUEST_SENT"
    assert record["turn_id"] == "turn-a"
    assert record["turn_revision"] == 4
    assert record["conversation_id"] == "conversation-a"
    assert calls[0]["model"] == "model-a"
    assert "_turn_revision" not in calls[0]["extra_body"]
