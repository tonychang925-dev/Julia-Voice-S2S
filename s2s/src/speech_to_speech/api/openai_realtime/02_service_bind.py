"""VOICE-C1B-V Patch 2: bind_julia_transport() on RealtimeService.

File to modify:
  speech_to_speech/api/openai_realtime/service.py

Add a public method bind_julia_transport() that writes Julia transport
routing metadata into RuntimeConfig. The websocket router calls this
after registering the session — it does NOT reach through _state().
"""

from __future__ import annotations


# ── NEW METHOD on RealtimeService ─────────────────────────────────────────────
# Add this method to the RealtimeService class.

def bind_julia_transport(
    self,
    conn_id: str,
    *,
    client: str,
    conversation_id: str,
) -> None:
    """Bind a Julia logical conversation ID to this S2S connection.

    Writes into RuntimeConfig.julia_transport — pure routing metadata.
    Does NOT touch chat history, persona, memory, or session cognition.

    Called by websocket_router after session registration.
    Ownership: websocket_router → RealtimeService public API → RuntimeConfig.
    """
    st = self._state(conn_id)

    st.runtime_config.julia_transport.client = client
    st.runtime_config.julia_transport.conversation_id = conversation_id
    st.runtime_config.julia_transport.bound = bool(
        client == "julia-electron-v2" and conversation_id
    )


# ── Usage in websocket_router.py ──────────────────────────────────────────────
#
#   julia_client = (ws.query_params.get("julia_client") or "").strip()
#   julia_conversation_id = (ws.query_params.get("julia_conversation_id") or "").strip()
#
#   # ... (fail-closed check — see 03_websocket_router.py) ...
#
#   session_id = unit.service.register()
#
#   if julia_client:
#       unit.service.bind_julia_transport(
#           session_id,
#           client=julia_client,
#           conversation_id=julia_conversation_id,
#       )
