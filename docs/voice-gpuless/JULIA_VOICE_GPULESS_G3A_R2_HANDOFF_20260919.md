# Julia Voice GPU-less G3-A R2 Handoff

Date: 2026-09-19

## 2026-09-23 R3 Known-Good Consolidation Checkpoint

This section is the current canonical new-agent entry point. It supersedes the
older source tuples and next-step boundaries below. Do not restart optimization
or create a replacement branch from this checkpoint; first preserve the runtime
and source identity recorded here.

### Frozen Source Identity

```text
REPO_FULL_NAME
= tonychang925-dev/Julia-Voice-S2S

WORKTREE_PATH
= /Users/admin/glm-workspace/Julia-Voice-S2S

BRANCH
= voice-el-p1-hosted-product-integration

VOICE_ACTIVE_HEAD
= db4d5fa21674215d5015da9493f15097b7599b0d

REMOTE_HEAD_SHA
= db4d5fa21674215d5015da9493f15097b7599b0d

REMOTE_HEAD_VERIFIED
= YES

NEW_BRANCH_CREATED
= NO
```

The branch relationship from the accepted Scribe prewarm base to the playback
candidate is intentionally two commits, not one:

```text
29d83e0e85a300d68c295d95c3b1b649dd1d269b
  ↓
9e3d9b3961f3d9c45d7a0c229d11fe389b997b02
  ↓
db4d5fa21674215d5015da9493f15097b7599b0d
```

Ancestry classification:

```text
ACTIVE_LINE_ADVANCE_FROM_29D83E0
= 2 COMMITS

INTERVENING_DOC_COMMIT
= PRESENT

INTERVENING_DOC_SHA
= 9e3d9b3961f3d9c45d7a0c229d11fe389b997b02

INTERVENING_DOC_MESSAGE
= Update GPU-less Voice handoff baseline

INTERVENING_DOC_PARENT
= 29d83e0e85a300d68c295d95c3b1b649dd1d269b

INTERVENING_DOC_SCOPE
= docs/voice-gpuless/JULIA_VOICE_GPULESS_G3A_R2_HANDOFF_20260919.md only

INTERVENING_DOC_PROVENANCE
= owner-requested documentation/handoff continuation

PLAYBACK_FIX_COMMIT
= db4d5fa21674215d5015da9493f15097b7599b0d

PLAYBACK_FIX_SCOPE
= frontend playback/client files plus focused test only

ACTIVE_LINE_ANCESTRY_CLEANLINESS
= RESOLVED
```

There is no missing merge parent, rebase, reset, or replacement ref. The
apparent ancestry anomaly is solely the legitimate docs-only handoff commit
between the accepted input-path base and playback fix. Do not rewrite this
history.

### Accepted Active-Line History

```text
a603692  fix latency observability perf_counter reference
954f389  Reuse ElevenLabs TTS session connections
21d63f0  Complete input path latency observability
29d83e0  Prewarm ElevenLabs Scribe connections
9e3d9b3  Update GPU-less Voice handoff baseline
db4d5fa  Gate response completion on playback drain
```

Current accepted outcomes:

```text
TTS_SESSION_CONNECTION_REUSE
= ACCEPTED at 954f389

INPUT_PATH_OBSERVABILITY
= ACCEPTED at 21d63f0

SCRIBE_CONNECTION_PREWARM
= ACCEPTED at 29d83e0

PLAYBACK_COMPLETION_GATING
= ACCEPTED at db4d5fa
```

### Playback Completion Freeze

Root cause and fix:

```text
ROOT_CAUSE_CLASS
= RESPONSE_DONE_BEFORE_QUEUE_DRAIN

ROOT_CAUSE
= response.done arrived while audio remained queued; the old client emitted response-finished immediately, exited ai-speaking, and a later user-speech reset could clear the remaining valid audio.

FIX
= response-finished now waits for worklet playback-complete, cancellation, or socket closure.

ROOT_CAUSE_CONFIDENCE
= HIGH
```

Acceptance evidence:

```text
VALID_REAL_USER_TURNS
= 10

INCOMPLETE_AUDIO_TURNS
= 0

PLAYBACK_COMPLETE_TURNS
= 10

INPUT_LATENCY_REGRESSION
= NO

LATEST_INPUT_LAST_SPEECH_TO_BRAIN_REQUEST
≈ 480.363ms
```

Final drain-gate accounting:

```text
PROVIDER_AUDIO_BYTES
= 596480

VOICE_AUDIO_BYTES_SENT
= 596992

ELECTRON_AUDIO_BYTES_RECEIVED
= 596992

WORKLET_AUDIO_BYTES_QUEUED
= 596992

WORKLET_AUDIO_BYTES_PLAYED
= 596992

PROVIDER_TO_VOICE_DIFFERENCE
= deterministic 512-byte output-block padding

DROPPED_BYTES
= 0

PLAYBACK_COMPLETE_AFTER_RESPONSE_DONE
≈ 14.475 seconds
```

Playback policy boundary:

```text
JITTER_BUFFER_POLICY_CHANGED
= NO

SOURCE_STARTUP_PREBUFFER
= 0ms

400MS_DIAGNOSTIC_PREBUFFER
= evidence-only; not production policy

PRODUCTION_ADAPTIVE_BUFFER_IMPLEMENTATION
= NOT AUTHORIZED
```

Regression result:

```text
node --test frontend/tests/playback-completeness.test.js
= 7 passed

tests/test_elevenlabs_scribe_stt.py
tests/test_latency_observability.py
= 28 passed
```

