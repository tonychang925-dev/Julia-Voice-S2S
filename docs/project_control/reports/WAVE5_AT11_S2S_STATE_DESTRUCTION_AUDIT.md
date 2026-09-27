# Wave5 AT-11 — S2S State Destruction Audit

Status: AUDIT COMPLETE ✅ / R0 CONTRACT NEXT  
Date: 2026-08-23  
Repository: `/Users/admin/Julia-Voice-S2S`  
Branch observed: `phase5/rmd-3g-observability`  
HEAD observed: `9d44c22`  
Acceptance item: AT-11 — S2S state destruction

## 1. Acceptance Item

Source Wave5 requirement:

```text
AT-11 — S2S state destruction

Restart/reconnect S2S.

Completed continuity preserved without S2S history transfer.
```

Important numbering clarification:

```text
AT-11 = S2S state destruction
AT-20 = Full restart recovery
```

This audit covers AT-11 only.

## 2. Audit Question

Does destroying/restarting/reconnecting S2S state preserve completed conversation continuity through Core/Assistant canonical state, without S2S replaying, storing, or transferring completed history?

Frozen boundary under audit:

```text
S2S runtime/media state
  ≠
conversation continuity authority
```

Required direction:

```text
Core canonical conversation state
  → Context/Brain continuity
  → new S2S live media session bound by conversation_id
```

Forbidden direction:

```text
old S2S session chat/history/workspace
  → restored conversation continuity
```

## 3. Inputs Reviewed

- `JULIA_CONVERSATION_STORAGE_AND_DIARY_DEVELOPMENT_PLAN_v1.0.md`
- `/Users/admin/Julia-Voice-S2S/ARCHITECTURE.md`
- `/Users/admin/Julia-Voice-S2S/julia/contracts/conversation_binding.md`
- `/Users/admin/Julia-Voice-S2S/frontend/voice-workspace.js`
- `/Users/admin/Julia-Voice-S2S/frontend/main.js`
- `/Users/admin/Julia-Voice-S2S/frontend/ws/s2s-ws-client.js`
- `/Users/admin/Julia-Voice-S2S/frontend/tests/voice-workspace.test.js`
- `/Users/admin/Julia-Voice-S2S/frontend/tests/cc1-c2-bind-contract.test.js`
- `/Users/admin/Julia-Voice-S2S/frontend/tests/cc1-c4-fail-closed-bind.test.js`
- `/Users/admin/Julia-Voice-S2S/s2s/api/openai_realtime/runtime_config.py`
- `/Users/admin/Julia-Voice-S2S/s2s/LLM/chat_completions_language_model.py`
- `/Users/admin/Julia-Voice-S2S/tests/test_rmd3a_chat_completions_identity.py`
- `/Users/admin/Julia-Voice-S2S/tests/test_cc1_c3_canonical_id_observability.py`

## 4. Lane Findings

| Lane | Result | Finding |
| --- | --- | --- |
| VoiceWorkspace authority | GREEN ✅ | `VoiceWorkspace.exportDelta()` always returns `[]`; drain/finalize are no-op for semantic turns. |
| Bind history rejection | GREEN ✅ | `bindCanonicalConversation()` rejects non-empty `payload.messages`; `bootstrapVoiceWorkspace()` passes `messages: []`. |
| Session metadata binding | GREEN ✅ | `S2sWsRealtimeClient` requires canonical `conversationId` in hosted mode and writes `session.metadata = { conversation_id }`. |
| Brain request routing | GREEN ✅ | ChatCompletions augments request `extra_body` with `conversation_id`, `voice_trace_id`, and `turn_id`; no SDK top-level authority fields. |
| Frontend live-message bridge | GREEN/AMBER ⚠️ | Live messages sent to Electron are marked `authority: "non_canonical"`, but they are projection events and must remain non-authoritative. |
| S2S runtime chat | AMBER ⚠️ | `RuntimeConfig.chat = Chat(10)` and `_chat_messages(chat)` are live-session context only. R0 must freeze that this state is disposable and cannot be used for restart continuity. |
| Legacy history seeding surface | RED / P0 GAP ⚠️ | `S2sWsRealtimeClient.seedConversationHistory(messages)` still exists despite the frozen contract listing `seedConversationHistory` as forbidden. No call sites found, but the surface itself violates AT-11 hardening. |
| Evidence gate hygiene | AMBER ⚠️ | Existing `cc1-c4-fail-closed-bind.test.js` has a stale static regex expecting older `electronHosted` source text. Actual implementation uses `_runtimeMode/_IN_IFRAME` fail-closed path. Test suite currently reports 17/18. |

