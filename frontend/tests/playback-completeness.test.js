import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { Script } from "node:vm";
import { S2sWsRealtimeClient } from "../ws/s2s-ws-client.js";

if (!globalThis.CustomEvent) {
  globalThis.CustomEvent = class CustomEvent extends Event {
    constructor(type, init = {}) {
      super(type);
      this.detail = init.detail;
    }
  };
}

function makeClient() {
  return new S2sWsRealtimeClient({
    directUrl: "ws://127.0.0.1:8765/v1/realtime",
    voice: "julia",
    instructions: "test instructions",
    conversationId: "conv-playback",
  });
}

function attachPlaybackNode(client) {
  const messages = [];
  client._playbackNode = { port: { postMessage: (message) => messages.push(message) } };
  return messages;
}

test("completed response-done marks provider completion without clearing queued audio", () => {
  const client = makeClient();
  const messages = attachPlaybackNode(client);
  const finishedResponses = [];
  client.addEventListener("response-finished", (event) => {
    finishedResponses.push(event.detail);
  });
  client._beginPlaybackResponse("resp-complete");
  client._pushAudioDelta("AAAA");

  client._onWsMessage(JSON.stringify({
    type: "response.done",
    response: { id: "resp-complete", status: "completed" },
  }));

  assert.deepEqual(messages.filter((message) => message.kind === "clear"), [{
    kind: "clear",
    reason: "response-replaced",
  }]);
  assert.equal(messages.at(-1).kind, "response-end");
  assert.equal(client._playbackDiagnostics.active, true);
  assert.equal(finishedResponses.length, 0);

  client._onPlaybackMessage({ kind: "playback-complete" });
  assert.equal(finishedResponses.length, 1);
  assert.deepEqual(finishedResponses[0], {
    responseId: "resp-complete",
    status: "completed",
    audible: false,
    transcript: "",
  });
});

test("cancelled response-done intentionally clears stale queued audio", () => {
  const client = makeClient();
  const messages = attachPlaybackNode(client);
  client._beginPlaybackResponse("resp-cancelled");
  client._pushAudioDelta("AAAA");

  client._onWsMessage(JSON.stringify({
    type: "response.done",
    response: { id: "resp-cancelled", status: "cancelled" },
  }));

  const clears = messages.filter((message) => message.kind === "clear");
  assert.equal(clears.at(-1).reason, "response-cancelled");
  assert.equal(messages.some((message) => message.kind === "response-end"), true);
  assert.equal(client._playbackDiagnostics.active, false);
});

test("new speech explicitly resets playback queue with a reason", () => {
  const client = makeClient();
  const messages = attachPlaybackNode(client);
  client._beginPlaybackResponse("resp-old");
  client._pushAudioDelta("AAAA");

  client._onWsMessage(JSON.stringify({ type: "input_audio_buffer.speech_started" }));

  assert.equal(messages.at(-1).kind, "clear");
  assert.equal(messages.at(-1).reason, "user-speech-started");
});

function loadWorkletProcessor() {
  const source = readFileSync(new URL("../worklets/audio-playback.js", import.meta.url), "utf8");
  let Processor;
  const messages = [];
  const context = {
    sampleRate: 48000,
    makeOutput: (frames) => new Float32Array(frames),
    AudioWorkletProcessor: class {
      constructor() {
        this.port = { postMessage: (message) => messages.push(message) };
      }
    },
    registerProcessor: (_name, exported) => {
      Processor = exported;
    },
  };
  new Script(source).runInNewContext(context);
  return { Processor, messages, context };
}

function makeProcessor(loaded) {
  const processor = new loaded.Processor();
  return {
    processor,
    messages: loaded.messages,
    send(message) {
      processor.port.onmessage({ data: message });
    },
    process(frames = 512) {
      const output = loaded.context.makeOutput(frames);
      processor.process(undefined, [[output]]);
    },
  };
}

function makeConfiguredProcessor() {
  const worklet = makeProcessor(loadWorkletProcessor());
  worklet.send({ kind: "config", inputRate: 16000 });
  return worklet;
}

test("response-done preserves queued audio and completion waits for queue drain", () => {
  const worklet = makeConfiguredProcessor();
  worklet.send({ kind: "response-begin" });
  worklet.send({ kind: "audio", samples: new Float32Array(100).fill(0.5) });
  worklet.send({ kind: "response-end" });

  assert.equal(worklet.messages.some(({ kind }) => kind === "playback-stopped"), false);
  worklet.process(512);

  const complete = worklet.messages.find(({ kind }) => kind === "playback-complete");
  assert.equal(complete.queuedByteCount, 200);
  assert.equal(complete.playedByteCount, 200);
  assert.equal(complete.droppedByteCount, 0);
});

test("cancellation drops only the stale response queue", () => {
  const worklet = makeConfiguredProcessor();
  worklet.send({ kind: "response-begin" });
  worklet.send({ kind: "audio", samples: new Float32Array(100).fill(0.5) });
  worklet.send({ kind: "clear", reason: "response-cancelled" });
  worklet.process(256);

  const stopped = worklet.messages.find(({ kind }) => kind === "playback-stopped");
  assert.equal(stopped.reason, "response-cancelled");
  assert.equal(stopped.queuedByteCount, 200);
  assert.equal(stopped.playedByteCount, 0);
  const reset = worklet.messages.filter(({ kind }) => kind === "queue-reset").at(-1);
  assert.equal(reset.reason, "response-cancelled");
  assert.equal(reset.droppedByteCount, 200);
  assert.equal(worklet.messages.some(({ kind }) => kind === "playback-complete"), false);
});

test("new response cannot inherit old queued audio", () => {
  const worklet = makeConfiguredProcessor();
  worklet.send({ kind: "response-begin" });
  worklet.send({ kind: "audio", samples: new Float32Array(100).fill(0.5) });
  worklet.send({ kind: "clear", reason: "response-replaced" });
  worklet.send({ kind: "response-begin" });
  worklet.send({ kind: "audio", samples: new Float32Array(50).fill(-0.5) });
  worklet.send({ kind: "response-end" });
  worklet.process(256);

  const complete = worklet.messages.find(({ kind }) => kind === "playback-complete");
  assert.equal(complete.queuedByteCount, 100);
  assert.equal(complete.playedByteCount, 100);
  assert.equal(complete.droppedByteCount, 0);
});

test("underrun telemetry remains available and response-end still completes", () => {
  const worklet = makeConfiguredProcessor();
  worklet.send({ kind: "response-begin" });
  worklet.send({ kind: "audio", samples: new Float32Array(1).fill(0.5) });
  worklet.process(256);
  assert.equal(worklet.messages.some(({ kind }) => kind === "underrun"), true);

  worklet.send({ kind: "response-end" });
  const complete = worklet.messages.find(({ kind }) => kind === "playback-complete");
  assert.equal(complete.queuedByteCount, 2);
  assert.equal(complete.playedByteCount, 2);
});