The wider frontend suite previously had two unrelated, pre-existing
conversation-binding source assertions failing. They are not playback
regressions and must not be silently mixed into a future playback task.

### Frozen Runtime Tuple

Loopback listeners verified after consolidation:

```text
VOICE_PROCESS
= PID 50304, 127.0.0.1:8765

VOICE_RUNTIME_SOURCE_BASE
= 29d83e0e85a300d68c295d95c3b1b649dd1d269b

VOICE_RUNTIME_INTERPRETER
= /opt/miniconda3/envs/julia_voice_gpuless/bin/python

VOICE_RUNTIME_ARGUMENTS
= realtime; ElevenLabs Scribe zh; chat-completions via local Brain; ElevenLabs TTS; local CPU Smart Turn

BRAIN_PROCESS
= PID 79987, 127.0.0.1:18089

FRONTEND_PROCESS
= PID 10741, 127.0.0.1:7860

PLAYBACK_DIAGNOSTIC_COLLECTOR
= PID 21837, 127.0.0.1:7861

AUTODL
= OUT_OF_SCOPE

SSH_TUNNEL
= OUT_OF_SCOPE

RD1_V1
= PROTECTED
```

The Voice process was started before the docs and frontend commits. That is
not a semantic mismatch for this checkpoint because neither intervening commit
changes Voice Python code. The Electron page was refreshed to load the playback
candidate without replacing the profile. Do not restart these services merely
because a new task begins.

Required proxy discipline remains:

```text
NO_PROXY
= includes 127.0.0.1,localhost

no_proxy
= includes 127.0.0.1,localhost

EXTERNAL_PROXY_ENV
= preserve when the selected VPN/proxy route is required
```

The owner observed transient external proxy instability during handoff. One
remote verification attempt failed through unavailable local proxy port 7890;
a retry verified the exact remote HEAD successfully. Local Brain/Voice traffic
must continue bypassing that proxy.

### Evidence Locations

```text
PLAYBACK_EVIDENCE
= /private/tmp/julia_playback_diagnostic.jsonl

PLAYBACK_FINAL_DRAIN_GATE_WINDOW
≈ lines 5017–5199

PLAYBACK_9_RESPONSE_WINDOW
≈ lines 2279–4850

VOICE_LOG
= /private/tmp/julia-voice-scribe-prewarm.log

LATENCY_SINK
= /var/folders/n3/v97n1r5j2l79b7gwkq1c87t80000gn/T/julia-voice-latency-events.jsonl
```

These are runtime-local evidence paths, not permanent authority stores. Copy
the bytes or preserve the Mac session before relying on them for later dispute
resolution.

### Uncommitted Leftovers

The canonical source state is `db4d5fa`, but the working tree intentionally
still contains unrelated material:

```text
s2s/TTS/elevenlabs_tts_handler.py
tests/test_elevenlabs_tts_handler.py
= uncommitted ElevenLabs multi-stream/context-id candidate work

docs/voice-el-p1-node2/
= pre-existing untracked evidence archive
```

Do not describe these as part of the accepted playback commit. Do not delete,
stage, commit, or roll them back without a separate owner-authorized task. A
future TTS task must first mechanically audit the dirty diff and decide whether
to preserve, test, or discard it.

### Current Stop Boundary

```text
R3_PLAYBACK_COMPLETENESS
= ACCEPTED

NEXT_WORK
= consolidation/read-only verification only unless Owner authorizes a new task

LATENCY_OPTIMIZATION
= NOT AUTHORIZED

PRODUCTION_JITTER_BUFFER
= NOT AUTHORIZED

VAD / SMART_TURN / SCRIBE / BRAIN / CORE CHANGES
= NOT AUTHORIZED
```

## 2026-09-21 R3 Latency Baseline Freeze

This section supersedes the older source/checklist SHA statements below for
continuation. Preserve the historical G3-A R2 evidence, but start new Voice
latency work from the tuple in this section.

### Frozen Source Identity

```text
REPO_FULL_NAME
= tonychang925-dev/Julia-Voice-S2S

WORKTREE_PATH
= /Users/admin/glm-workspace/Julia-Voice-S2S

BRANCH
= voice-el-p1-hosted-product-integration

LOCAL_HEAD_SHA
= a60369221079c1bfc26d2e15d0e78364605cc43d

REMOTE_HEAD_SHA
= a60369221079c1bfc26d2e15d0e78364605cc43d

BASE_SHA
= 9a68d91ca7b6890ba66d62df66e74f2aa9baee0f

CANDIDATE_COMMIT
= a603692 fix latency observability perf_counter reference

REMOTE_HEAD_VERIFIED
= YES
```

The branch progression is:

```text
f06d514
  ↓
9a68d91  end-to-end latency observability
  ↓
a603692  fix latency observability perf_counter reference
```

Do not create a new branch, new runtime, or second authority path merely
because a new agent/task begins. Continue sequentially on this active branch.

### Frozen Runtime Prerequisites

These are mandatory before any Electron/UI testing:

```text
CUDA_VISIBLE_DEVICES
= ""

NO_PROXY
= 127.0.0.1,localhost

no_proxy
= 127.0.0.1,localhost

ELEVENLABS_API_KEY
= REQUIRED, VALUE REDACTED

AUTODL
= OUT OF SCOPE
```

The known-good restore order remains:

```text
Brain :18089
  ↓
Voice/S2S :8765
  ↓
frontend :7860
  ↓
Electron
```

Do not click through Electron to diagnose a missing backend. First prove the
listener/topology, binding, and proxy exclusions. Stop if `:8765` has no
listener.

