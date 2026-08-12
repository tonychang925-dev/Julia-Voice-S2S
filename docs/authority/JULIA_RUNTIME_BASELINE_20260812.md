# JULIA RUNTIME BASELINE — 2026-08-12

**Status:** FROZEN
**Verified:** 2026-08-12 19:15 CST
**Rule:** Deployment must match these SHAs or pass JPSG Gate 0 + Gate 1

## Component Versions

| Component | Repo | Branch | SHA | Role |
|---|---|---|---|---|
| Voice/S2S (server) | Julia-Voice-S2S | phase5/rmd-3g-observability | `e2b2a28` | Voice runtime |
| Voice/S2S (github) | Julia-Voice-S2S | phase5/rmd-3g-observability | `e6168da` | Docs + launcher |
| Electron | Julia_client | codex/bugfix/electron-c10-c11-projection | `3f8bca0` | Desktop shell |
| Core/CRT | Julia_core | cm-r0-fix | `5439e99` | Conversation authority |
| Brain | julia_ai_assistant_rmd3g_prod | (detached) | `bbd90af` | Voice API bridge |

Note: GitHub Voice-S2S `e6168da` is ahead of server `e2b2a28` by docs + launcher fix only. The s2s/frontend runtime code is identical.

## Server Runtime (AutoDL)

```
Release:       manual-e2b2a28-20260812_135217
Manifest SHA:  e2b2a28
S2S PID:       109973
S2S PYTHONPATH: /root/julia_voice_v2/releases/current/release ✅
Frontend:      :7860 ✅
S2S:           :8765 ✅
CC1_SESSION_UPDATE: ✅ conversation_id flowing
```

## Mac Runtime

```
Brain PID:     21424
Brain port:    :18089 ✅
CRT commit:    ✅
Electron:      running ✅
```

## Verified Capabilities

- [x] Voice realtime (S2S → Brain → LLM → TTS)
- [x] Text mode (Electron → Brain → CRT)
- [x] Voice → Text sync (CRT commit → Electron sync)
- [x] Conversation context (workspace.bootstrap → CRT history → LLM)
- [x] CC1 canonical conversation_id propagation (S2S → Brain)
- [x] CRT turn persistence (turn_id, modality, status, source)
- [x] S2S import provenance fail-closed (G0.7)
- [x] Dual review safety gate (JPSG documented)

## Known Gaps

- Voice prompt: parenthetical descriptions not yet suppressed (fix in `02b941a`, not deployed)
- Server GitHub Voice-S2S is ahead by docs + launcher fix — non-runtime
- CC-2 VoiceSessionCache Phase 1 deployed (Electron `3f8bca0`) — minimal MVP
