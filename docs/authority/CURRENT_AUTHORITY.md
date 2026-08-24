# Julia-Voice-S2S Current Authority

UPDATED: 2026-08-24
FROZEN: SOP v1.1

## Deployment Authority

**Single canonical document**: `docs/JULIA_VOICE_MANUAL_DEPLOYMENT_SOP_v1.1.md` (SOP v1.1)

That document is the ONLY authority for how to deploy Julia Voice to production.
No other runbook, wiki, or verbal instruction overrides it.

## Canonical Release Layout

```
<release>/
├── manifest.json
├── <archive>.tar.gz
└── release/
    ├── speech_to_speech/
    └── frontend/
```

## Runtime Invariants

```
:8765 PYTHONPATH = <release>/release
:7860 cwd        = <release>/release/frontend
:7860 served main.js SHA = manifest frontend_main_sha
:7860 served s2s-ws-client.js SHA = manifest frontend_ws_sha
```

## Any Other Layout

```
NON-COMPLIANT
DO NOT TEST
```

Specific examples of NON-COMPLIANT:
- `current/frontend/` (should be `current/release/frontend/`)
- `:7860 cwd = /root` or pointing to old release
- Multiple `speech-to-speech` processes from different releases
- `:7860` and `:8765` from different release directories
- Any files manually patched or copied into release after extraction

## Source Authority

- Repository: `tonychang925-dev/Julia-Voice-S2S`
- Branch: `phase5/rmd-3g-observability`
- Repo HEAD: `fe31651`
- Deployed source: `a500f55` (VOICE-WS-LIFECYCLE-001 frontend lifecycle fix)
- Deployed release: `/root/julia_voice_v2/releases/manual-a500f55-20260824_145318`
- Builder: `scripts/build_s2s_release.py` (deterministic, git-provenance)

## VOICE-C1 Closure

- RC-1 runtime drift → RP-1 provenance gate ✅
- RC-2 authority cutover → ADR-002 ✅
- RC-3 turn_id collision → RP-2 UUID uniqueness ✅ (`5c85c4f`)
- RC-4 voice session handoff race → VOICE-WS-LIFECYCLE-001 ✅ (`a500f55` frontend + `31b4504` Electron)

## Fault Concealment

- P0: 0
- P1: 6 (WAIVED — `docs/authority/P1_ALLOW_DEGRADED_WAIVERS.md`)

## Historical

- VOICE-GOLDEN-C0_RUNBOOK.md — SUPERSEDED
- RMD3G C1-C4 split-release model — SUPERSEDED
- `julia-release-activate` / `julia-runtime-attest` — SUPERSEDED by SOP v1.0 manual verification steps V1-V6