### Frozen Composition

```text
BRAIN_WORKTREE
= /private/tmp/g3a-r2-brain-bbd90af

BRAIN_SHA
= bbd90af42ba659684c25f1e9473c24804364548c

BRAIN_ENDPOINT
= http://127.0.0.1:18089

JULIA_CORE
= frozen-865ffc4

VOICE
= a60369221079c1bfc26d2e15d0e78364605cc43d

S2S
= http://127.0.0.1:8765

FRONTEND
= http://127.0.0.1:7860

ELECTRON_PRODUCT_SHA
= b2b4b3ea7cbc6c9d45a75f37badd5731c760f55d

CANONICAL_CONVERSATION
= conv_d26511ce35074798b8fe2dd1e57aa855
```

The current Electron profile is bound to the canonical conversation above.
Do not replace it with an isolated/unbound profile for latency continuation.

### Environment Root Causes Closed

Two earlier “voice completely dead” symptoms were runtime-environment
prerequisites, not latency/architecture regressions:

```text
FAULT_A
= ELEVENLABS_API_KEY missing
→ Scribe/TTS provider unavailable

FAULT_B
= NO_PROXY/no_proxy missing
→ Python/OpenAI SDK routed loopback Brain through 127.0.0.1:7890
→ Brain request returned HTTP 502
```

Also closed:

```text
9a68d91 input-not-recognized
= VAD instrumentation called undefined perf_counter_ns()
= fixed by time.perf_counter_ns() in a603692
```

The regression is covered by
`tests/test_latency_observability.py::test_vad_instrumentation_executes_before_audio_dispatch`.

### Measured Baseline Status

One successful natural-voice turn was measured on the frozen composition:

```text
SPEECH_END_TO_FIRST_AUDIO
= 3.51s

TTS_TTFA
= 1.474s

SPEECH_END_TO_TTS_COMPLETE
= 4.19s
```

Classification:

```text
LOCAL_VOICE_CHAIN
= PASS

VOICE_OBSERVABILITY
= WORKING

CURRENT_FIRST_AUDIO_SAMPLE
= 3.51s

LATENCY_OPTIMIZATION
= NOT STARTED
```

An earlier approximately 5.1s observation is not proof of a code optimization.
Runtime conditions, provider variation, and utterance shape can change a
single-turn result. Do not claim an optimization until the planned 20-turn
corpus reports median/p90/p95 and the changed segment is isolated.

## 2026-09-23 R3 Input-Path / Scribe-Prewarm Baseline Freeze

This section supersedes the older “collect 20 turns before optimization”
continuation instruction above. That corpus was interrupted by a mechanical
progressive-TTS/playback investigation and then deliberately split into
separate input-path and output/playback tasks. Start new input-path work from
the tuple and measurements in this section.

### Frozen Source Identity

```text
REPO_FULL_NAME
= tonychang925-dev/Julia-Voice-S2S

WORKTREE_PATH
= /Users/admin/glm-workspace/Julia-Voice-S2S

BRANCH
= voice-el-p1-hosted-product-integration

VOICE_BASE_SHA
= 21d63f07cfb98b615456aa2b992803ad7d1c688f

VOICE_CANDIDATE_SHA
= 29d83e0e85a300d68c295d95c3b1b649dd1d269b

REMOTE_HEAD_SHA
= 29d83e0e85a300d68c295d95c3b1b649dd1d269b

REMOTE_HEAD_VERIFIED
= YES
```

Sequential branch progression:

```text
a603692  fix latency observability perf_counter reference
  ↓
954f389  Reuse ElevenLabs TTS session connections
  ↓
21d63f0  Complete input path latency observability
  ↓
29d83e0  Prewarm ElevenLabs Scribe connections
```

Do not create a replacement Voice branch, reset to `f06d514`, or reopen a
second latency line. A new bug or a new agent does not justify a new branch;
continue sequentially on this active branch.

### Problem Decomposition Before The Fix

The original complaint, “speech is recognized but the assistant takes too long
to begin responding,” was not treated as one opaque latency number. The accepted
structured latency sink exposed this input sequence:

```text
INPUT_LAST_SPEECH_FRAME
→ VAD_SOFT_END
→ SMART_TURN_DECISION_COMPLETE
→ SCRIBE_CONNECTION_START
→ SCRIBE_CONNECTION_READY
→ SCRIBE_COMMIT_SENT
→ SCRIBE_FINAL_RECEIVED
→ BRAIN_REQUEST_SENT
```

The five-turn real-user baseline established:

```text
LAST_SPEECH_TO_BRAIN_REQUEST
median = 4486.909ms
p90    = 5695.513ms
max    = 5702.557ms

SMART_TURN_TO_SCRIBE_COMMIT
median = 2579.917ms
p90    = 4000.022ms
max    = 4201.643ms

SCRIBE_COMMIT_TO_FINAL
median = 1507.839ms
```

Scribe connection establishment was measured separately from transcription:

```text
SCRIBE_CONNECTION_START_TO_READY
= [5427.481, 1070.483, 2796.651, 1504.852, 2806.864] ms
```

Root-cause conclusion:

```text
SCRIBE_CONNECTION_ESTABLISHMENT
= post-speech/blocking dependency

PRIMARY_INPUT_BOTTLENECK
= waiting for a Scribe connection that could have overlapped active speech
```

The Scribe finalization wait itself was not changed in this task.

### Implemented Solution

The fix is limited to Scribe connection lifecycle timing:

