# RD1 V1 × Local GPU-less S2S — Final Integration Handoff

Date: 2026-09-27  
Task family: `RD1-V1-LOCAL-S2S-FINAL-CLOSURE-P0`

## 0. Executive Result

The real RD1 V1 product path is integrated with the local GPU-less Voice/S2S runtime and passed real-user voice validation.

```text
Electron / frontend
→ local Voice S2S :8765
→ ElevenLabs Scribe STT
→ Julia-AI-Assistant :18089
→ Julia Core
→ Julia cognition / canonical conversation
→ Assistant response
→ local Voice S2S
→ ElevenLabs TTS
→ Electron speaker
```

Final classification: functional integration PASS; real mic PASS; Scribe PASS; canonical binding PASS; RD1 response PASS; TTS first audio/complete PASS; real playback PASS; multi-turn PASS; barge-in PASS; stale audio NO; fallback/mock/synthetic success NO.## 1. Authority Model

```text
GitHub exact ref + exact SHA = durable engineering authority
Materialized runtime from exact SHA = executable recovery artifact
Running PID + cwd + PYTHONPATH + port + environment = runtime evidence
Tests / real E2E = validation evidence
Chat / Slack / prose = coordination only
```

GitHub remains canonical truth. A local worktree, detached checkout, temporary `/private/tmp` tree, process command line, or historical label may not silently replace an exact remote SHA.

## 2. Frozen Component Matrix

### Voice / S2S

```text
REPO = tonychang925-dev/Julia-Voice-S2S
BRANCH = voice-el-p1-hosted-product-integration
CODE_BASELINE_SHA = 9036aa4946a58d4fb32ab7b408a5c17ff3156319
PREVIOUS_BASE = 74f128e22822451bf439de95897ce08a7aea631d
PR = #1
PR_TITLE = Deliver accumulated GPU-less Voice product integration line
PR_BASE = main @ ad21dadf2a23b710c963a0507ef4874eecfe1020
PR_SCOPE = 104 commits / 94 files
PR_STATE_AT_FREEZE = OPEN / MERGEABLE
```The final TTS correction is one commit over `74f128e`, changing only:
```text
s2s/TTS/elevenlabs_tts_handler.py
tests/test_elevenlabs_tts_handler.py
```

### Assistant transport edge

```text
REPO = tonychang925-dev/Julia-AI-Assistant
BASE_MAIN = ec20d4f2be6db09cfb63c8340777dcb1c76e4921
INTEGRATION_BRANCH = rd1-v1-local-s2s-conversation-read-closure
INTEGRATION_SHA = 208a4d0d8ce2c0e6a34d01e63150ccf2b31011ca
PR = #67
PR_STATE_AT_FREEZE = OPEN / MERGEABLE
DELTA = 1 commit / 3 files / +119 -9
```

The Assistant candidate formalizes only canonical conversation read compatibility for Electron binding: list/get/messages through Core public read seam. Unsupported writes remain fail-closed.

### Core

```text
REPO = tonychang925-dev/Julia_core
CANONICAL_MAIN_SHA = b1406c6f2c4046c8b399bfd89f9288f1b10e173b
MATERIALIZED_RUNTIME = /private/tmp/rd1-v1-core-runtime-b1406c6
```Important identity rule:

```text
Assistant health may report: julia_core = frozen-865ffc4
This is a historical runtime/contract label.
It is NOT the current Git source SHA.
Do NOT resolve it as Git commit 865ffc4...
Current Core source provenance is b1406c6f2c4046c8b399bfd89f9288f1b10e173b.
```

### Electron

```text
PRODUCT_RUNTIME = /private/tmp/julia-voice-gpuless-0919-restore/electron-b2b4b3e
HISTORICAL_PRODUCT_SHA = b2b4b3ea7cbc6c9d45a75f37badd5731c760f55d
```

## 3. Current Exact Runtime Snapshot

Observed after exact-SHA restart on 2026-09-27:

