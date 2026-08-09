# Julia-Voice-S2S

Julia Voice transport runtime — monorepo for `:7860` frontend + `:8765` S2S backend.

**Status**: Repository bootstrap complete; runtime Golden baseline pending.
**Owner**: Claude / Voice负责人

## Quick Links

- [ARCHITECTURE.md](ARCHITECTURE.md) — topology, component map, data flow
- [OWNERSHIP.md](OWNERSHIP.md) — boundary rules: what Voice owns vs Core vs Electron
- [UPSTREAM.lock](UPSTREAM.lock) — frozen upstream SHAs (fill from AutoDL)
- [docs/VOICE-C1B.md](docs/VOICE-C1B.md) — conversation transport binding contract
- [julia/contracts/](julia/contracts/) — frozen transport contracts

## Directory

```
frontend/        — (pending) hf-realtime-voice (:7860) — import from AutoDL
s2s/             — (pending) speech-to-speech (:8765) — import from AutoDL
patches/         — VOICE-C1B reference patches (apply after golden import)
julia/           — contracts + tests
deploy/          — AutoDL launchers + Mac tunnel
scripts/         — verification + provenance snapshot + smoke tests
docs/            — VOICE-C1B, golden baseline, legacy deprecation
```

## Tags

- `voice-repo-bootstrap-20260809` — repository/governance bootstrap (current)
- `voice-golden-pre-c1b-20260809` — pending: runtime baseline import from AutoDL
- `voice-c1b-v1` — target: VOICE-C1B transport binding
