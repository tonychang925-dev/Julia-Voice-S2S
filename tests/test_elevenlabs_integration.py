"""VOICE-EL-P0C — integration dry-run.

P0A proved the provider engine in isolation; P0B proved the wiring. This file
proves the two hold together along the real path, without touching a server:

    CLI --tts elevenlabs
      -> prepare_all_args
      -> build_pipeline(mode=realtime)
      -> real pipeline handlers (LMOutputProcessor, TTS dispatch)
      -> real ElevenLabsTTSHandler, driven by controlled provider frames
      -> send_audio_chunks_queue

It adds no production code. The only things stubbed are the stages that need
model weights this machine does not have (VAD / STT / LLM) and the provider
websocket itself, which is replaced by a deterministic frame source so the test
never opens a network connection.

Like test_elevenlabs_wiring.py, this module skips where the runtime dependency
set is absent (it imports speech_to_speech.s2s_pipeline).
"""

from __future__ import annotations

import base64
import importlib
import json
import sys
import threading
import time
import types
from queue import Empty, Queue
from typing import Any

import pytest

pytest.importorskip("torch", reason="s2s_pipeline requires the full runtime dependency set")
pytest.importorskip("openai", reason="s2s_pipeline requires the full runtime dependency set")

BLOCK = 1024  # 512 samples of int16 mono
TAGGED_TEXT = "[laughs] 老公，你今天怎么这么简短呀，是不是刚忙完"


# ═══════════════════════════════════════════════════════════════════════════
# Harness
# ═══════════════════════════════════════════════════════════════════════════


def _alias_package():
    nltk = types.ModuleType("nltk")
    nltk.sent_tokenize = lambda text: [text]  # noqa: E731
    nltk.data = types.ModuleType("nltk.data")
    nltk.data.find = lambda *a, **k: "stub"
    nltk.download = lambda *a, **k: True
    sys.modules.setdefault("nltk", nltk)
    import s2s

    sys.modules.setdefault("speech_to_speech", s2s)


def _pipeline():
    _alias_package()
    return importlib.import_module("speech_to_speech.s2s_pipeline")


def _messages():
    _alias_package()
    return importlib.import_module("speech_to_speech.pipeline.messages")


def pcm(length: int, seed: int = 0) -> bytes:
    return bytes(((i * 7 + 11 + seed) % 251) + 1 for i in range(length))


def b64(payload: bytes) -> str:
    return base64.b64encode(payload).decode("ascii")


class _Stage:
    """Cheap stand-in for a model-loading pipeline stage."""

    def __init__(self, *a, **k):
        self.queue_in = k.get("queue_in")
        self.queue_out = k.get("queue_out")

    def run(self):
        pass

    def stop(self):
        pass


class ControlledStream:
    """Provider stream the test drives frame by frame. No network."""

    def __init__(self, frames):
        self.frames = list(frames)
        self.i = 0
        self.closed = False
        self.over_ran = False

    def read(self, timeout):
        from speech_to_speech.TTS.elevenlabs_tts_handler import StreamEnded

        if self.i >= len(self.frames):
            raise StreamEnded()
        item = self.frames[self.i]
        self.i += 1
        if callable(item):
            return item(timeout)
        if isinstance(item, Exception):
            raise item
        return item

    def close(self):
        self.closed = True


class _Harness:
    def __init__(self, manager, handler, queues, provider):
        self.manager = manager
        self.handler = handler
        self.queues = queues
        self.provider = provider
        self.thread: threading.Thread | None = None

    # A realtime PipelineUnit creates its OWN queues internally; the dict from
    # initialize_queues_and_events() is not what the unit's handlers read and
    # write. The handler itself is the authority on which queues it is wired to.
    @property
    def send_queue(self):
        return self.handler.queue_out

    @property
    def input_queue(self):
        return self.handler.queue_in

    def start(self):
        self.thread = threading.Thread(target=self.handler.run, daemon=True)
        self.thread.start()
        return self

    def stop(self):
        self.queues["stop_event"].set()
        if self.thread is not None:
            self.thread.join(timeout=5.0)


