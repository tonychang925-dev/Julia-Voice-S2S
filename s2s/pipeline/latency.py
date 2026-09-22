"""Structured latency instrumentation for the S2S pipeline.

The recorder is deliberately passive: it emits JSON log records and never
participates in turn, provider, cancellation, or output decisions.
"""

from __future__ import annotations

from collections import OrderedDict
from contextvars import ContextVar
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
from threading import RLock
from time import perf_counter_ns, time_ns
from typing import Any

logger = logging.getLogger("julia.voice.latency")

_MAX_TRACKED_TURNS = 256
_SUMMARY_STAGES = (
    ("input_last_speech_to_vad_soft_end_ms", "INPUT_LAST_SPEECH_FRAME", "VAD_SOFT_END"),
    ("vad_soft_end_to_smart_turn_decision_ms", "VAD_SOFT_END", "SMART_TURN_DECISION_COMPLETE"),
    ("smart_turn_to_grace_start_ms", "SMART_TURN_DECISION_COMPLETE", "TURN_GRACE_STARTED"),
    ("grace_start_to_observed_expiry_ms", "TURN_GRACE_STARTED", "TURN_GRACE_EXPIRED"),
    ("scribe_commit_to_final_ms", "SCRIBE_COMMIT_SENT", "SCRIBE_FINAL_RECEIVED"),
    ("scribe_final_to_brain_request_ms", "SCRIBE_FINAL_RECEIVED", "BRAIN_REQUEST_SENT"),
    ("input_last_speech_to_scribe_final_ms", "INPUT_LAST_SPEECH_FRAME", "SCRIBE_FINAL_RECEIVED"),
    ("input_last_speech_to_brain_request_ms", "INPUT_LAST_SPEECH_FRAME", "BRAIN_REQUEST_SENT"),
    ("brain_ingress_ms", "BRAIN_REQUEST_SENT", "LLM_FIRST_CHUNK_RECEIVED"),
    ("llm_first_token_ms", "BRAIN_REQUEST_SENT", "LLM_FIRST_CHUNK_RECEIVED"),
    ("first_token_to_tts_request_ms", "T10_FIRST_TEXT_CHUNK_READY_FOR_TTS", "T11_TTS_REQUEST_SENT"),
    ("tts_ttfa_ms", "T11_TTS_REQUEST_SENT", "T12_TTS_FIRST_AUDIO_RECEIVED"),
    ("playback_handoff_ms", "T12_TTS_FIRST_AUDIO_RECEIVED", "T14_FIRST_AUDIO_SENT_TO_CLIENT"),
    ("speech_end_to_first_audio_ms", "T0_USER_LAST_SPEECH_FRAME", "T14_FIRST_AUDIO_SENT_TO_CLIENT"),
)
_EVENT_SINK_LOCK = RLock()


def _default_event_path() -> Path:
    configured = os.environ.get("JULIA_VOICE_LATENCY_EVENT_PATH")
    if configured:
        return Path(configured)
    return Path(os.environ.get("TMPDIR", "/tmp")) / "julia-voice-latency-events.jsonl"


