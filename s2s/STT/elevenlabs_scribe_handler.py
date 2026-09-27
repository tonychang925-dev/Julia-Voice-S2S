from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import threading
from collections import deque
from queue import Empty as QueueEmpty, Queue
from threading import Event, RLock, Thread
from time import perf_counter
from typing import Any, Callable, Iterator, Protocol
from urllib.parse import urlencode

import numpy as np

from speech_to_speech.pipeline.handler_types import STTIn, STTOut
from speech_to_speech.pipeline.latency import recorder
from speech_to_speech.pipeline.messages import (
    PartialTranscription,
    Transcription,
    VADAudio,
)
from speech_to_speech.STT.base_stt_handler import BaseSTTHandler

logger = logging.getLogger(__name__)

DEFAULT_API_KEY_ENV = "ELEVENLABS_API_KEY"
DEFAULT_MODEL_ID = "scribe_v2_realtime"
DEFAULT_LANGUAGE_CODE = "zh"
DEFAULT_AUDIO_FORMAT = "pcm_16000"
DEFAULT_COMMIT_STRATEGY = "manual"
DEFAULT_WS_URL = "wss://api.elevenlabs.io/v1/speech-to-text/realtime"
DEFAULT_CONNECT_TIMEOUT_S = 10.0
DEFAULT_RECEIVE_TIMEOUT_S = 0.05

_RATE_LIMIT_TYPES = {"rate_limited", "quota_exceeded", "resource_exhausted"}
_PROVIDER_ERROR_TYPES = {
    "error",
    "transcriber_error",
    "input_error",
    "invalid_request",
    "unaccepted_terms",
    "queue_overflow",
    "session_time_limit_exceeded",
    "chunk_size_exceeded",
    "insufficient_audio_activity",
}


class ScribeProviderError(RuntimeError):
    kind: str = "provider"


class ScribeAuthenticationError(ScribeProviderError):
    kind = "authentication"


class ScribeRateLimitError(ScribeProviderError):
    kind = "rate_limit"


class ScribeConnectionError(ScribeProviderError):
    kind = "connection"


class ScribeProtocolError(ScribeProviderError):
    kind = "protocol"


class ScribeTimeoutError(ScribeProviderError):
    kind = "timeout"


class ScribeLocalCancellation(ScribeProviderError):
    kind = "local_cancellation"


class ScribeStream(Protocol):
    def connect(self) -> None:
        """Open the selected provider transport."""

    def send_audio(self, audio: bytes, *, commit: bool) -> None:
        """Send one PCM chunk and optionally request a commit."""

    def receive(self, timeout_s: float) -> dict[str, Any] | None:
        """Return one provider event or None before the timeout."""

    def close(self) -> None:
        """Close the selected provider transport."""


def float_pcm_to_pcm16_le(audio: np.ndarray) -> bytes:
    clipped = np.clip(np.asarray(audio, dtype=np.float32), -1.0, 1.0)
    return np.round(clipped * 32767.0).astype("<i2").tobytes()


def _scrub(value: str, api_key: str) -> str:
    return value.replace(api_key, "[redacted]") if api_key else value