```text
IMPLEMENTATION
= s2s/STT/elevenlabs_scribe_handler.py

TRIGGER
= first progressive VAD audio / speech activity

NEW_SEQUENCE
speech starts
→ Scribe connection starts in background
→ progressive speech continues
→ connection becomes ready while speech may still be active
→ speech ends
→ manual commit no longer waits for initial connection establishment
```

Preserved semantics:

```text
COMMIT_POLICY_CHANGED
= NO

TRANSCRIPT_SEMANTICS_CHANGED
= NO

VAD_POLICY_CHANGED
= NO

SMART_TURN_POLICY_CHANGED
= NO

BRAIN_DISPATCH_POLICY_CHANGED
= NO
```

Early audio is preserved as the latest cumulative audio representation. The
adapter does not lose, reorder, or duplicate speech because the provider
handshake overlaps speech. Connections remain revision-scoped; a reopen or
revision transition invalidates stale in-flight connection state so a new
revision cannot inherit stale transcript/audio. Provider connection failure
remains fail-closed: no fabricated transcript, hidden provider fallback, or
same-revision retry loop.

### Testing Process

Focused regression command:

```bash
CUDA_VISIBLE_DEVICES="" \
NO_PROXY=127.0.0.1,localhost \
no_proxy=127.0.0.1,localhost \
/opt/miniconda3/envs/julia_voice_gpuless/bin/python -m pytest \
  tests/test_elevenlabs_scribe_stt.py \
  tests/test_latency_observability.py
```

Focused result:

```text
28 passed
```

Mechanical coverage included: speech-triggered prewarm, overlap with
progressive speech, early-audio preservation, no duplication/reordering,
revision invalidation, no stale-revision inheritance, unchanged commit/final
transcript semantics, fail-closed provider failure, and preserved observability.

Git checks:

```text
git diff --check
= PASS

NEW_BRANCH_CREATED
= NO

MERGE
= NO

REBASE
= NO

FORCE_PUSH
= NO
```

The broader ElevenLabs wiring/integration suite still has a pre-existing local
`nltk.data` attribute failure. It was not fixed or hidden in this task. Compare
future failures against the authorized base before changing code.

### Runtime Environment Incident And Correction

An intermediate Voice restart accidentally preserved
`ELEVENLABS_API_KEY` and loopback `NO_PROXY` but omitted the external proxy
variables. This made Scribe/TTS attempt direct provider connections and caused
the owner-visible “not recognized / connecting” regression. It was not caused by
the Scribe prewarm design.

Measured WebSocket behavior:

```text
DIRECT_ELEVENLABS_WS
≈ 2.27s

LOCAL_PROXY_ELEVENLABS_WS
≈ 0.74s
```

Required provider-facing runtime environment:

```text
ELEVENLABS_API_KEY
= PRESENT, VALUE REDACTED

HTTP_PROXY
= http://127.0.0.1:7890

HTTPS_PROXY
= http://127.0.0.1:7890

http_proxy / https_proxy
= matching lowercase values

NO_PROXY
= 127.0.0.1,localhost

no_proxy
= 127.0.0.1,localhost
```

The uppercase/lowercase distinction matters because different Python/SDK layers
read different variables. Local Brain/Voice/frontend traffic must still bypass
the proxy; ElevenLabs provider traffic uses the proxy. Never diagnose this as
an AutoDL or architecture issue.

### Real-User Candidate Corpus

Seven valid post-proxy natural Chinese turns were recovered from the structured
sink, including reopen-heavy revisions:

```text
VALID_POST_PROXY_TURNS
= 7

SCRIBE_READY_BEFORE_LAST_SPEECH
= 4/7
= majority

SCRIBE_CONNECTION_START_TO_READY
median = 747.279ms
p90    = 1944.886ms
max    = 1944.886ms

SMART_TURN_TO_SCRIBE_COMMIT
median = 8.623ms
p90    = 487.701ms
max    = 487.701ms

LAST_SPEECH_TO_COMMIT
median = 332.779ms
p90    = 855.134ms
max    = 855.134ms

SCRIBE_COMMIT_TO_FINAL
median = 586.548ms
p90    = 1635.431ms
max    = 1635.431ms

LAST_SPEECH_TO_BRAIN_REQUEST
median = 868.197ms
p90    = 2506.332ms
max    = 2506.332ms
```

Baseline-to-candidate reductions:

```text
SMART_TURN_TO_SCRIBE_COMMIT
2579.917ms → 8.623ms
median reduction ≈ 99.7%

LAST_SPEECH_TO_BRAIN_REQUEST
4486.909ms → 868.197ms
median reduction ≈ 80.6%
```

The non-ready minority cases were reopen-heavy revisions, where a late reopen
legitimately forced a new revision-scoped connection. They did not reproduce the
original synchronous post-speech establishment blocker. `SCRIBE_COMMIT_TO_FINAL`
is expected to remain substantially provider-bound and was not optimized here.

### Exact-Commit Runtime Acceptance

Voice was restarted once, Voice-only, to load the exact pushed candidate:

```text
RUNTIME_VOICE_PID
= 50304

RUNTIME_VOICE_SHA
= 29d83e0e85a300d68c295d95c3b1b649dd1d269b

LISTENER
= 127.0.0.1:8765

BRAIN / FRONTEND / ELECTRON_PROFILE
= unchanged
```

One additional natural Chinese turn was then measured on the exact commit:

```text
VALID_TURNS
= 1

SCRIBE_READY_BEFORE_LAST_SPEECH
= YES

SCRIBE_CONNECTION_START_TO_READY
= 724.285ms

SMART_TURN_TO_SCRIBE_COMMIT
= 4.988ms

LAST_SPEECH_TO_COMMIT
= 243.048ms

SCRIBE_COMMIT_TO_FINAL
= 300.039ms

LAST_SPEECH_TO_BRAIN_REQUEST
= 557.967ms
```

The owner separately confirmed that perceived input latency was “much better.”

### Current Frozen Result

```text
TASK_ID
= JULIA-VOICE-R3-SCRIBE-CONNECTION-PREWARM-OPTIMIZATION-P1

VOICE_SHA
= 29d83e0e85a300d68c295d95c3b1b649dd1d269b

REMOTE_HEAD_VERIFIED
= YES

INPUT_PATH_ACCEPTANCE
= PASS

SCRIBE_CONNECTION_OVERLAP
= PASS

EARLY_AUDIO_PRESERVATION
= PASS

REVISION_ISOLATION
= PASS

TRANSCRIPT_CORRECTNESS_REGRESSION
= NO

REOPEN_CORRECTNESS
= PASS
```

Structured evidence sink at acceptance:

```text
/var/folders/n3/v97n1r5j2l79b7gwkq1c87t80000gn/T/julia-voice-latency-events.jsonl
```

The useful candidate window starts at `2026-09-22T14:12:53Z`; exact-commit
verification starts after `2026-09-22T14:26:16Z`. The temporary sink path is
runtime-local and not a permanent authority store. Preserve copied evidence or
the report values above before terminating the Mac session if later dispute
resolution is required.

### Separately Tracked Output/Playback Facts

Do not mix these with Scribe prewarm:

```text
TTS_CONNECTION_REUSE
= previously accepted on this same branch

PROVIDER_CHUNK_DELIVERY_JITTER
= observed

ZERO_STARTUP_BUFFER_STARVATION
= mechanically confirmed

400MS_DIAGNOSTIC_PREBUFFER
= strongly supported, not accepted as production policy
```

One response did not play completely, while Voice-side evidence showed full TTS
completion with `cancelled=false`. That remains an Electron playback/output
issue. No production Electron jitter-buffer policy or TTS change was authorized
or implemented as part of the Scribe prewarm commit.

### Historical Next Authorized Step

Keep the same branch, topology, Electron profile, Brain/Core tuple, and
environment. Collect at least 20 natural voice turns and decompose every turn
through:

```text
T0/T1  speech end / VAD
T2/T3  turn decision/finalization
T5     Scribe final
T6/T7  Brain request
T8     provider request
T9S    complete LLM response
T10    first TTS text ready
T11    TTS request
T12    first TTS audio
T13    enqueue
T14    playback
```

Report median, p90, and p95 before selecting an optimization target. Current
candidate areas are STT/finalization wait, serial Brain-complete-to-TTS
architecture, and ElevenLabs TTFA. Do not alter TTS, buffering, VAD, turn
semantics, provider authority, Brain, or Core while collecting the baseline.

### Regression Gate

```bash
NO_PROXY=127.0.0.1,localhost \
no_proxy=127.0.0.1,localhost \
/opt/miniconda3/envs/julia_voice_gpuless/bin/python \
-m pytest tests/test_latency_observability.py
```

Frozen result at `a603692`:

```text
5 passed
```

This document is the authoritative new-window handoff for the GPU-less Julia
Voice work completed through G3-A R2. It records the current source identity,
runtime topology, completed gates, live troubleshooting conclusions, known
quality issue, and the next authorized boundary.

## Current Source Identity

```text
REPO_FULL_NAME
= tonychang925-dev/Julia-Voice-S2S

WORKTREE_PATH
= /Users/admin/glm-workspace/Julia-Voice-S2S

BRANCH
= voice-el-p1-hosted-product-integration

LOCAL_HEAD_SHA
= f06d51477538ea21ec5b611bdef93c77bf3deba7

REMOTE_HEAD_SHA
= f06d51477538ea21ec5b611bdef93c77bf3deba7

TRACKED_DIFF
= clean

WORKTREE_NOISE
= pre-existing untracked docs/voice-el-p1-node2/
```

The remote branch was last verified through the GitHub API after the E2E run.
The untracked `docs/voice-el-p1-node2/` directory predates the GPU-less work
and contains evidence archives/ledgers; do not delete it as part of a future
task unless separately authorized.

## Completed Delivery Chain

The branch contains the following sequence from the frozen G1 base:

```text
4c55d75  frozen G1 architecture base
f0e3cad  G1 STT provider boundary
a8a5e52  G2 ElevenLabs Scribe realtime provider
ff98880  G2-R1 cumulative audio delta correction
a410373  G3-A R2-P1 realtime Scribe argument wiring
708fc76  G3-A R2-P2 Scribe argument normalization
f06d514  G3-A R2-P3 non-semantic Brain startup readiness
```

## Architecture And Design Process

### Final Runtime Shape

```text
Mac microphone
    ↓
Electron / Julia_client media path
    ↓
local Julia Voice :8765
    ↓
Silero VAD
    ↓
Smart Turn CPU ONNX
    ↓
STT provider boundary
    ├── faster-whisper (preserved selected-path provider)
    └── ElevenLabs Scribe Realtime
    ↓
Julia transcription identity / speculative filtering
    ↓
chat-completions Brain :18089
    ↓
canonical Julia Core conversation
    ↓
ElevenLabs TTS
    ↓
Electron speaker playback
```

Provider replacement is allowed; authority transfer is not. Scribe owns only
`audio → transcript`. Julia VAD/Smart Turn, turn IDs, revisions, cancellation,
speculative filtering, and canonical conversation binding remain authoritative.