class LatencyRecorder:
    """Thread-safe, bounded per-turn event collector."""

    def __init__(self, *, event_path: str | Path | None = None) -> None:
        self._lock = RLock()
        self._turns: OrderedDict[tuple[str, int | None], dict[str, Any]] = OrderedDict()
        self.event_path = Path(event_path) if event_path is not None else _default_event_path()
        self._sink_available = True

    def emit(
        self,
        event: str,
        *,
        turn_id: str | None,
        turn_revision: int | None = None,
        conversation_id: str | None = None,
        voice_trace_id: str | None = None,
        monotonic_ns: int | None = None,
        **details: Any,
    ) -> int:
        """Record one exact execution boundary and return its monotonic time."""
        monotonic_ns = monotonic_ns if monotonic_ns is not None else perf_counter_ns()
        key = (turn_id or "", turn_revision)
        if not turn_id:
            self._log(event, monotonic_ns, None, turn_revision, conversation_id, voice_trace_id, details)
            return monotonic_ns

        with self._lock:
            trace = self._turns.get(key)
            if trace is None:
                trace = {
                    "conversation_id": conversation_id,
                    "voice_trace_id": voice_trace_id or turn_id,
                    "events": {},
                }
                self._turns[key] = trace
                while len(self._turns) > _MAX_TRACKED_TURNS:
                    self._turns.popitem(last=False)
            if conversation_id:
                trace["conversation_id"] = conversation_id
            if voice_trace_id:
                trace["voice_trace_id"] = voice_trace_id
            trace["events"].setdefault(event, monotonic_ns)

        self._log(
            event,
            monotonic_ns,
            turn_id,
            turn_revision,
            trace.get("conversation_id"),
            trace.get("voice_trace_id"),
            details,
        )
        return monotonic_ns

    def bind_conversation(self, turn_id: str | None, turn_revision: int | None, conversation_id: str) -> None:
        if not turn_id or not conversation_id:
            return
        key = (turn_id, turn_revision)
        with self._lock:
            trace = self._turns.setdefault(
                key,
                {"conversation_id": conversation_id, "voice_trace_id": turn_id, "events": {}},
            )
            trace["conversation_id"] = conversation_id

    def emit_first(self, event: str, **kwargs: Any) -> bool:
        """Emit only the first occurrence of a first-stage event."""
        turn_id = kwargs.get("turn_id")
        turn_revision = kwargs.get("turn_revision")
        if not turn_id:
            return False
        key = (turn_id, turn_revision)
        with self._lock:
            trace = self._turns.get(key)
            if trace is not None and event in trace["events"]:
                return False
        self.emit(event, **kwargs)
        return True

    def finish(self, *, turn_id: str, turn_revision: int | None) -> dict[str, float | None] | None:
        """Emit one completed-turn summary if the terminal stage was observed."""
        with self._lock:
            trace = self._turns.get((turn_id, turn_revision))
            if trace is None or "T14_FIRST_AUDIO_SENT_TO_CLIENT" not in trace["events"]:
                return None
            summary = self._summary(trace["events"])
            record = {
                "conversation_id": trace.get("conversation_id"),
                "turn_id": turn_id,
                "turn_revision": turn_revision,
                "voice_trace_id": trace.get("voice_trace_id", turn_id),
                **summary,
            }

        logger.info("LATENCY_SUMMARY %s", json.dumps(record, separators=(",", ":"), ensure_ascii=False))
        return record

    @staticmethod
    def _summary(events: dict[str, int]) -> dict[str, float | None]:
        summary: dict[str, float | None] = {}
        for name, start_event, end_event in _SUMMARY_STAGES:
            start = events.get(start_event)
            end = events.get(end_event)
            summary[name] = (
                round((end - start) / 1_000_000, 3)
                if start is not None and end is not None and end >= start
                else None
            )
        return summary

    def _log(
        self,
        event: str,
        monotonic_ns: int,
        turn_id: str | None,
        turn_revision: int | None,
        conversation_id: str | None,
        voice_trace_id: str | None,
        details: dict[str, Any],
    ) -> None:
        record = {
            "event": event,
            "conversation_id": conversation_id,
            "turn_id": turn_id,
            "turn_revision": turn_revision,
            "voice_trace_id": voice_trace_id,
            "monotonic_ns": monotonic_ns,
            "timestamp_ns": time_ns(),
            "wall_time_iso": datetime.now(timezone.utc).isoformat(),
            **details,
        }
        logger.info("LATENCY_EVENT %s", json.dumps(record, separators=(",", ":"), ensure_ascii=False))
        self._persist(record)

    def _persist(self, record: dict[str, Any]) -> None:
        payload = json.dumps(record, separators=(",", ":"), ensure_ascii=False) + "\n"
        with _EVENT_SINK_LOCK:
            try:
                existed = self.event_path.exists()
                with self.event_path.open("a", encoding="utf-8") as event_file:
                    event_file.write(payload)
                if not existed:
                    self.event_path.chmod(0o600)
                self._sink_available = True
            except OSError:
                if self._sink_available:
                    logger.warning("Latency event persistence unavailable at %s", self.event_path)
                self._sink_available = False


recorder = LatencyRecorder()
_current_turn_id: ContextVar[str | None] = ContextVar("julia_latency_turn_id", default=None)
_current_turn_revision: ContextVar[int | None] = ContextVar(
    "julia_latency_turn_revision", default=None
)


def set_current_turn(turn_id: str | None, turn_revision: int | None = None) -> None:
    _current_turn_id.set(turn_id)
    _current_turn_revision.set(turn_revision)


def emit_current(event: str, **details: Any) -> None:
    recorder.emit(
        event,
        turn_id=_current_turn_id.get(),
        turn_revision=_current_turn_revision.get(),
        **details,
    )


__all__ = ["LatencyRecorder", "emit_current", "recorder", "set_current_turn"]
