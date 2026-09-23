# RD1 V1 / R3 Canonical Baseline and Handoff Freeze — 2026-09-23

## Scope and Result

This document freezes the canonical RD1 V1 and R3 engineering baseline for handoff. It separates durable GitHub authority from timestamped runtime observations, transient active worktrees, and historical evidence. No production, test, runtime configuration, or historical evidence is changed by this handoff.

Task identifier: `RD1-V1-R3-CANONICAL-BASELINE-AND-HANDOFF-FREEZE-P0`

## A. Authority Model

```text
GitHub refs + exact SHA
= CANONICAL ENGINEERING TRUTH

Local checkout / worktree
= TRANSIENT OBSERVATION

Tests passed
≠ architecture authority

Remote object exists
≠ authorized remote ref
≠ accepted recovery source
```

Only an exact remote ref and SHA establish the current authorized baseline. A local branch, detached HEAD, temporary runtime process, test result, or unmerged remote object may not silently substitute for that authority. A passing result can validate a tested revision, but it cannot rewrite ownership boundaries or create a new canonical lineage.

## B. Canonical Repository Baseline

Live GitHub refs were independently verified before editing. No drift from the expected issuance SHAs was detected.

| Repository | Canonical ref | Exact live SHA | Verification timestamp (UTC) | Role in RD1 V1 |
| --- | --- | --- | --- | --- |
| `tonychang925-dev/Julia_core` | `main` | `289514558728712e8c73f6b904a5aefb75d636f7` | `2026-09-23T10:54:36Z` | Cognition / final judgment authority |
| `tonychang925-dev/Julia-AI-Assistant` | `main` | `ec20d4f2be6db09cfb63c8340777dcb1c76e4921` | `2026-09-23T10:54:36Z` | Transport / session / presentation edge |
| `tonychang925-dev/ai_theme_app` | `main` | `d65225394184fe83124471f1a3e61a01a67bd2f3` | `2026-09-23T10:54:36Z` | Market domain semantics / public Market capability provider |
| `tonychang925-dev/Julia-Voice-S2S` | `voice-el-p1-hosted-product-integration` | `ed8b19121ecca44e2dda24d218e51a9470b42a65` | `2026-09-23T10:54:36Z` | Voice transport/runtime implementation |

The live remote refs are rechecked immediately before final delivery. Any later remote drift does not retroactively alter the SHAs frozen above; a new task must explicitly reconcile and supersede this document.

## C. Local-Remote Baseline Reconciliation Result

### Core

Historical stale state:

```text
old local main
= 6b815cf3df58e6bfd3906b61ba5f918f11ef35c7

intermediate canonical main
= 872ee25d6d7fe7a8d845cf675ba824a87aad85a6

later canonical main
= cb507e6e96eeb2730b74e5587e5d638c450a6453
```

Current live `main` at documentation time is `289514558728712e8c73f6b904a5aefb75d636f7`.

```text
Core local main had no unique local commits.
Reconciliation was fast-forward only.
No active worktree checkout was intentionally changed by reconciliation.
```

The transient active Core checkout changed during the audit. That checkout movement is a local observation only and must not be treated as canonical Core authority or as evidence that an architecture decision changed.

### Assistant

Reconciled `main` baseline:

```text
old local main
= 1309b1d18a86346480d5196533d3245840d1ff24

canonical main
= ec20d4f2be6db09cfb63c8340777dcb1c76e4921

LOCAL_UNIQUE_COMMITS = 0
RECONCILIATION = FAST_FORWARD
```

Historical R3 branch:

```text
JULIA-VOICE-R3-P2B-BRAIN-CONVERSATION-MANAGEMENT-ADAPTER-WIRING

HEAD
= 9f1d8de4650b2c573fb13b726afc97007bb6c8c9

CLASSIFICATION
= HISTORICAL_R3_EVIDENCE
```

Required disposition:

```text
PRESERVE
DO NOT DELETE
NOT CURRENT_RUNTIME_AUTHORITY
NO UPSTREAM AT AUDIT TIME
```

The branch remains evidence of the historical R3 work. Absence of an upstream is a provenance observation, not authorization to delete, rewrite, merge, or promote it.

### Market

```text
canonical SHA
= d65225394184fe83124471f1a3e61a01a67bd2f3

detached HEAD by itself
≠ baseline defect

Exact canonical object match
= acceptable
```

A detached local checkout is not canonical, but exact object identity with the canonical remote `main` SHA is an acceptable local observation.

### Voice

```text
branch
= voice-el-p1-hosted-product-integration

canonical SHA
= ed8b19121ecca44e2dda24d218e51a9470b42a65

REMOTE_MATCH = YES
EXPECTED_DIRTY_STATE = PRESERVED
```

The expected pre-existing local dirty/untracked state consists only of:

```text
M  s2s/TTS/elevenlabs_tts_handler.py
M  tests/test_elevenlabs_tts_handler.py
?? docs/voice-el-p1-node2/
```

That state belongs to separate in-progress TTS work and is not staged, modified, committed, cleaned, reset, or otherwise consumed by this documentation freeze.

## R3 Accepted Voice Lineage

The accepted R3 sequence is:

