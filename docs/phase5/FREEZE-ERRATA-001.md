STATUS: HISTORICAL ERRATA
SUPERSEDED BY: docs/authority/CURRENT_AUTHORITY.md for current production state
DO NOT USE AS CURRENT RELEASE DASHBOARD

# Julia Phase 5 — FREEZE-ERRATA-001

**Status:** ACTIVE ERRATA / CODE MUTATION STOP  
**Date:** 2026-08-11  
**Scope:** RMD-3A deployed S2S handler patch map only

## What remains valid

The architecture freeze, Wave B GO, and RMD-3A-only release remain valid. RMD-3B / RMD-3G / RMD-4+ remain HOLD. The RMD-3A target remains `conversation_id` propagation from Voice session metadata into the S2S chat-completions request and then the existing Brain native CRT branch. Electron production mutation remains `0 expected`; no semantic history transfer is allowed.

## Provenance mismatch found before first code mutation

WB-JA-08 described the deployed patch locus as `ChatCompletionsApiModelHandler._generate()` plus `_request_chat_completions()` in `chat_completions_language_model.py`.

Repository evidence from both imported Golden `b2c7567` and current source generation `49ef5ba` instead shows:

```text
ChatCompletionsApiModelHandler
  → _serialize()
  → _build_optional_kwargs()
  → _request()
  → event hooks

BaseOpenAICompatibleHandler
  → _generate(..., turn, optional_kwargs, ...)
```

Therefore `modify subclass _generate()` is not yet a source-safe implementation instruction.

## Gate consequence

```text
RMD-3A architecture GO                    PASS / unchanged
RMD-3A development branch                 allowed
RMD-3A handler source mutation            STOP
RMD-3A source commit                      STOP until reconciliation
Deployment/service/package mutation       HOLD
```

No opportunistic partial source patch is permitted after this mismatch.

## Required reconciliation

Attest the exact LIVE deployed source snippets and SHA256 for:

1. `ChatCompletionsApiModelHandler` class and methods;
2. actual `_generate()` owner;
3. `_request()` and `_request_chat_completions()`;
4. exact `turn.runtime_config.session.metadata` → outbound request path;
5. every live source file involved;
6. byte/hash comparison against repo `b2c7567` / `49ef5ba` files.

Final classification:

```text
A. WB-JA-08 function-attribution error; live bytes match repo architecture
B. live site-packages drift; live bytes differ from imported repo source
C. other, with exact evidence
```

Only after this correction may the Exact Patch Map be amended and source mutation resume.
