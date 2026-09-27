"""Argument dataclass for the ElevenLabs TTS handler.

Status: VOICE-EL-P0A — defined but **deliberately NOT wired**. This module is
not imported by ``s2s_pipeline.py`` and ``--tts elevenlabs`` does not exist.
It is provided so the handler can be constructed with the same
``setup_kwargs=vars(args)`` convention the other TTS handlers use, once a later
task adds the dispatch branch.

Note the deliberate absence of an ``*_api_key`` CLI field: a key passed on the
command line would be visible in ``ps``. Only the *name* of the environment
variable is configurable here.
"""

from dataclasses import dataclass, field
from typing import Optional

from speech_to_speech.TTS.elevenlabs_tts_handler import (
    DEFAULT_API_KEY_ENV,
    DEFAULT_CONNECT_TIMEOUT_S,
    DEFAULT_MODEL_ID,
    DEFAULT_OUTPUT_FORMAT,
    DEFAULT_RECV_POLL_S,
    DEFAULT_WS_URL,
)


@dataclass
class ElevenLabsTTSHandlerArguments:
    elevenlabs_api_key_env: str = field(
        default=DEFAULT_API_KEY_ENV,
        metadata={
            "help": "Name of the environment variable holding the ElevenLabs API key. "
            "The key itself is never passed as a CLI argument (argv is visible in `ps`). "
            f"Default is {DEFAULT_API_KEY_ENV}."
        },
    )
    elevenlabs_voice_id: Optional[str] = field(
        default=None,
        metadata={
            "help": "ElevenLabs voice id to synthesise with. Falls back to $ELEVENLABS_VOICE_ID when unset."
        },
    )
    elevenlabs_model_id: str = field(
        default=DEFAULT_MODEL_ID,
        metadata={
            "help": "ElevenLabs model id. The Text-to-Dialogue WebSocket requires an eleven_v3* model. "
            f"Default is {DEFAULT_MODEL_ID}."
        },
    )
    elevenlabs_output_format: str = field(
        default=DEFAULT_OUTPUT_FORMAT,
        metadata={
            "help": "Provider output format. pcm_16000 is mono signed 16-bit little-endian at 16 kHz, "
            "which matches the pipeline rate exactly and therefore requires no resampling. "
            f"Default is {DEFAULT_OUTPUT_FORMAT}."
        },
    )
    elevenlabs_ws_url: str = field(
        default=DEFAULT_WS_URL,
        metadata={"help": f"ElevenLabs Text-to-Dialogue WebSocket endpoint. Default is {DEFAULT_WS_URL}."},
    )
    elevenlabs_connect_timeout_s: float = field(
        default=DEFAULT_CONNECT_TIMEOUT_S,
        metadata={"help": "Connection timeout in seconds for the provider WebSocket. Default is 20.0."},
    )
    elevenlabs_recv_poll_s: float = field(
        default=DEFAULT_RECV_POLL_S,
        metadata={
            "help": "Maximum seconds a single synchronous provider read may block before returning, "
            "bounding cancellation latency during a network wait. Default is 0.05."
        },
    )
