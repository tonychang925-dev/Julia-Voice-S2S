# Julia Voice GPU-less × RD1 V1 — Canonical Runtime Baseline Freeze

Freeze date: 2026-09-27  
Baseline ID: `JULIA-VOICE-GPULESS-RD1-V1-BASELINE-20260927`

## 1. Purpose

This is the mechanical recovery baseline for the validated local GPU-less Voice path integrated with RD1 V1.

It prevents runtime drift, ambiguous restore instructions, and reconstruction from similarly named historical labels.

The baseline is valid only when exact source identity, runtime provenance, environment prerequisites, listener topology, canonical conversation binding, and real-user validation agree.

## 2. Canonical Source Identity

### Voice
```text
repo = tonychang925-dev/Julia-Voice-S2S
branch = voice-el-p1-hosted-product-integration
code_baseline_sha = 9036aa4946a58d4fb32ab7b408a5c17ff3156319
previous_sha = 74f128e22822451bf439de95897ce08a7aea631d
formal_tts_fix = 9036aa4946a58d4fb32ab7b408a5c17ff3156319
remote_pr = #1
```

### Assistant
```text
repo = tonychang925-dev/Julia-AI-Assistant
main_base = ec20d4f2be6db09cfb63c8340777dcb1c76e4921
integration_branch = rd1-v1-local-s2s-conversation-read-closure
integration_sha = 208a4d0d8ce2c0e6a34d01e63150ccf2b31011ca
remote_pr = #67
```### Core
```text
repo = tonychang925-dev/Julia_core
canonical_main_sha = b1406c6f2c4046c8b399bfd89f9288f1b10e173b
runtime_path = /private/tmp/rd1-v1-core-runtime-b1406c6
```

### Electron
```text
historical_product_runtime = /private/tmp/julia-voice-gpuless-0919-restore/electron-b2b4b3e
historical_product_sha = b2b4b3ea7cbc6c9d45a75f37badd5731c760f55d
```

## 3. Critical Identity Warning

```text
"frozen-865ffc4" ≠ Git SHA authority
```

Assistant health currently reports `julia_core=frozen-865ffc4`. Treat this only as a historical contract/runtime label.

Current Core source authority:
```text
b1406c6f2c4046c8b399bfd89f9288f1b10e173b
```

Never reconstruct Core by running `git archive 865ffc4` merely because the health label contains that string.## 4. Deterministic Voice Artifact

Repository-owned build:
```bash
python3 scripts/build_s2s_release.py \
  /private/tmp/rd1-v1-voice-build-9036aa4 \
  --experiment \
  --commit 9036aa4946a58d4fb32ab7b408a5c17ff3156319
```

Frozen artifact:
```text
/private/tmp/rd1-v1-voice-build-9036aa4/speech_to_speech-obs-9036aa4.tar.gz
SHA256 = 0304809948c5212e5092f9c7ab326baf97d8558a03dbb208f49e878850cad28b
```

Extracted runtime:
```text
/private/tmp/rd1-v1-voice-runtime-9036aa4
PYTHONPATH=/private/tmp/rd1-v1-voice-runtime-9036aa4/release
```

TTS handler attestation:
```text
runtime = .../release/speech_to_speech/TTS/elevenlabs_tts_handler.py
repository = s2s/TTS/elevenlabs_tts_handler.py
SHA256 = 3dcc263d4d899521a70dfae17c881d92cc9c88202f660a978cc2ed94d41c87da
```

Runtime and repository handler bytes are identical.## 5. Runtime Listener Topology

```text
Electron
  ↓
frontend :7860
  ↓
Voice S2S :8765
  ↓
Assistant :18089
  ↓
Core
```

Observed exact-runtime processes at freeze:
```text
Assistant PID 20175 → 127.0.0.1:18089
Voice PID 20184     → 127.0.0.1:8765
Frontend PID 20244  → 127.0.0.1:7860
Electron PID 30863
```

PIDs are evidence only.

