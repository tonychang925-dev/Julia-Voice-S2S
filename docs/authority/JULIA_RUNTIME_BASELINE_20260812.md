# JULIA RUNTIME BASELINE CHECKPOINT — 2026-08-12

**Status:** FROZEN
**Scope:** All components verified working together
**Rule:** Any deployment must match these SHAs or be explicitly approved

## Repo Versions

| Component | Repo | Branch | SHA |
|---|---|---|---|
| Voice/S2S | Julia-Voice-S2S | phase5/rmd-3g-observability | `25497cd` |
| Electron | Julia_client | codex/bugfix/electron-c10-c11-projection | `3f8bca0` |
| Core/CRT | Julia_core | cm-r0-fix | `f3d41f6` |
| Brain | julia_ai_assistant_rmd3g_prod | (detached) | `bbd90af` |

## Server (AutoDL) Runtime

| Component | PID | Path | SHA |
|---|---|---|---|
| S2S :8765 | 104073 | manual-25497cd-20260812_175124/release | `25497cd` |
| Frontend :7860 | 103904 | manual-25497cd-20260812_175124/release/frontend | `25497cd` |

## Mac Runtime

| Component | PID | Status |
|---|---|---|
| Brain :18089 | 21424 | CRT commit: ✅ |
| Electron | running | Host bind + CC-2 cache: ✅ |

## Verified Capabilities

- [x] Voice → Text display (CRT sync)
- [x] Text → Voice (workspace.bootstrap)
- [x] Canonical conversation_id propagation (S2S → Brain → CRT)
- [x] CRT voice turn persistence (turn_id, modality, status)
- [x] Electron host.attach / workspace.bootstrap
- [x] Voice prompt: Chinese parenthetical descriptions blocked (`25497cd`)

## Key Fixes in This Baseline

1. `e2b2a28`: const reassignment fix (handleHostMessage)
2. Electron `b5ed986`: workspace.bootstrap restoration
3. Core `f3d41f6`: CRT turn_id/modality/status to_dict whitelist
4. Brain `bbd90af`: nested conversation_id + turn_id generation
5. Electron `ec83805`: filter accepts null/empty turn_id
6. Electron `3f8bca0`: CC-2 Phase 1 VoiceSessionCache
7. `25497cd`: voice prompt Chinese parenthetical ban

## Test Evidence

```
Voice → S2S → Brain → CRT: ✅
CRT → Electron text sync: ✅
Conversation context: ✅ (workspace.bootstrap restores history)
Voice clone (ref_text): ✅ (17-char Chinese baseline preserved)
```

## Three-Way Consistency

```
GitHub Voice-S2S:  25497cd ✅
Mac local:         25497cd ✅
Server running:    25497cd ✅
```
