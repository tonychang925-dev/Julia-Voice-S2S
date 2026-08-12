import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

// P0-CC1-VOICE-001: host.attach handler const reassignment regression test.
// The handler receives julia.voice.host.attach and re-routes to
// conversation.bind by reassigning payload. This MUST be `let`, not `const`.

const src = readFileSync(new URL("../main.js", import.meta.url), "utf-8");

test("handleHostMessage uses let payload (not const) for host.attach reroute", () => {
  // Locate the handler
  const handlerStart = src.indexOf("async function handleHostMessage(event)");
  assert.notStrictEqual(handlerStart, -1, "handleHostMessage not found");

  const handlerBody = src.slice(handlerStart, src.indexOf("\n  }", handlerStart + 5000));

  // Verify there is a reassignable payload
  assert.ok(
    /let\s+payload\s*=/.test(handlerBody),
    "payload must be declared with `let` to allow host.attach reroute"
  );

  // The incoming event data must be const (never reassigned)
  assert.ok(
    /const\s+incoming\s*=/.test(handlerBody),
    "incoming must be `const` — original event data must not be mutated"
  );

  // The reroute: payload = { ...incoming, type: "julia.voice.conversation.bind", ... }
  assert.ok(
    /payload\s*=\s*\{\s*\.\.\.incoming\s*,/.test(handlerBody) ||
    /payload\s*=\s*\{\s*\.\.\.incoming\s*\n/.test(handlerBody),
    "host.attach must reroute into conversation.bind via new object from incoming"
  );

  // Must NOT contain the old buggy pattern: const payload = event.data with reassignment
  const constPayload = /const\s+payload\s*=\s*event\.data/.test(handlerBody);
  assert.ok(!constPayload, "const payload = event.data (old bug) must not be present");
});

test("handleHostMessage extracts requestId from incoming", () => {
  const handlerStart = src.indexOf("async function handleHostMessage(event)");
  const handlerBody = src.slice(handlerStart, src.indexOf("\n  }", handlerStart + 5000));

  assert.ok(
    /requestId.*incoming/.test(handlerBody),
    "requestId must be extracted from incoming for ACK routing"
  );
});
