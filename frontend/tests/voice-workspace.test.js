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

test("cumulative transcript produces one stable turn", () => {
  const workspace = new VoiceWorkspace({ conversationId: "conv-A", voiceSessionId: "vws-test" });
  workspace.onUserTurnStarted("item-1");
  workspace.onUserTranscript({ itemId: "item-1", text: "hello", partial: true });
  workspace.onUserTranscript({ itemId: "item-1", text: "hello Julia", partial: false });
  workspace.onAssistantTranscript({ responseId: "resp-1", text: "hi" });
  workspace.onResponseFinished({ responseId: "resp-1", status: "completed", transcript: "hi Tony" });
  const delta = workspace.exportDelta();
  assert.equal(delta.length, 1);
  assert.equal(delta[0].turn_id, "voice:vws-test:0001");
  assert.equal(delta[0].user_content, "hello Julia");
  assert.equal(delta[0].assistant_content, "hi Tony");
  assert.equal(delta[0].assistant_status, "completed");
});

test("cancelled assistant is interrupted and retry is stable until commit", () => {
  const workspace = new VoiceWorkspace({ conversationId: "conv-A", voiceSessionId: "vws-test" });
  workspace.onUserTranscript({ itemId: "item-1", text: "continue", partial: false });
  workspace.onAssistantTranscript({ responseId: "resp-1", text: "part" });
  workspace.onResponseFinished({ responseId: "resp-1", status: "cancelled", transcript: "partial answer" });
  const first = workspace.exportDelta();
  const retry = workspace.exportDelta();
  assert.deepEqual(retry, first);
  assert.equal(first[0].assistant_status, "interrupted");
  workspace.markCommitted([first[0].turn_id], "msg-new");
  assert.deepEqual(workspace.exportDelta(), []);
  assert.equal(workspace.baseLastMessageId, "msg-new");
});

test("conversation workspaces remain isolated", () => {
  const a = new VoiceWorkspace({ conversationId: "conv-A", voiceSessionId: "a" });
  const b = new VoiceWorkspace({ conversationId: "conv-B", voiceSessionId: "b" });
  a.onUserTranscript({ itemId: "one", text: "secret", partial: false });
  a.onResponseFinished({ responseId: "r", status: "completed", transcript: "known" });
  assert.equal(a.exportDelta().length, 1);
  assert.equal(b.exportDelta().length, 0);
});