```text
9a68d91ca7b6890ba66d62df66e74f2aa9baee0f
→ a60369221079c1bfc26d2e15d0e78364605cc43d
→ 954f389660408cec7b10d03434ebe488b08fb7a5
→ 21d63f07cfb98b615456aa2b992803ad7d1c688f
→ 29d83e0e85a300d68c295d95c3b1b649dd1d269b
→ 9e3d9b3961f3d9c45d7a0c229d11fe389b997b02
→ db4d5fa21674215d5015da9493f15097b7599b0d
→ ed8b19121ecca44e2dda24d218e51a9470b42a65
```

Required lineage interpretation:

- `954f389` — TTS connection/session reuse.
- `21d63f0` — input-path latency observability.
- `29d83e0` — Scribe connection prewarm.
- `db4d5fa` — Electron playback completeness fix.
- `ed8b191` — R3 known-good consolidation baseline.

Commits preceding `954f389` remain part of the preserved accepted lineage. The R3 authority is the exact sequence ending at `ed8b19121ecca44e2dda24d218e51a9470b42a65`, not merely a set of object names.

## Accepted R3 Technical Results

The following are accepted historical measurements and validation results. This handoff does not create new measurements or merge observations into fabricated summary statistics.

### Scribe Prewarm

```text
SMART_TURN_TO_SCRIBE_COMMIT
before median ≈ 2579.917 ms
after median ≈ 8.623 ms

LAST_SPEECH_TO_BRAIN_REQUEST
before median ≈ 4486.909 ms
after median ≈ 868.197 ms
```

Exact-runtime validation separately observed approximately:

```text
LAST_SPEECH_TO_BRAIN_REQUEST
≈ 557.967 ms
```

A later playback-validation sample separately observed approximately:

```text
≈ 480.363 ms
```

The 557.967 ms and 480.363 ms observations remain distinct samples and must not be combined with each other or with the earlier median into one new statistic.

### Playback Completeness

Root cause:

```text
RESPONSE_DONE_BEFORE_QUEUE_DRAIN
```

Accepted invariant:

```text
response.done
+ playback queue drained
+ no stale-generation cancellation
→ response-finished
```

Accepted validation result:

```text
10 valid real-user turns
incomplete audio = 0
playback complete = 10
```

Startup prebuffer remains:

```text
0 ms
```

No production 400 ms jitter-buffer policy was accepted.

### TTS

```text
TTS connection/session reuse
= ACCEPTED
```

The currently dirty TTS multi-stream/context-id work is not part of the accepted baseline. It is separate active work and has no authority over the frozen R3 result unless a future task explicitly reviews, accepts, and lands it.

## Current GPU-less Voice Topology

Known-good architecture:

```text
Electron / local frontend
→ local Voice S2S :8765
  - local VAD / Smart Turn
  - ElevenLabs Scribe STT
  - ElevenLabs TTS
→ local Julia-AI-Assistant / Brain :18089
→ Julia Core
→ configured external LLM/provider
```

Operational meaning:

```text
AutoDL GPU server
= NOT REQUIRED FOR CURRENT VOICE DEFAULT PATH

SSH tunnel
= NOT REQUIRED FOR CURRENT VOICE DEFAULT PATH

GPU-less
≠ fully local AI
```

Hosted external providers remain possible and may remain required depending on the selected configuration. “GPU-less” describes removal of the GPU server from the default path, not removal of external AI services.

## RD1 V1 Voice Adoption Boundary

This section is documentation only and must not be implemented as part of this handoff.

Target architectural direction:

```text
Mic / Electron
→ local Voice S2S :8765
→ Julia-AI-Assistant :18089
→ JuliaCoreAdapter
→ julia_core.public.CoreConversationIngress
→ Julia cognition
```

Required ownership boundaries:

```text
Voice S2S
= audio transport/runtime only

Julia-AI-Assistant
= transport/session/presentation only

Julia Core
= cognition/final judgment authority

Market
= Market domain semantics authority
```

Forbidden future shortcuts:

```text
Voice direct LLM cognition
Assistant direct final-answer LLM fallback
Voice-side persona authority
Voice-side memory authority
Voice-side second conversation-history authority
hidden fallback
synthetic success
```

Any proposed implementation must preserve these boundaries and receive explicit task authorization. Tests may not be made to pass by adding hidden fallback behavior, synthetic success, or a competing authority.

## Local Runtime Snapshot Policy

```text
CANONICAL_BASELINE
= durable GitHub ref + exact SHA

LOCAL_RUNTIME_SNAPSHOT
= timestamped observation only

ACTIVE_WORKTREE
= transient and non-authoritative
```

HISTORICAL_EVIDENCE is also distinct from current authority: it may explain why a decision exists, but it cannot silently become the current runtime baseline.

A local branch, detached HEAD, or currently running process must never silently replace the canonical project baseline. Runtime snapshots must identify repository, ref/commit, process/port, timestamp, environment, and provenance, and must be compared against the exact canonical SHA before use.

## Historical Worktrees

```text
parallel / historical worktrees
= PROTECTED

prunable metadata observed
= NOT AUTHORIZED FOR CLEANUP

UNCERTAINTY
→ KEEP
```

Observed prunable metadata is not a cleanup request. No worktree cleanup, pruning, deletion, reset, or removal recommendation from this task may be executed. If ownership is uncertain, preserve the worktree and its evidence.

## Freeze Disposition

- GitHub is the canonical engineering truth.
- The four remote baselines above are explicit and exact.
- Local runtime and active worktree state are transient observations.
- Accepted R3 lineage, measurements, and validation results are preserved.
- The RD1 V1 adoption boundary is documented only.
- Production code, tests, runtime configuration, and historical evidence are unchanged.
