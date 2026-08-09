# VOICE-C1B — Conversation Transport Binding

**Status**: Contract frozen 2026-08-09. Implementation in progress.
**Next**: VOICE-C1B-E (Codex Electron bind sender)

## Problem

Electron `activeConversationId` is not propagated through Voice/S2S to Core. Voice turns appear as isolated sessions, not part of the same conversation.

## Root Cause

Four layers missing:

1. `:7860` frontend — no bind receiver for Electron `postMessage`
2. `:7860 → :8765` WS — `conversation_id` not in connection params
3. `:8765` S2S — no Julia transport routing state
4. `:8765 → :18089` Brain HTTP — `conversation_id` not in request body

## Fix: 4-Layer Transport Chain

```
Electron activeConversationId
  ↓ postMessage("julia.conversation.bind", {conversationId: "conv-A"})
:7860 frontend (bind receiver + state machine)
  ↓ WS ?julia_client=julia-electron-v2&julia_conversation_id=conv-A
:8765 S2S (RuntimeConfig.julia_transport)
  ↓ HTTP body {conversation_id, turn_id, modality}
:18089 Brain (already supports conversation_id @84fbbb9)
  ↓
Core ConversationRuntime
```

## State Machine

```
UNBOUND  → mic BLOCKED
BINDING  → mic BLOCKED
BOUND    → mic enabled
TURN_ACTIVE → rebind BLOCKED
```

## Files Modified

| Layer | File | Change |
|-------|------|--------|
| Frontend | `frontend/main.js` | bind receiver, state machine, ACK bridge |
| Frontend | `frontend/ws/s2s-ws-client.js` | WS URL julia params |
| S2S | `s2s/.../runtime_config.py` | JuliaTransportContext model |
| S2S | `s2s/.../service.py` | bind_julia_transport() |
| S2S | `s2s/.../websocket_router.py` | query params + fail closed + ACK |
| S2S | `s2s/.../chat_completions_language_model.py` | per-request extra_body + current-STT-only |

## NOT Modified

Core, Brain, Electron, PCM, VAD, STT, TTS
