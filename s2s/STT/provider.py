"""Provider-neutral contract for the S2S speech-to-text stage.

The pipeline already uses queue-backed ``BaseHandler`` lifecycle semantics.  A
separate async provider framework would duplicate cancellation and turn-state
handling, so this protocol names the existing contract instead:

* construction/setup corresponds to provider ``start``;
* ``process(VADAudio)`` consumes PCM for a turn;
* a ``mode="final"`` VAD item requests finalization for that turn revision;
* speculative-turn/cancel filtering remains owned by ``BaseSTTHandler``;
* ``cleanup`` closes provider resources.
"""

from __future__ import annotations

from typing import Iterator, Protocol, runtime_checkable

from speech_to_speech.pipeline.handler_types import STTIn, STTOut


@runtime_checkable
class STTProvider(Protocol):
    """The selected-path STT contract used by the pipeline scheduler."""

    def setup(self, *args: object, **kwargs: object) -> None:
        """Initialize only the selected provider."""

    def process(self, audio: STTIn) -> Iterator[STTOut]:
        """Emit partial or final transcription items while preserving turn IDs."""

    def cleanup(self) -> None:
        """Release provider resources without changing pipeline cancel semantics."""
