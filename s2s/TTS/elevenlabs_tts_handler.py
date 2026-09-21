"""ElevenLabs Text-to-Dialogue realtime TTS handler (isolated provider).

Status: VOICE-EL-P0A — implemented, NOT wired. Nothing in the production
pipeline constructs this handler yet; `--tts elevenlabs` does not exist.

Contract (mirrors every other TTS handler in this package)
---------------------------------------------------------
``process`` accepts :class:`TTSInput` or :class:`EndOfResponse` and yields
``bytes``. Pipeline-level generation tagging is intentionally NOT duplicated
here — :meth:`speech_to_speech.baseHandler.BaseHandler.output_for_queue`
wraps every emitted ``bytes`` into
``AudioOutput(audio=..., cancel_generation=<input>.cancel_generation)``.
This handler therefore never touches cancellation *state*; it only reads it.

Wire facts (measured 2026-09-14, see VOICE_EL_AUDIT_P0_REPORT.md §10A)
--------------------------------------------------------------------
* ``output_format=pcm_16000`` is accepted on the WS endpoint and yields
  **mono, signed 16-bit little-endian, 16 kHz** — byte-identical to
  ``PIPELINE_SR``. **No resampling happens in the normal path.**
* Provider chunks are **variable length and NOT frame aligned** (observed
  468 B .. 80 KB). They are transport boundaries with no relationship to
  playback frames, so this handler re-blocks into 512-sample frames with a
  byte-level carry. Nothing is assumed about chunk length, divisibility, or
  alignment.

Chosen policy for malformed (non-even) payloads
-----------------------------------------------
The carry is byte-level, so a chunk boundary that splits a sample is fine
as long as its partner arrives. A stream that *terminates* with an odd
number of pending bytes cannot be interpreted as int16 without inventing
half a sample, so the trailing byte is dropped with a structured error log
and the remaining even-length audio is still emitted, zero-padded to a full
block. A partial sample is never emitted and never zero-padded into a
corrupted sample. See ``tests/test_elevenlabs_tts_handler.py`` T6.

Secrets
-------
The API key is read from the environment (or injected) at construction and
is never logged, never embedded in the URL (auth travels as the ``xi_api_key``
field of the first WebSocket message), and scrubbed from provider error text.
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import json
import logging
import os
from collections.abc import Callable, Iterator
from queue import Empty, Queue
from threading import Event
from threading import Lock, Thread
from time import perf_counter
from typing import Any, Optional, Protocol

from speech_to_speech.baseHandler import BaseHandler
from speech_to_speech.pipeline.cancel_scope import CancelScope
from speech_to_speech.pipeline.handler_types import TTSIn, TTSOut
from speech_to_speech.pipeline.latency import emit_current, recorder, set_current_turn
from speech_to_speech.pipeline.messages import AUDIO_RESPONSE_DONE, EndOfResponse, TTSInput
from speech_to_speech.pipeline.speculative_turns import SpeculativeTurnTracker

logger = logging.getLogger(__name__)

# ── Audio contract ────────────────────────────────────────────────────
PIPELINE_SR = 16000
"""Provider output rate. Equal to the pipeline rate, so no resampling."""

BLOCK_SAMPLES = 512
BLOCK_BYTES = BLOCK_SAMPLES * 2  # int16 mono → 1024 bytes per emitted block

# ── Provider defaults ─────────────────────────────────────────────────
DEFAULT_WS_URL = "wss://api.elevenlabs.io/v1/text-to-dialogue/stream-input"
DEFAULT_MODEL_ID = "eleven_v3_conversational"
DEFAULT_OUTPUT_FORMAT = "pcm_16000"
DEFAULT_API_KEY_ENV = "ELEVENLABS_API_KEY"
DEFAULT_CONNECT_TIMEOUT_S = 20.0
DEFAULT_RECV_POLL_S = 0.05
"""How long one synchronous ``read`` may block before returning to the caller so
cancellation can be observed. Bounds cancellation latency during a network wait."""
DEFAULT_KEEPALIVE_S = 10.0
"""Interval for provider keep-alive frames while a session socket is idle."""


class ProviderError(RuntimeError):
    """Provider reported a failure (error frame, auth, transport, timeout).

    Messages are scrubbed of credentials before being raised or logged.
    """


class StreamEnded(Exception):
    """The provider finished the utterance cleanly (``is_final`` or clean close)."""


class DialogueStream(Protocol):
    """Synchronous facade over one provider utterance.

    Implementations own whatever async machinery they need. The handler only
    ever sees these three calls, which is what keeps the async boundary fully
    encapsulated in this module and makes the handler testable without network.
    """

    def read(self, timeout: float) -> Optional[str]:
        """Return the next base64 audio frame, or ``None`` on timeout.

        Raises :class:`StreamEnded` when the utterance is complete and
        :class:`ProviderError` on any provider/transport failure.
        """
        ...

    def start(self, text: str) -> None:
        """Send one utterance over the session transport."""
        ...

    def close(self) -> None:
        """Release the provider connection. Must be idempotent."""
        ...


def _scrub(text: str, secret: Optional[str]) -> str:
    """Remove a credential from error text. Never let a key reach a log line."""
    if secret and secret in text:
        return text.replace(secret, "<redacted>")
    return text


def _import_websockets() -> Any:
    """Resolve the ``websockets`` module.

    Deliberately a module-level helper rather than a local ``import`` inside
    :meth:`ElevenLabsDialogueStream._connect`: a local import binds the name in
    ``_connect``'s scope only, so ``_open`` could not see it and the real
    transport path failed with ``NameError`` before the first connection.
    Resolving it here gives both methods one explicit, patchable binding, and
    keeps the import lazy so the offline tests never need the dependency.
    """
    import websockets

    return websockets


class ElevenLabsDialogueStream:
    """One session-lifetime Text-to-Dialogue WebSocket.

    One connection and one private event loop serve all utterances in a Voice
    session. A reader task and keep-alive task run on that loop; the synchronous
    handler boundary consumes decoded provider frames from a handoff queue.
    Normal utterances use ``new_turn`` and ``flush`` while leaving the
    socket open; ``close_socket`` is reserved for teardown.

    The loop is owned by a dedicated daemon thread so the provider's 20-second
    inactivity timer is reset even while no utterance is being read. ``close``
    is idempotent and settles both tasks before closing the loop.
    """

    def __init__(
        self,
        *,
        text: str,
        api_key: str,
        voice_id: str,
        ws_url: str = DEFAULT_WS_URL,
        model_id: str = DEFAULT_MODEL_ID,
        output_format: str = DEFAULT_OUTPUT_FORMAT,
        connect_timeout_s: float = DEFAULT_CONNECT_TIMEOUT_S,
        keepalive_s: float = DEFAULT_KEEPALIVE_S,
    ) -> None:
        self._api_key = api_key
        self._voice_id = voice_id
        self._url = f"{ws_url}?model_id={model_id}&output_format={output_format}"
        self._connect_timeout_s = connect_timeout_s
        self._keepalive_s = keepalive_s
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._ws_module: Any = None
        self._ws: Any = None
        self._reader_task: Optional[asyncio.Future] = None
        self._keepalive_task: Optional[asyncio.Future] = None
        self._loop_thread: Optional[Thread] = None
        self._frames: Queue[Any] = Queue()
        self._close_lock = Lock()
        self._closed = False

    # ── connection ────────────────────────────────────────────────────

    def _connect(self) -> None:
        if self._ws_module is None:
            try:
                self._ws_module = _import_websockets()
            except ImportError as exc:  # pragma: no cover - dependency of speech-to-speech
                raise ProviderError(f"websockets is required for the ElevenLabs transport: {exc}") from exc

        self._loop = asyncio.new_event_loop()
        try:
            self._loop.run_until_complete(self._open())
            self._reader_task = self._loop.create_task(self._receive_loop())
            self._keepalive_task = self._loop.create_task(self._keepalive_loop())
            self._loop_thread = Thread(
                target=self._loop.run_forever,
                name="elevenlabs-tts-session",
                daemon=True,
            )
            self._loop_thread.start()
        except Exception as exc:  # noqa: BLE001 - normalised into ProviderError
            self.close()
            raise ProviderError(_scrub(f"ElevenLabs connect failed: {type(exc).__name__}: {exc}", self._api_key)) from exc

    async def _open(self) -> None:
        assert self._loop is not None
        self._ws = await asyncio.wait_for(
            self._ws_module.connect(self._url),
            timeout=self._connect_timeout_s,
        )
        # Credentials travel as a message field, not a header and never in the URL.
        await self._ws.send(json.dumps({"voices": [self._voice_id], "xi_api_key": self._api_key}))
        emit_current("TTS_CONNECTION_READY")

    def start(self, text: str) -> None:
        if self._closed:
            raise StreamEnded()
        if self._loop is None or self._ws is None:
            emit_current("TTS_CONNECTION_START")
            self._connect()
            assert self._loop is not None and self._ws is not None
        else:
            emit_current("TTS_CONNECTION_REUSED")
        future = asyncio.run_coroutine_threadsafe(
            self._ws.send(
                json.dumps(
                    {
                        "inputs": [
                            {
                                "text": text,
                                "voice_id": self._voice_id,
                                "new_turn": True,
                                "flush": True,
                            }
                        ]
                    }
                )
            ),
            self._loop,
        )
        try:
            future.result(self._connect_timeout_s)
        except Exception as exc:
            self.close()
            raise ProviderError(
                _scrub(f"ElevenLabs turn send failed: {type(exc).__name__}: {exc}", self._api_key)
            ) from exc
        emit_current("T11_TTS_REQUEST_SENT")

    # ── reading ───────────────────────────────────────────────────────

    def read(self, timeout: float) -> Optional[str]:
        if self._closed:
            raise StreamEnded()
        if self._loop is None:
            emit_current("TTS_CONNECTION_START")
            self._connect()
        try:
            item = self._frames.get(timeout=timeout)
        except (ProviderError, StreamEnded):
            raise
        except Empty:
            return None
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(
                _scrub(f"ElevenLabs read failed: {type(exc).__name__}: {exc}", self._api_key)
            ) from exc
        if isinstance(item, ProviderError):
            raise item
        if isinstance(item, StreamEnded):
            raise item
        return item

    async def _keepalive_loop(self) -> None:
        while not self._closed:
            await asyncio.sleep(self._keepalive_s)
            if self._closed or self._ws is None:
                return
            try:
                await self._ws.send(json.dumps({"keep_alive": True}))
            except Exception as exc:
                self._put(ProviderError(_scrub(f"ElevenLabs keep-alive failed: {exc}", self._api_key)))
                return

    async def _receive_loop(self) -> None:
        try:
            while not self._closed:
                raw = await self._ws.recv()
                if isinstance(raw, (bytes, bytearray)):
                    raise ProviderError(f"ElevenLabs returned a non-JSON frame ({len(raw)} bytes)")
                try:
                    msg = json.loads(raw)
                except (ValueError, TypeError) as exc:
                    raise ProviderError(f"ElevenLabs returned an unparsable frame: {exc}") from exc
                if not isinstance(msg, dict):
                    raise ProviderError("ElevenLabs returned a non-object frame")
                if msg.get("error") or msg.get("message"):
                    detail = json.dumps(
                        {
                            "error": msg.get("error"),
                            "message": msg.get("message"),
                            "code": msg.get("code"),
                        }
                    )
                    raise ProviderError(_scrub(f"ElevenLabs provider error frame: {detail}", self._api_key))
                audio = msg.get("audio")
                if audio:
                    self._put(audio)
                elif msg.get("is_final"):
                    self._put(StreamEnded())
                    return
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self._put(ProviderError(_scrub(f"ElevenLabs receive failed: {exc}", self._api_key)))

    def _put(self, item: Any) -> None:
        while True:
            try:
                self._frames.put_nowait(item)
                return
            except Exception:
                try:
                    self._frames.get_nowait()
                except Empty:
                    pass

    async def _read(self, timeout: float) -> Optional[str]:
        if self._ws is None:
            raise StreamEnded()

        deadline = asyncio.get_running_loop().time() + timeout
        while True:
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                return None

            if self._recv_task is None:
                self._recv_task = asyncio.ensure_future(self._ws.recv())

            done, _ = await asyncio.wait({self._recv_task}, timeout=remaining)
            if not done:
                return None

            task, self._recv_task = self._recv_task, None
            raw = task.result()  # raises on transport error → normalised by read()

            if isinstance(raw, (bytes, bytearray)):
                # The dialogue endpoint is JSON-only; a binary frame is a protocol surprise.
                raise ProviderError(f"ElevenLabs returned a non-JSON frame ({len(raw)} bytes)")

            try:
                msg = json.loads(raw)
            except (ValueError, TypeError) as exc:
                raise ProviderError(f"ElevenLabs returned an unparsable frame: {exc}") from exc

            if not isinstance(msg, dict):
                raise ProviderError("ElevenLabs returned a non-object frame")

            if msg.get("error") or msg.get("message"):
                detail = json.dumps(
                    {
                        "error": msg.get("error"),
                        "message": msg.get("message"),
                        "code": msg.get("code"),
                    }
                )
                raise ProviderError(_scrub(f"ElevenLabs provider error frame: {detail}", self._api_key))

            audio = msg.get("audio")
            if audio:
                return audio  # base64; decoded by the handler

            if msg.get("is_final"):
                raise StreamEnded()

            # Informational frame (e.g. is_final_audio_for_turn) — keep waiting.

    # ── teardown ──────────────────────────────────────────────────────

    def close(self) -> None:
        with self._close_lock:
            if self._closed:
                return
            self._closed = True
            emit_current("TTS_CONNECTION_CLOSE")

            loop = self._loop
            thread = self._loop_thread
            tasks = [self._reader_task, self._keepalive_task]
            ws = self._ws
            self._loop = None
            self._loop_thread = None
            self._reader_task = None
            self._keepalive_task = None
            self._ws = None

            if loop is None or loop.is_closed():
                return
            try:
                if ws is not None:
                    try:
                        future = asyncio.run_coroutine_threadsafe(ws.send(json.dumps({"close_socket": True})), loop)
                        future.result(1.0)
                    except Exception as exc:  # noqa: BLE001
                        logger.debug(
                            "ElevenLabs close_socket send raised (ignored): %s",
                            _scrub(str(exc), self._api_key),
                        )
                teardown = asyncio.run_coroutine_threadsafe(self._teardown(ws, tasks), loop)
                teardown.result(2.0)
                loop.call_soon_threadsafe(loop.stop)
                if thread is not None:
                    thread.join(timeout=2.0)
            except Exception as exc:  # noqa: BLE001
                logger.debug("ElevenLabs transport close raised (ignored): %s", _scrub(str(exc), self._api_key))
            finally:
                try:
                    loop.run_until_complete(loop.shutdown_asyncgens())
                except Exception:  # noqa: BLE001
                    pass
                loop.close()

    async def _teardown(self, ws: Any, tasks: list[Optional[asyncio.Future]]) -> None:
        """Settle the in-flight receive *before* the socket and the loop go away.

        A bare ``task.cancel()`` would leave the task pending across
        ``loop.close()``, so the invariant "no pending async task after close()"
        would not hold. Cancelling and then awaiting it settles the task.
        """
        active = [task for task in tasks if task is not None and not task.done()]
        for task in active:
            task.cancel()
        if active:
            await asyncio.wait(active)
        for task in tasks:
            if task is None:
                continue
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception:  # noqa: BLE001 - the task's own failure is not teardown's problem
                logger.debug("ElevenLabs receive task ended with an error during teardown", exc_info=True)
        if ws is not None:
            try:
                await ws.close()
            except Exception:  # noqa: BLE001
                logger.debug("ElevenLabs websocket close raised during teardown", exc_info=True)


class ElevenLabsTTSHandler(BaseHandler[TTSIn, TTSOut]):
    """Synthesise ``TTSInput.text`` through ElevenLabs and emit 512-sample blocks.

    Owns no cancellation state (see module docstring). Emits ``bytes`` only;
    ``BaseHandler`` performs the ``AudioOutput`` wrapping.
    """

    def setup(  # noqa: D102 - documented on the class
        self,
        should_listen: Event | None = None,
        cancel_scope: CancelScope | None = None,
        speculative_turns: SpeculativeTurnTracker | None = None,
        api_key: str | None = None,
        api_key_env: str = DEFAULT_API_KEY_ENV,
        voice_id: str | None = None,
        model_id: str = DEFAULT_MODEL_ID,
        output_format: str = DEFAULT_OUTPUT_FORMAT,
        ws_url: str = DEFAULT_WS_URL,
        connect_timeout_s: float = DEFAULT_CONNECT_TIMEOUT_S,
        recv_poll_s: float = DEFAULT_RECV_POLL_S,
        keepalive_s: float = DEFAULT_KEEPALIVE_S,
        stream_factory: Callable[[str], DialogueStream] | None = None,
        gen_kwargs: dict[str, Any] | None = None,
    ) -> None:
        # `gen_kwargs` is part of the pipeline's handler-kwargs convention:
        # prepare_all_args() -> rename_args() injects it into every TTS args dict,
        # so setup() must accept it even though this provider has no generation
        # parameters of its own. Omitting it made the handler un-instantiable
        # through get_tts_handler().
        self.gen_kwargs = gen_kwargs or {}
        self.should_listen = should_listen
        self.cancel_scope = cancel_scope
        self.speculative_turns = speculative_turns
        self.model_id = model_id
        self.output_format = output_format
        self.ws_url = ws_url
        self.connect_timeout_s = connect_timeout_s
        self.recv_poll_s = recv_poll_s
        self.keepalive_s = keepalive_s

        # Key resolution: explicit argument wins, otherwise environment. Never a CLI arg.
        self._api_key = api_key or os.environ.get(api_key_env) or ""
        self._api_key_env = api_key_env
        self.voice_id = voice_id or os.environ.get("ELEVENLABS_VOICE_ID") or ""

        # Test seam: production leaves this None and the real transport is used.
        self._stream_factory = stream_factory
        self._active_stream: DialogueStream | None = None

        logger.debug(
            "ElevenLabsTTSHandler configured: model=%s output_format=%s voice=%s key=%s",
            self.model_id,
            self.output_format,
            self.voice_id or "<unset>",
            "set" if self._api_key else "MISSING",
        )

    # ── provider lifecycle ────────────────────────────────────────────

    def _open_stream(self, text: str) -> DialogueStream:
        if self._active_stream is not None:
            return self._active_stream
        if self._stream_factory is not None:
            return self._stream_factory(text)
        if not self._api_key:
            raise ProviderError(
                f"ElevenLabs API key is not configured (set ${self._api_key_env} or pass api_key)"
            )
        if not self.voice_id:
            raise ProviderError("ElevenLabs voice_id is not configured (set $ELEVENLABS_VOICE_ID or pass voice_id)")
        return ElevenLabsDialogueStream(
            text=text,
            api_key=self._api_key,
            voice_id=self.voice_id,
            ws_url=self.ws_url,
            model_id=self.model_id,
            output_format=self.output_format,
            connect_timeout_s=self.connect_timeout_s,
            keepalive_s=self.keepalive_s,
        )

    def on_session_end(self) -> None:
        """Close the provider dialogue session."""
        logger.debug("ElevenLabsTTSHandler: session end")
        self._close_active_stream()

    def cleanup(self) -> None:
        """Hard teardown. Idempotent; safe to call more than once."""
        self._close_active_stream()

    def _close_active_stream(self) -> None:
        stream, self._active_stream = self._active_stream, None
        if stream is None:
            return
        try:
            stream.close()
        except Exception:  # noqa: BLE001
            logger.exception("ElevenLabsTTSHandler: stream close failed")

    # ── pipeline ──────────────────────────────────────────────────────

    def _is_stale(self, generation: int | None) -> bool:
        scope = self.cancel_scope
        return scope is not None and generation is not None and scope.is_stale(generation)

    def process(self, tts_input: TTSIn) -> Iterator[TTSOut]:
        # ── EndOfResponse: close the response, never synthesise ──────────
        if isinstance(tts_input, EndOfResponse):
            turns = self.speculative_turns
            if turns is not None and not turns.is_latest_after_reopen_grace(
                tts_input.turn_id, tts_input.turn_revision
            ):
                logger.debug(
                    "ElevenLabsTTSHandler: dropping stale end-of-response turn=%s rev=%s",
                    tts_input.turn_id,
                    tts_input.turn_revision,
                )
                return
            yield AUDIO_RESPONSE_DONE
            return

        if not isinstance(tts_input, TTSInput):
            logger.warning("ElevenLabsTTSHandler: unexpected input type %s", type(tts_input))
            return

        # ── speculative-turn gate ───────────────────────────────────────
        turns = self.speculative_turns
        if turns is not None:
            if not turns.is_latest_after_reopen_grace(tts_input.turn_id, tts_input.turn_revision):
                logger.debug(
                    "ElevenLabsTTSHandler: dropping stale TTS input turn=%s rev=%s",
                    tts_input.turn_id,
                    tts_input.turn_revision,
                )
                return
            turns.commit(tts_input.turn_id, tts_input.turn_revision)

        # ── cancellation that predates this generation ──────────────────
        if self._is_stale(tts_input.cancel_generation):
            logger.debug(
                "ElevenLabsTTSHandler: input already cancelled turn=%s gen=%s",
                tts_input.turn_id,
                tts_input.cancel_generation,
            )
            return

        text = (tts_input.text or "").strip()
        if not text:
            return

        generation = self.cancel_scope.generation if self.cancel_scope is not None else None

        stream: DialogueStream | None = None
        carry = bytearray()
        cancelled = False
        received_bytes = 0
        emitted_blocks = 0
        chunk_count = 0
        first_audio_frame_received = False
        first_audio_at: float | None = None
        provider_error = False
        started_at = perf_counter()
        set_current_turn(tts_input.turn_id, tts_input.turn_revision)

        try:
            try:
                stream = self._open_stream(text)
                stream.start(text)
            except ProviderError as exc:
                logger.error(
                    "ElevenLabsTTSHandler: could not start synthesis turn=%s rev=%s: %s",
                    tts_input.turn_id,
                    tts_input.turn_revision,
                    _scrub(str(exc), self._api_key),
                )
                return
            self._active_stream = stream

            while True:
                if self._is_stale(generation):
                    cancelled = True
                    logger.info(
                        "ElevenLabsTTSHandler: cancelled mid-stream turn=%s gen %s -> %s",
                        tts_input.turn_id,
                        generation,
                        self.cancel_scope.generation if self.cancel_scope is not None else None,
                    )
                    break

                try:
                    frame = stream.read(self.recv_poll_s)
                except StreamEnded:
                    emit_current("TTS_COMPLETE")
                    break
                except ProviderError as exc:
                    provider_error = True
                    logger.error(
                        "ElevenLabsTTSHandler: provider error turn=%s after %d chunk(s): %s",
                        tts_input.turn_id,
                        chunk_count,
                        _scrub(str(exc), self._api_key),
                    )
                    break

                if frame is None:
                    continue
                if not first_audio_frame_received:
                    first_audio_frame_received = True
                    emit_current("T12_TTS_FIRST_AUDIO_RECEIVED")

                try:
                    pcm = base64.b64decode(frame, validate=True)
                except (binascii.Error, ValueError) as exc:
                    provider_error = True
                    logger.error(
                        "ElevenLabsTTSHandler: base64 decode failed turn=%s chunk=%d: %s",
                        tts_input.turn_id,
                        chunk_count,
                        exc,
                    )
                    break

                chunk_count += 1
                received_bytes += len(pcm)
                if first_audio_at is None:
                    first_audio_at = perf_counter()
                    logger.info(
                        "ElevenLabsTTSHandler TTFA: %.3fs (turn=%s rev=%s model=%s)",
                        first_audio_at - started_at,
                        tts_input.turn_id,
                        tts_input.turn_revision,
                        self.model_id,
                    )

                carry += pcm
                while len(carry) >= BLOCK_BYTES:
                    if self._is_stale(generation):
                        cancelled = True
                        break
                    yield bytes(carry[:BLOCK_BYTES])
                    del carry[:BLOCK_BYTES]
                    emitted_blocks += 1
                if cancelled:
                    break

            if not cancelled and carry:
                if len(carry) % 2:
                    logger.error(
                        "ElevenLabsTTSHandler: stream ended with an odd byte count (%d) turn=%s — "
                        "dropping the trailing partial sample rather than emitting or padding it",
                        len(carry),
                        tts_input.turn_id,
                    )
                    del carry[-1:]
                if carry:
                    carry += b"\x00" * (BLOCK_BYTES - len(carry))
                    yield bytes(carry)
                    emitted_blocks += 1
        finally:
            if cancelled or provider_error:
                self._close_active_stream()

            logger.info(
                "ElevenLabsTTSHandler: turn=%s rev=%s cancelled=%s chunks=%d received_bytes=%d "
                "emitted_blocks=%d elapsed=%.3fs",
                tts_input.turn_id,
                tts_input.turn_revision,
                cancelled,
                chunk_count,
                received_bytes,
                emitted_blocks,
                perf_counter() - started_at,
            )