### G1 Design Process

The frozen orchestration previously selected STT handlers through direct
provider branching. That made each GPU-less STT replacement an orchestration
change and gave no mechanical boundary at which to prove non-Whisper import
isolation.

Design sequence:

1. Define the already-used runtime contract as `STTProvider`, rather than
   invent a second async STT framework:
   `setup()`, `process(VADAudio)`, `cleanup()`.
2. Preserve `BaseSTTHandler` queue behavior because it already carries Julia
   cancellation and speculative-turn semantics.
3. Move selected-handler dispatch behind `create_stt_provider()`.
4. Preserve the validated Node-2 `faster-whisper large-v3` profile and all
   existing provider selectors.
5. Make `faster_whisper` and `ctranslate2` imports selected-path-only so a
   non-Whisper path can be mechanically guarded.

Rejected alternatives:

- adding a cloud provider branch directly in `s2s_pipeline.py`;
- changing VAD or turn-finalization semantics;
- replacing queue lifecycle with provider callbacks;
- removing faster-whisper or changing the existing production default.

This turned G2 into an additive provider implementation rather than another
orchestration redesign.

### G2 Scribe Design Process

The selected endpoint and protocol are:

```text
wss://api.elevenlabs.io/v1/speech-to-text/realtime
model_id = scribe_v2_realtime
audio_format = pcm_16000
commit_strategy = manual
```

`ElevenLabsScribeSTTHandler` implements the G1 provider contract. Julia's
`VADAudio.mode="final"` is the only signal translated into explicit manual
commit.

Event mapping:

```text
session_started       → provider session ready; no Julia semantic completion
partial_transcript    → PartialTranscription only
committed_transcript  → final Transcription only
warning/rate_limit/error/close → typed provider failure or lifecycle handling
```

Identity mapping:

```text
Scribe session_id      → provider metadata only
Scribe segment identity → never canonical Julia identity
turn_id/turn_revision  → copied from input to every provider output
```

Float PCM is converted locally to clipped signed little-endian PCM16, 16 kHz,
mono. The global frontend/media representation is unchanged. No SDK or new
dependency was introduced; existing `websockets` and `numpy` support sufficed.

Rejected alternatives:

- using Scribe VAD as Julia turn authority;
- treating `partial_transcript` as final text;
- exposing the API key to Electron/browser;
- adding Scribe-specific orchestration branching;
- using ElevenLabs IDs as Julia IDs.

### G2-R1 Cumulative Audio Design Process

Julia VAD emits cumulative candidates per revision:

```text
progressive-1 = A
progressive-2 = A+B
progressive-3 = A+B+C
final         = A+B+C+D
```

Sending each array wholesale would duplicate samples. The provider-local model
is therefore:

```text
active_revision_key = (turn_id, turn_revision)
sent_sample_count   = samples already sent for this revision
delta               = audio[sent_sample_count:]
```

When the revision changes, `sent_sample_count` resets to zero because revision
1 is a new complete semantic candidate, not a continuation of revision 0.

For a final frame with no unsent suffix, the adapter sends the real-provider
verified empty `input_audio_chunk` with `commit=true`. It never resends the
whole cumulative buffer merely to attach commit.

Rejected alternatives:

- changing VAD cumulative semantics;
- inferring revision identity from Scribe session IDs;
- sharing sample position across revisions;
- allowing provider completion to override Julia authority.

### G3-A Startup Repair Design Process

Real startup exposed three narrow defects:

1. **P1 realtime builder wiring**: `_build_realtime_pipeline_unit()` required
   Scribe handler arguments, but the realtime call omitted them. The fix
   forwarded the existing argument object without adding orchestration logic.
2. **P2 argument normalization**: pipeline fields were prefixed while handler
   setup expected normalized fields. The fix reused the existing
   `rename_args(..., "elevenlabs_scribe")` architecture instead of teaching
   setup two naming schemes.
3. **P3 semantic warmup**: generic Chat Completions warmup sent a semantic
   request without canonical conversation identity. Brain routed it through
   the legacy compatibility path and returned HTTP 502. Startup readiness now
   remains non-semantic; real turn failures remain real.

The invariant across all three fixes was that Brain/Core authority and
canonical history must not be weakened or fabricated to make startup pass.

### Local Proxy And Runtime Design Decision

The apparent Brain/DeepSeek failure was initially ambiguous because `curl`
succeeded while Python/OpenAI SDK traffic failed. Evidence separated the layers:

```text
DeepSeek /models               = HTTP 200
DeepSeek non-streaming probe   = HTTP 200
DeepSeek streaming probe       = HTTP 200
Brain via SDK with proxy       = HTTP 502
Brain via SDK with loopback excluded from proxy = HTTP 200
```

macOS had configured `127.0.0.1:7890` as an HTTP proxy. Python/OpenAI SDK sent
loopback Brain calls through that proxy; when the proxy was unavailable, the
result looked like a Brain 502.

The architecture rule for this Mac runtime is that localhost calls explicitly
exclude proxy resolution. This is not a source change and does not justify
restoring legacy DeepSeek or moving Brain off localhost.

### Real E2E Validation Design

Final acceptance used the real product path, not synthetic-only proof:

```text
real microphone
→ Electron/browser audio worklet
→ local Voice WebSocket
→ local Silero and Smart Turn CPU
→ cloud Scribe
→ local Brain/Core
→ cloud TTS
→ real speaker playback
```

It validated four dimensions independently:

