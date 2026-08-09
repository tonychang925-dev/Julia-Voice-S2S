"""VOICE-C1B-V Patch 3: WebSocket router — conversation binding entry point.

File to modify:
  speech_to_speech/api/openai_realtime/websocket_router.py

The /v1/realtime endpoint must:
  1. Read julia_client and julia_conversation_id from WS query params
  2. Fail closed: julia-electron-v2 without conversation_id → reject
  3. Call service.bind_julia_transport() after session registration
  4. Send julia.conversation.bound ACK BEFORE session.created
  5. Append conversation_id to session.created for frontend awareness

Key: ACK must come from S2S (proof that routing state is stored),
NOT from frontend optimism.
"""

from __future__ import annotations


# ── MODIFIED: /v1/realtime endpoint ──────────────────────────────────────────
# The existing handler structure is approximately:
#
#   @app.websocket("/v1/realtime")
#   async def realtime_endpoint(ws: WebSocket):
#       await ws.accept()
#       transport = WebSocketTransport(ws)
#       unit = _claim_unit(transport)
#       ...
#       session_id = unit.service.register()
#       unit.session.session_id = session_id
#       await send_ws_event(ws, unit.service.build_session_created(session_id))
#
# The patched version below adds Julia transport binding before session.created.

# PATCH — insert after WebSocket accept, before session registration:

PATCH_CODE = '''
# ── VOICE-C1B-V: Extract Julia transport routing from query params ─────────

julia_client = (ws.query_params.get("julia_client") or "").strip()
julia_conversation_id = (
    ws.query_params.get("julia_conversation_id") or ""
).strip()

hosted_julia = julia_client == "julia-electron-v2"

# Fail closed: Electron-hosted Voice MUST have a conversation_id
if hosted_julia and not julia_conversation_id:
    await ws.accept()
    await send_ws_event(
        ws,
        {
            "type": "error",
            "error": {
                "type": "conversation_not_bound",
                "code": "conversation_not_bound",
                "message": (
                    "julia-electron-v2 client must provide "
                    "julia_conversation_id. Send julia.conversation.bind "
                    "before starting voice input."
                ),
            },
        },
    )
    await ws.close(code=1008)
    return
'''


# PATCH — insert after session registration, before session.created:

PATCH_SESSION = '''
# ── VOICE-C1B-V: Bind Julia transport BEFORE session.created ──────────────

if julia_client:
    unit.service.bind_julia_transport(
        session_id,
        client=julia_client,
        conversation_id=julia_conversation_id,
    )

    # Send bind ACK from S2S — proves routing state is stored
    if hosted_julia and julia_conversation_id:
        await send_ws_event(
            ws,
            {
                "type": "julia.conversation.bound",
                "conversation_id": julia_conversation_id,
                "ok": True,
            },
        )

    # Append conversation_id to session.created so frontend can verify
    session_created_event = unit.service.build_session_created(session_id)
    if isinstance(session_created_event, dict):
        session_created_event["julia_conversation_id"] = julia_conversation_id
    await send_ws_event(ws, session_created_event)
'''


# ── Design Notes ──────────────────────────────────────────────────────────────
#
# 1. ACK order: bind ACK BEFORE session.created
#    This ensures the frontend receives proof of binding before any audio
#    session events. The frontend's bind ACK handler must track the pending
#    requestId and match conversation_id before transitioning to BOUND.
#
# 2. session.created carries julia_conversation_id
#    This is optional but useful for debugging — the frontend can verify
#    that its requested conversation_id matches what S2S received.
#
# 3. No session.update modification
#    session.update goes through strict Pydantic validation. Adding unknown
#    fields will cause validation failures. Keep bind as query param only.
#
# 4. WebSocket close code 1008 = Policy Violation
#    Appropriate for "you didn't bind but you're required to".
