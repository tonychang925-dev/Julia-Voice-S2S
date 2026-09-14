"""VOICE-EL-P0A — ElevenLabs TTS handler unit tests.

Offline only: the provider transport is injected as a fake, so no test in this
file opens a network connection or needs an API key.

Covers the rechunk contract (T1-T6), the pipeline contract (T7-T11) and secret
hygiene (T12). Test ids map 1:1 to the VOICE-EL-P0A task spec.
"""

from __future__ import annotations

import asyncio
import base64
import importlib
import json
import logging
import sys
import types
from queue import Queue
from threading import Event

import pytest


# ═══════════════════════════════════════════════════════════════════════════
# Harness — mirrors the package aliasing used by the other tests in this dir
# ═══════════════════════════════════════════════════════════════════════════


def _alias_package():
    nltk = types.ModuleType("nltk")
    nltk.sent_tokenize = lambda text: [text]  # noqa: E731
    sys.modules.setdefault("nltk", nltk)
    import s2s

    sys.modules.setdefault("speech_to_speech", s2s)


def _imports():
    _alias_package()
    return types.SimpleNamespace(
        handler=importlib.import_module("speech_to_speech.TTS.elevenlabs_tts_handler"),
        messages=importlib.import_module("speech_to_speech.pipeline.messages"),
        cancel_scope=importlib.import_module("speech_to_speech.pipeline.cancel_scope"),
        turns=importlib.import_module("speech_to_speech.pipeline.speculative_turns"),
    )


BLOCK = 1024  # 512 samples × 2 bytes, int16 mono


def b64(payload: bytes) -> str:
    return base64.b64encode(payload).decode("ascii")


def pcm(length: int, seed: int = 0) -> bytes:
    """Deterministic, non-zero, even-spread PCM byte pattern."""
    return bytes(((i * 7 + 11 + seed) % 251) + 1 for i in range(length))


class FakeStream:
    """Injected provider transport. Never touches the network."""

    def __init__(self, frames, on_read=None):
        self.frames = list(frames)
        self.i = 0
        self.closed = False
        self.on_read = on_read

    def read(self, timeout):
        if self.on_read is not None:
            self.on_read(self.i)
        if self.i >= len(self.frames):
            raise self._ended()
        item = self.frames[self.i]
        self.i += 1
        if isinstance(item, Exception):
            raise item
        return item

    def close(self):
        self.closed = True

    @staticmethod
    def _ended():
        from speech_to_speech.TTS.elevenlabs_tts_handler import StreamEnded

        return StreamEnded()


class NeverCalled:
    """A factory that fails the test if the handler tries to synthesise."""

    def __init__(self):
        self.called = False

    def __call__(self, text):  # pragma: no cover - only reached on failure
        self.called = True
        raise AssertionError("provider stream must not be opened")


def build(H, *, frames=(), cancel_scope=None, speculative_turns=None, on_read=None, factory=None, api_key="test-api-key"):
    if factory is None:
        stream = FakeStream(frames, on_read=on_read)

        def factory(_text, _stream=stream):
            return _stream
    else:
        stream = None

    handler = H.ElevenLabsTTSHandler(
        Event(),
        Queue(),
        Queue(),
        setup_args=(Event(),),
        setup_kwargs={
            "cancel_scope": cancel_scope,
            "speculative_turns": speculative_turns,
            "stream_factory": factory,
            "api_key": api_key,
            "voice_id": "test-voice-id",
        },
    )
    return handler, stream


def tts_input(msgs, text="hello world", **kw):
    return msgs.TTSInput(text=text, **kw)


# ═══════════════════════════════════════════════════════════════════════════
# T1 — exact block
# ═══════════════════════════════════════════════════════════════════════════


def test_t1_exact_block_passes_through_unchanged():
    M = _imports()
    payload = pcm(BLOCK, seed=1)
    handler, _ = build(M.handler, frames=[b64(payload)])

    out = list(handler.process(tts_input(M.messages)))[0]

    assert isinstance(out, bytes)
    assert len(out) == BLOCK
    assert out == payload