1. committed STT transcript and identity preservation;
2. canonical Brain/Core conversation binding;
3. barge-in cancellation and stale-audio discard;
4. CPU VAD/Smart Turn with no Whisper/CUDA dependency.

The observed stutter is retained as evidence for a future latency diagnostic,
not converted into a G4 accuracy conclusion or authorization to redesign TTS.

### G1 Result

```text
STT_PROVIDER_BOUNDARY
= PASS

DEFAULT_PROVIDER_CHANGED_BY_G1
= NO

UNCONDITIONAL_FASTER_WHISPER_IMPORTS_IN_ORCHESTRATION
= 0

UNCONDITIONAL_WHISPER_MODEL_INITIALIZATIONS_IN_ORCHESTRATION
= 0
```

The validated existing Node-2 profile remains `faster-whisper` plus
`large-v3`. G1 did not replace it. Provider dispatch moved behind
`create_stt_provider()`, with `faster-whisper` retained as a selected-path
provider.

### G2 Result

```text
SELECTOR
= elevenlabs-scribe

MODEL
= scribe_v2_realtime

AUDIO_FORMAT
= pcm_16000

COMMIT_STRATEGY
= manual

NEW_DEPENDENCIES
= NONE

FACTORY_PATH
= PASS

PARTIAL_TRANSCRIPT_MAPPING
= PASS

COMMITTED_TRANSCRIPT_MAPPING
= PASS

MANUAL_COMMIT
= PASS

STALE_TRANSCRIPT_FILTERING
= PASS

RESULT
= G2_SCRIBE_REALTIME_PROVIDER_PASS
```

Scribe is only an STT provider. Julia VAD/Smart Turn remains authoritative for
turn start/finalization, `turn_id`, `turn_revision`, cancellation, speculative
filtering, and canonical conversation identity.

### G2-R1 Cumulative Audio Result

Julia's VAD continues to emit cumulative audio. The Scribe adapter tracks the
number of samples already sent independently for each
`(turn_id, turn_revision)` and sends only the unsent suffix. A reopened
revision starts a fresh provider-local stream and receives the full complete
candidate for that revision.

```text
CUMULATIVE_AUDIO_DELTA_TRACKING
= PASS

DUPLICATED_AUDIO_SAMPLES
= 0

ZERO_DELTA_FINAL_COMMIT
= PASS

REVISION_RESET
= PASS

SPECULATIVE_REOPEN_FULL_REVISION_AUDIO
= PASS

STALE_REVISION_FILTERING
= PASS

RESULT
= G2_R1_SCRIBE_AUDIO_SEMANTICS_PASS
```

When the final cumulative frame has no unsent audio, the adapter sends the
provider-valid empty `input_audio_chunk` frame with `commit=true`; it does not
resend the accumulated audio merely to trigger commit.

## Runtime Environment

```text
ENV
= /opt/miniconda3/envs/julia_voice_gpuless

PYTHON
= 3.12.11

NLTK_DATA
= /Users/admin/.cache/julia_voice/nltk_data

SMART_TURN_MODEL
= /Users/admin/.cache/julia_voice/models/smart-turn-v3.2-cpu.onnx

SMART_TURN_PROVIDER
= CPUExecutionProvider

SILERO
= local cache, CPU execution

CUDA_VISIBLE_DEVICES
= ""
```

The disposable source copy used for the final E2E run was:

```text
/private/tmp/g3a-r2-resume-runtime
```

All test runtime processes were stopped after evidence collection:

```text
Electron
= stopped

Voice :8765
= stopped

Frontend :7860
= stopped
```

Do not assume any process is still running. Brain is a separate service and may
still be managed independently.

## Local Brain/Core Identity

```text
BRAIN_REPO
= tonychang925-dev/Julia-AI-Assistant

BRAIN_SHA
= bbd90af42ba659684c25f1e9473c24804364548c

BRAIN_ENDPOINT
= http://127.0.0.1:18089

CONTRACT_VERSION
= 1.0.0

JULIA_CORE
= frozen-865ffc4
```

Health, Core connectivity, canonical routing, and real request generation were
validated during E2E. Do not start `baseline_llm.py` or any replacement Brain.

## Critical Network Finding

The apparent DeepSeek/Brain 502 was not an API-key or quota failure. DeepSeek
model, non-streaming, and streaming probes all returned HTTP 200.

macOS had a system HTTP proxy configured at:

```text
127.0.0.1:7890
```

Python/httpx/OpenAI SDK honored that setting for loopback Brain requests while
some `curl` probes did not. When the local proxy was unavailable, the Brain
request was forwarded to the proxy and returned an empty HTTP 502.

The required runtime-only correction is:

```bash
export NO_PROXY=127.0.0.1,localhost
export no_proxy=127.0.0.1,localhost
```

Keep these variables in the local Voice runtime environment. This was not a
source change.

Also verify the Electron-cached Brain endpoint remains:

```text
127.0.0.1:18089
```

It was accidentally changed to `127.0.0.1:8765` during UI troubleshooting and
then restored. That was a local settings mistake, not a repository regression.

## G3-A R2 Real Product E2E

Final result:

```text
RESULT
= G3A_MAC_REAL_PRODUCT_E2E_PASS
```

Effective profile:

```text
MODE
= realtime

STT
= elevenlabs-scribe

TTS
= elevenlabs

LLM_BACKEND
= chat-completions

RESPONSES_API_WARMUP_ENABLED
= false

VAD
= existing Silero CPU path

SMART_TURN
= existing CPU ONNX path
```

Canonical conversation:

