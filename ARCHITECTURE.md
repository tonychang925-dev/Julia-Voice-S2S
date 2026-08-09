# Julia Voice/S2S — Architecture

## Topology (Production)

```
Mac                                                  AutoDL (RTX 3090)
---                                                  -----------------
Electron V2                                          :7860 hf-realtime-voice
  activeConversationId                                 ↓ WebSocket
  ↓ postMessage(bind)                                 :8765 speech-to-speech
  ↓                                                     ↓ VAD → STT → TTS
  ↓                                                     ↓ ChatCompletions
  ↓                                                     ↓
Julia Brain :18089 ←──────────────────────────── SSH reverse tunnel :8089
  /v1/chat/completions
  ↓
Julia Core ConversationRuntime
```

## Component Map

| Port | Component | Source | Owner |
|------|-----------|--------|-------|
| :7860 | Voice Frontend | `frontend/` | Voice/S2S |
| :8765 | S2S Realtime | `s2s/` | Voice/S2S |
| :18089 | Brain API | `julia_ai_assistant/` | Julia Core |
| — | ConversationRuntime | `julia_core/` | Julia Core |

## Data Flow (Voice Turn)

```
1. Electron → postMessage → :7860
   { source: "julia-electron-v2", type: "julia.conversation.bind", conversationId: "conv-A" }

2. :7860 → WebSocket → :8765
   ws://localhost:8765/v1/realtime?julia_client=julia-electron-v2&julia_conversation_id=conv-A

3. :8765 → RuntimeConfig.julia_transport
   { client: "julia-electron-v2", conversation_id: "conv-A", bound: true }

4. :8765 → HTTP → :18089
   POST /v1/chat/completions
   { messages: [{role:"user",content:"<STT>"}], stream:true,
     conversation_id:"conv-A", turn_id:"voice-xxx", modality:"voice" }

5. :18089 → ConversationRuntime.process_turn()
   → Core canonical persistence
```

## Modification Rules

1. PCM / VAD / STT / TTS = golden baseline, read-only
2. Transport metadata = control plane only
3. Never modify site-packages directly
4. One commit = full transport chain visible
5. UPSTREAM.lock updated after every upstream sync
