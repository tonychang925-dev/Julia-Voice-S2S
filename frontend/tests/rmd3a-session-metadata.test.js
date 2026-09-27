import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { S2sWsRealtimeClient } from "../ws/s2s-ws-client.js";

function captureSessionUpdate(options = {}) {
  const sent = [];
  globalThis.WebSocket = { OPEN: 1 };
  const client = new S2sWsRealtimeClient({
    directUrl: "ws://127.0.0.1:8080/v1/realtime",
    voice: "julia",
    instructions: "test instructions",
    ...options,
  });
  client._ws = {
    readyState: globalThis.WebSocket.OPEN,
    send: (payload) => sent.push(JSON.parse(payload)),
  };
  client._sendSessionUpdate();
  assert.equal(sent.length, 1);
  assert.equal(sent[0].type, "session.update");
  return sent[0].session;
}

test("RMD-3A T01: conversationId is sent as session.metadata.conversation_id", () => {
  const session = captureSessionUpdate({ conversationId: " conv-rmd3a " });
  assert.deepEqual(session.metadata, { conversation_id: "conv-rmd3a" });
});

test("RMD-3A T02/T06: empty conversationId preserves existing session.update shape", () => {
  const session = captureSessionUpdate({ conversationId: "   " });
  assert.equal(Object.hasOwn(session, "metadata"), false);
  assert.equal(session.type, "realtime");
  assert.equal(session.instructions, "test instructions");
  assert.deepEqual(session.audio, { output: { voice: "julia" } });
});

test("RMD-3A T08: session metadata carries only identity, not semantic history", () => {
  const session = captureSessionUpdate({
    conversationId: "conv-rmd3a",
    tools: [{ type: "function", name: "noop", description: "noop", parameters: {} }],
  });
  assert.deepEqual(session.metadata, { conversation_id: "conv-rmd3a" });
  assert.equal(Object.hasOwn(session, "messages"), false);
  assert.equal(Object.hasOwn(session, "history"), false);
  assert.equal(Object.hasOwn(session, "baseLastMessageId"), false);
  assert.equal(Object.hasOwn(session, "baseMessages"), false);
  assert.equal(session.tools.length, 1);
  assert.equal(session.tool_choice, "auto");
});

test("RMD-3A/CC-1-C4 source handoff: Electron-hosted doStart requires canonical conversationId", () => {
  const source = readFileSync(new URL("../main.js", import.meta.url), "utf8");
  assert.match(source, /function requireActiveCanonicalConversationId\(\)/);
  assert.match(source, /conversationId:\s*requiredConversationId/);
  assert.match(source, /canonicalConversationRequired:\s*electronHosted/);
});