class RealtimeScribeStream:
    def __init__(
        self,
        *,
        api_key: str,
        ws_url: str,
        model_id: str,
        language_code: str | None,
        audio_format: str,
        commit_strategy: str,
        keyterms: list[str],
        connect_timeout_s: float,
    ) -> None:
        self._api_key = api_key
        self._connect_timeout_s = connect_timeout_s
        parameters: dict[str, Any] = {
            "model_id": model_id,
            "audio_format": audio_format,
            "commit_strategy": commit_strategy,
        }
        if language_code:
            parameters["language_code"] = language_code
        if keyterms:
            parameters["keyterms"] = keyterms
        self._url = f"{ws_url}?{urlencode(parameters, doseq=True)}"
        self._loop: asyncio.AbstractEventLoop | None = None
        self._loop_thread: Thread | None = None
        self._websocket: Any = None
        self._receive_task: asyncio.Task[None] | None = None
        self._events: Queue[dict[str, Any]] = Queue()
        self._closed = False

    def connect(self) -> None:
        if self._websocket is not None:
            return
        websockets = self._import_websockets()
        self._loop = asyncio.new_event_loop()
        self._loop_thread = Thread(target=self._loop.run_forever, daemon=True)
        self._loop_thread.start()
        try:
            connect_future = asyncio.run_coroutine_threadsafe(
                self._connect(websockets), self._loop
            )
            self._websocket = connect_future.result(self._connect_timeout_s)

            def start_receive_task() -> None:
                assert self._loop is not None
                self._receive_task = self._loop.create_task(
                    self._receive_loop(self._websocket)
                )

            self._loop.call_soon_threadsafe(start_receive_task)
        except asyncio.TimeoutError as exc:
            self._teardown_sync()
            raise ScribeTimeoutError(
                "Timed out connecting to ElevenLabs Scribe"
            ) from exc
        except Exception as exc:
            self._teardown_sync()
            message = _scrub(str(exc), self._api_key)
            if "401" in message or "unauthorized" in message.lower():
                raise ScribeAuthenticationError(message) from exc
            raise ScribeConnectionError(message) from exc

    async def _connect(self, websockets: Any) -> Any:
        return await asyncio.wait_for(
            websockets.connect(
                self._url, additional_headers={"xi-api-key": self._api_key}
            ),
            self._connect_timeout_s,
        )

    @staticmethod
    def _import_websockets() -> Any:
        try:
            import websockets
        except ImportError as exc:
            raise ScribeConnectionError(
                "websockets is required by the selected Scribe provider"
            ) from exc
        return websockets

    async def _receive_loop(self, websocket: Any) -> None:
        try:
            async for raw_event in websocket:
                try:
                    event = json.loads(raw_event)
                except (TypeError, json.JSONDecodeError) as exc:
                    raise ScribeProtocolError(
                        "Scribe returned a non-object frame"
                    ) from exc
                if not isinstance(event, dict):
                    raise ScribeProtocolError("Scribe returned a non-object frame")
                self._events.put(event)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self._events.put(
                {
                    "message_type": "__stream_closed__",
                    "error": _scrub(str(exc), self._api_key),
                }
            )

    def send_audio(self, audio: bytes, *, commit: bool) -> None:
        if self._loop is None or self._websocket is None:
            raise ScribeConnectionError("Scribe transport is not connected")
        message = {
            "message_type": "input_audio_chunk",
            "audio_base_64": base64.b64encode(audio).decode("ascii"),
            "commit": commit,
            "sample_rate": 16000,
        }
        try:
            send_future = asyncio.run_coroutine_threadsafe(
                self._websocket.send(json.dumps(message, separators=(",", ":"))),
                self._loop,  # noqa: COM812
            )
            send_future.result(self._connect_timeout_s)
        except Exception as exc:
            raise ScribeConnectionError(_scrub(str(exc), self._api_key)) from exc

    def receive(self, timeout_s: float) -> dict[str, Any] | None:
        if self._loop is None:
            return None
        try:
            return self._events.get(timeout=timeout_s)
        except QueueEmpty:
            return None
        except Exception as exc:
            raise ScribeConnectionError(_scrub(str(exc), self._api_key)) from exc

    def close(self) -> None:
        self._teardown_sync()

    def _teardown_sync(self) -> None:
        loop, loop_thread, websocket, receive_task = (
            self._loop,
            self._loop_thread,
            self._websocket,
            self._receive_task,
        )
        self._loop, self._loop_thread = None, None
        self._websocket, self._receive_task = None, None
        if loop is None or loop.is_closed():
            return
        try:
            if loop_thread is None or not loop_thread.is_alive():
                loop.run_until_complete(self._teardown(websocket, receive_task))
            else:
                teardown_future = asyncio.run_coroutine_threadsafe(
                    self._teardown(websocket, receive_task), loop
                )
                teardown_future.result(self._connect_timeout_s)
                loop.call_soon_threadsafe(loop.stop)
                loop_thread.join(self._connect_timeout_s)
        finally:
            loop.close()

    async def _teardown(
        self, websocket: Any, receive_task: asyncio.Task[None] | None
    ) -> None:
        if receive_task is not None and not receive_task.done():
            receive_task.cancel()
            try:
                await receive_task
            except asyncio.CancelledError:
                pass
        if websocket is not None:
            await websocket.close()


