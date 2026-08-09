# Julia-Voice-S2S

Julia Voice transport runtime — monorepo for `:7860` frontend + `:8765` S2S backend.

**Status**: Golden Baseline + VOICE-C1B transport binding in progress.
**Owner**: Claude / Voice负责人

## Quick Links

- [ARCHITECTURE.md](ARCHITECTURE.md) — topology, component map, data flow
- [OWNERSHIP.md](OWNERSHIP.md) — boundary rules: what Voice owns vs Core vs Electron
- [UPSTREAM.lock](UPSTREAM.lock) — frozen upstream SHAs and versions
- [julia/contracts/](julia/contracts/) — frozen transport contracts

## Directory

```
frontend/     — hf-realtime-voice (:7860)
s2s/          — speech-to-speech (:8765)
julia/        — contracts + tests
deploy/       — AutoDL launchers + Mac tunnel
scripts/      — verification + smoke tests
docs/         — VOICE-C1B, golden baseline, legacy deprecation
```

## Tags

- `voice-golden-pre-c1b-20260809` — pre-C1B working baseline
- `voice-c1b-v1` — VOICE-C1B transport binding (target)
