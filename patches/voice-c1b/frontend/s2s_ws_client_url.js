/* ============================================================================
 * VOICE-C1B-V Frontend Patch B: s2s-ws-client.js — WS URL routing params
 *
 * File to modify:
 *   /root/julia_voice_v2/golden/frontend/ws/s2s-ws-client.js
 *   (or wherever the WebSocket URL is constructed for S2S connection)
 *
 * Only changes the WebSocket URL construction. PCM code: ZERO lines touched.
 * ========================================================================== */

// ── BEFORE (existing) ────────────────────────────────────────────────────────
//
//   this._ws = new WebSocket(url);
//

// ── AFTER ─────────────────────────────────────────────────────────────────────

// ── VOICE-C1B-V: Append Julia transport routing to WS URL ────────────────

const wsUrl = new URL(url);

// conversationId comes from hostBinding set by main.js bind receiver
const convId = this._hostConversationId ||
               (window._juliaHostBinding &&
                window._juliaHostBinding.conversationId);

if (convId) {
  wsUrl.searchParams.set(
    "julia_client",
    "julia-electron-v2"
  );
  wsUrl.searchParams.set(
    "julia_conversation_id",
    convId
  );
}

this._ws = new WebSocket(wsUrl.toString());

// ── END OF VOICE-C1B-V PATCH ─────────────────────────────────────────────


// ── Integration notes ────────────────────────────────────────────────────────
//
// 1. The ws client must store _hostConversationId so reconnectVoice()
//    (called from main.js bind receiver) can pass the new conversation_id.
//    Add this setter:
//
//      setHostConversationId(id) {
//        this._hostConversationId = id;
//      }
//
// 2. reconnectVoice() in main.js:
//
//    async function reconnectVoice({ conversationId }) {
//      if (s2sClient && s2sClient._ws) {
//        s2sClient._ws.close(1000, "conversation_switch");
//      }
//      s2sClient.setHostConversationId(conversationId);
//      await s2sClient.connect();  // opens new WS with julia_conversation_id
//    }
//
// 3. Wire S2S message events to the bind/turn handlers:
//
//    ws.addEventListener("message", (event) => {
//      try {
//        const data = JSON.parse(event.data);
//        if (window._juliaHostBinding) {
//          window._juliaHostBinding.handleBindAck(data);
//          window._juliaHostBinding.handleTurnEvent(data);
//        }
//      } catch (_) { /* binary audio, not JSON */ }
//      // ... existing message handling ...
//    });
//
// 4. Mic gate in appendInputAudio:
//
//    appendInputAudio(buffer) {
//      if (window._juliaHostBinding && !window._juliaHostBinding.isMicAllowed()) {
//        console.warn("[voice-c1b] Mic blocked: unbound");
//        return;
//      }
//      // ... existing PCM append ...
//    }
