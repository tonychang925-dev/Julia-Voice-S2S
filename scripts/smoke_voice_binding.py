#!/usr/bin/env python3
"""Smoke test: verify VOICE-C1B transport binding contracts.

Run on AutoDL after deploying C1B patches.
"""
import asyncio
import json
import websockets


S2S_WS_URL = "ws://localhost:8765/v1/realtime"


async def test_unbound_electron_rejected():
    """Electron client without conversation_id → rejected."""
    url = f"{S2S_WS_URL}?julia_client=julia-electron-v2"
    try:
        async with websockets.connect(url) as ws:
            msg = json.loads(await ws.recv())
            assert msg["type"] == "error", f"Expected error, got {msg['type']}"
            assert "conversation_not_bound" in str(msg), f"Wrong error: {msg}"
            print("PASS: unbound_electron_rejected")
    except websockets.exceptions.ConnectionClosed as e:
        # S2S may close the connection immediately — also valid
        assert e.code == 1008, f"Expected 1008, got {e.code}"
        print("PASS: unbound_electron_rejected (close code 1008)")


async def test_bound_receives_ack():
    """Electron client with conversation_id → receives bind ACK."""
    url = (
        f"{S2S_WS_URL}"
        f"?julia_client=julia-electron-v2"
        f"&julia_conversation_id=test-conv-smoke-001"
    )
    async with websockets.connect(url) as ws:
        received_bound = False
        received_created = False
        for _ in range(10):
            msg = json.loads(await ws.recv())
            if msg["type"] == "julia.conversation.bound":
                assert msg["ok"] is True
                assert msg["conversation_id"] == "test-conv-smoke-001"
                received_bound = True
            if msg["type"] == "session.created":
                received_created = True
                break
        assert received_bound, "Did not receive bind ACK"
        assert received_created, "Did not receive session.created"
        print("PASS: bound_receives_ack")


async def main():
    print("VOICE-C1B-V Smoke Tests")
    print("=" * 40)
    await test_unbound_electron_rejected()
    await test_bound_receives_ack()
    print("=" * 40)
    print("ALL PASS")


if __name__ == "__main__":
    asyncio.run(main())
