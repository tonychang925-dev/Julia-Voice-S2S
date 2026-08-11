import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const mainSource = () => readFileSync(new URL("../main.js", import.meta.url), "utf8");
const wsSource = () => readFileSync(new URL("../ws/s2s-ws-client.js", import.meta.url), "utf8");

test("CC-1-C2 active Voice receiver accepts canonical conversation bind", () => {
  const source = mainSource();
  assert.match(source, /payload\.type === "julia\.voice\.conversation\.bind"/);
  assert.match(source, /bindCanonicalConversation\(payload\)/);
  assert.match(source, /type: "julia\.voice\.conversation\.bound"/);
  assert.match(source, /conversationId\s*=\s*String\(payload\.conversationId \|\| ""\)\.trim\(\)/);
  assert.match(source, /if \(!conversationId\) throw new Error\("Voice bind requires conversationId"\)/);
});

test("CC-1-C2 bind is transport identity only and rejects copied history", () => {
  const source = mainSource();
  const bindFn = source.slice(
    source.indexOf("async function bindCanonicalConversation"),
    source.indexOf("async function bootstrapVoiceWorkspace")
  );
  const bindHandler = source.slice(
    source.indexOf('if (payload.type === "julia.voice.conversation.bind")'),
    source.indexOf('if (payload.type === "julia.voice.workspace.bootstrap")')
  );
  assert.match(source, /activeCanonicalConversationId = conversationId/);
  assert.match(source, /new VoiceWorkspace\(\{ conversationId \}\)/);
  assert.match(source, /conversationId: activeCanonicalConversationId \|\| voiceWorkspace\?\.conversationId \|\| ""/);
  assert.match(bindFn, /CC-1-C2: bind is transport identity only\. Do not seed copied history\./);
  assert.match(bindFn, /CC-1 bind must not carry message history/);
  assert.doesNotMatch(bindFn + bindHandler, /baseLastMessageId|baseMessages|messages:\s*payload|payload\.messages\.map/);
});

test("CC-1-C2 S2S session metadata still carries conversation_id", () => {
  const source = wsSource();
  assert.match(source, /const conversationId = String\(this\._conversationId \|\| ""\)\.trim\(\)/);
  assert.match(source, /session\.metadata = \{ conversation_id: conversationId \}/);
});