```text
Assistant PID 20175
PORT = 127.0.0.1:18089
CWD = /private/tmp/rd1-v1-assistant-runtime-208a4d0
PYTHONPATH = /private/tmp/rd1-v1-assistant-runtime-208a4d0:/private/tmp/rd1-v1-core-runtime-b1406c6

Voice PID 20184
PORT = 127.0.0.1:8765
CWD = /private/tmp/rd1-v1-voice-runtime-9036aa4
PYTHONPATH = /private/tmp/rd1-v1-voice-runtime-9036aa4/release

Frontend PID 20244
PORT = 127.0.0.1:7860
CWD = /private/tmp/rd1-v1-voice-runtime-9036aa4/release/frontend

Electron PID 30863
CWD = /private/tmp/julia-voice-gpuless-0919-restore/electron-b2b4b3e
```

PIDs are observations only, never reusable authority.## 4. Canonical Conversation Authority

```text
CANONICAL_CONVERSATION_ID = rd1-v1-electron-voice-binding
STATE = active
MESSAGE_COUNT_AT_FREEZE = 52
LAST_TURN_ID_AT_FREEZE = turn_72e52217be2743e2b08205aa0d664b1b
```

Assistant health returned `status=ok`, contract version `1.0.0`; conversation list returned HTTP 200 after exact-SHA restart.

Canonical conversation belongs to Core. Voice session IDs, Scribe IDs, WebSocket IDs, and Electron media/session state are transport metadata only.

## 5. Voice Runtime Profile

```text
MODE = realtime
STT = elevenlabs-scribe
SCRIBE_LANGUAGE = zh
SCRIBE_MODEL = scribe_v2_realtime
SCRIBE_AUDIO = pcm_16000
SCRIBE_COMMIT_STRATEGY = manual
LLM_BACKEND = chat-completions
BRAIN = http://127.0.0.1:18089/v1
RESPONSES_STREAM = enabled
RESPONSES_WARMUP = disabled
TTS = elevenlabs
TTS_MODEL = eleven_v3_conversational
TTS_OUTPUT = pcm_16000
VAD = Silero / CPU
SMART_TURN = /Users/admin/.cache/julia_voice/models/smart-turn-v3.2-cpu.onnx
SMART_TURN_PROVIDER = CPUExecutionProvider
CUDA_VISIBLE_DEVICES = ""
AUTO_DL = NOT USED
REMOTE_GPU = NOT USED
FASTER_WHISPER_SELECTED = NO
```## 6. Runtime Environment Contract

Secret values must never be persisted.

```text
ELEVENLABS_API_KEY = PRESENT / VALUE REDACTED
ELEVENLABS_VOICE_ID = PRESENT / VALUE REDACTED
DEEPSEEK_API_KEY = PRESENT / VALUE REDACTED
HTTP_PROXY = http://127.0.0.1:7890
HTTPS_PROXY = http://127.0.0.1:7890
http_proxy = http://127.0.0.1:7890
https_proxy = http://127.0.0.1:7890
NO_PROXY = 127.0.0.1,localhost
no_proxy = 127.0.0.1,localhost
CUDA_VISIBLE_DEVICES = ""
NLTK_DATA = /Users/admin/.cache/julia_voice/nltk_data
```

Missing loopback proxy exclusions can create misleading Brain 502 failures. Missing provider-facing proxy settings can break hosted Scribe/TTS while local listeners remain healthy.

## 7. TTS Regression and Root-Cause Proof

Known-good 9/19 lifecycle:
```text
one utterance → create WebSocket → auth
→ inputs(new_turn=false) → close_socket=true
→ synchronously receive audio → close connection
```

Regressed lifecycle:
```text
persistent socket → new_turn=true → flush=true
→ keep_alive → background reader
```

A/B changed only the TTS lifecycle while preserving current RD1 integration. It produced `TTS_FIRST_AUDIO_RECEIVED=YES`, `TTS_COMPLETE=YES`, `provider_audio_bytes=268800`, `emitted_blocks=263`, `cancelled=false`, and real speaker playback.Final classification:
```text
ROOT_CAUSE_CLASS = TTS lifecycle regression
BROKEN = persistent ElevenLabs session implementation
KNOWN_GOOD = per-utterance one-shot WebSocket lifecycle
```

## 8. Formal Fix and Validation

```text
VOICE_BASE = 74f128e22822451bf439de95897ce08a7aea631d
VOICE_FIX = 9036aa4946a58d4fb32ab7b408a5c17ff3156319
DELTA = 1 commit / 2 files / +179 -346
```