# ═══════════════════════════════════════════════════════════════════════════
# T2 — sub-block carry (two chunks that only together form one block)
# ═══════════════════════════════════════════════════════════════════════════


def test_t2_two_sub_block_chunks_are_carried_into_one_exact_block():
    M = _imports()
    a, b = pcm(468, seed=2), pcm(556, seed=3)
    handler, _ = build(M.handler, frames=[b64(a), b64(b)])

    out = list(handler.process(tts_input(M.messages)))

    assert len(out) == 1
    assert out[0] == a + b
    assert len(out[0]) == BLOCK


# ═══════════════════════════════════════════════════════════════════════════
# T3 — oversized variable chunk
# ═══════════════════════════════════════════════════════════════════════════


def test_t3_oversized_chunk_splits_into_exact_blocks_without_loss():
    M = _imports()
    payload = pcm(80 * 1024, seed=4)
    handler, _ = build(M.handler, frames=[b64(payload)])

    out = list(handler.process(tts_input(M.messages)))

    assert all(len(block) == BLOCK for block in out)
    assert len(out) == 80
    assert b"".join(out) == payload


# ═══════════════════════════════════════════════════════════════════════════
# T4 — arbitrary split boundaries (the core rechunk correctness test)
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    "sizes",
    [
        [468, 1703, 8191, 511, 1025, 12344],
        [1, 1023, 2, 65535, 7, 334],
        [1, 1, 2048, 1024, 512, 512],
    ],
)
def test_t4_arbitrary_boundaries_reassemble_losslessly(sizes):
    M = _imports()
    total = sum(sizes)
    assert total % 2 == 0, "T4 asserts lossless reassembly of VALID pcm; odd totals are T6"
    original = pcm(total, seed=5)

    frames, offset = [], 0
    for size in sizes:
        frames.append(b64(original[offset : offset + size]))
        offset += size

    handler, stream = build(M.handler, frames=frames)
    out = list(handler.process(tts_input(M.messages)))

    joined = b"".join(out)
    padding = len(joined) - total

    assert padding >= 0
    assert joined[:total] == original, "no sample loss, duplication or reordering"
    assert joined[total:] == b"\x00" * padding, "only the tail may be zero padding"
    assert all(len(block) == BLOCK for block in out)
    assert stream.closed


# ═══════════════════════════════════════════════════════════════════════════
# T5 — tail padding
# ═══════════════════════════════════════════════════════════════════════════


def test_t5_tail_is_padded_to_a_full_block_and_nothing_else_is():
    M = _imports()
    tail_len = 690
    original = pcm(BLOCK + tail_len, seed=6)
    assert original[-1] != 0

    handler, _ = build(M.handler, frames=[b64(original)])
    out = list(handler.process(tts_input(M.messages)))

    assert len(out) == 2
    assert out[0] == original[:BLOCK]
    assert len(out[1]) == BLOCK
    assert out[1][:tail_len] == original[BLOCK:]
    assert out[1][tail_len:] == b"\x00" * (BLOCK - tail_len)


# ═══════════════════════════════════════════════════════════════════════════
# T6 — odd-byte (malformed) payload
#
# Documented policy: the carry is byte-level, so a split sample is fine as long
# as its partner arrives. A stream that ENDS with an odd byte cannot be
# interpreted as int16 without inventing half a sample, so the trailing byte is
# dropped (logged) and the remaining even-length audio is still emitted padded.
# A partial sample is never emitted and never zero-padded into a bad sample.
# ═══════════════════════════════════════════════════════════════════════════


