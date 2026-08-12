# Julia-Voice-S2S Current Authority

UPDATED: 2026-08-12
AUTHORITATIVE BRANCH: phase5/rmd-3g-observability

## Current release

- Source commit: `bf295c2f342603d3b3b9996f40c0740b9e11774f`
- Archive: `speech_to_speech-obs-bf295c2.tar.gz`
- Archive SHA256: `dc0977c8522c8613e66ab4eb5ee7078fb8eb469dfb4af26c415a3be17c6b5805`
- File count: 144 (124 files + 20 directories — git-tracked only)
- Builder: `scripts/build_s2s_release.py` (deterministic, git-provenance)

## Build provenance

Builder reads from exact git commit object. Never reads ambient working tree.
Archive is deterministic: same commit always produces byte-identical tar.gz.

```
SOURCE COMMIT (remote, pushed)
  → build_s2s_release.py (git clone + checkout exact commit)
  → speech_to_speech-obs-<hash>.tar.gz + manifest.json
```

## Deployment

Deployment is **manual**. There is no automated deployment tool.

The only automated piece is the verification gate:

```
/opt/julia/bin/verify_deployment <expected_git_sha>
```

Rule: **never test Julia until verify_deployment returns DEPLOYMENT VERIFIED.**

verify_deployment checks:
1. manifest source_commit = expected SHA
2. :7860 cwd = current/release/frontend
3. :7860 served main.js/ws SHA = manifest
4. :8765 PYTHONPATH = current/release
5. 0 stale processes from old releases

## Fault concealment gate

P0: 0  (no blocking fallbacks)
P1: 6  (all WAIVED — see docs/authority/P1_ALLOW_DEGRADED_WAIVERS.md)

## Authoritative files

- `scripts/build_s2s_release.py` — canonical builder
- `deploy/autodl/bin/verify_deployment` — deployment verification gate
- `docs/authority/CURRENT_AUTHORITY.md` — this file
- `docs/RMD3G_PRODUCTION_RUNBOOK.md` — production runbook
- `docs/authority/P1_ALLOW_DEGRADED_WAIVERS.md` — P1 waivers

## Historical

RMD3G C1-C4 split-release model → superseded by single-artifact build.
RCP deployment automation → intentionally NOT built. Manual deploy + verify is the right level of automation.

## External runtime assets

- Ref audio `/root/julia_voice_v2/golden/julia_ref.wav` = `48d65eba7f4c76259dcd3d5106fd6579cb80c3e8621c08c2ab13ba60460324fc`
- Silero cache = `e1122837f4154c511485fe0b9c64455f7b929c96fbb8d79fbdb336383ebd3720`
- Smart Turn = `f766f81d3cfdf7737ac64aad813d91bbfd56bf93`
- Qwen3-TTS = `fd4b254389122332181a7c3db7f27e918eec64e3`