Focused tests:
```text
test_elevenlabs_tts_handler.py = 26 passed
test_elevenlabs_integration.py = 7 passed
test_elevenlabs_wiring.py = 12 passed, 2 skipped
test_latency_observability.py = 10 passed
```

Assistant closure:
```text
BASE = ec20d4f2be6db09cfb63c8340777dcb1c76e4921
HEAD = 208a4d0d8ce2c0e6a34d01e63150ccf2b31011ca
test_rc3_rework.py = 6 passed
conversation list = HTTP 200
canonical binding = PASS
```

No authority moved into Assistant; it remains transport/session/presentation only.## 9. Deterministic Artifact and Byte Attestation

Voice exact artifact was built from `9036aa4` with the repository deterministic builder.

```text
ARTIFACT = /private/tmp/rd1-v1-voice-build-9036aa4/speech_to_speech-obs-9036aa4.tar.gz
ARTIFACT_SHA256 = 0304809948c5212e5092f9c7ab326baf97d8558a03dbb208f49e878850cad28b
RUNTIME = /private/tmp/rd1-v1-voice-runtime-9036aa4
TTS_HANDLER_SHA256 = 3dcc263d4d899521a70dfae17c881d92cc9c88202f660a978cc2ed94d41c87da
```

Runtime TTS handler and repository TTS handler are byte-identical.

## 10. Recovery / Restart Procedure

Mandatory order:
```text
1. Materialize Core exact SHA b1406c6
2. Materialize Assistant exact SHA 208a4d0
3. Start Assistant :18089
4. Verify health HTTP 200
5. Verify conversation list HTTP 200
6. Build/materialize Voice exact SHA 9036aa4
7. Start Voice :8765
8. Start frontend :7860 from same artifact
9. Start/reconnect Electron
10. Confirm canonical conversation binding
11. Run one real microphone turn
```

Never run from a dirty worktree when restoring the baseline.## 11. Ownership Boundaries

```text
Voice S2S = audio transport/runtime only
Assistant = transport/session/serialization/presentation only
Core = cognition/final judgment/canonical conversation authority
Electron = product UI/media transport/playback
```

Forbidden: Voice direct cognition, Voice-side persona/memory authority, Voice-side canonical history, Assistant final-answer fallback, hidden fallback, mock/synthetic PASS. Golden Mira/persona migration remains a separate experiment.

## 12. Local / Remote Consistency Gate

```text
Voice code baseline = 9036aa4946a58d4fb32ab7b408a5c17ff3156319
Voice local/remote branch heads = MUST MATCH at restore time
Voice tracked code diff after baseline fix = clean
Voice protected untracked = docs/voice-el-p1-node2/

Assistant local integration head = 208a4d0d8ce2c0e6a34d01e63150ccf2b31011ca
Assistant remote integration head = 208a4d0d8ce2c0e6a34d01e63150ccf2b31011ca
Core canonical remote main = b1406c6f2c4046c8b399bfd89f9288f1b10e173b

Runtime Voice = exact 9036aa4 deterministic artifact
Runtime Assistant = exact 208a4d0 materialized tree
Runtime Core = exact b1406c6 materialized tree
```

After this documentation is committed, the Voice branch head may advance by docs-only commit(s). Runtime code authority remains CODE_BASELINE_SHA=9036aa4. Any future restore must verify the local branch head equals its remote tracking head and fail closed if these identities cannot be reconstructed or explicitly superseded.

## 13. Protected Evidence and Stop Boundary

`docs/voice-el-p1-node2/` is pre-existing protected evidence. Do not delete, clean, stage, relocate, or silently absorb it.

Not authorized by this handoff: persistent-TTS redesign, latency optimization, provider replacement, VAD/Smart Turn/Scribe authority changes, Voice-side memory/persona, second conversation authority, or Golden Mira production admission.

## 14. Final Handoff State

```text
FUNCTIONAL_INTEGRATION = PASS
VOICE_TTS_REGRESSION = FIXED
CANONICAL_BINDING = PASS
LOCAL_REMOTE_RUNTIME_PROVENANCE = ALIGNED
REAL_PRODUCT_PATH = PASS
VOICE_PR = #1 OPEN / MERGEABLE
ASSISTANT_PR = #67 OPEN / MERGEABLE
```

Next action is review/merge according to Owner governance. Do not reopen technical diagnosis without contradictory evidence.
