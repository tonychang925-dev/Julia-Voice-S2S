import test from "node:test";
import assert from "node:assert/strict";
import { VoiceWorkspace, selectBootstrapWindow } from "../voice-workspace.js";

const message = (role, content, status = "completed") => ({ role, content, status });

test("seed window starts at user boundary and keeps last ten complete turns", () => {
  const history = [];
  for (let i = 1; i <= 30; i += 1) {
    history.push(message("user", `u${i}`), message("assistant", `a${i}`));
  }
  const selected = selectBootstrapWindow(history);
  assert.equal(selected.length, 20);
  assert.equal(selected[0].role, "user");
  assert.equal(selected[0].content, "u21");
  assert.equal(selected.at(-1).content, "a30");
});

test("seed window never exceeds ten user boundaries in irregular history", () => {
  const history = [message("assistant", "orphan")];
  for (let i = 1; i <= 14; i += 1) history.push(message("user", `u${i}`));
  history.push(message("assistant", "last answer"));
  const selected = selectBootstrapWindow(history);
  assert.equal(selected[0].role, "user");
  assert.ok(selected.filter((item) => item.role === "user").length <= 10);
  assert.ok(selected.length <= 20);
});

test("canonical bootstrap messages never enter delta", () => {
  const workspace = new VoiceWorkspace({
    conversationId: "conv-A",
    baseMessages: [message("user", "old"), message("assistant", "known")],
  });
  assert.deepEqual(workspace.exportDelta(), []);
});

test("ephemeral transcripts produce stable projection turn ids but no semantic delta", () => {
  const workspace = new VoiceWorkspace({ conversationId: "conv-A", voiceSessionId: "vws-test" });
  workspace.onUserTurnStarted("item-1");
  const userTurnId = workspace.onUserTranscript({ itemId: "item-1", text: "hello Julia", partial: false });
  workspace.onAssistantTranscript({ responseId: "resp-1", text: "hi" });
  const assistantTurnId = workspace.onResponseFinished({ responseId: "resp-1", status: "completed", transcript: "hi Tony" });

  assert.equal(userTurnId, "voice:vws-test:0001");
  assert.equal(assistantTurnId, userTurnId);
  assert.deepEqual(workspace.exportDelta(), []);
});

test("cancelled assistant remains projection-only and never exports external turns", () => {
  const workspace = new VoiceWorkspace({ conversationId: "conv-A", voiceSessionId: "vws-test" });
  const turnId = workspace.onUserTranscript({ itemId: "item-1", text: "continue", partial: false });
  workspace.onAssistantTranscript({ responseId: "resp-1", text: "part" });
  const finished = workspace.onResponseFinished({ responseId: "resp-1", status: "cancelled", transcript: "partial answer" });

  assert.equal(finished, turnId);
  assert.deepEqual(workspace.exportDelta(), []);
  workspace.markCommitted([turnId], "msg-new");
  assert.deepEqual(workspace.exportDelta(), []);
  assert.equal(workspace.baseLastMessageId, "msg-new");
});

test("conversation workspaces remain isolated without becoming conversation authority", () => {
  const a = new VoiceWorkspace({ conversationId: "conv-A", voiceSessionId: "a" });
  const b = new VoiceWorkspace({ conversationId: "conv-B", voiceSessionId: "b" });
  const turnA = a.onUserTranscript({ itemId: "one", text: "secret", partial: false });
  a.onResponseFinished({ responseId: "r", status: "completed", transcript: "known" });

  assert.equal(turnA, "voice:a:0001");
  assert.deepEqual(a.exportDelta(), []);
  assert.deepEqual(b.exportDelta(), []);
});

test("drain is a no-op because Core/CRT is the sole durable authority", () => {
  const workspace = new VoiceWorkspace({ conversationId: "conv-A", voiceSessionId: "drain" });
  const turnId = workspace.onUserTranscript({ itemId: "item-1", text: "final question", partial: false });
  assert.equal(workspace.isStable(), true);
  workspace.finalizeAfterDrain();
  assert.equal(workspace.isStable(), true);
  assert.equal(turnId, "voice:drain:0001");
  assert.deepEqual(workspace.exportDelta(), []);
});
