"""VOICE-C1B-V Patch 1: JuliaTransportContext in RuntimeConfig.

File to modify:
  speech_to_speech/api/openai_realtime/runtime_config.py

Add JuliaTransportContext model and a julia_transport field to RuntimeConfig.
This is pure routing metadata — NOT cognition, NOT history, NOT memory.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


# ── NEW: Julia Transport Routing Context ──────────────────────────────────────
# Add this class to runtime_config.py, before the RuntimeConfig class.

class JuliaTransportContext(BaseModel):
    """Per-connection Julia transport routing metadata.

    This is NOT chat history. It is NOT sent to the LLM as messages.
    It is pure transport-level routing state that flows through
    RuntimeConfig to the LLM handler for HTTP request metadata injection.

    Distinct from S2S's own ConnState.conversation_id (OpenAI Realtime protocol
    identifier). The name 'julia_conversation_id' is deliberately different.
    """
    client: str = ""             # "julia-electron-v2" or "" (legacy)
    conversation_id: str = ""    # Julia Core canonical conversation ID
    bound: bool = False          # True when julia-electron-v2 + valid ID


# ── MODIFIED: RuntimeConfig ───────────────────────────────────────────────────
# Add julia_transport field to the existing RuntimeConfig class.

# BEFORE (existing):
#
#   class RuntimeConfig(BaseModel):
#       chat: Chat = Field(default_factory=Chat)
#       session: RealtimeSessionCreateRequest = Field(
#           default_factory=RealtimeSessionCreateRequest
#       )
#

# AFTER:
#
#   class RuntimeConfig(BaseModel):
#       chat: Chat = Field(default_factory=Chat)
#       session: RealtimeSessionCreateRequest = Field(
#           default_factory=RealtimeSessionCreateRequest
#       )
#
#       # VOICE-C1B-V: Julia transport routing (NOT cognition)
#       julia_transport: JuliaTransportContext = Field(
#           default_factory=JuliaTransportContext
#       )
