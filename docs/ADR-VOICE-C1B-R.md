# ADR-VOICE-C1B-R — Voice Workspace Reconciliation

**Status**: ACCEPTED 2026-08-09
**Supersedes**: VOICE-C1B-V (realtime Core-bound turn, 7f75fdc)
**Architecture**: Core durable authority + Voice ephemeral workspace

## Context

VOICE-C1B-V attempted realtime Voice→Core turn binding. It introduced:
speculative Core gating, streaming rollback, and S2S turn-id mapping.
This proved too complex and violated the Core authority boundary.

## Decision

VOICE-C1B-R adopts a Git branch/commit model:

```
Core conversation = main branch (durable authority)
Voice workspace   = temporary branch (ephemeral)
Flush             = atomic commit
```

Voice loads a Core snapshot, works locally, and atomically appends
final turns at session end. Core never sees speculative revisions.

## Bootstrap — Core-produced history IS allowed

Previously FORBIDDEN under VOICE-C1B-V:
- seedConversationHistory
- history replay into Voice
- caller-owned history as Core authority

These prohibitions were targeted at the old architecture where
Voice/S2S invented history and treated it as authority.

Under VOICE-C1B-R, the distinction is:

```
caller invents history              ❌ STILL FORBIDDEN
Core produces canonical history
→ Electron transports it
→ Voice temporarily seeds it        ✅ ALLOWED
```

The canonical history originates from Core. Voice seeds it as
a temporary working copy. This is fundamentally different from
Voice/S2S owning conversation authority.

## Bootstrap Window

Voice seeds the **last 10 complete turns (max 20 messages)** from
Core canonical history into S2S Chat.

- Must begin at a user turn boundary.
- First seed item must have role="user".
- Must not start with an orphaned assistant message.

This matches S2S internal `chat_size = 10 user turns`.

## External Turn Schema — Null Assistant

```json
{
  "turn_id": "voice:vws_xxx:0001",
  "modality": "voice",
  "user_content": "...",
  "user_created_at": "...",
  "assistant_content": null,
  "assistant_status": null
}
```

- `assistant_content: null` → `assistant_status` must be `null` → no assistant message created.
- `assistant_content: non-null` → `assistant_status` required: "completed" | "interrupted".
- Empty string `""` (completed empty reply) ≠ `null` (no reply at all).

## Idempotency Order

1. Check existing turn IDs.
2. Same ID + same content → skip.
3. If ALL turns already exist → idempotent success (do NOT check base cursor).
4. Only if NEW turns exist → validate `base_last_message_id`.
5. One lock, one append, one save.

This prevents a successful commit whose HTTP response was lost
from being rejected on retry due to a stale base cursor.

## Consequences

- S2S Python changes: 0
- Realtime Core Voice writes: 0
- Electron authoritative history: 0
- 7f75fdc: superseded experiment, not reverted, not merged, not continued.