class ElevenLabsScribeSTTHandler(BaseSTTHandler):
    def setup(
        self,
        api_key: str | None = None,
        api_key_env: str = DEFAULT_API_KEY_ENV,
        model_id: str = DEFAULT_MODEL_ID,
        language_code: str | None = DEFAULT_LANGUAGE_CODE,
        audio_format: str = DEFAULT_AUDIO_FORMAT,
        commit_strategy: str = DEFAULT_COMMIT_STRATEGY,
        keyterms: list[str] | None = None,
        ws_url: str = DEFAULT_WS_URL,
        connect_timeout_s: float = DEFAULT_CONNECT_TIMEOUT_S,
        response_timeout_s: float = 8.0,
        stream_factory: Callable[..., ScribeStream] | None = None,
        gen_kwargs: dict[str, Any] | None = None,
    ) -> None:
        if audio_format != "pcm_16000":
            raise ValueError("ElevenLabs Scribe requires pcm_16000 audio format")
        if commit_strategy != "manual":
            raise ValueError(
                "Julia turn authority requires elevenlabs_scribe_commit_strategy=manual"
            )
        self.gen_kwargs = gen_kwargs or {}
        self.api_key = api_key or os.environ.get(api_key_env) or ""
        self.model_id = model_id
        self.language_code = language_code
        self.audio_format = audio_format
        self.commit_strategy = commit_strategy
        self.keyterms = list(keyterms or [])
        self.ws_url = ws_url
        self.connect_timeout_s = connect_timeout_s
        self.response_timeout_s = response_timeout_s
        self.stream_factory = stream_factory or RealtimeScribeStream
        self.stream: ScribeStream | None = None
        self.active_revision_key: tuple[str | None, int | None] | None = None
        self._connection_lock = RLock()
        self._connection_generation = 0
        self._connection_key: tuple[str | None, int | None] | None = None
        self._connection_ready = Event()
        self._connection_error: Exception | None = None
        self._connection_threads: set[Thread] = set()
        self.sent_sample_count = 0
        self._pending_progressive_audio: np.ndarray | None = None
        self.active_turn: tuple[str, int, float] | None = None
        self.pending_commits: deque[tuple[str, int, float]] = deque()
        self._current_conversation_id: str | None = None

    def _start_stream_connect(
        self, revision_key: tuple[str | None, int | None]
    ) -> None:
        if not self.api_key:
            raise ScribeAuthenticationError(
                "ElevenLabs Scribe API key is unavailable"
            )
        turn_id, turn_revision = revision_key
        recorder.emit(
            "SCRIBE_CONNECTION_START",
            turn_id=turn_id,
            turn_revision=turn_revision,
            conversation_id=self._current_conversation_id,
        )
        stream = self.stream_factory(
            api_key=self.api_key,
            ws_url=self.ws_url,
            model_id=self.model_id,
            language_code=self.language_code,
            audio_format=self.audio_format,
            commit_strategy=self.commit_strategy,
            keyterms=self.keyterms,
            connect_timeout_s=self.connect_timeout_s,
        )
        with self._connection_lock:
            generation = self._connection_generation
            self._connection_key = revision_key
            self._connection_error = None
            self._connection_ready = Event()
            thread = Thread(
                target=self._connect_stream,
                args=(stream, revision_key, generation),
                daemon=True,
            )
            self._connection_threads.add(thread)
        thread.start()

    def _connect_stream(
        self,
        stream: ScribeStream,
        revision_key: tuple[str | None, int | None],
        generation: int,
    ) -> None:
        try:
            try:
                stream.connect()
            except Exception as exc:
                with self._connection_lock:
                    if generation == self._connection_generation:
                        self._connection_error = exc
                        self._connection_ready.set()
                return

            with self._connection_lock:
                if generation != self._connection_generation:
                    stream.close()
                    return
                if self.active_revision_key != revision_key:
                    stream.close()
                    self._connection_key = None
                    self._connection_ready.set()
                    return
                self.stream = stream
                self._connection_key = None
                recorder.emit(
                    "SCRIBE_CONNECTION_READY",
                    turn_id=revision_key[0],
                    turn_revision=revision_key[1],
                    conversation_id=self._current_conversation_id,
                )
                self._connection_ready.set()
        finally:
            with self._connection_lock:
                self._connection_threads.discard(threading.current_thread())

    def _ensure_stream(self, *, wait_for_connection: bool) -> ScribeStream | None:
        revision_key = self.active_revision_key
        with self._connection_lock:
            if self.stream is not None:
                stream = self.stream
            elif self._connection_key == revision_key:
                stream = None
            else:
                self._start_stream_connect(revision_key)
                stream = None

        if stream is not None:
            recorder.emit(
                "SCRIBE_CONNECTION_REUSED",
                turn_id=revision_key[0],
                turn_revision=revision_key[1],
                conversation_id=self._current_conversation_id,
            )
            return stream

        if not wait_for_connection:
            return None

        if not self._connection_ready.wait(self.connect_timeout_s):
            raise ScribeTimeoutError(
                "Timed out connecting to ElevenLabs Scribe"
            )
        with self._connection_lock:
            if self._connection_error is not None:
                raise self._connection_error
            if self.stream is None:
                raise ScribeConnectionError(
                    "Scribe connection was invalidated before it became ready"
                )
            recorder.emit(
                "SCRIBE_CONNECTION_REUSED",
                turn_id=revision_key[0],
                turn_revision=revision_key[1],
                conversation_id=self._current_conversation_id,
            )
            return self.stream

    def _context(self, vad_audio: VADAudio) -> tuple[str, int, float] | None:
        if vad_audio.turn_id is None or vad_audio.turn_revision is None:
            return None
        return vad_audio.turn_id, vad_audio.turn_revision, vad_audio.created_at_s

    @staticmethod
    def _conversation_id(vad_audio: VADAudio) -> str | None:
        session = getattr(vad_audio.runtime_config, "session", None)
        metadata = getattr(session, "metadata", None)
        if isinstance(metadata, dict):
            conversation_id = str(metadata.get("conversation_id") or "").strip()
            return conversation_id or None
        return None

    def _reset_for_revision(
        self, turn_id: str | None, turn_revision: int | None
    ) -> None:
        revision_key = (turn_id, turn_revision)
        if self.active_revision_key == revision_key:
            return
        with self._connection_lock:
            stream = self.stream
            self.stream = None
            self._connection_generation += 1
            self._connection_key = None
            self._connection_error = None
            self._connection_ready = Event()
        if stream is not None:
            stream.close()
        self.active_revision_key = revision_key
        self.sent_sample_count = 0
        self._pending_progressive_audio = None
        self.pending_commits.clear()

    def process(self, vad_audio: STTIn) -> Iterator[STTOut]:
        context = self._context(vad_audio)
        self._current_conversation_id = self._conversation_id(vad_audio) or self._current_conversation_id
        if context is not None:
            self.active_turn = context
        self._reset_for_revision(vad_audio.turn_id, vad_audio.turn_revision)
        is_final = vad_audio.mode == "final"
        stream = self._ensure_stream(wait_for_connection=is_final)
        if stream is None:
            self._pending_progressive_audio = (
                np.asarray(vad_audio.audio, dtype=np.float32).copy()
            )
            return
        if self._pending_progressive_audio is not None:
            buffered_audio = self._pending_progressive_audio
            self._pending_progressive_audio = None
            yield from self._send_audio(stream, buffered_audio, vad_audio, is_final=False)
        if is_final and context is not None:
            self.pending_commits.append(context)
        yield from self._send_audio(stream, vad_audio.audio, vad_audio, is_final=is_final)

    def _send_audio(
        self,
        stream: ScribeStream,
        audio: np.ndarray,
        vad_audio: STTIn,
        *,
        is_final: bool,
    ) -> Iterator[STTOut]:
        context = self._context(vad_audio)
        audio_delta = np.asarray(audio)[self.sent_sample_count :]
        self.sent_sample_count = len(audio)
        if audio_delta.size == 0 and not is_final:
            return
        try:
            if is_final:
                recorder.emit(
                    "SCRIBE_LAST_AUDIO_SENT",
                    turn_id=vad_audio.turn_id,
                    turn_revision=vad_audio.turn_revision,
                )
                recorder.emit(
                    "T4_SCRIBE_MANUAL_COMMIT_SENT",
                    turn_id=vad_audio.turn_id,
                    turn_revision=vad_audio.turn_revision,
                )
                recorder.emit(
                    "SCRIBE_COMMIT_SENT",
                    turn_id=vad_audio.turn_id,
                    turn_revision=vad_audio.turn_revision,
                    conversation_id=self._current_conversation_id,
                )
            stream.send_audio(float_pcm_to_pcm16_le(audio_delta), commit=is_final)
        except ScribeProviderError:
            if (
                is_final
                and self.pending_commits
                and self.pending_commits[-1] == context
            ):
                self.pending_commits.pop()
            raise

        deadline = perf_counter() + (self.response_timeout_s if is_final else 0.01)
        while perf_counter() < deadline:
            event = stream.receive(0.05 if is_final else 0.0)
            if event is None:
                if not is_final:
                    return
                if self.stop_event.is_set():
                    raise ScribeLocalCancellation(
                        "Scribe finalization interrupted by pipeline stop"
                    )
                continue
            for output in self._event_to_outputs(event):
                if is_final and event.get("message_type") == "committed_transcript":
                    recorder.emit(
                        "T5_SCRIBE_FINAL_RECEIVED",
                        turn_id=vad_audio.turn_id,
                        turn_revision=vad_audio.turn_revision,
                    )
                    recorder.emit(
                        "SCRIBE_FINAL_RECEIVED",
                        turn_id=vad_audio.turn_id,
                        turn_revision=vad_audio.turn_revision,
                        conversation_id=self._current_conversation_id,
                    )
                yield output
            if is_final and event.get("message_type") == "committed_transcript":
                return
        if is_final:
            raise ScribeTimeoutError(
                "Timed out waiting for committed Scribe transcript"
            )

    def _event_to_outputs(self, event: dict[str, Any]) -> Iterator[STTOut]:
        message_type = event.get("message_type")
        if message_type in (
            "error",
            "auth_error",
            *_RATE_LIMIT_TYPES,
            *_PROVIDER_ERROR_TYPES,
        ):
            raise self._error_for_event(event)
        if message_type == "__stream_closed__":
            raise ScribeConnectionError(str(event.get("error", "Scribe socket closed")))
        if message_type not in ("partial_transcript", "committed_transcript"):
            return
        text = str(event.get("text", "")).strip()
        if not text:
            if message_type == "committed_transcript" and self.pending_commits:
                context = self.pending_commits.popleft()
                yield Transcription(
                    text="",
                    language_code=event.get("language_code") or self.language_code,
                    turn_id=context[0],
                    turn_revision=context[1],
                    speech_stopped_at_s=context[2],
                )
            return
        context = (
            self.pending_commits.popleft()
            if message_type == "committed_transcript"
            else self.active_turn
        )
        if context is None:
            return
        if message_type == "partial_transcript":
            yield PartialTranscription(
                text=text,
                turn_id=context[0],
                turn_revision=context[1],
            )
        else:
            yield Transcription(
                text=text,
                language_code=event.get("language_code") or self.language_code,
                turn_id=context[0],
                turn_revision=context[1],
                speech_stopped_at_s=context[2],
            )

    @staticmethod
    def _error_for_event(event: dict[str, Any]) -> ScribeProviderError:
        message_type = str(event.get("message_type", "error"))
        detail = str(event.get("error") or event.get("message") or message_type)
        if message_type == "auth_error":
            return ScribeAuthenticationError(detail)
        if message_type in _RATE_LIMIT_TYPES:
            return ScribeRateLimitError(detail)
        if message_type == "invalid_request" or message_type == "input_error":
            return ScribeProtocolError(detail)
        return ScribeProviderError(detail)

    def cleanup(self) -> None:
        logger.info("Stopping ElevenLabsScribeSTTHandler")
        with self._connection_lock:
            stream = self.stream
            self.stream = None
            self._connection_generation += 1
            self._connection_key = None
            self._connection_error = None
            self._connection_ready = Event()
            threads = tuple(self._connection_threads)
            self._connection_threads.clear()
        if stream is not None:
            stream.close()
        for thread in threads:
            if thread is not threading.current_thread():
                thread.join(self.connect_timeout_s)
        self.active_turn = None
        self.active_revision_key = None
        self.sent_sample_count = 0
        self._pending_progressive_audio = None
        self.pending_commits.clear()