```text
CANONICAL_CONVERSATION_ID
= conv_15e973cafd834d5584471ad8e00b3722
```

Representative required turns:

```text
TURN_ID
= turn_d78d60697bf5491fbbd021d17d9eb6b8
TURN_REVISION
= 0
TRANSCRIPT
= 你现在能听到我声音吗？

TURN_ID
= turn_c43fb6ec32cc4e80860421de05a95ff2
TURN_REVISION
= 1
TRANSCRIPT
= 我能，我能听到你的声音。

TURN_ID
= turn_1828562395e64e9ba48d68b91cad8e85
TURN_REVISION
= 2
TRANSCRIPT
= 请检查 Julia Core、Websocket 和 conversation ID。
```

Each completed Scribe commit, Brain HTTP 200, LLM completion, ElevenLabs TTS,
and audible playback. The final canonical snapshot remained bound to the
intended conversation:

```text
MESSAGE_DELTA
= +23

TURN_DELTA
= +12

DUPLICATE_TURN_IDS
= 0

DUPLICATE_MESSAGE_IDS
= 0

PHANTOM_CONVERSATIONS
= 0
```

Barge-in was successful:

```text
OLD_TTS_CANCELLED
= YES

STALE_AUDIO_DROPPED
= YES

NEW_TURN_ACCEPTED
= YES

DUPLICATE_BRAIN_SEMANTIC_TURN
= NO
```

## GPU-Less Gate

```text
CUDA_REQUIRED
= NO

CUDA_CONTEXT_CREATED
= NO

FASTER_WHISPER_IMPORTED
= NO

CTRANSLATE2_IMPORTED
= NO

WHISPER_MODEL_INITIALIZED
= NO

REMOTE_GPU_SERVER_REQUIRED
= NO
```

This proves the selected Julia Voice STT/product path does not require NVIDIA
or CUDA infrastructure. It does not claim the full runtime is PyTorch-free,
VPS-portable, or that Scribe Chinese accuracy is superior; those are separate
G3+/G4 questions.

## Current Known Quality Issue

The owner confirmed:

- microphone recognition is accurate;
- barge-in works;
- Julia's returned speech is severely stuttery/laggy.

Mechanical incidents observed during E2E included:

- one Scribe committed-transcript timeout;
- one Scribe connect timeout;
- one ElevenLabs TTS `keepalive ping timeout` after roughly 51 seconds;
- several long TTS elapsed times.

These are provider/network latency observations, not architecture failures and
not accuracy-benchmark conclusions. The current architecture authority and
turn semantics passed.

A future diagnostic task should instrument and distinguish at least:

1. Brain first-token latency;
2. ElevenLabs TTS time-to-first-audio;
3. TTS chunk arrival jitter;
4. browser playback underruns;
5. proxy/routing effects on provider WebSocket streams;
6. TTS model/output format and whether generation is truly chunk-streamed.

Do not silently change TTS model, buffering, provider, or turn authority as
part of a latency fix without a new task and explicit scope.

## Regression Commands

The relevant targeted test files are:

```text
tests/test_stt_provider_boundary.py
tests/test_elevenlabs_scribe_stt.py
tests/test_elevenlabs_wiring.py
tests/test_elevenlabs_integration.py
tests/test_elevenlabs_tts_handler.py
tests/test_chat_completions_warmup.py
```

Use the isolated runtime interpreter:

```bash
CUDA_VISIBLE_DEVICES="" \
NO_PROXY=127.0.0.1,localhost \
no_proxy=127.0.0.1,localhost \
/opt/miniconda3/envs/julia_voice_gpuless/bin/python -m pytest \
  tests/test_stt_provider_boundary.py \
  tests/test_elevenlabs_scribe_stt.py \
  tests/test_elevenlabs_wiring.py \
  tests/test_elevenlabs_integration.py \
  tests/test_elevenlabs_tts_handler.py \
  tests/test_chat_completions_warmup.py
```

The historical unrelated LLM observability failures were mechanically compared
to the frozen G1 base and established as pre-existing. Future suites should
still report failure names and compare against the current authorized base
rather than treating prose as proof.

## New-Window Startup Checklist

1. Verify local and remote HEAD are both `f06d514`.
2. Verify the tracked diff is clean and only the documented untracked evidence
   directory is present.
3. Confirm Brain at `127.0.0.1:18089`, contract `1.0.0`, and Core
   `frozen-865ffc4`.
4. Start the isolated Julia environment with `CUDA_VISIBLE_DEVICES=""` and
   loopback proxy exclusions.
5. Explicitly select realtime mode, `elevenlabs-scribe`, ElevenLabs TTS, and
   chat-completions; do not enable Mac defaults that override Scribe.
6. Confirm Smart Turn uses the explicit local CPU ONNX model.
7. Confirm Scribe model `scribe_v2_realtime`, `pcm_16000`, language `zh`, and
   manual commit.
8. Verify Electron's Brain endpoint is `127.0.0.1:18089` and its canonical
   conversation is the intended existing conversation.
9. Run only the newly authorized diagnostic/validation scope.

## Stop Boundary

G3-A R2 is complete. Do not begin any of the following without a new task and
architecture review:

```text
G3-B Linux/VPS migration
G4 Chinese STT benchmark
G5 cloud migration
full-runtime PyTorch removal
provider authority redesign
TTS replacement or streaming redesign
```

## Canonical Continuation

This R3 historical handoff remains valid as historical evidence. The current
cross-project canonical continuation is
`docs/rd1/RD1_V1_R3_CANONICAL_BASELINE_HANDOFF_2026-09-23.md`.
