"""Selected-path construction for speech-to-text providers."""

from __future__ import annotations

import importlib
from collections.abc import Callable
from dataclasses import dataclass, field
from queue import Queue
from threading import Event
from typing import Any

from speech_to_speech.pipeline.queue_types import STTOutItem, VADOutItem
from speech_to_speech.pipeline.speculative_turns import SpeculativeTurnTracker


@dataclass
class STTHandlerContext:
    stop_event: Event
    queue_in: Queue[VADOutItem]
    queue_out: Queue[STTOutItem]
    speculative_turns: SpeculativeTurnTracker | None
    module_kwargs: Any
    provider_kwargs: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class STTProviderSpec:
    module_path: str
    handler_name: str
    setup_kwargs: Callable[[STTHandlerContext], dict[str, Any]]


def _plain_setup(argument_name: str) -> Callable[[STTHandlerContext], dict[str, Any]]:
    def build(context: STTHandlerContext) -> dict[str, Any]:
        return vars(context.provider_kwargs[argument_name])

    return build


def _mlx_audio_setup(context: STTHandlerContext) -> dict[str, Any]:
    setup_kwargs = dict(
        vars(context.provider_kwargs["mlx_audio_whisper_stt_handler_kwargs"])
    )
    setup_kwargs["language"] = context.provider_kwargs[
        "whisper_stt_handler_kwargs"
    ].language
    return setup_kwargs


def _parakeet_setup(context: STTHandlerContext) -> dict[str, Any]:
    setup_kwargs = dict(
        vars(context.provider_kwargs["parakeet_tdt_stt_handler_kwargs"])
    )
    setup_kwargs.update(
        enable_live_transcription=context.module_kwargs.enable_live_transcription,
        live_transcription_update_interval=context.module_kwargs.live_transcription_update_interval,
    )
    return setup_kwargs


_STT_PROVIDER_SPECS: dict[str, STTProviderSpec] = {
    "whisper": STTProviderSpec(
        "speech_to_speech.STT.whisper_stt_handler",
        "WhisperSTTHandler",
        _plain_setup("whisper_stt_handler_kwargs"),
    ),
    "whisper-mlx": STTProviderSpec(
        "speech_to_speech.STT.lightning_whisper_mlx_handler",
        "LightningWhisperSTTHandler",
        _plain_setup("whisper_stt_handler_kwargs"),
    ),
    "mlx-audio-whisper": STTProviderSpec(
        "speech_to_speech.STT.mlx_audio_whisper_handler",
        "MLXAudioWhisperSTTHandler",
        _mlx_audio_setup,
    ),
    "paraformer": STTProviderSpec(
        "speech_to_speech.STT.paraformer_handler",
        "ParaformerSTTHandler",
        _plain_setup("paraformer_stt_handler_kwargs"),
    ),
    "faster-whisper": STTProviderSpec(
        "speech_to_speech.STT.faster_whisper_handler",
        "FasterWhisperSTTHandler",
        _plain_setup("faster_whisper_stt_handler_kwargs"),
    ),
    "parakeet-tdt": STTProviderSpec(
        "speech_to_speech.STT.parakeet_tdt_handler",
        "ParakeetTDTSTTHandler",
        _parakeet_setup,
    ),
}


def create_stt_provider(context: STTHandlerContext, selector: str | None = None) -> Any:
    """Construct one provider while importing only its selected dependency path."""

    selected_provider = selector if selector is not None else context.module_kwargs.stt
    try:
        spec = _STT_PROVIDER_SPECS[selected_provider]
    except KeyError:
        raise ValueError(
            "The STT should be either none, whisper, whisper-mlx, mlx-audio-whisper, faster-whisper, parakeet-tdt, or paraformer."
        ) from None

    handler_module = importlib.import_module(spec.module_path)
    handler_class = getattr(handler_module, spec.handler_name)
    handler = handler_class(
        context.stop_event,
        queue_in=context.queue_in,
        queue_out=context.queue_out,
        setup_kwargs=spec.setup_kwargs(context),
    )
    if context.speculative_turns is not None:
        handler.speculative_turns = context.speculative_turns
    return handler
