# Julia-Voice-S2S Current Authority

STATUS: CANONICAL
UPDATED: 2026-08-11
REPOSITORY: Julia-Voice-S2S
ROLE: Voice/S2S runtime, AutoDL production release, unified frontend+S2S lifecycle, observability, production supervisor/watchdog
AUTHORITATIVE BRANCH: codex/bugfix/workbench-intelligence-binding
DEPLOYMENT MODEL: RCP (Release Control Plane)

## RCP: Release Control Plane (CANONICAL)

RCP replaces the RMD3G C1-C4 split-release model. The key structural change: frontend (:7860) and S2S (:8765) are now deployed from a SINGLE immutable artifact built from an exact git commit. Split-brain deployment (C2 frontend with C4 S2S) is now structurally impossible.

### Build provenance chain

```
SOURCE COMMIT (remote, pushed)
  → build_s2s_release.py (reads exact git commit object, NEVER ambient worktree)
  → speech_to_speech-obs-<commit_short>.tar.gz (deterministic, reproducible)
  → manifest.json (SHA256 of every file in archive)
```

Builder authority:
- `scripts/build_s2s_release.py` — now tracked in git, canonical build authority
- Builds from exact git commit object (must be pushed to remote)
- Deterministic: same commit always produces byte-identical archive
- Archive contains BOTH `speech_to_speech/` and `frontend/` in one artifact

### Deployment chain

```
ARTIFACT (tar.gz + manifest.json)
  → Extract to /root/julia_voice_v2/releases/speech_to_speech-obs-<hash>/
  → julia-release-activate (locks read-only, atomic current symlink swap)
  → supervisor restarts from current/
  → julia-runtime-attest (verifies live PID bytes match manifest)
```

### Runtime attestation gate

`deploy/autodl/bin/julia-runtime-attest` verifies:
- :7860 cwd in current
- :7860 served main.js SHA = manifest
- :7860 disk main.js SHA = manifest
- :7860 served s2s-ws-client.js SHA = manifest
- :8765 PYTHONPATH in current/release
- :8765 health = READY
- No stale processes

ALL checks must PASS. Any mismatch → FAIL. This prevents deployment drift structurally.

### Current release

- Source commit: `56c3a10ad704` (latest on codex/bugfix/workbench-intelligence-binding)
- Archive: `speech_to_speech-obs-56c3a10.tar.gz`
- File count: 144 (124 files + 20 directories — git-tracked only, no ambient artifacts)
- Builder: `scripts/build_s2s_release.py` (deterministic, git-provenance)

### Release structure

```
/root/julia_voice_v2/releases/
├── current → speech_to_speech-obs-<hash>/   (atomic symlink)
├── .previous                                  (rollback target)
└── speech_to_speech-obs-<hash>/
    ├── manifest.json
    ├── speech_to_speech-obs-<hash>.tar.gz
    ├── release/                               (PYTHONPATH)
    │   ├── speech_to_speech/                  (S2S code)
    │   └── frontend/                          (served by :7860)
    └── frontend/                              (served by :7860)
```

### Key invariants

1. CODE → GIT → ARTIFACT → SERVER → PID must ALL match
2. Releases are content-addressed and read-only after seal
3. `current` symlink provides atomic activation (no partial deploys)
4. Same release root for :7860 and :8765 (structurally prevents split-brain)
5. Builder never reads ambient working tree — only git commit objects
6. Server runs code, never produces code

---

## Historical: RMD3G C1-C4 (SUPERSEDED)

RMD3G C1-C4 used a split-release model where frontend and S2S had independent lifecycles. This caused P0_DEPLOYMENT_SPLIT_BRAIN: C2 frontend running with C4 S2S. RCP makes this structurally impossible.

### C1 (historical)
- Source authority: `1552470f3f8f4e33a9cb90181daa1353f0702eb2`
- Artifact authority: `b18d1e42ca2e1383829b6d5f0670652efa066944ba92823a815a35253291c9ac`
- Status: SUPERSEDED by RCP

### C2 (historical)
- Source: `e44de36f96e270532e3c734a43d0a0317e0ec11c`
- Added: `julia.voice.conversation.bind` handling in frontend
- Status: SUPERSEDED by RCP

### C3 (historical)
- Source: `c0dc177558e300ed4325dbc1f89eb08515d9906c`
- Observability-only: CC1 session.update → LLM request conversation_id tracing
- Status: SUPERSEDED by RCP

### C4 (historical)
- Source: `47c03e0357c13f97b3e584935cf7d5d98567ab51`
- Fail-closed canonical Voice binding
- Status: SUPERSEDED by RCP

---

## External runtime assets (unchanged)

- Ref audio `/root/julia_voice_v2/golden/julia_ref.wav` = `48d65eba7f4c76259dcd3d5106fd6579cb80c3e8621c08c2ab13ba60460324fc`
- Silero cache = `e1122837f4154c511485fe0b9c64455f7b929c96fbb8d79fbdb336383ebd3720`
- Smart Turn snapshot = `f766f81d3cfdf7737ac64aad813d91bbfd56bf93`
- Smart Turn ONNX = `2bb026316b14a660486a75b1733cd3fbab8c2fd0314dc9af7be49f8cca967e4f`
- Qwen3-TTS snapshot = `fd4b254389122332181a7c3db7f27e918eec64e3`

---

## Authoritative deployment docs/code

CANONICAL:
- `docs/authority/CURRENT_AUTHORITY.md` (this file)
- `docs/RMD3G_PRODUCTION_RUNBOOK.md` (RCP runbook)
- `scripts/build_s2s_release.py` (canonical builder)
- `deploy/autodl/bin/julia-release-activate` (atomic activation)
- `deploy/autodl/bin/julia-runtime-attest` (runtime verification gate)
- `deploy/autodl/julia-voice.env` (environment template)
- `deploy/autodl/bin/start-julia-voice` (S2S launcher)
- `deploy/autodl/bin/julia-voice-preflight` (preflight checks)
- `deploy/autodl/bin/julia-voice-health` (health check)
- `deploy/autodl/bin/julia-voice-watchdog` (watchdog)
- `deploy/autodl/bin/bootstrap-julia-voice-supervisor` (supervisor bootstrap)
- `deploy/autodl/supervisor/julia-voice.conf` (process supervisor config)
- `deploy/autodl/boot.sh` (AutoDL boot hook)
- `deploy/autodl/start_frontend.sh` (:7860 frontend launcher)

HISTORICAL:
- `docs/VOICE-C1B.md`
- `docs/VOICE-GOLDEN-C0_RUNBOOK.md`
- `docs/phase5/FREEZE-ERRATA-001.md`
- Any old recovery/nohup/tmux/manual startup notes

DO-NOT-USE:
- `python launch_s2s.py` as production launcher (use supervisor)
- Manual `export` or `.bashrc` for environment (use `/etc/julia/julia-voice.env`)
- Development worktrees as PYTHONPATH in production

---

## Open remediation items

- RMD-3G LIVE barge-in causal chain validation
- RMD-4 remains HOLD
- 6 P1 silent fallbacks need formal ALLOW_DEGRADED waivers with expiry
- Brain F1/F4 committed fixes pending remote push
- Rebuild sealed RCP release for production deployment
- Mira RCP review and DEPLOY APPROVAL before E2E testing
