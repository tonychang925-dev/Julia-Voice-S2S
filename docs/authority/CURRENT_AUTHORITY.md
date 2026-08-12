# Julia-Voice-S2S Current Authority

STATUS: CANONICAL
UPDATED: 2026-08-11
REPOSITORY: Julia-Voice-S2S
ROLE: Voice/S2S runtime, AutoDL production release, observability, production supervisor/watchdog
AUTHORITATIVE BRANCH: phase5/rmd-3g-observability
AUTHORITY-DOCUMENT HEAD AT CLOSEOUT: 09373281c6e8342c0728f4c2be54f4c94b9178f4 plus later metadata-only successors

## Current production/development status

- RMD-3G C1 normal voice recovery is production-effective.
- AutoDL S2S is supervised by dedicated supervisord and watchdog.
- Manual `python launch_s2s.py` startup is no longer production authority.

## Source, artifact, launcher, and document authority

These roles are deliberately separate. REPO HEAD is not automatically SOURCE AUTHORITY, ARTIFACT AUTHORITY, DEPLOYMENT AUTHORITY, or LIVE RUNTIME AUTHORITY.

- AUTHORITY-DOCUMENT HEAD: `09373281c6e8342c0728f4c2be54f4c94b9178f4` plus later metadata-only successors.
- C1 PRODUCTION SOURCE AUTHORITY: `1552470f3f8f4e33a9cb90181daa1353f0702eb2`.
- C1 PRODUCTION ARTIFACT AUTHORITY: `b18d1e42ca2e1383829b6d5f0670652efa066944ba92823a815a35253291c9ac`.
- CANONICAL LAUNCHER AUTHORITY: `90077d209cafcc428e9cb29498e75414973bbac9`, later superseded operationally by supervisor/watchdog commits through `09373281...`.
- INTERMEDIATE OPS COMMIT: `a5a90803794cdc7e8dd3b3ead534801c7f7bf85b` is historical/intermediate documentation commit, not C1 production source authority and not artifact authority.

C1 source authority:

- `1552470f3f8f4e33a9cb90181daa1353f0702eb2`

C1 artifact authority:

- artifact SHA256: `b18d1e42ca2e1383829b6d5f0670652efa066944ba92823a815a35253291c9ac`
- manifest SHA256: `3137878712a0bf689fc9e381f8c1ab081512abdaea89dfedcd9106e65f2869c1`
- production release: `/root/julia_voice_v2/releases/rmd3g-c1-b18d1e42`

Critical runtime file hashes:

- base handler = `2f904a05128d5b11c92e6a2bd04769cd12c6e06f3a66e7d23dbb09b7eb34004c`
- chat handler = `725db87b6313a2cc601173be751ea8bca258eb2c601450ac4a0e273f92acb621`
- websocket router = `12769ece09b8da10f6ea7be06064cb37dc58d8a41026d8d47bfe1d6ecd0c033c`

Historical failed candidates:

- `5f343195...` / `3a2feaf7...` = HISTORICAL RMD-3G LIVE FAILED CANDIDATE, not production authority.

## CC-1-C2 production E2E failure and source remediation

STATUS: SOURCE REMEDIATION DEPLOYED / SEMANTIC CONTINUITY STILL FAILING

Production evidence superseded the prior CC-1 source IV&V conclusion because the review did not cover the active Voice frontend receiver.

Failure root cause:

- Electron sent `julia.voice.conversation.bind`.
- Active Voice frontend only handled legacy `julia.voice.workspace.bootstrap` / `flush`.
- Therefore canonical `conversation_id` did not cross Electron → Voice → S2S.

C2 source authority:

- Voice C2 code commit: `e44de36f96e270532e3c734a43d0a0317e0ec11c`
- Active receiver: `frontend/main.js` handles `julia.voice.conversation.bind` and ACKs `julia.voice.conversation.bound`.
- S2S transport: `S2sWsRealtimeClient` receives the active canonical `conversationId`.
- Old workspace bootstrap/flush are legacy compatibility only and must not seed semantic history.

Production evidence after C2 deployment:

- C2 frontend bind/ACK path deployed.
- Voice media path remains functional.
- Text → Voice semantic continuity still fails: real Voice turns do not appear under canonical Core conversation `conv_20260810_215104_4415455312`.
- Direct Brain top-level `conversation_id` probe reaches CRT and persists under the canonical conversation, so the remaining broken region is `session.update → RuntimeConfig → S2S→Brain request`.

## CC-1-C3 observability / RCA authority

STATUS: MISSION COMPLETE / ROOT CAUSE CONFIRMED

C3 is an observability-only work package. It does not change conversation behavior, timeout behavior, copied-history behavior, or Brain/Core architecture.

C3 source authority:

- Voice C3 observability code commit: `c0dc177558e300ed4325dbc1f89eb08515d9906c`
- Voice C3 deployed release: `/root/julia_voice_v2/releases/cc1-c3-87971eb3`
- Voice C3 artifact: `87971eb33489be32d8ffea5cf51b88336da29c194efe0c6859e4697399543fe6`

C3 production-safe log points:

