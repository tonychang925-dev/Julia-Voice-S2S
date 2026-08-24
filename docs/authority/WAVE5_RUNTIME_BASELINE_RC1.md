# Wave5 Runtime Baseline Record — RC1

**Tag:** `wave5-continuity-rc1` (julia_core / Julia-Voice-S2S / Julia_client)
**Date:** 2026-08-24
**Status:** RC1 — RUNNABLE candidate, **manual E2E still in progress (NOT final freeze)**

---

## Components

| Component | Repo | SHA | Note |
|---|---|---|---|
| Julia Core | tonychang925-dev/Julia_core | `935b231` | Context OS continuity frames fix + AT-21/21V evidence |
| S2S (voice transport) | tonychang925-dev/Julia-Voice-S2S | `7e42fa6` | VOICE-WS-LIFECYCLE-001 frontend fix + SOP v1.1 + AT-20B evidence |
| Electron (projection) | tonychang925-dev/Julia_client | `7a9506d` | VOICE-WS fix + AT-22 Core-first identity/title/delete |
| Brain (application host) | Julia-AI-Assistant | runtime `bbd90af` | runtime authority (git sync pending) |

## Server Runtime Provenance (RC1)

```
Brain  :18089  authority=bbd90af9853bf709089b78b208b4c6b6347cf6b3
S2S    :8765   release=manual-a500f55-20260824_145318 (manifest source a500f55)
Frontend :7860  same release
Electron     running from julia_electron_v2 @ 7a9506d
```

S2S deployment provenance (SOP v1.1 V1-V6 verified):
```
current → /root/julia_voice_v2/releases/manual-a500f55-20260824_145318
PYTHONPATH (:8765) = current/release
cwd (:7860)       = current/release/frontend
manifest.source_commit = a500f55
```

## Validation at RC1

| Gate | Status |
|---|---|
| AT-20 Restart Recovery | ✅ PASS |
| VOICE-WS-LIFECYCLE-001 | ✅ PASS |
| AT-21 Identity Continuity | ✅ PASS |
| AT-21V Voice Continuity | ✅ PASS |
| Electron voice UX (manual) | ✅ PASS (user confirmed) |
| Conversation delete / auto-title (manual) | ✅ PASS (user confirmed) |

## Pending (NOT in RC1 scope)

- AT-21B Memory Boundary Governance
- Manual E2E completion (full user acceptance)
- Brain authority sync (behind-8)
- Brain list API placeholder title root fix (Electron-side projection workaround in `7a9506d`)

## Purpose

Recoverable checkpoint. If future changes regress, return to `wave5-continuity-rc1`
across the three repos + Brain authority `bbd90af`.
