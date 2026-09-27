# Mira L2 Review — RCP Deployment Evidence

SUBMITTED: 2026-08-12
REVIEWER: Mira

---

## 1. Source Provenance

| Field | Value |
|---|---|
| Remote branch | `origin/phase5/rmd-3g-observability` |
| Remote commit | `997a37ff92b9e399655419a33fa50458aa5fc0de` |
| Builder | `scripts/build_s2s_release.py` (git-clone + exact checkout) |
| Builder reads ambient worktree | NO — reads git commit object only |

## 2. Artifact

Artifact built deterministically from remote commit `997a37f`.

Files in artifact: s2s/ (96 files) + frontend/ (28 files) = 124 code files + 20 directories = 144 entries.
No gitignored files. No ambient working tree contamination.

Archive content:
```
speech_to_speech/     ← S2S code (:8765)
frontend/             ← frontend code (:7860)
```

## 3. Fault Concealment Gate

```
P0 (BLOCKING):  0  ✅
P1 (WAIVED):    6  ✅ (documented waivers, 30-day review)
```

All 6 P1 are in non-canonical paths (TTS fallback, demo, cleanup). None in conversation authority path.

## 4. Deployment Verification

Deployment is manual. Single automated gate:

```
/opt/julia/bin/verify_deployment 997a37ff92b9e399655419a33fa50458aa5fc0de
```

Checks:
1. manifest source_commit = `997a37f...`
2. :7860 cwd = `current/release/frontend`
3. :7860 served main.js / s2s-ws-client.js SHA = manifest
4. :8765 PYTHONPATH = `current/release`
5. 0 stale processes from old releases

Expected output:
```
DEPLOYMENT VERIFIED
```

## 5. Rules Enforced

- Both :7860 and :8765 from same release directory
- No pip install at runtime
- Release content = git content (no ambient files)
- Never test Julia until DEPLOYMENT VERIFIED

## 6. Mira Decision Required

- [ ] Source provenance: CONFIRMED / ISSUES
- [ ] Fault concealment: CONFIRMED / ISSUES
- [ ] Deployment verification: CONFIRMED / ISSUES

Final:
- [ ] MIRA DEPLOY APPROVAL
- [ ] E2E AUTHORIZED

---

Tony: please confirm verify_deployment output.
