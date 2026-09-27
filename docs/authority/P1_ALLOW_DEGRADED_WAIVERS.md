# P1 ALLOW_DEGRADED Waivers

STATUS: ACTIVE
CREATED: 2026-08-12
EXPIRES: 2026-09-12 (30-day review)
GATE: FAULT-CONCEALMENT-AUDIT-01 Static Gate
REVIEWER: Mira (DEPLOY APPROVAL authority)

## Summary

P0 count: 0 (PASS — no blocking fallbacks)
P1 count: 6 (requires explicit ALLOW_DEGRADED waiver)

All 6 are F3_SILENT_DEGRADATION: `except Exception: pass` or `return None` without logging.
Each waiver is individually reviewed below. Categories:

- **WAIVED**: Non-critical path, failure is acceptable degradation
- **FIX-NEXT**: Must be fixed before waiver expiry (2026-09-12)
- **DENIED**: Cannot ship — fix now

---

## Waiver Index

### W01 — context_execution_runtime.py:255 (density cache)
- **Repo**: julia_core
- **Path**: julia_core/runtime/context_execution_runtime.py:255
- **Pattern**: `except Exception: pass` → returns cached density value
- **Impact**: Density computation failure silently returns stale cache
- **Risk**: Stale density values may affect context assembly quality
- **Disposition**: **WAIVED** — density is advisory, not canonical; stale cache is better than crash
- **Fix plan**: Add structured mark_frame_failure() call (same pattern as other 5 already-fixed sites)
- **Review cycle**: 30 days

### W02 — voice_loop.py:42 (demo only)
- **Repo**: julia_ai_assistant
- **Path**: demo/voice_loop.py:42
- **Pattern**: `except Exception: return None`
- **Impact**: Demo voice loop silently exits on error
- **Risk**: Zero — demo code, never runs in production
- **Disposition**: **WAIVED** — demo utility, not production path
- **Fix plan**: Remove file or add logger.warning; no urgency
- **Review cycle**: 30 days

### W03 — elevenlabs_provider.py:57 (TTS fallback)
- **Repo**: julia_ai_assistant
- **Path**: providers/voice/elevenlabs_provider.py:57
- **Pattern**: `except Exception: pass` → `return None`
- **Impact**: ElevenLabs TTS failure silently returns None
- **Risk**: Voice output missing — user-visible but non-fatal
- **Disposition**: **WAIVED** — Voice degradation is acceptable; TTS failure is self-evident to user
- **Fix plan**: Add logger.warning with voice provider name
- **Review cycle**: 30 days

### W04 — fish_audio_provider.py:52 (TTS fallback)
- **Repo**: julia_ai_assistant
- **Path**: providers/voice/fish_audio_provider.py:52
- **Pattern**: `except Exception: pass` → `return None`
- **Impact**: Fish Audio TTS failure silently returns None
- **Risk**: Same as W03 — voice output missing, user-visible
- **Disposition**: **WAIVED** — same rationale as W03
- **Fix plan**: Add logger.warning with voice provider name
- **Review cycle**: 30 days

### W05 — base_openai_compatible_language_model.py:709 (transaction rollback)
- **Repo**: Julia-Voice-S2S
- **Path**: s2s/LLM/base_openai_compatible_language_model.py:709
- **Pattern**: `except Exception: pass` after `rollback_transaction()`
- **Impact**: Rollback failure silently ignored; cancel_scope updated
- **Risk**: Low — transaction rollback is best-effort cleanup, not semantic path
- **Disposition**: **WAIVED** — rollback failure during cancellation is non-recoverable anyway
- **Fix plan**: Add pipeline_log_ctx warning
- **Review cycle**: 30 days

### W06 — websocket_router.py:439 (lifespan setup)
- **Repo**: Julia-Voice-S2S
- **Path**: s2s/api/openai_realtime/websocket_router.py:439
- **Pattern**: `except Exception: pass` during lifespan initialization
- **Impact**: Cleanup failure during shutdown silently ignored
- **Risk**: Low — lifespan shutdown errors are non-recoverable; process is terminating
- **Disposition**: **WAIVED** — shutdown path, not runtime; failure is acceptable
- **Fix plan**: Add logger.debug
- **Review cycle**: 30 days

---

## Decision

**All 6 P1 findings are WAIVED** for the current RCP release cycle.

Rationale:
1. None are in the canonical conversation authority path (CRT)
2. All are in auxiliary or cleanup paths where silent degradation is preferable to crash
3. All have fix plans for the next review cycle
4. P0 count is 0 — no blocking fallbacks exist

**Next review**: 2026-09-12 (30 days)
**Reviewer**: Mira / Tony

---

## Signoff

- [ ] Tony (L2 review)
- [ ] Mira (DEPLOY APPROVAL)
