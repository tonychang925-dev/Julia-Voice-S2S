# Julia Production Safety Gate (JPSG)

**Status:** ACTIVE
**Effective:** 2026-08-12
**Applies to:** All Julia runtime component deployments and protocol changes

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
COMPONENT=<name> GIT_SHA=<sha> PATH=<release_path>
```

If absent: STARTUP BLOCKED.

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

---

## Deployment Checklist

Before any `TEST AUTHORIZED` declaration, confirm ALL items:

```
[ ] GitHub SHA = Mac SHA = Server manifest SHA
[ ] G0.1-G0.7: ALL PASS
[ ] G1.1-G1.4: ALL PASS
[ ] Runtime attestation: ALL components verified
[ ] Process hygiene: counts verified
[ ] S2S import provenance: release path confirmed
[ ] Reviewer signoff: COMPLETE
```

Only then:

```
✅ TEST AUTHORIZED
```
