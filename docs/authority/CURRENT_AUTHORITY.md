# Julia-Voice-S2S Current Authority

STATUS: CANONICAL
UPDATED: 2026-08-11
REPOSITORY: Julia-Voice-S2S
ROLE: Voice/S2S runtime, AutoDL production release, observability, production supervisor/watchdog
AUTHORITATIVE BRANCH: phase5/rmd-3g-observability
AUTHORITATIVE COMMIT AT CLOSEOUT: a5a90803794cdc7e8dd3b3ead534801c7f7bf85b plus this G0 closeout successor commit

## Current production/development status

- RMD-3G C1 normal voice recovery is production-effective.
- AutoDL S2S is supervised by dedicated supervisord and watchdog.
- Manual `python launch_s2s.py` startup is no longer production authority.

## Source and artifact authority

C1 source authority:

- `1552470f3f8f4e33a9cb90181daa1353f0702eb2`

C1 artifact authority:

- artifact SHA256: `b18d1e42ca2e1383829b6d5f0670652efa066944ba92823a815a35253291c9ac`
- manifest SHA256: `3137878712a0bf689fc9e381f8c1ab081512abdaea89dfedcd9106e65f2869c1`
- production release: `/root/julia_voice_v2/releases/rmd3g-c1-b18d1e42`

Critical runtime file hashes:

- base handler = `2f904a05128d5b11c92e6a2bd04769cd12c6e06f3a66e7d23dbb09b7eb34004c`
- chat handler = `725db87b6313a2cc601173be751ea8bca258eb2c601450ac4a0e273f92acb621`
- websocket router = `12769ece09b8da10f6ea7be06064cb37dc58d8a41026d8d47bfe1d6ecd0c033c`

Historical failed candidates:

- `5f343195...` / `3a2feaf7...` = HISTORICAL RMD-3G LIVE FAILED CANDIDATE, not production authority.

## Authoritative deployment docs/code

CANONICAL:

- `docs/RMD3G_PRODUCTION_RUNBOOK.md`
- `deploy/autodl/julia-voice.env`
- `deploy/autodl/bin/julia-voice-preflight`
- `deploy/autodl/bin/start-julia-voice`
- `deploy/autodl/bin/julia-voice-health`
- `deploy/autodl/bin/julia-voice-watchdog`
- `deploy/autodl/bin/bootstrap-julia-voice-supervisor`
- `deploy/autodl/supervisor/julia-voice.conf`
- `deploy/autodl/boot.sh`
- `deploy/autodl/launch_s2s.py` as historical accepted launcher/recovery config reference; normal lifecycle now uses supervisor launcher above.

Deployed production paths:

- `/etc/julia/julia-voice.env`
- `/opt/julia/bin/start-julia-voice`
- `/opt/julia/bin/julia-voice-preflight`
- `/opt/julia/bin/julia-voice-health`
- `/opt/julia/bin/julia-voice-watchdog`
- `/opt/julia/bin/bootstrap-julia-voice-supervisor`
- `/etc/supervisor/conf.d/julia-voice.conf`
- `/root/boot.sh`, `/root/autodl_boot.sh`

## External runtime assets

- Ref audio `/root/julia_voice_v2/golden/julia_ref.wav` = `48d65eba7f4c76259dcd3d5106fd6579cb80c3e8621c08c2ab13ba60460324fc`
- EXT-VAD-001 Silero cache asset = `912123d2040d45272212f6f3b4889285bf96907b05ba8a85825dbca5d0b80c71`
- Silero JIT = `e1122837f4154c511485fe0b9c64455f7b929c96fbb8d79fbdb336383ebd3720`
- Smart Turn snapshot = `f766f81d3cfdf7737ac64aad813d91bbfd56bf93`
- Smart Turn ONNX = `2bb026316b14a660486a75b1733cd3fbab8c2fd0314dc9af7be49f8cca967e4f`
- Qwen3-TTS snapshot = `fd4b254389122332181a7c3db7f27e918eec64e3`

## Document disposition

CANONICAL:

- `docs/RMD3G_PRODUCTION_RUNBOOK.md`
- this file

HISTORICAL:

- `docs/VOICE-C1B.md`
- `docs/VOICE-GOLDEN-C0_RUNBOOK.md`
- `docs/phase5/FREEZE-ERRATA-001.md`

DO-NOT-USE:

- any old recovery/nohup/tmux/manual startup notes not referenced by `docs/RMD3G_PRODUCTION_RUNBOOK.md`
- `scripts/build_s2s_release.py` if untracked in a worktree; builder authority must be explicit before artifact builds

## Open remediation items

- RMD-3G LIVE barge-in causal chain remains to be validated.
- RMD-4 remains HOLD.
