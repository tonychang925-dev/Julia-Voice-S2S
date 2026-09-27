from dataclasses import dataclass, field
from typing import Optional

from speech_to_speech.STT.elevenlabs_scribe_handler import (
    DEFAULT_API_KEY_ENV,
    DEFAULT_AUDIO_FORMAT,
    DEFAULT_COMMIT_STRATEGY,
    DEFAULT_LANGUAGE_CODE,
    DEFAULT_MODEL_ID,
)


@dataclass
class ElevenLabsScribeSTTHandlerArguments:
    elevenlabs_scribe_api_key_env: str = field(
        default=DEFAULT_API_KEY_ENV,
        metadata={
            "help": "Environment variable containing the ElevenLabs Scribe API key. The value is never accepted as a CLI argument."
        },
    )
    elevenlabs_scribe_model_id: str = field(
        default=DEFAULT_MODEL_ID,
        metadata={"help": "ElevenLabs Scribe realtime model id."},
    )
    elevenlabs_scribe_language_code: Optional[str] = field(
        default=DEFAULT_LANGUAGE_CODE,
        metadata={"help": "ISO language code used for the Scribe session."},
    )
    elevenlabs_scribe_audio_format: str = field(
        default=DEFAULT_AUDIO_FORMAT,
        metadata={"help": "Audio format sent to Scribe."},
    )
    elevenlabs_scribe_commit_strategy: str = field(
        default=DEFAULT_COMMIT_STRATEGY,
        metadata={
            "help": "Scribe commit strategy. Julia's VAD authority requires manual."
        },
    )
    elevenlabs_scribe_keyterms: list[str] = field(
        default_factory=list,
        metadata={"help": "Optional repeated keyterms passed to Scribe."},
    )
    elevenlabs_scribe_response_timeout_s: float = field(
        default=8.0,
        metadata={
            "help": "Maximum wait for a committed Scribe transcript after a final Julia turn."
        },
    )
