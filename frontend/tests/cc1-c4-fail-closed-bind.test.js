import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { S2sWsRealtimeClient } from "../ws/s2s-ws-client.js";

if (!globalThis.CustomEvent) {
  globalThis.CustomEvent = class CustomEvent extends Event {
    constructor(type, init = {}) {
      super(type, init);
      this.detail = init.detail;
    }
  };
}

globalThis.WebSocket = { OPEN: 1 };

function makeClient(options = {}) {
  return new S2sWsRealtimeClient({
    directUrl: "ws://127.0.0.1:8765/v1/realtime",
    voice: "julia",
    instructions: "test instructions",
    ...options,
  });
}

function attachOpenSocket(client) {
  const sent = [];
  client._ws = {
    readyState: globalThis.WebSocket.OPEN,
    send: (payload) => sent.push(JSON.parse(payload)),
    close: () => { sent.closed = true; },
  };
  return sent;
}

test("CC-1-C4 canonical-required client normalizes and exposes immutable conversation id", () => {
  const client = makeClient({ conversationId: " conv-c4 ", canonicalConversationRequired: true });
  assert.equal(client.conversationId, "conv-c4");
  assert.equal(client.configuredConversationId, "");
});

test("CC-1-C4 canonical-required client rejects empty conversation id before startup", () => {
  assert.throws(
    () => makeClient({ conversationId: "   ", canonicalConversationRequired: true }),
    /Canonical conversation_id is required/,
  );
});

test("CC-1-C4 initial session.update carries canonical conversation_id", () => {
  const client = makeClient({ conversationId: "conv-c4", canonicalConversationRequired: true });
  const sent = attachOpenSocket(client);
  const configured = client._sendSessionUpdate();
  assert.equal(configured, "conv-c4");
  assert.equal(sent.length, 1);
  assert.equal(sent[0].type, "session.update");
  assert.deepEqual(sent[0].session.metadata, { conversation_id: "conv-c4" });
  assert.equal(sent[0].session.metadata.conversation_id, client.conversationId);
});

test("CC-1-C4 session.created sends session.update(C) before configured promise resolves", async () => {
  const client = makeClient({ conversationId: "conv-c4", canonicalConversationRequired: true });
  const sent = attachOpenSocket(client);
  let resolved = false;
  const configuredPromise = client.waitUntilConfigured().then((conversationId) => {
    resolved = true;
    return conversationId;
  });

  await client._onWsMessage(JSON.stringify({ type: "session.created" }));

  assert.equal(sent[0].type, "session.update");
  assert.equal(sent[0].session.metadata.conversation_id, "conv-c4");
  assert.equal(await configuredPromise, "conv-c4");
  assert.equal(resolved, true);
  assert.equal(client.configuredConversationId, "conv-c4");
});

test("CC-1-C4 live session updates retain canonical metadata", () => {
  const client = makeClient({ conversationId: "conv-c4", canonicalConversationRequired: true });
  const sent = attachOpenSocket(client);
  client.updateSession({ instructions: "updated", voice: "julia" });
  client.setTools([{ type: "function", name: "noop", description: "noop", parameters: {} }]);

  assert.equal(sent.length, 2);
  assert.equal(sent[0].session.metadata.conversation_id, "conv-c4");
  assert.equal(sent[1].session.metadata.conversation_id, "conv-c4");
});

test("CC-1-C4 standalone mode preserves legacy empty conversation behavior", () => {
  const client = makeClient({ conversationId: "   " });
  const sent = attachOpenSocket(client);
  const configured = client._sendSessionUpdate();
  assert.equal(configured, "");
  assert.equal(Object.hasOwn(sent[0].session, "metadata"), false);
});

test("CC-1-C4 active frontend source uses fail-closed canonical path", () => {
  const source = readFileSync(new URL("../main.js", import.meta.url), "utf8");
  assert.match(source, /function requireActiveCanonicalConversationId\(\)/);
  assert.match(source, /if \(electronHosted\) return requireActiveCanonicalConversationId\(\)/);
  assert.match(source, /canonicalConversationRequired: electronHosted/);
  const constructorCall = source.slice(
    source.indexOf("const c = new S2sWsRealtimeClient"),
    source.indexOf("client = c;"),
  );
  assert.doesNotMatch(constructorCall, /conversationId:\s*activeCanonicalConversationId \|\| voiceWorkspace\?\.conversationId \|\| ""/);
});

test("CC-1-C4 same-C reuse requires configured active client C", () => {
  const source = readFileSync(new URL("../main.js", import.meta.url), "utf8");
  const bindFn = source.slice(
    source.indexOf("async function bindCanonicalConversation"),
    source.indexOf("async function bootstrapVoiceWorkspace"),
  );
  assert.match(bindFn, /client\?\.conversationId === conversationId/);
  assert.match(bindFn, /client\?\.configuredConversationId === conversationId/);
  assert.match(bindFn, /waitForSessionConfigured: true/);
});
