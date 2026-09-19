# Julia Voice GPU-less G2: ElevenLabs Scribe Realtime

## Identity

- Task: `JULIA-VOICE-GPULESS-G2-ELEVENLABS-SCRIBE-REALTIME`
- Base: `f0e3cadc7a8cc428c43f620625a8a5c2bb56ad1d`
- Branch: `voice-el-p1-hosted-product-integration`
- Selector: `elevenlabs-scribe`
- Model: `scribe_v2_realtime`
- Audio: `pcm_16000`
- Commit strategy: `manual`
- Default language profile: `zh`
- New dependencies: none

## Boundary

Scribe is selected through `create_stt_provider()` and implements the existing
`BaseSTTHandler` queue contract. Julia VAD/Smart Turn remains the sole turn
authority. A Julia `mode="final"` item sends the final PCM chunk with
`commit=true`. `partial_transcript` maps to `PartialTranscription`, and only
`committed_transcript` maps to final `Transcription`. Existing
speculative-turn filtering continues to reject stale provider output.

`faster_whisper` and `ctranslate2` are not imported on the selected Scribe
path. The provider locally converts float PCM to clipped signed little-endian
PCM16 at 16 kHz mono. ElevenLabs session IDs are metadata only and never become
Julia turn or conversation IDs.

## Validation

- New provider tests: 8 passed
- G1 boundary tests: 3 passed
- ElevenLabs TTS regression: 25 passed
- Targeted combined suite: 36 passed
- Full suite: 113 passed, 2 skipped, 5 pre-existing failures
- The five failures were reproduced identically at the frozen G2 base in an
  isolated worktree and are unrelated LLM observability expectations.

With `CUDA_VISIBLE_DEVICES=""`, real provider-handler smoke testing established:

- WebSocket handshake: pass
- `session_started`: received
- Audio upload: pass
- Manual commit: pass
- `committed_transcript`: received
- `turn_id=g2-smoke-turn` preserved
- `turn_revision=0` preserved
- `faster_whisper` imported: no
- `ctranslate2` imported: no
- Raw committed transcript: `我刚才看了一下这个问题。我-`

The bounded 2.5-second Mandarin smoke sample was local, temporary evidence and
is not retained as a benchmark corpus. The displayed text is raw provider
output, not a quality judgment.
