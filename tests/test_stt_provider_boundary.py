"""G1 tests for selected-path STT construction and GPU isolation."""

from __future__ import annotations

import importlib
import sys
import types
from queue import Queue
from threading import Event
from types import SimpleNamespace

import numpy as np
import pytest

import s2s

sys.modules.setdefault("speech_to_speech", s2s)

from s2s.STT import provider_factory
from s2s.STT.provider import STTProvider
from s2s.arguments_classes.faster_whisper_stt_arguments import (
    FasterWhisperSTTHandlerArguments,
)
from s2s.pipeline.messages import Transcription, VADAudio


def _block_optional_whisper_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    for module_name in ("faster_whisper", "ctranslate2"):
        blocked_module = types.ModuleType(module_name)

        def blocked(name: str, _module_name: str = module_name) -> object:
            raise AssertionError(
                f"{_module_name} was imported on a non-Whisper provider path"
            )

        blocked_module.__getattr__ = blocked
        monkeypatch.setitem(sys.modules, module_name, blocked_module)


def test_non_whisper_provider_construction_is_selected_path_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _block_optional_whisper_dependencies(monkeypatch)
    initialized: list[dict[str, object]] = []

    class FakeSTTHandler:
        def __init__(
            self,
            stop_event: Event,
            *,
            queue_in: Queue[object],
            queue_out: Queue[object],
            setup_kwargs: dict[str, object],
        ) -> None:
            self.stop_event = stop_event
            self.queue_in = queue_in
            self.queue_out = queue_out
            self.marker = setup_kwargs["marker"]
            initialized.append(setup_kwargs)

        def setup(self, *args: object, **kwargs: object) -> None:
            return None

        def process(self, audio: VADAudio):
            yield Transcription(
                text="provider text",
                turn_id=audio.turn_id,
                turn_revision=audio.turn_revision,
            )

        def cleanup(self) -> None:
            return None

    fake_module = types.ModuleType("voice_test_stt_provider")
    fake_module.FakeSTTHandler = FakeSTTHandler
    monkeypatch.setitem(sys.modules, fake_module.__name__, fake_module)
    monkeypatch.setitem(
        provider_factory._STT_PROVIDER_SPECS,
        "fake-test",
        provider_factory.STTProviderSpec(
            fake_module.__name__,
            "FakeSTTHandler",
            lambda context: {"marker": context.provider_kwargs["marker"]},
        ),
    )

    context = provider_factory.STTHandlerContext(
        stop_event=Event(),
        queue_in=Queue(),
        queue_out=Queue(),
        speculative_turns=None,
        module_kwargs=SimpleNamespace(stt="fake-test"),
        provider_kwargs={"marker": "selected"},
    )
    handler = provider_factory.create_stt_provider(context)
    audio = VADAudio(
        audio=np.zeros(16, dtype=np.float32), turn_id="turn-test", turn_revision=3
    )
    output = next(handler.process(audio))

    assert initialized == [{"marker": "selected"}]
    assert isinstance(handler, STTProvider)
    assert output.turn_id == "turn-test"
    assert output.turn_revision == 3


def test_faster_whisper_adaptor_preserves_model_configuration_and_turn_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    handler_module = importlib.import_module("s2s.STT.faster_whisper_handler")
    initialized: list[dict[str, object]] = []

    class FakeWhisperModel:
        def transcribe(
            self, audio: np.ndarray, **kwargs: object
        ) -> tuple[list[SimpleNamespace], object]:
            assert kwargs["language"] == "zh"
            assert kwargs["without_timestamps"] is True
            return [
                SimpleNamespace(start=0.0, end=0.1, text=" 你好 ")
            ], SimpleNamespace(language="zh")

    def whisper_model_factory(*args: object, **kwargs: object) -> FakeWhisperModel:
        initialized.append({"args": args, "kwargs": kwargs})
        return FakeWhisperModel()

    monkeypatch.setattr(handler_module, "WhisperModel", whisper_model_factory)

    arguments = FasterWhisperSTTHandlerArguments(
        faster_whisper_stt_model_name="large-v3",
        faster_whisper_stt_device="auto",
        faster_whisper_stt_compute_type="auto",
        faster_whisper_stt_gen_language="zh",
    )
    handler = handler_module.FasterWhisperSTTHandler(
        Event(),
        queue_in=Queue(),
        queue_out=Queue(),
        setup_kwargs={
            "model_name": arguments.faster_whisper_stt_model_name,
            "device": arguments.faster_whisper_stt_device,
            "compute_type": arguments.faster_whisper_stt_compute_type,
            "gen_kwargs": {
                "language": arguments.faster_whisper_stt_gen_language,
                "return_timestamps": False,
            },
        },
    )
    audio = VADAudio(
        audio=np.zeros(16, dtype=np.float32),
        turn_id="turn-faster-whisper",
        turn_revision=0,
    )
    output = next(handler.process(audio))

    assert initialized == [
        {
            "args": ("large-v3",),
            "kwargs": {"device": "auto", "compute_type": "auto"},
        }
    ]
    assert output.text == "你好"
    assert output.turn_id == "turn-faster-whisper"
    assert output.turn_revision == 0


