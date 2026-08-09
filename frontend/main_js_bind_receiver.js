/* ============================================================================
 * VOICE-C1B-V Frontend Patch A: main.js — Electron bind receiver
 *
 * File to modify:
 *   /root/julia_voice_v2/golden/frontend/main.js
 *   (or the equivalent entry point in hf-realtime-voice)
 *
 * Add BEFORE the S2S WebSocket client initialization.
 * PCM, getUserMedia, AudioWorklet, AEC, VAD — NOT TOUCHED.
 * ========================================================================== */

// ── VOICE-C1B-V: Host binding state machine ──────────────────────────────

const hostBinding = {
  state: "UNBOUND",       // UNBOUND | BINDING | BOUND | TURN_ACTIVE
  requestId: null,
  conversationId: null,
};

let voiceTurnActive = false;

// ── Listen for Electron conversation.bind ────────────────────────────────

window.addEventListener("message", async (event) => {
  const msg = event.data;

  if (
    msg?.source !== "julia-electron-v2" ||
    msg?.type !== "julia.conversation.bind"
  ) {
    return;
  }

  const conversationId = String(msg.conversationId || "").trim();
  if (!conversationId) {
    window.parent.postMessage({
      source: "julia-voice",
      type: "julia.conversation.bound",
      requestId: msg.requestId,
      conversationId: "",
      ok: false,
      reason: "missing_conversation_id",
    }, "*");
    return;
  }

  if (voiceTurnActive) {
    // TURN_ACTIVE: reject rebind
    window.parent.postMessage({
      source: "julia-voice",
      type: "julia.conversation.bound",
      requestId: msg.requestId,
      conversationId: conversationId,
      ok: false,
      reason: "voice_turn_active",
    }, "*");
    return;
  }

  // ── Transition to BINDING ──────────────────────────────────────────
  hostBinding.state = "BINDING";
  hostBinding.requestId = msg.requestId;
  hostBinding.conversationId = conversationId;

  // bind = reconnect control-plane with new conversation_id.
  // This closes the current S2S WebSocket and opens a new one
  // with julia_conversation_id in the query params.
  // PCM, VAD, STT are NOT affected — only the WS URL changes.
  try {
    await reconnectVoice({ conversationId });
  } catch (err) {
    hostBinding.state = "UNBOUND";
    window.parent.postMessage({
      source: "julia-voice",
      type: "julia.conversation.bound",
      requestId: msg.requestId,
      conversationId: conversationId,
      ok: false,
      reason: "reconnect_failed: " + (err.message || "unknown"),
    }, "*");
  }
});


// ── Listen for S2S bind ACK ─────────────────────────────────────────────

// This handler must be registered on the S2S WebSocket message event.
// When the S2S sends { type: "julia.conversation.bound", ... },
// verify the conversation_id matches and transition to BOUND.

function handleS2SBindAck(data) {
  if (data.type !== "julia.conversation.bound") return false;

  if (
    data.ok === true &&
    data.conversation_id === hostBinding.conversationId
  ) {
    hostBinding.state = "BOUND";

    // ACK back to Electron — S2S has confirmed the binding
    window.parent.postMessage({
      source: "julia-voice",
      type: "julia.conversation.bound",
      requestId: hostBinding.requestId,
      conversationId: hostBinding.conversationId,
      ok: true,
    }, "*");

    return true;
  }

  // S2S rejected the bind
  hostBinding.state = "UNBOUND";
  window.parent.postMessage({
    source: "julia-voice",
    type: "julia.conversation.bound",
    requestId: hostBinding.requestId,
    conversationId: data.conversation_id || hostBinding.conversationId,
    ok: false,
    reason: data.reason || "s2s_rejected",
  }, "*");

  return false;
}


// ── Track voice turn state from S2S events ──────────────────────────────

function handleS2STurnEvent(data) {
  switch (data.type) {
    case "input_audio_buffer.speech_started":
      voiceTurnActive = true;
      hostBinding.state = "TURN_ACTIVE";
      break;

    case "response.done":
    case "response.cancelled":
      voiceTurnActive = false;
      if (hostBinding.state === "TURN_ACTIVE") {
        hostBinding.state = "BOUND";
      }
      break;
  }
}


// ── Expose on window for ws client integration ──────────────────────────

window._juliaHostBinding = {
  get state() { return hostBinding.state; },
  get conversationId() { return hostBinding.conversationId; },
  get turnActive() { return voiceTurnActive; },
  handleBindAck: handleS2SBindAck,
  handleTurnEvent: handleS2STurnEvent,
};


// ── Microphone gate ─────────────────────────────────────────────────────
// Override mic append to block when unbound for julia-electron-v2.
// The original appendInputAudio/realtime input push must check
// hostBinding.state before sending audio to S2S.

function isMicAllowed() {
  return hostBinding.state === "BOUND" || hostBinding.state === "TURN_ACTIVE";
}

window._juliaHostBinding.isMicAllowed = isMicAllowed;
