// @ts-check

/**
 * Keep the latest complete canonical turns without cutting into an assistant
 * message. `maxTurns` counts user boundaries, matching the realtime Chat size.
 * @param {Array<Record<string, any>>} messages
 * @param {number} [maxTurns]
 */
export function selectBootstrapWindow(messages, maxTurns = 10) {
  const completed = (Array.isArray(messages) ? messages : []).filter((message) =>
    message
    && message.status === "completed"
    && (message.role === "user" || message.role === "assistant")
    && typeof message.content === "string"
    && message.content.trim(),
  );
  const userIndexes = [];
  completed.forEach((message, index) => {
    if (message.role === "user") userIndexes.push(index);
  });
  if (!userIndexes.length) return [];
  const firstUserIndex = userIndexes[Math.max(0, userIndexes.length - maxTurns)];
  const selected = [];
  let userTurns = 0;
  for (const message of completed.slice(firstUserIndex)) {
    if (message.role === "user") {
      if (userTurns >= maxTurns) break;
      userTurns += 1;
    }
    if (selected.length >= maxTurns * 2) break;
    selected.push(message);
  }
  return selected;
}

function cloneTurn(turn) {
  return JSON.parse(JSON.stringify(turn));
}

export class VoiceWorkspace {
  /**
   * VC-03: VoiceWorkspace = media/runtime workspace only.
   * Completed semantic turns live in Core ConversationMessage.
   * This class generates stable turnIds for UI projection but
   * does NOT store or export completed conversation truth.
   *
   * @param {{ conversationId: string; voiceSessionId?: string; baseLastMessageId?: string; baseMessages?: any[] }} input
   */
  constructor(input) {
    if (!input?.conversationId) throw new Error("Voice workspace requires conversationId");
    this.conversationId = input.conversationId;
    this.voiceSessionId = input.voiceSessionId || `vws_${crypto.randomUUID?.() || Date.now()}`;
    this.baseLastMessageId = input.baseLastMessageId || "";
    /** @type {Map<string, any>} */
    this._turnByItem = new Map();
    /** @type {Map<string, any>} */
    this._turnByResponse = new Map();
    this._committedTurnIds = new Set();
    this._sequence = 0;
  }

  _newTurn(itemId) {
    const turn = {
      turn_id: `voice:${this.voiceSessionId}:${String(++this._sequence).padStart(4, "0")}`,
      modality: "voice",
      _itemId: itemId,
      _userFinal: false,
      _settled: false,
    };
    this._turnByItem.set(itemId, turn);
    return turn;
  }

  onUserTurnStarted(itemId) {
    const id = itemId || `anon-user-${this._sequence + 1}`;
    return this._turnByItem.get(id) || this._newTurn(id);
  }

  onUserTranscript({ itemId, text, partial }) {
    const id = itemId || `anon-user-${this._sequence + 1}`;
    const turn = this._turnByItem.get(id) || this._newTurn(id);
    turn._userFinal = !partial && Boolean(String(text || "").trim());
    return turn.turn_id;
  }

  onAssistantTranscript({ responseId, text }) {
    // VC-03: Track response→turn mapping for postToElectron bridge.
    const rid = responseId || `anon-response-${this._sequence}`;
    this._turnByResponse.set(rid, this._latestTurnId);
    return this._latestTurnId;
  }

  onResponseFinished({ responseId, status, transcript }) {
    // VC-03: Return turn_id for postToElectron projection bridge.
    const rid = responseId || `anon-response-${this._sequence}`;
    const turnId = this._turnByResponse.get(rid) || this._latestTurnId;
    return turnId || null;
  }

  get _latestTurnId() {
    let latest = null;
    for (const turn of this._turnByItem.values()) {
      if (turn._userFinal) latest = turn.turn_id;
    }
    return latest;
  }

  isStable() {
    // VC-03: No accumulated turns to drain. Always stable.
    return true;
  }

  finalizeAfterDrain() {
    // VC-03: No accumulated turns. No-op.
  }

  exportDelta() {
    // VC-03: No shadow conversation turns. Core is sole canonical authority.
    return [];
  }

  markCommitted(turnIds, baseLastMessageId = "") {
    for (const turnId of turnIds || []) this._committedTurnIds.add(turnId);
    if (baseLastMessageId) this.baseLastMessageId = baseLastMessageId;
  }
}