- `CC1_SESSION_UPDATE conversation_id=<C|EMPTY>` at active S2S `session.update` receiver.
- `CC1_RUNTIME_BIND conversation_id=<C|EMPTY>` immediately after `RuntimeConfig.apply_session_update()`.
- `S2S_LLM_REQUEST_START ... conversation_id=<C|EMPTY>` at LLM request start.
- `CC1_BRAIN_REQUEST conversation_id=<C|EMPTY> voice_trace_id=<V|EMPTY>` at actual Chat Completions HTTP request boundary after `extra_body` merge.

C3 tests:

- `tests/test_cc1_c3_canonical_id_observability.py`
- Exercises real OpenAI `SessionUpdateEvent` parser → `RuntimeConfig.apply_session_update()` → actual request augmentation → strict mocked HTTP boundary.
- Includes negative case proving missing metadata leaves `conversation_id` absent.

Production C3 evidence:

- `CC1_SESSION_UPDATE conversation_id=EMPTY`
- `CC1_RUNTIME_BIND conversation_id=EMPTY`
- `S2S_LLM_REQUEST_START ... conversation_id=EMPTY`
- `CC1_BRAIN_REQUEST conversation_id=EMPTY`

Confirmed first broken boundary:

- Voice frontend -> realtime `session.update` emitted an empty canonical conversation identity.
- Brain/Core are not implicated by C3 evidence; direct Brain top-level `conversation_id` probes enter CRT correctly.

## CC-1-C4 fail-closed canonical Voice binding

STATUS: SOURCE COMMITTED / AWAITING JULIA AGENT IV&V AND DEPLOYMENT

C4 source authority:

- Voice C4 code commit: `47c03e0357c13f97b3e584935cf7d5d98567ab51`

C4 purpose:

- Fail closed when Electron-hosted Voice lacks a canonical `conversation_id`.
- Remove permissive Electron-hosted S2S identity fallback.
- Require `S2sWsRealtimeClient` canonical-required sessions to normalize and retain the non-empty `conversationId`.
- Require `session.update.session.metadata.conversation_id` to equal the active client conversation before any canonical-required session can be considered configured.
- Make same-C reuse valid only when the active client and configured session both prove the same canonical C.
- Preserve standalone non-Electron empty-conversation behavior.

C4 tests:

- `frontend/tests/cc1-c4-fail-closed-bind.test.js`
- Updated `frontend/tests/rmd3a-session-metadata.test.js`
- `frontend npm test`: 22/22 PASS
- Python C3/RMD focused suite: 17/17 PASS

C4 does not restore copied history, `/external-turns`, workspace semantic bootstrap, or any Brain/Core authority path.

## Authoritative deployment docs/code

CANONICAL:

- `docs/RMD3G_PRODUCTION_RUNBOOK.md`
- `deploy/autodl/julia-voice.env`
- `deploy/autodl/bin/julia-voice-preflight`
- `deploy/autodl/bin/start-julia-voice`
- `deploy/autodl/bin/julia-voice-health`
- `deploy/autodl/bin/julia-voice-watchdog`
- `deploy/autodl/bin/bootstrap-julia-voice-supervisor`
- `deploy/autodl/supervisor/julia-voice.conf`
- `deploy/autodl/boot.sh`
- `deploy/autodl/launch_s2s.py` as historical accepted launcher/recovery config reference; normal lifecycle now uses supervisor launcher above.

Deployed production paths:

- `/etc/julia/julia-voice.env`
- `/opt/julia/bin/start-julia-voice`
- `/opt/julia/bin/julia-voice-preflight`
- `/opt/julia/bin/julia-voice-health`
- `/opt/julia/bin/julia-voice-watchdog`
- `/opt/julia/bin/bootstrap-julia-voice-supervisor`
- `/etc/supervisor/conf.d/julia-voice.conf`
- `/root/boot.sh`, `/root/autodl_boot.sh`

## External runtime assets

- Ref audio `/root/julia_voice_v2/golden/julia_ref.wav` = `48d65eba7f4c76259dcd3d5106fd6579cb80c3e8621c08c2ab13ba60460324fc`
- EXT-VAD-001 Silero cache asset = `912123d2040d45272212f6f3b4889285bf96907b05ba8a85825dbca5d0b80c71`
- Silero JIT = `e1122837f4154c511485fe0b9c64455f7b929c96fbb8d79fbdb336383ebd3720`
- Smart Turn snapshot = `f766f81d3cfdf7737ac64aad813d91bbfd56bf93`
- Smart Turn ONNX = `2bb026316b14a660486a75b1733cd3fbab8c2fd0314dc9af7be49f8cca967e4f`
- Qwen3-TTS snapshot = `fd4b254389122332181a7c3db7f27e918eec64e3`

## Document disposition

CANONICAL:

- `docs/RMD3G_PRODUCTION_RUNBOOK.md`
- this file

HISTORICAL:

- `docs/VOICE-C1B.md`
- `docs/VOICE-GOLDEN-C0_RUNBOOK.md`
- `docs/phase5/FREEZE-ERRATA-001.md`

DO-NOT-USE:

- any old recovery/nohup/tmux/manual startup notes not referenced by `docs/RMD3G_PRODUCTION_RUNBOOK.md`
- `scripts/build_s2s_release.py` if untracked in a worktree; builder authority must be explicit before artifact builds

## Open remediation items

- RMD-3G LIVE barge-in causal chain remains to be validated.
- RMD-4 remains HOLD.
