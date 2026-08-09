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
   * @param {{ conversationId: string; voiceSessionId?: string; baseLastMessageId?: string; baseMessages?: any[] }} input
   */
  constructor(input) {
    if (!input?.conversationId) throw new Error("Voice workspace requires conversationId");
    this.conversationId = input.conversationId;
    this.voiceSessionId = input.voiceSessionId || `vws_${crypto.randomUUID?.() || Date.now()}`;
    this.baseLastMessageId = input.baseLastMessageId || "";
    this.baseMessages = selectBootstrapWindow(input.baseMessages || []);
    /** @type {Map<string, any>} */
    this._turnByItem = new Map();
    /** @type {Map<string, any>} */
    this._turnByResponse = new Map();
    /** @type {any[]} */
    this._turns = [];
    this._committedTurnIds = new Set();
    this._sequence = 0;
  }

  _newTurn(itemId) {
    const turn = {
      turn_id: `voice:${this.voiceSessionId}:${String(++this._sequence).padStart(4, "0")}`,
      modality: "voice",
      user_content: "",
      user_created_at: new Date().toISOString(),
      assistant_content: null,
      assistant_status: null,
      assistant_created_at: null,
      _itemId: itemId,
      _userFinal: false,
      _settled: false,
    };
    this._turnByItem.set(itemId, turn);
    this._turns.push(turn);
    return turn;
  }

  onUserTurnStarted(itemId) {
    const id = itemId || `anon-user-${this._sequence + 1}`;
    return this._turnByItem.get(id) || this._newTurn(id);
  }

  onUserTranscript({ itemId, text, partial }) {
    const id = itemId || `anon-user-${this._sequence + 1}`;
    const turn = this._turnByItem.get(id) || this._newTurn(id);
    turn.user_content = String(text || "").trim();
    turn._userFinal = !partial && Boolean(turn.user_content);
    return turn.turn_id;
  }

  _latestOpenTurn() {
    return [...this._turns].reverse().find((turn) => turn._userFinal && !turn._settled) || null;
  }

  onAssistantTranscript({ responseId, text }) {
    const rid = responseId || `anon-response-${this._sequence}`;
    const turn = this._turnByResponse.get(rid) || this._latestOpenTurn();
    if (!turn) return null;
    this._turnByResponse.set(rid, turn);
    turn.assistant_content = String(text || "").trim() || null;
    return turn.turn_id;
  }

  onResponseFinished({ responseId, status, transcript }) {
    const rid = responseId || `anon-response-${this._sequence}`;
    const turn = this._turnByResponse.get(rid) || this._latestOpenTurn();
    if (!turn) return null;
    this._turnByResponse.set(rid, turn);
    const content = String(transcript || turn.assistant_content || "").trim();
    turn.assistant_content = content || null;
    turn.assistant_status = content ? (status === "cancelled" ? "interrupted" : "completed") : null;
    turn.assistant_created_at = content ? new Date().toISOString() : null;
    // A tool-call response can finish without transcript and be followed by a
    // second response carrying the actual answer. Keep that logical turn open.
    turn._settled = Boolean(content) || status === "cancelled" || status === "failed";
    return turn.turn_id;
  }

  isStable() {
    return this._turns.every((turn) => !turn.user_content || (turn._userFinal && turn._settled));
  }

  exportDelta() {
    return this._turns
      .filter((turn) => turn._userFinal && turn._settled && !this._committedTurnIds.has(turn.turn_id))
      .map((turn) => {
        const clean = cloneTurn(turn);
        for (const key of Object.keys(clean)) {
          if (key.startsWith("_")) delete clean[key];
        }
        return clean;
      });
  }

  markCommitted(turnIds, baseLastMessageId = "") {
    for (const turnId of turnIds || []) this._committedTurnIds.add(turnId);
    if (baseLastMessageId) this.baseLastMessageId = baseLastMessageId;
  }
}