## 5. Positive Evidence

### 5.1 VoiceWorkspace is projection/media state only

Observed in `frontend/voice-workspace.js`:

```text
exportDelta() → []
finalizeAfterDrain() → no-op
isStable() → true
```

Interpretation:

```text
VoiceWorkspace state cannot restore completed conversation continuity.
```

### 5.2 Bind and bootstrap do not accept copied history

Observed in `frontend/main.js`:

```text
bindCanonicalConversation(payload)
  rejects Array.isArray(payload.messages) && payload.messages.length

bootstrapVoiceWorkspace(payload)
  calls bindCanonicalConversation({ ...payload, messages: [] })
```

Interpretation:

```text
Electron/S2S bind is transport identity only, not history transfer.
```

### 5.3 Hosted S2S requires canonical conversation_id before session.update

Observed in `frontend/ws/s2s-ws-client.js`:

```text
canonicalConversationRequired + empty conversationId → throw
session.metadata = { conversation_id: conversationId }
```

Interpretation:

```text
Reconnect/new S2S session is bound by Core conversation identity, not by copied history.
```

### 5.4 Brain request carries routing ids, not copied transcript authority

Observed in `s2s/LLM/chat_completions_language_model.py`:

```text
extra_body.conversation_id
extra_body.voice_trace_id
extra_body.turn_id
```

Interpretation:

```text
S2S forwards identity/control metadata; Brain/Core remain responsible for canonical continuity/context.
```

## 6. Audit Probe Results

Command attempted first:

```bash
cd /Users/admin/Julia-Voice-S2S/frontend
npm test -- --test-reporter=spec tests/voice-workspace.test.js tests/cc1-c2-bind-contract.test.js tests/cc1-c4-fail-closed-bind.test.js
```

Result:

```text
FAILED: npm script argument shape treated --test-reporter=spec as a path.
```

Corrected command:

```bash
cd /Users/admin/Julia-Voice-S2S/frontend
node --test tests/voice-workspace.test.js tests/cc1-c2-bind-contract.test.js tests/cc1-c4-fail-closed-bind.test.js
```

Result:

```text
pass 17
fail 1
```

Failure:

```text
CC-1-C4 active frontend source uses fail-closed canonical path
```

Classification:

```text
Evidence hygiene gap: stale static regex expects older `if (electronHosted) return requireActiveCanonicalConversationId()` text.
Actual implementation now routes through `_runtimeMode`, `_IN_IFRAME`, `requireActiveCanonicalConversationId()`, and `canonicalConversationRequired: _runtimeMode !== RTMode.STANDALONE`.
```

## 7. P0 Gap Frozen for R0

### P0-GAP-1 — Legacy `seedConversationHistory()` surface still exists

Observed:

```text
frontend/ws/s2s-ws-client.js
  async seedConversationHistory(messages, timeoutMs = 5000) { ... }
```

Contract says forbidden:

```text
seedConversationHistory
history replay
effectiveInstructions(history)
caller-owned Voice history
```

No call sites were found, but AT-11 hardening should not leave a callable history-transfer method in the S2S client.

Required R0 behavior:

```text
seedConversationHistory unavailable or fail-closed
  → no conversation.item.create history replay from caller-owned messages
```

## 8. R0 Contract Requirements

R0 must freeze:

1. S2S restart/reconnect creates a new disposable media/runtime session.
2. S2S live chat/workspace state is not completed continuity authority.
3. New S2S session may carry only canonical `conversation_id` and per-turn identity/control metadata.
4. Completed continuity must be recovered from Assistant/Core by `conversation_id`, not by S2S replay.
5. Any history seeding/replay surface must be removed or fail closed.
6. Existing evidence tests must be updated so AT-11 gates are clean and source-pattern checks match current `_runtimeMode/_IN_IFRAME` implementation.

## 9. Out of Scope

AT-11 does not include:

```text
AT-12 Diary NO_ENTRY
AT-20 Full Restart Recovery
Electron UI redesign
Context OS policy changes
transcript redesign
search optimization
voice model/audio quality changes
```

## 10. Current Gate Position

```text
AT-11 Audit: COMPLETE ✅
R0 Contract: NEXT ▶
Minimal Remediation: HOLD ⚠️
R1 Permanent Evidence: HOLD ⚠️
Integration Acceptance: HOLD ⚠️
Freeze: NOT READY
```
