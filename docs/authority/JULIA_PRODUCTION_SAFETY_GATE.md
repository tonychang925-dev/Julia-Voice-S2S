# Julia Production Safety Gate (JPSG)

**Status:** FROZEN v1.0
**Effective:** 2026-08-12
**Applies to:** All Julia runtime component deployments and protocol changes
**Governance:** SOP v1.1 (deployment) + JPSG v1.0 (safety gate)

## Principle

```
Code correct ≠ Deploy correct ≠ Runtime correct
```

No component may enter TEST AUTHORIZED state without passing both gates.

## State Machine

```
DEV           → Code exists locally
BUILD PASS    → Artifact generated, manifest verified
GATE0 PASS    → Automated verification passed
REVIEW PASS   → Human architecture review approved
DEPLOY PASS   → Server runtime identity verified
TEST AUTHORIZED → User testing allowed
```

Any failure: STOP. Do not proceed to next state.

---

## GATE 0 — Automated Verification

### G0.1 Source Identity

Every component must answer "who am I" on startup:

```
COMPONENT=<name> GIT_SHA=<sha> BUILD_ID=<uuid> BUILD_TIME=<timestamp> PATH=<release_path>
```

Two environments with same SHA but different deps/models/config are different runtimes.
If any field absent: STARTUP BLOCKED.

### G0.2 Three-Way Consistency

```
GitHub SHA = Mac build SHA = Server manifest SHA
```

Mismatch: DEPLOY BLOCKED.

### G0.3 Artifact Manifest

Every release must have `manifest.json` with full file SHAs.
Before deploy: verify all manifest hashes against extracted files.

### G0.4 Runtime Attestation

Post-startup verification:
- Brain: PID, SHA, CRT_COMMIT=enabled, PORT=18089
- S2S: PID, SHA, PYTHONPATH must resolve to release, PORT=8765  
- Frontend: PID, SHA, CWD must resolve to release/frontend, PORT=7860

On PASS: save `runtime_attestation.json` snapshot for incident review.

```json
{
  "timestamp": "ISO8601",
  "components": {
    "brain":   { "pid": 0, "sha": "", "port": 0, "crt_commit": true },
    "s2s":     { "pid": 0, "sha": "", "port": 0, "pythonpath": "" },
    "frontend":{ "pid": 0, "sha": "", "port": 0, "cwd": "" }
  }
}
```

### G0.5 Process Hygiene

- :8765 count = 1
- :7860 count = 1
- :18089 count = 1
- Old runtime process count = 0

### G0.6 Protocol Compatibility

Any host.attach or bind protocol change must pass:
- workspace.bootstrap compatibility test
- host.attach → conversation.bound ACK test

### G0.7 Import Provenance (S2S Fail-Closed)

Before S2S exec: verify `speech_to_speech.__file__` starts with expected release path.
If it resolves to site-packages: STARTUP BLOCKED (exit 3).

### G0.8 Environment Hash

Same commit, different environment = different runtime. Capture on every deploy:

```
PYTHON_VERSION=$(python --version)
DEPENDENCY_HASH=$(sha256sum requirements.freeze.txt)
MODEL_CONFIG_HASH=$(sha256sum model_config.json 2>/dev/null || echo "N/A")
```

Store in manifest or runtime attestation. Changes to environment must be reviewed — not just code changes.

### G0.9 Data Schema Compatibility (FUTURE)

When Conversation/Memory/Context schemas are versioned, this gate activates.

```
ConversationSchema=v1.2  MemorySchema=v1.0  ContextSchema=v1.0
```

Schema mismatch between components: STARTUP BLOCKED.
Prevents silent data corruption from schema drift.

---

## GATE 1 — Human Architecture Review

### G1.1 Architecture Impact

- Does this change data ownership?
- Who is the source of truth? (CRT, Memory Store, Frontend Cache)
- Does it introduce a second authority?

### G1.2 Migration Completeness

Protocol changes must preserve ALL capabilities of the old protocol.
Check: old protocol test suite still passes.

### G1.3 Rollback Plan

- Rollback commit: _______________
- Rollback release: _______________
- Rollback procedure tested: YES / NO

### G1.4 Reviewer Signoff

- [ ] Architecture review: PASS
- [ ] Data authority: PRESERVED
- [ ] Protocol migration: COMPLETE
- [ ] Rollback tested: YES

Reviewer: ____________ Date: ____________

### G1.5 Memory / Conversation Authority (FUTURE)

When Memory System is introduced, this gate activates. Until then: informational.

- [ ] Conversation Authority preserved (CRT is sole conversation truth)
- [ ] Memory can only append/govern — never mutate Conversation
- [ ] Context Loader is sole cognitive ingress path
- [ ] No bypass: raw history injection into LLM blocked
- [ ] Memory extraction idempotent (same input → same output)

---

## Deployment Checklist

Before any `TEST AUTHORIZED` declaration, confirm ALL items:

```
[ ] GitHub SHA = Mac SHA = Server manifest SHA
[ ] G0.1-G0.8: ALL PASS
[ ] G1.1-G1.5: ALL PASS
[ ] Runtime attestation snapshot saved
[ ] Process hygiene: counts verified
[ ] S2S import provenance: release path confirmed
[ ] Environment hash captured
[ ] Reviewer signoff: COMPLETE
```

Only then:

```
✅ TEST AUTHORIZED
```