def test_t6a_odd_trailing_byte_is_dropped_not_reinterpreted(caplog):
    M = _imports()
    original = pcm(BLOCK + 1, seed=7)
    assert len(original) % 2 == 1

    handler, _ = build(M.handler, frames=[b64(original)])
    with caplog.at_level(logging.ERROR):
        out = list(handler.process(tts_input(M.messages)))

    assert len(out) == 1
    assert out[0] == original[:BLOCK]
    assert any("odd byte count" in rec.getMessage() for rec in caplog.records)


def test_t6b_odd_tail_keeps_the_valid_even_prefix():
    M = _imports()
    original = pcm(BLOCK + 7, seed=8)
    assert len(original) % 2 == 1

    handler, _ = build(M.handler, frames=[b64(original)])
    out = list(handler.process(tts_input(M.messages)))

    assert len(out) == 2
    assert out[0] == original[:BLOCK]
    # 7 bytes → drop the 1 malformed byte → 6 valid bytes + 2 bytes of padding
    assert len(out[1]) == BLOCK
    assert out[1][:6] == original[BLOCK : BLOCK + 6]
    assert out[1][6:] == b"\x00" * (BLOCK - 6)


# ═══════════════════════════════════════════════════════════════════════════
# T7 — EndOfResponse
# ═══════════════════════════════════════════════════════════════════════════


def test_t7_end_of_response_emits_sentinel_and_never_synthesises():
    M = _imports()
    guard = NeverCalled()
    handler, _ = build(M.handler, factory=guard)

    out = list(handler.process(M.messages.EndOfResponse(turn_id="t", turn_revision=0)))

    assert out == [M.messages.AUDIO_RESPONSE_DONE]
    assert guard.called is False


# ═══════════════════════════════════════════════════════════════════════════
# T8 — cancellation before generation
# ═══════════════════════════════════════════════════════════════════════════


def test_t8_input_cancelled_before_generation_produces_no_audio():
    M = _imports()
    scope = M.cancel_scope.CancelScope()
    scope.cancel()  # generation is now 1; the input carries generation 0
    assert scope.generation == 1

    guard = NeverCalled()
    handler, _ = build(M.handler, factory=guard, cancel_scope=scope)

    out = list(handler.process(tts_input(M.messages, cancel_generation=0)))

    assert out == []
    assert guard.called is False


# ═══════════════════════════════════════════════════════════════════════════
# T9 — cancellation during streaming
# ═══════════════════════════════════════════════════════════════════════════


def test_t9_cancel_mid_stream_stops_emitting_and_closes_provider():
    M = _imports()
    a, b, c = pcm(BLOCK, seed=9), pcm(BLOCK, seed=10), pcm(BLOCK, seed=11)
    scope = M.cancel_scope.CancelScope()

    def on_read(index):
        # Cancel after chunk A has been consumed, i.e. just before B is read.
        if index == 1:
            scope.cancel()

    handler, stream = build(M.handler, frames=[b64(a), b64(b), b64(c)], cancel_scope=scope, on_read=on_read)
    out = list(handler.process(tts_input(M.messages, cancel_generation=None)))

    assert out == [a], "A may be emitted; B and C must not reach the output"
    assert b not in out
    assert c not in out
    assert stream.closed is True


def test_t9b_handler_never_mutates_cancel_state():
    M = _imports()
    scope = M.cancel_scope.CancelScope()
    handler, _ = build(M.handler, frames=[b64(pcm(BLOCK, seed=12))], cancel_scope=scope)

    before = scope.generation
    list(handler.process(tts_input(M.messages)))

    assert scope.generation == before, "the handler is a consumer of cancellation state, not its owner"


# ═══════════════════════════════════════════════════════════════════════════
# T10 — stale speculative revision
# ═══════════════════════════════════════════════════════════════════════════


def test_t10_stale_speculative_revision_is_dropped_without_a_provider_call():
    M = _imports()
    tracker = M.turns.SpeculativeTurnTracker()
    tracker.observe("turn-x", 2)  # a newer revision exists

    guard = NeverCalled()
    handler, _ = build(M.handler, factory=guard, speculative_turns=tracker)

    out = list(handler.process(tts_input(M.messages, turn_id="turn-x", turn_revision=0)))

    assert out == []
    assert guard.called is False


