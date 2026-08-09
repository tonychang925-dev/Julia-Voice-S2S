# Julia Voice/S2S — Ownership Boundaries

**Repo**: `tonychang925-dev/Julia-Voice-S2S`
**Status**: 🔒 FROZEN 2026-08-09

## Voice/S2S Owns

- Microphone transport (getUserMedia, AudioWorklet)
- Realtime WebSocket protocol
- VAD (Silero)
- STT (faster-whisper)
- TTS (Qwen3-TTS Base)
- voice_session_id
- Transport routing metadata (julia_conversation_id, julia_client)
- Barge-in / cancel
- Audio playback queue
- Browser AEC / NS / AGC

## Voice/S2S Does NOT Own

- Julia conversation history
- Julia context / persona / memory
- Cognitive session state
- Canonical conversation persistence
- Prompt assembly
- Tool selection
- DeepSeek API key management
- Electron UI state

## Core (julia_core) Owns

- conversation_id
- Canonical messages / history
- Cognition / context / memory / persona
- ConversationRuntime
- Turn lifecycle (begin → stream → commit → cancel)
- Interaction state

## Electron Owns

- UI rendering
- activeConversationId selection
- bind sender (postMessage to :7860)
- Canonical UI cache
- CLIENT-C1B reconcile

## Boundary Rules

1. Voice/S2S must NOT seed conversation history
2. Voice/S2S must NOT persist Julia transcripts (beyond ephemeral turn buffer)
3. Core must NOT process PCM / Opus / WebRTC
4. Electron must NOT proxy PCM or own voice transport

## Modification Protocol

Any change crossing these boundaries requires:
1. Explicit OWNERSHIP.md review
2. Cross-repo audit
3. Frozen contract update before implementation