## 6. Exact Runtime Roots

```text
Assistant CWD = /private/tmp/rd1-v1-assistant-runtime-208a4d0
Assistant PYTHONPATH =
  /private/tmp/rd1-v1-assistant-runtime-208a4d0:
  /private/tmp/rd1-v1-core-runtime-b1406c6

Voice CWD = /private/tmp/rd1-v1-voice-runtime-9036aa4
Voice PYTHONPATH = /private/tmp/rd1-v1-voice-runtime-9036aa4/release

Frontend CWD = /private/tmp/rd1-v1-voice-runtime-9036aa4/release/frontend

Electron CWD = /private/tmp/julia-voice-gpuless-0919-restore/electron-b2b4b3e
```## 7. Voice Launch Profile

```text
--mode realtime
--ws_host 127.0.0.1
--ws_port 8765
--stt elevenlabs-scribe
--elevenlabs_scribe_language_code zh
--no_enable_live_transcription
--llm_backend chat-completions
--model_name baseline
--responses_api_base_url http://127.0.0.1:18089/v1
--responses_api_stream
--no_responses_api_warmup_enabled
--tts elevenlabs
--elevenlabs_model_id eleven_v3_conversational
--elevenlabs_output_format pcm_16000
--thresh 0.6
--min_speech_ms 500
--min_speech_continuation_ms 192
--min_silence_ms 800
--speech_pad_ms 300
--speculative_reopen_ms 2500
--short_segment_merge_ms 800
--smart_turn_model_path /Users/admin/.cache/julia_voice/models/smart-turn-v3.2-cpu.onnx
```## 8. Provider / Compute Profile

```text
STT = ElevenLabs Scribe Realtime
STT model = scribe_v2_realtime
STT audio = pcm_16000
STT language = zh
commit strategy = manual

TTS = ElevenLabs
TTS model = eleven_v3_conversational
TTS output = pcm_16000
TTS lifecycle = one WebSocket per utterance

Silero = CPU
Smart Turn = CPU ONNX
CUDA required = NO
remote GPU = NO
AutoDL = NO
faster-whisper selected = NO
ctranslate2 selected = NO
```

## 9. Required Environment Contract

Secrets:
```text
ELEVENLABS_API_KEY = required / never persist value
ELEVENLABS_VOICE_ID = required / never persist value
DEEPSEEK_API_KEY = required / never persist value
```

Network:
```text
HTTP_PROXY=http://127.0.0.1:7890
HTTPS_PROXY=http://127.0.0.1:7890
http_proxy=http://127.0.0.1:7890
https_proxy=http://127.0.0.1:7890
NO_PROXY=127.0.0.1,localhost
no_proxy=127.0.0.1,localhost
```

Compute: `CUDA_VISIBLE_DEVICES=""`; `NLTK_DATA=/Users/admin/.cache/julia_voice/nltk_data`.## 10. TTS Baseline Contract

Accepted:
```text
for each utterance:
  create provider WebSocket
  authenticate / initialize
  send inputs with new_turn=false
  request close_socket=true
  synchronously consume provider audio
  complete utterance
  close provider WebSocket
```

Forbidden unless a new task re-proves it:
```text
session-level persistent TTS socket
new_turn=true persistent-session flow
flush=true persistent-session flow
background TTS receive task
TTS keepalive loop
cross-utterance provider session reuse
```

Reason: the persistent implementation produced a real regression where the request was sent but no valid provider audio reached playback. A/B restoration of the one-shot lifecycle restored real speaker output.

## 11. Canonical Conversation Gate

Electron-hosted Voice requires canonical conversation binding before S2S start.

Required gates:
```text
GET /internal/v1/voice/health → HTTP 200
GET /internal/v1/conversations → HTTP 200
```

Frozen conversation:
```text
conversation_id = rd1-v1-electron-voice-binding
state = active
message_count_at_freeze = 52
last_turn_id_at_freeze = turn_72e52217be2743e2b08205aa0d664b1b
```Do not bypass canonical binding with Voice-local history or a synthetic conversation.

