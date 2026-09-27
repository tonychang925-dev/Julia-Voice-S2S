# VOICE-WS-LIFECYCLE-001 — S2S single-slot handoff race (1008)

**Status:** RESOLVED ✅
**Severity:** Medium
**Data Integrity Impact:** None
**AT-20 Impact:** None
**Detected:** 2026-08-24 (post-AT-20 real user E2E)
**Type:** Runtime session state-machine correctness (not continuity recovery)

---

## 1. Symptom

On rapid conversation switching in the Electron voice surface:

```
WebSocket closed (1008) All session slots are in use
```

S2S log pattern (per occurrence):

```
…disconnected from pipeline 0
WARNING - Rejected connection: all 1 pipeline slots in use   (≈36ms after disconnect)
…unregistered
Pipeline 0 released
```

## 2. Root Cause

`Voice session lifecycle was not a closed loop.`

```
Conversation switch
        ↓
old voice frame still alive (old WS close initiated)
        ↓
S2S slot not yet released (~36ms handoff window)
        ↓
new bootstrap dials
        ↓
collision → close(1008)
```

Contributing defects:

1. **frontend `close()` was fire-and-forget** — `_ws.close(1000)` returned immediately
   without awaiting the socket close event, so teardown did not wait for the
   server slot to release.
2. **`_openWebSocket` resolved on `open`** — transport open was treated as
   session success, even though the server rejects an overlapping dial with
   close(1008) *after* the TCP/Upgrade handshake. `open ≠ session established`.
3. **Electron kept the voice frame alive in Text mode** — the S2S slot stayed
   occupied while the user was not using Voice, so any later Voice entry raced
   a stale session teardown.

## 3. Fix (three layers)

### Layer 1 — frontend `close()` awaits WS close (root fix, `a500f55`)

```js
// previously: this._ws.close(1000); this._ws = null;   (fire-and-forget)
// now: send close, await the socket close event (1s timeout), then clear
```

Ensures teardown completion ⇒ server slot released.

### Layer 2 — `_openWebSocket` resolves on `session.created` (`a500f55`)

```js
// previously: resolve on "open"
// now: resolve on the first server message (session.created)
//      a 1008 close before that rejects connect() so callers can retry
```

Removes the hidden `transport open == voice ready` state error.

### Layer 3 — Electron unloads voice frame on Text exit (`31b4504`)

```js
// switchToTextMode(): pauseVoiceCapture → flushVoiceWorkspace →
//                    teardownVoiceFrame() → showSurface('text')
// switchToVoiceMode(): ensureVoiceLoaded() → bootstrapVoiceWorkspace() → resumeMicCapture()
```

Voice is now an explicit per-entry session: Text mode holds no S2S slot;
entering Voice builds a fresh frame + bootstrap. Plus a defensive 1008
retry with 300/700/1500ms backoff in `bindVoiceConversation`.

## 4. Evidence

### Before fix (reproduced in production log)

```
14:33:17,021 disconnect
14:33:17,057 Rejected connection: all 1 pipeline slots in use
14:33:17,075 unregistered
14:33:17,076 Pipeline 0 released
```

### After fix (real user test, 2026-08-24 15:20:15 → 15:20:39)

6 rapid conversation switches — every session released cleanly:

```
session_2bd1e1 … released  ✅
session_3ee93b … released  ✅
session_3761de … released  ✅
session_edbab7 … released  ✅
session_ed23d6 … released  ✅
```

`Rejected connection` count remained at the pre-fix value (2) — **zero new rejects**.

## 5. Deployment

| Layer | Repo | SHA | Status |
|---|---|---|---|
| Frontend (close + session.created) | Julia-Voice-S2S | `a500f55` | deployed via SOP (release `manual-a500f55-20260824_145318`) |
| Electron (frame unload + retry) | Julia_client | `31b4504` | branch `fix/voice-ws-lifecycle-001`, pushed |

## 6. Classification

- **Persistence Continuity:** PASS (unchanged, AT-20 verified)
- **Voice Session Continuity:** PASS after fix
- Data integrity impact: **None** (no canonical state touched)
