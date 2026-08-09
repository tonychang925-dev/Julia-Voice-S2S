# VOICE-C1B-V — Conversation Transport Binding Contract

**Status**: 🔒 FROZEN 2026-08-09
**Owner**: Claude / Voice负责人 (S2S + Frontend)
**Next**: VOICE-C1B-E (Codex Electron bind sender)

## Frozen Contract

### 1. Electron → :7860 Frontend (postMessage)
```json
{
  "source": "julia-electron-v2",
  "type": "julia.conversation.bind",
  "requestId": "bind_xxx",
  "conversationId": "conv-A"
}
```

### 2. :7860 → :8765 S2S (WebSocket query param)
```
ws://localhost:8765/v1/realtime?conversation_id=conv-A&client=julia-electron-v2
```

### 3. :8765 S2S → :7860 (bind ACK)
```json
{
  "type": "julia.conversation.bound",
  "conversation_id": "conv-A",
  "ok": true
}
```

### 4. :8765 S2S → :18089 Brain (HTTP request body)
```json
{
  "messages": [{"role": "user", "content": "<current STT only>"}],
  "stream": true,
  "conversation_id": "conv-A",
  "turn_id": "voice-turn-a81234567890",
  "modality": "voice"
}
```

## State Machine
```
UNBOUND  → mic BLOCKED
BINDING  → mic BLOCKED
BOUND    → mic enabled
TURN_ACTIVE → rebind BLOCKED
```

## Hard Rules
1. ACK.requestId != pendingRequestId → reject
2. ACK.conversationId != requestedId → reject
3. UNBOUND/BINDING → microphone turn BLOCK
4. TURN_ACTIVE → rebind BLOCK
5. turn retry → SAME turn_id
6. new STT final → NEW turn_id
7. Bound mode → single current STT message only (Core owns history)
8. Unbound + julia-electron-v2 → fail closed (NEVER call legacy LLM path)

## Forbidden
- seedConversationHistory
- history replay
- effectiveInstructions(history)
- Electron transcript persistence
- caller-owned Voice history
- conversation_id in PCM/audio frames
- fallback to legacy S2S when julia-electron-v2 is unbound

## DoD
1. :7860 receives activeConversationId → PASS
2. bind ACK matches request/conversation → PASS
3. S2S request carries conversation_id → PASS
4. S2S request carries turn_id → PASS
5. S2S request carries modality=voice → PASS
6. Only current STT sent (no history) → PASS
7. Unbound Electron mic blocked → PASS
8. Core same conversation receives Voice turns → PASS