def test_t10b_current_revision_is_committed_and_synthesised():
    M = _imports()
    tracker = M.turns.SpeculativeTurnTracker()
    tracker.observe("turn-y", 0)

    handler, _ = build(M.handler, frames=[b64(pcm(BLOCK, seed=13))], speculative_turns=tracker)
    out = list(handler.process(tts_input(M.messages, turn_id="turn-y", turn_revision=0)))

    assert len(out) == 1
    assert tracker.is_committed("turn-y", 0)


# ═══════════════════════════════════════════════════════════════════════════
# T11 — provider error recovery
# ═══════════════════════════════════════════════════════════════════════════


def test_t11_handler_survives_a_provider_error_and_recovers():
    M = _imports()
    good = pcm(BLOCK, seed=14)

    broken = FakeStream([M.handler.ProviderError("synthetic provider failure")])
    healthy = FakeStream([b64(good)])
    streams = [broken, healthy]

    def factory(_text, _streams=streams):
        return _streams.pop(0)

    handler, _ = build(M.handler, factory=factory)

    first = list(handler.process(tts_input(M.messages, text="first")))
    assert first == []
    assert broken.closed is True

    second = list(handler.process(tts_input(M.messages, text="second")))
    assert second == [good], "handler must remain usable after a provider failure"


def test_t11b_base64_decode_failure_does_not_kill_the_handler():
    M = _imports()
    good = pcm(BLOCK, seed=15)
    bad = FakeStream(["!!!not-base64!!!"])
    ok = FakeStream([b64(good)])

    handler, _ = build(M.handler, factory=lambda _t, _q=[bad, ok]: _q.pop(0))

    assert list(handler.process(tts_input(M.messages, text="bad"))) == []
    assert list(handler.process(tts_input(M.messages, text="ok"))) == [good]


# ═══════════════════════════════════════════════════════════════════════════
# T12 — secret hygiene
# ═══════════════════════════════════════════════════════════════════════════


def test_t12_api_key_never_reaches_logs_or_error_text(caplog):
    M = _imports()
    secret = "sk-super-secret-value-1234567890"
    leaked_stream = FakeStream([M.handler.ProviderError(f"auth failed for key {secret}")])

    handler, _ = build(M.handler, factory=lambda _t: leaked_stream, api_key=secret)

    with caplog.at_level(logging.DEBUG):
        list(handler.process(tts_input(M.messages, text="hello")))

    rendered = "\n".join(rec.getMessage() for rec in caplog.records)
    assert secret not in rendered, "the API key must never reach a log record"
    assert "<redacted>" in rendered, "provider error text must be scrubbed, not merely omitted"

    # The key is legitimately held in memory (it is required to authenticate);
    # what must never happen is that it is *logged* or placed in the URL.
    assert secret not in handler.ws_url


# ═══════════════════════════════════════════════════════════════════════════
# VOICE-EL-P0A-R1 — the real transport code path
#
# These tests exist because every other test in this file injects a fake
# stream_factory, which bypasses ElevenLabsDialogueStream entirely. A defect
# that only manifests on the real path (a local `import websockets` in
# _connect() that _open() could not see) therefore shipped undetected. Only
# the network call itself is patched here; all of _connect()/_open() runs.
# ═══════════════════════════════════════════════════════════════════════════