def test_pipeline_orchestration_imports_with_cuda_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    torch_module = types.ModuleType("torch")
    torch_module.cuda = SimpleNamespace(is_available=lambda: False)
    torch_module._logging = SimpleNamespace(set_logs=lambda **kwargs: None)
    torch_module.Tensor = np.ndarray

    class NoGradContext:
        def __call__(self, function: object) -> object:
            return function

        def __enter__(self) -> None:
            return None

        def __exit__(self, *args: object) -> None:
            return None

    def no_grad(function: object = None) -> object:
        return NoGradContext() if function is None else function

    torch_module.no_grad = no_grad

    transformers_module = types.ModuleType("transformers")
    transformers_module.HfArgumentParser = object
    nltk_module = types.ModuleType("nltk")
    nltk_module.data = SimpleNamespace(
        find=lambda *args, **kwargs: "stub", download=lambda *args, **kwargs: True
    )

    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "")
    monkeypatch.setitem(sys.modules, "torch", torch_module)
    monkeypatch.setitem(sys.modules, "transformers", transformers_module)
    monkeypatch.setitem(sys.modules, "nltk", nltk_module)
    sys.modules.pop("speech_to_speech.s2s_pipeline", None)

    import s2s

    monkeypatch.setitem(sys.modules, "speech_to_speech", s2s)
    pipeline = importlib.import_module("speech_to_speech.s2s_pipeline")
    provider_factory_module = importlib.import_module(
        "speech_to_speech.STT.provider_factory"
    )

    _block_optional_whisper_dependencies(monkeypatch)
    monkeypatch.delitem(sys.modules, "s2s.STT.faster_whisper_handler", raising=False)
    monkeypatch.delitem(
        sys.modules, "speech_to_speech.STT.faster_whisper_handler", raising=False
    )

    class PipelineFakeSTTHandler:
        marker: object

        def __init__(
            self,
            stop_event: Event,
            *,
            queue_in: Queue[object],
            queue_out: Queue[object],
            setup_kwargs: dict[str, object],
        ) -> None:
            self.marker = setup_kwargs["marker"]

    fake_module = types.ModuleType("voice_pipeline_test_stt_provider")
    fake_module.PipelineFakeSTTHandler = PipelineFakeSTTHandler
    monkeypatch.setitem(sys.modules, fake_module.__name__, fake_module)
    monkeypatch.setitem(
        provider_factory_module._STT_PROVIDER_SPECS,
        "fake-pipeline",
        provider_factory_module.STTProviderSpec(
            fake_module.__name__,
            "PipelineFakeSTTHandler",
            lambda context: {
                "marker": context.provider_kwargs["faster_whisper_stt_handler_kwargs"]
            },
        ),
    )

    handler = pipeline.get_stt_handler(
        SimpleNamespace(stt="fake-pipeline"),
        Event(),
        Queue(),
        Queue(),
        None,
        "pipeline-selected",
        "pipeline-selected",
        "pipeline-selected",
        "pipeline-selected",
        "pipeline-selected",
        "pipeline-selected",
    )

    assert pipeline.get_stt_handler is not None
    assert handler.marker == "pipeline-selected"