def _build_via_cli(monkeypatch, tts="elevenlabs", frames=()):
    """Real CLI parse -> prepare_all_args -> real build_pipeline(realtime)."""
    P = _pipeline()
    sys.argv = ["prog", "--mode", "realtime", "--tts", tts]
    args = P.parse_arguments()
    P.prepare_all_args(
        args.module_kwargs,
        args.whisper_stt_handler_kwargs,
        args.paraformer_stt_handler_kwargs,
        args.faster_whisper_stt_handler_kwargs,
        args.mlx_audio_whisper_stt_handler_kwargs,
        args.parakeet_tdt_stt_handler_kwargs,
        args.language_model_handler_kwargs,
        args.responses_api_language_model_handler_kwargs,
        args.chat_tts_handler_kwargs,
        args.facebook_mms_tts_handler_kwargs,
        args.pocket_tts_handler_kwargs,
        args.kokoro_tts_handler_kwargs,
        args.qwen3_tts_handler_kwargs,
        args.elevenlabs_tts_handler_kwargs,
    )

    # Only the model-loading stages are stubbed; LMOutputProcessor and the TTS
    # dispatch below are the real implementations.
    monkeypatch.setattr(P, "VADHandler", _Stage)
    monkeypatch.setattr(P, "get_stt_handler", lambda *a, **k: _Stage())
    monkeypatch.setattr(P, "get_llm_handler", lambda *a, **k: _Stage())

    queues = P.initialize_queues_and_events()
    manager = P.build_pipeline(
        args.module_kwargs,
        args.socket_receiver_kwargs,
        args.socket_sender_kwargs,
        args.websocket_streamer_kwargs,
        args.vad_handler_kwargs,
        args.whisper_stt_handler_kwargs,
        args.faster_whisper_stt_handler_kwargs,
        args.paraformer_stt_handler_kwargs,
        args.mlx_audio_whisper_stt_handler_kwargs,
        args.parakeet_tdt_stt_handler_kwargs,
        args.language_model_handler_kwargs,
        args.responses_api_language_model_handler_kwargs,
        args.chat_tts_handler_kwargs,
        args.facebook_mms_tts_handler_kwargs,
        args.pocket_tts_handler_kwargs,
        args.kokoro_tts_handler_kwargs,
        args.qwen3_tts_handler_kwargs,
        args.elevenlabs_tts_handler_kwargs,
        queues,
    )

    from speech_to_speech.TTS.elevenlabs_tts_handler import ElevenLabsTTSHandler

    handlers = [h for h in manager.handlers if isinstance(h, ElevenLabsTTSHandler)]
    assert len(handlers) == 1, f"expected one ElevenLabs handler in the real pipeline, got {manager.handlers}"
    handler = handlers[0]

    provider = ControlledStream(frames)
    # Test-only injection of the provider transport. Production resolves the real
    # websocket; nothing in the pipeline is modified to make this possible.
    handler._stream_factory = lambda _text: provider

    return P, args, _Harness(manager, handler, queues, provider)


def _drain(queue, deadline_s=2.0):
    """Collect everything the pipeline pushes onto queue_out until it goes quiet."""
    items = []
    deadline = time.monotonic() + deadline_s
    while time.monotonic() < deadline:
        try:
            items.append(queue.get(timeout=0.05))
        except Empty:
            if items:
                break
    return items


def _payloads(items):
    """Unwrap AudioOutput exactly as the realtime send loop does."""
    from speech_to_speech.api.openai_realtime.websocket_router import _audio_payload

    return [_audio_payload(i) for i in items]


# ═══════════════════════════════════════════════════════════════════════════
# I1 — CLI to send_audio_chunks_queue
# ═══════════════════════════════════════════════════════════════════════════


def test_i1_cli_to_audio_output_queue(monkeypatch):
    """The whole point of P0C: the provider selected on the command line produces
    PCM on the pipeline's real output queue, in the pipeline's frame contract."""
    M = _messages()
    first, second = pcm(BLOCK, seed=1), pcm(BLOCK, seed=2)
    _, _, h = _build_via_cli(monkeypatch, frames=[b64(first), b64(second)])

    h.start()
    try:
        h.input_queue.put(M.TTSInput(text="hello", turn_id="t1", turn_revision=0))
        items = _drain(h.send_queue)
    finally:
        h.stop()

    blocks = [p for p in _payloads(items) if isinstance(p, (bytes, bytearray)) and len(p) == BLOCK]
    assert blocks == [first, second], "exact 512-sample blocks, in order, on the real output queue"
    assert h.provider.closed, "provider stream must be closed at the end of the utterance"


def test_i1b_end_of_response_reaches_the_queue_as_a_detectable_sentinel(monkeypatch):
    """The done-sentinel must survive the AudioOutput wrapping the base handler
    applies when cancel_generation is set — the realtime send loop relies on
    being able to recover it."""
    M = _messages()
    _, _, h = _build_via_cli(monkeypatch, frames=[b64(pcm(BLOCK, seed=3))])

    h.start()
    try:
        # cancel_generation must equal the scope's current generation, otherwise
        # BaseHandler.should_process_input() drops the item as stale.
        h.input_queue.put(M.TTSInput(text="hi", turn_id="t1", turn_revision=0, cancel_generation=0))
        _drain(h.send_queue)
        h.input_queue.put(M.EndOfResponse(turn_id="t1", turn_revision=0, cancel_generation=0))
        items = _drain(h.send_queue)
    finally:
        h.stop()

    assert M.AUDIO_RESPONSE_DONE in _payloads(items)


def test_i1c_generation_tag_crosses_the_queue_boundary(monkeypatch):
    """Generation tagging is BaseHandler's job; the provider must not duplicate it.

    cancel_generation uses the current generation (0 here) rather than an
    arbitrary value: anything else is stale by definition and the input would
    be dropped before reaching the handler.
    """
    M = _messages()
    _, _, h = _build_via_cli(monkeypatch, frames=[b64(pcm(BLOCK, seed=4))])

    h.start()
    try:
        h.input_queue.put(M.TTSInput(text="hi", turn_id="t1", turn_revision=0, cancel_generation=0))
        items = _drain(h.send_queue)
    finally:
        h.stop()

    wrapped = [i for i in items if isinstance(i, M.AudioOutput)]
    assert wrapped, "outputs must be wrapped into AudioOutput when cancel_generation is set"
    assert all(i.cancel_generation == 0 for i in wrapped)


