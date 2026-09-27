# AT-20B — Conversation Switch Stress Regression

**Status:** PASS ✅ (evidence frozen 2026-08-24)
**Linked issue:** VOICE-WS-LIFECYCLE-001 (RESOLVED)
**Scope:** Rapid conversation switching while Voice is active — S2S single-slot
handoff must not produce `1008 All session slots are in use`.

---

## 1. Regression Target

The pre-fix failure mode:

```
Conversation A (voice) → switch → Conversation B (voice)
        ⇓
old slot not released (~36ms)
        ⇓
new bootstrap dial → close(1008)
```

Acceptance: N rapid switches with **zero** 1008 / zero rejected connections,
and correct conversation/voice-session binding.

## 2. Fixes Under Test

| Layer | Repo / SHA | Mechanism |
|---|---|---|
| frontend | Julia-Voice-S2S `a500f55` | `close()` awaits WS close (1s cap); `_openWebSocket` resolves on `session.created` |
| Electron | Julia_client `31b4504` | Text exit unloads voice frame (slot released); Voice entry re-bootstraps; 1008 retry 300/700/1500ms |

## 3. Test Method

1. Deploy `a500f55` via SOP (release `manual-a500f55-20260824_145318`).
2. Run Electron with `fix/voice-ws-lifecycle-001` (local run, `electron .`).
3. Rapidly switch conversations, entering/exiting Voice repeatedly.
4. Verify S2S log: every disconnect followed by clean slot release,
   `Rejected connection` count does **not** increase.

## 4. Result (real user test, 2026-08-24 15:20:15 → 15:20:39)

Six conversation switches — every session released cleanly:

```
15:20:15  session_2bd1e1  disconnected → Pipeline 0 released ✅
15:20:19  session_3ee93b  disconnected → Pipeline 0 released ✅
15:20:25  session_3761de  disconnected → Pipeline 0 released ✅
15:20:30  session_edbab7  disconnected → Pipeline 0 released ✅
15:20:39  session_ed23d6  disconnected → Pipeline 0 released ✅
```

`Rejected connection` total: **2** (pre-fix historical at 14:58) — **zero new**.

Pool after test: `{"size":1,"in_use":0,"units":[{"index":0,"state":"idle"}]}`

## 5. Supporting Tools

- Stress harness: `at20b_stress_test.py` (fire-and-forget close simulation;
  direct python-websockets dial through the local tunnel). Note: script-level
  runs do not reproduce the JS microtask timing, so the authoritative evidence
  is the real-user UI switch log above.

## 6. Verdict

```
AT-20B Conversation Switch Stress: PASS ✅
VOICE-WS-LIFECYCLE-001:            RESOLVED ✅
Runtime session continuity:        PASS ✅
```