def test_r1_real_transport_connect_path_binds_websockets_and_sends_init_frames(monkeypatch):
    M = _imports()
    ws = pytest.importorskip("websockets")

    sent = []

    class FakeConnection:
        async def send(self, payload):
            sent.append(json.loads(payload))

        async def close(self):
            sent.append({"__closed__": True})

    async def fake_connect(url, *args, **kwargs):
        sent.append({"__url__": url})
        return FakeConnection()

    # Patch ONLY the network call; the real _connect()/_open() body executes.
    monkeypatch.setattr(ws, "connect", fake_connect)

    stream = M.handler.ElevenLabsDialogueStream(text="hello julia", api_key="k", voice_id="voice-1")
    stream._connect()  # the defect locus — used to raise NameError before connecting

    assert sent[0]["__url__"].endswith("?model_id=eleven_v3_conversational&output_format=pcm_16000")
    assert sent[1] == {"voices": ["voice-1"], "xi_api_key": "k"}
    assert sent[2] == {"inputs": [{"text": "hello julia", "voice_id": "voice-1", "new_turn": False}]}
    assert sent[3] == {"close_socket": True}

    stream.close()
    assert sent[-1] == {"__closed__": True}


def test_r1_close_settles_pending_recv_task_and_closes_private_loop(monkeypatch):
    M = _imports()
    ws = pytest.importorskip("websockets")

    class FakeConnection:
        async def send(self, payload):
            pass

        async def recv(self):
            await asyncio.Event().wait()  # never completes: a permanently pending receive

        async def close(self):
            pass

    async def fake_connect(url, *args, **kwargs):
        return FakeConnection()

    monkeypatch.setattr(ws, "connect", fake_connect)

    stream = M.handler.ElevenLabsDialogueStream(text="t", api_key="k", voice_id="v")
    stream._connect()

    assert stream.read(0.02) is None, "no frame within the poll window"
    task = stream._recv_task
    assert task is not None and not task.done(), "a receive must still be in flight"

    loop = stream._loop
    stream.close()

    assert task.done(), "close() must settle the pending receive task, not merely cancel it"
    assert task.cancelled(), "the settled task must be cancelled"
    assert loop.is_closed(), "close() must close the private event loop"
    assert stream._recv_task is None, "no task may outlive close()"


# ═══════════════════════════════════════════════════════════════════════════
# Optional — provider request shaping, lifecycle idempotence
# ═══════════════════════════════════════════════════════════════════════════


def test_opt_request_url_carries_model_and_pcm_format():
    M = _imports()
    stream = M.handler.ElevenLabsDialogueStream(
        text="hi",
        api_key="k",
        voice_id="v",
        model_id="eleven_v3_conversational",
        output_format="pcm_16000",
    )
    assert stream._url.endswith("?model_id=eleven_v3_conversational&output_format=pcm_16000")
    assert "k" not in stream._url, "the API key must never be placed in the URL"


def test_opt_default_output_format_is_pcm_16000_and_needs_no_resampling():
    M = _imports()
    handler, _ = build(M.handler, frames=[])
    assert handler.output_format == "pcm_16000"
    assert M.handler.PIPELINE_SR == 16000


def test_opt_cleanup_is_idempotent_and_closes_the_active_stream():
    M = _imports()
    handler, stream = build(M.handler, frames=[b64(pcm(BLOCK, seed=16))])
    list(handler.process(tts_input(M.messages)))

    handler.cleanup()
    handler.cleanup()
    handler.on_session_end()
    assert stream.closed is True


def test_opt_closed_stream_does_not_silently_reconnect():
    M = _imports()
    stream = M.handler.ElevenLabsDialogueStream(text="hi", api_key="k", voice_id="v")
    stream.close()
    stream.close()  # idempotent

    with pytest.raises(M.handler.StreamEnded):
        stream.read(0.01)  # must not attempt a new connection


def test_opt_missing_key_fails_closed_without_network(monkeypatch):
    M = _imports()
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    handler = M.handler.ElevenLabsTTSHandler(
        Event(),
        Queue(),
        Queue(),
        setup_args=(Event(),),
        setup_kwargs={"api_key": None, "voice_id": "v", "stream_factory": None},
    )
    assert list(handler.process(tts_input(M.messages))) == []