## 12. Assistant Read Compatibility Contract

Electron requires historical response shapes for list conversation, get conversation, and get messages.

Assistant candidate:
```text
208a4d0d8ce2c0e6a34d01e63150ccf2b31011ca
```

delegates those reads to Core public ingress. Unsupported writes remain fail-closed.

Validation:
```text
tests/test_rc3_rework.py = 6 passed
conversation list = HTTP 200
canonical binding = PASS
```

## 13. Voice Fix Validation

```text
tests/test_elevenlabs_tts_handler.py = 26 passed
tests/test_elevenlabs_integration.py = 7 passed
tests/test_elevenlabs_wiring.py = 12 passed, 2 skipped
tests/test_latency_observability.py = 10 passed

real microphone = PASS
Scribe transcript = PASS
canonical binding = PASS
RD1 response = PASS
TTS first audio = PASS
TTS complete = PASS
real speaker = PASS
multi-turn = PASS
barge-in = PASS
stale audio = NO
```## 14. Restore SOP

### A — Verify remote authority

Before starting:
```text
Voice code baseline = 9036aa4946a58d4fb32ab7b408a5c17ff3156319
Assistant integration = 208a4d0d8ce2c0e6a34d01e63150ccf2b31011ca
Core main = b1406c6f2c4046c8b399bfd89f9288f1b10e173b
```

If refs moved, reconcile explicitly.

### B — Materialize exact objects

```text
Core b1406c6 → /private/tmp/rd1-v1-core-runtime-b1406c6
Assistant 208a4d0 → /private/tmp/rd1-v1-assistant-runtime-208a4d0
Voice 9036aa4 deterministic build → /private/tmp/rd1-v1-voice-runtime-9036aa4
```

Do not run a dirty source worktree.

### C — Start in order

```text
1. Assistant + Core composition :18089
2. verify health
3. verify conversation list
4. Voice :8765
5. frontend :7860
6. Electron
7. verify canonical binding
8. one real mic turn
```

### D — Fail closed

Stop if health/listener/binding/env/provenance cannot be proven.## 15. Local / Remote Parity Gate

Voice code baseline:
```text
local and remote code-fix identity = 9036aa4946a58d4fb32ab7b408a5c17ff3156319
tracked code diff after fix = clean
protected untracked evidence = docs/voice-el-p1-node2/
```

Assistant:
```text
local branch = rd1-v1-local-s2s-conversation-read-closure
local head = 208a4d0d8ce2c0e6a34d01e63150ccf2b31011ca
remote branch head = 208a4d0d8ce2c0e6a34d01e63150ccf2b31011ca
```

Core:
```text
remote main / runtime source = b1406c6f2c4046c8b399bfd89f9288f1b10e173b
```

Runtime:
```text
Assistant = exact 208a4d0 materialized tree
Core = exact b1406c6 materialized tree
Voice = exact deterministic 9036aa4 artifact
Frontend = same 9036aa4 artifact
```

After this documentation is committed, the Voice branch head may advance by docs-only commit(s). Runtime code authority remains `CODE_BASELINE_SHA=9036aa4`. Always verify local branch head equals its remote tracking head at restore time.## 16. Protected Evidence

```text
/Users/admin/glm-workspace/Julia-Voice-S2S/docs/voice-el-p1-node2/
```

Classification: PRE-EXISTING PROTECTED EVIDENCE.

Do not delete, reset, clean, stage, rename, or use as an implicit dependency.

## 17. Stop Boundary

Not authorized by this freeze:
```text
TTS persistent-session redesign
latency optimization
provider replacement
VAD semantic changes
Smart Turn semantic changes
Scribe authority changes
Assistant cognition
Voice-side memory/persona
second conversation authority
Golden Mira production admission
```

Any future task starts from this exact baseline or explicitly supersedes it with new GitHub authority and real evidence.
