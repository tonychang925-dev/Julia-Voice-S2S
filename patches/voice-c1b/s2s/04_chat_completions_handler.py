"""VOICE-C1B-V Patch 4: ChatCompletions LLM handler — metadata injection.

Files to modify:
  speech_to_speech/llm/chat_completions_language_model.py
  speech_to_speech/llm/base_openai_compatible_language_model.py

The ChatCompletions handler is where the Brain HTTP request is built.
This patch:
  1. Reads julia_transport from RuntimeConfig in process()
  2. Packs transport metadata into optional_kwargs as _julia_transport
  3. In _request(): pops _julia_transport, extracts current-user-only
     message when bound, builds per-request extra_body copy
  4. Preserves legacy standalone behavior when not bound

CRITICAL: Never modify self._extra_body — it's shared across sessions.
Always build a per-request copy.
"""

from __future__ import annotations


# ═══════════════════════════════════════════════════════════════════════════════
# PATCH A: base_openai_compatible_language_model.py — process() method
# ═══════════════════════════════════════════════════════════════════════════════

BASE_HANDLER_PATCH = '''
# ── VOICE-C1B-V: Pack Julia transport into optional_kwargs ────────────────

# In the process() method, after building optional_kwargs:

optional_kwargs = self._build_optional_kwargs(
    req_tools,
    req_tool_choice,
)

# VOICE-C1B-V: Route Julia transport metadata to the request builder
runtime_config = getattr(request, "runtime_config", None)
if runtime_config is not None:
    transport = runtime_config.julia_transport
    if transport.bound:
        if not transport.conversation_id:
            raise RuntimeError(
                "VOICE-C1B-V: bound Julia voice has no conversation_id"
            )

        turn_id = getattr(request, "turn_id", None)
        if not turn_id:
            raise RuntimeError(
                "VOICE-C1B-V: bound Julia voice has no turn_id"
            )

        optional_kwargs["_julia_transport"] = {
            "conversation_id": transport.conversation_id,
            "turn_id": f"voice-{turn_id}",
            "modality": "voice",
        }
'''


# ═══════════════════════════════════════════════════════════════════════════════
# PATCH B: chat_completions_language_model.py — _request() method
# ═══════════════════════════════════════════════════════════════════════════════

CHAT_COMPLETIONS_PATCH = '''
# ── VOICE-C1B-V: Inject transport metadata into HTTP request ──────────────

# In the _request() method, BEFORE the client.chat.completions.create() call:

def _request(self, api_input, optional_kwargs):
    kwargs = dict(optional_kwargs)

    # Pop Julia transport — must NOT reach the OpenAI SDK as a kwarg
    julia = kwargs.pop("_julia_transport", None)

    # ── Build messages ───────────────────────────────────────────────────
    if julia:
        # Bound Julia Voice: send ONLY current user message
        # Core owns conversation history; S2S is transport only
        current_user = None
        for msg in reversed(api_input):
            role = msg.get("role") if isinstance(msg, dict) else getattr(msg, "role", None)
            if role == "user":
                current_user = msg
                break

        if current_user is None:
            raise RuntimeError(
                "VOICE-C1B-V: Julia-bound voice turn has no user transcript"
            )

        messages = [current_user]
    else:
        # Standalone S2S: preserve existing full-history serialization
        messages = api_input

    # ── Build extra_body — PER-REQUEST COPY (never self._extra_body) ──────
    extra_body = dict(self._extra_body or {})

    if julia:
        extra_body.update({
            "conversation_id": julia["conversation_id"],
            "turn_id": julia["turn_id"],
            "modality": "voice",
        })

    # ── Build create_kwargs ───────────────────────────────────────────────
    model_name = kwargs.pop("model_name", self._model_name)
    stream = kwargs.pop("stream", True)
    timeout = kwargs.pop("timeout", self._timeout)
    create_kwargs = {
        k: v for k, v in kwargs.items()
        if k not in ("_julia_transport",)
    }

    return client.chat.completions.create(
        model=model_name,
        messages=messages,
        stream=stream,
        extra_body=extra_body,
        timeout=timeout,
        **create_kwargs,
    )
'''


# ── Resulting HTTP body (bound Julia Voice) ───────────────────────────────────
#
# POST /v1/chat/completions
# {
#   "model": "julia-brain",
#   "messages": [
#     {"role": "user", "content": "刚才测试代号是什么？"}
#   ],
#   "stream": true,
#   "conversation_id": "conv-A",
#   "turn_id": "voice-s2s_turn_abc123",
#   "modality": "voice"
# }
#
# This matches the Brain receiver at 84fbbb9:
#   conversation_id = body.get("conversation_id", "").strip()
#   turn_id = body.get("turn_id", "").strip()
#   modality = body.get("modality", "voice")


# ── Fallback safety ───────────────────────────────────────────────────────────
#
# self._extra_body is a shared provider-level dict.
# NEVER do:
#   self._extra_body["conversation_id"] = convA   # ❌ session contamination
# Always build a per-request copy:
#   extra_body = dict(self._extra_body or {})       # ✅ isolated per-request
