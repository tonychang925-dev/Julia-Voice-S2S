# RCP Evidence Bundle — Mira DEPLOY APPROVAL Review

SUBMITTED: 2026-08-12
REVIEWER: Mira
STATUS: AWAITING REVIEW

---

## 1. Source Provenance

| Field | Value |
|---|---|
| Remote branch | `origin/phase5/rmd-3g-observability` |
| Remote HEAD | `bf295c2f342603d3b3b9996f40c0740b9e11774f` |
| Local HEAD | `bf295c2f342603d3b3b9996f40c0740b9e11774f` |
| LOCAL = REMOTE | **YES** |
| Builder (committed) | `scripts/build_s2s_release.py` (SHA: `e01e7a07`) |
| Builder commit | `56c3a10` — full clone for commit reachability, no ambient worktree |

### Commit chain (since main divergence)

```
bf295c2 RCP: add P1 ALLOW_DEGRADED waivers
1478ec3 RCP: converge all deploy paths to current symlink
56c3a10 RCP: fix builder to use full clone for commit reachability
b04ffd3 RCP: builder enforces remote-commit provenance
cc5ceaf RCP: add runtime attestation gate
86d55e5 CC-1-RT1: unified release builder — frontend+S2S in one artifact
... (continuity back to main at ad21dad)
```

---

## 2. Artifact

| Field | Value |
|---|---|
| Archive | `speech_to_speech-obs-bf295c2.tar.gz` |
| Archive SHA256 | `dc0977c8522c8613e66ab4eb5ee7078fb8eb469dfb4af26c415a3be17c6b5805` |
| File count | 144 (124 files + 20 directories) |
| Content | `speech_to_speech/` + `frontend/` from exact git commit |

### Artifact = content-addressed

Archive SHA identical to `56c3a10` build because s2s/frontend code unchanged between `56c3a10` and `bf295c2` (only docs/deploy files changed, which are not in the artifact). This proves builder determinism.

### Critical runtime file SHAs

| File | SHA256 |
|---|---|
| `frontend/main.js` | `77fdc4d7dce54ed258dab2d93ee4fa69e139c3912f43be18ebf9d86aa77e6e3d` |
| `frontend/ws/s2s-ws-client.js` | `6eccccabfa3b99e0011f5ec2c0380cf9a8c6b64ca3c70db1c85bf70f7d8c8521` |

---

## 3. Fault Concealment Gate

```
FAULT-CONCEALMENT-AUDIT-01 — Static Gate

✅ F1_AUTHORITY_FALLBACK: 0 (P0)
✅ F2_FAKE_SUCCESS: 0 (P0)
⛔ F3_SILENT_DEGRADATION: 6 (P1) — WAIVED
✅ F4_AUTO_CREATE_ON_RESUME: 0 (P0)
✅ F5_LEGACY_RESURRECTION: 0 (P0)
✅ F6_MOCK_CONFIDENCE: 0 (P1)
✅ F7_DEPLOYMENT_FALLBACK: 0 (P0)

P0 (BLOCKING): 0 ✅
P1 (NEEDS WAIVER): 6 — all WAIVED (see waivers doc)
```

### P1 Waivers

Documented at `docs/authority/P1_ALLOW_DEGRADED_WAIVERS.md` (committed, pushed).
All 6 are in non-canonical paths (TTS fallback, demo, cleanup, shutdown).
Review cycle: 30 days (expires 2026-09-12).

---

## 4. RCP Architecture Invariants

| Invariant | Status |
|---|---|
| Builder reads only git commit objects (no ambient worktree) | ✅ |
| `verify_remote_commit()` before build | ✅ |
| Deterministic archive metadata (mtime=0, uid/gid=0) | ✅ |
| Unified frontend + S2S in single artifact | ✅ |
| Content-addressed release naming | ✅ |
| Atomic `current` symlink activation | ✅ |
| Read-only seal after activation | ✅ |
| Runtime attestation gate (PID bytes vs manifest) | ✅ |
| Same release root for :7860 and :8765 | ✅ |
| All deploy paths → `current` symlink (not hardcoded hashes) | ✅ |

---

## 5. Deployment Chain (pending — NOT YET EXECUTED)

The following steps are documented but have NOT been executed. They require Tony's explicit authorization after Mira DEPLOY APPROVAL:

```
1. scp artifact + manifest → AutoDL
2. Extract to /root/julia_voice_v2/releases/speech_to_speech-obs-bf295c2/
3. julia-release-activate (read-only seal, atomic current symlink)
4. Supervisor restart → :8765 + :7860 bind from same release
5. julia-runtime-attest (ALL SAME = YES)
6. Tony E2E: speak → Julia replies with audio
```

**Current server state:**
- Server is running OLD RMD3G-C1 release (rmd3g-c1-b18d1e42)
- NOT yet updated to RCP
- NO deployment has been attempted
- NO E2E testing has been performed

---

## 6. Pre-Deployment Check

- [x] All RCP source fixes committed and pushed to remote
- [x] LOCAL SHA = REMOTE SHA (`bf295c2`)
- [x] P0 fault concealment count = 0
- [x] P1 waivers documented and source-controlled
- [x] Builder produces deterministic artifact from remote commit
- [x] All deploy paths converged to `current` symlink
- [ ] Mira DEPLOY APPROVAL received
- [ ] Tony authorizes deployment
- [ ] Artifact transferred to AutoDL
- [ ] `julia-release-activate` executed
- [ ] `julia-runtime-attest` = PASS (ALL SAME = YES)
- [ ] Tony E2E = Julia replies with audio

---

## 7. Evidence Integrity

```
REMOTE SOURCE SHA: bf295c2f342603d3b3b9996f40c0740b9e11774f
MANIFEST SOURCE:   bf295c2f342603d3b3b9996f40c0740b9e11774f  ← MATCH ✅
ARTIFACT SHA:      dc0977c8522c8613e66ab4eb5ee7078fb8eb469dfb4af26c415a3be17c6b5805
BUILDER:           scripts/build_s2s_release.py (committed, pushed)
BUILDER MODE:      git-clone + exact checkout (no ambient worktree)
```

---

**Submitted for Mira L2 review.**
**Awaiting DEPLOY APPROVAL before any E2E testing.**