# ═══════════════════════════════════════════════════════════════════════════
# I2 — the expression tag survives LMOutputProcessor -> provider input
# ═══════════════════════════════════════════════════════════════════════════


def test_i2_expression_tag_reaches_the_provider_verbatim(monkeypatch):
    """Real LMOutputProcessor -> TTSInput -> real handler -> provider.

    The tag is part of the LLM's text. Nothing between the LLM and the provider
    may strip, rewrite, reorder or normalise it, or ElevenLabs never sees the
    expressive direction we paid for.
    """
    P, _, h = _build_via_cli(monkeypatch, frames=[b64(pcm(BLOCK, seed=5))])
    M = _messages()

    lm_processors = [x for x in h.manager.handlers if type(x).__name__ == "LMOutputProcessor"]
    assert len(lm_processors) == 1, "the real pipeline must contain a real LMOutputProcessor"
    lm_processor = lm_processors[0]

    received: list[str] = []
    h.handler._stream_factory = lambda text: (received.append(text), h.provider)[1]

    chunk = M.LLMResponseChunk(text=TAGGED_TEXT, turn_id="t1", turn_revision=0, response=None)
    tts_inputs = list(lm_processor.process(chunk))
    assert len(tts_inputs) == 1 and isinstance(tts_inputs[0], M.TTSInput)

    list(h.handler.process(tts_inputs[0]))

    assert received == [TAGGED_TEXT], f"provider text was altered in flight: {received!r}"


def test_i2b_tag_survives_the_full_queue_boundary(monkeypatch):
    """Same guarantee, but pushed through queue_in so the handler thread does the
    work rather than a direct process() call."""
    M = _messages()
    P, _, h = _build_via_cli(monkeypatch, frames=[b64(pcm(BLOCK, seed=6))])

    received: list[str] = []
    h.handler._stream_factory = lambda text: (received.append(text), h.provider)[1]

    lm_processor = next(x for x in h.manager.handlers if type(x).__name__ == "LMOutputProcessor")
    chunk = M.LLMResponseChunk(text=TAGGED_TEXT, turn_id="t1", turn_revision=0, response=None)
    for item in lm_processor.process(chunk):
        h.input_queue.put(item)

    h.start()
    try:
        _drain(h.send_queue)
    finally:
        h.stop()

    assert received == [TAGGED_TEXT]
    assert json.dumps(received[0], ensure_ascii=False).count("[laughs]") == 1


# ═══════════════════════════════════════════════════════════════════════════
# I3 — cancellation across the pipeline queue boundary
#
# P0A proved cancellation inside the handler. This proves it across the queue:
# a cancel raised outside the handler, while the provider still holds later
# audio, must keep that audio off send_audio_chunks_queue.
# ═══════════════════════════════════════════════════════════════════════════


def test_i3_cancel_while_provider_still_holds_audio_keeps_it_off_the_queue(monkeypatch):
    M = _messages()
    early, late = pcm(BLOCK, seed=7), pcm(BLOCK, seed=8)
    release = threading.Event()

    def late_frame(_timeout):
        release.wait(timeout=5.0)
        return b64(late)

    _, _, h = _build_via_cli(monkeypatch, frames=[b64(early), late_frame])

    h.start()
    try:
        h.input_queue.put(M.TTSInput(text="hello", turn_id="t1", turn_revision=0))

        # Wait until the early audio has actually reached the output queue.
        deadline = time.monotonic() + 5.0
        blocks: list[bytes] = []
        while time.monotonic() < deadline:
            try:
                blocks.extend(p for p in _payloads([h.send_queue.get(timeout=0.05)]) if isinstance(p, bytes))
            except Empty:
                pass
            if early in blocks:
                break
        assert early in blocks, "the early block must land before we cancel"

        h.handler.cancel_scope.cancel()  # raised outside the handler thread
        release.set()
        items = _drain(h.send_queue)
    finally:
        h.stop()

    everything = blocks + [p for p in _payloads(items) if isinstance(p, (bytes, bytearray))]
    assert late not in everything, "audio the provider still held must never reach the output queue"
    assert h.provider.closed


def test_i3b_cancelled_input_never_reaches_the_provider(monkeypatch):
    M = _messages()
    _, _, h = _build_via_cli(monkeypatch, frames=[b64(pcm(BLOCK, seed=9))])

    opened: list[str] = []
    h.handler._stream_factory = lambda text: (opened.append(text), h.provider)[1]

    h.handler.cancel_scope.cancel()  # generation 1; the input below carries 0
    h.input_queue.put(M.TTSInput(text="hello", turn_id="t1", turn_revision=0, cancel_generation=0))

    h.start()
    try:
        items = _drain(h.send_queue)
    finally:
        h.stop()

    assert opened == [], "an already-cancelled input must not open a provider stream"
    assert not [p for p in _payloads(items) if isinstance(p, (bytes, bytearray))]
