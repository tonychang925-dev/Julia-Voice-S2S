# Julia Voice GPU-less G1 STT Provider Boundary

Date: 2026-09-19

## Task

```text
TASK_ID
= JULIA-VOICE-GPULESS-G1-STT-PROVIDER-BOUNDARY
```

## Source Baseline

```text
REPO
= tonychang925-dev/Julia-Voice-S2S

BRANCH
= voice-el-p1-hosted-product-integration

BASE_SHA
= 4c55d75d61dd0718c5bbd766c99e797e24242797

CANDIDATE_SHA
= assigned by the G1 delivery-closure commit; it is not the base SHA

WORKTREE_STATUS
= source clean before G1; pre-existing untracked docs/voice-el-p1-node2 evidence retained
```

The exact SHA resolves on both the local candidate branch and
`origin/experiment/voice-elevenlabs-p0`.

## GPU / STT Dependency Map

| Location | Evidence | Classification |
|---|---|---|
| `s2s/s2s_pipeline.py` | imports only `FasterWhisperSTTHandlerArguments` | runtime configuration; no `faster_whisper` import |
| `s2s/s2s_pipeline.py` | `_get_handlers` calls `get_stt_handler` | selected-provider dispatch boundary |
| `s2s/s2s_pipeline.py` | imports generic `torch` for the current monolithic runtime | generic runtime import; no CUDA initialization at import |
| `s2s/STT/provider.py` | `STTProvider` protocol | provider boundary |
| `s2s/STT/provider_factory.py` | selector-to-handler registry | selected-path lazy import factory |
| `s2s/STT/provider_factory.py` | `faster-whisper` registry entry | selected-provider import target |
| `s2s/STT/faster_whisper_handler.py` | module-level `from faster_whisper import WhisperModel` | selected-provider import |
| `s2s/STT/faster_whisper_handler.py` | `WhisperModel(...)` in `setup` | selected-path model initialization |
| `s2s/STT/faster_whisper_handler.py.bak` | retained historical backup | non-runtime legacy file |
| `s2s/arguments_classes/faster_whisper_stt_arguments.py` | model/device/compute/language fields | inert runtime configuration |
| `deploy/experiment/runtime.args` | `faster-whisper`, `large-v3`, `zh` | frozen deployment configuration |
| `deploy/autodl/launch_s2s.py`, `deploy/autodl/bin/start-julia-voice` | same frozen selector/model | deployment configuration |
| `deploy/experiment/native_gate.py` | passes argument objects and substitutes a test STT stage | native-gate composition/test-only |
| `s2s/STT/parakeet_tdt_handler.py` | `torch.cuda` availability checks | other selected-provider initialization |
| `s2s/STT/whisper_stt_handler.py` | CUDA event timing | other selected-provider benchmark path |
| `s2s/LLM/language_model.py`, TTS handlers | device/CUDA handling | unrelated selected LLM/TTS paths, unchanged by G1 |
| `s2s/STT/paraformer_handler.py` | optional GPU model initialization | other selected-provider path |
| tests | import guards and fake provider | test-only |

No source module directly imports `ctranslate2`; it is a transitive dependency of
the selected `faster_whisper` path only.

## Provider Contract

The repository already owns queue-backed handler lifecycle semantics. G1
therefore does not introduce a parallel async framework. `STTProvider` names
the existing selected-path contract:

```text
construction/setup
= provider start

process(VADAudio)
= PCM 16000 audio processing

VADAudio.mode="final"
= turn finalization request

BaseSTTHandler/speculative-turn filtering
= cancel and stale-turn semantics

cleanup()
= provider close
```

`STTIn` is the existing `VADAudio` and carries:

```text
audio
turn_id
turn_revision
runtime_config
mode
```

`STTOut` remains `PartialTranscription | Transcription` and carries:

```text
text
partial/final classification by message type
turn_id
turn_revision
```

Provider-specific metadata remains provider-owned. It must not become a
Brain/Core or canonical-conversation dependency. A future provider can add
typed metadata only at the STT boundary if runtime evidence requires it.

## Implementation

- Added `s2s/STT/provider.py`.
- Added selected-path registry and construction in `s2s/STT/provider_factory.py`.
- Replaced direct provider branching in `s2s/s2s_pipeline.py` with factory delegation.
- Preserved `--stt faster-whisper` as the backward-compatible provider selector.
- Preserved model, language, `device=auto`, and `compute_type=auto` behavior.
- Added only a test-local fake provider; no cloud STT provider was added.

Current production provider registry remains:

```text
whisper
whisper-mlx
mlx-audio-whisper
paraformer
faster-whisper
parakeet-tdt
```

No Scribe, Deepgram, OpenAI STT, or Google STT implementation is present.

## Isolation Result

```text
UNCONDITIONAL_FASTER_WHISPER_IMPORTS_IN_ORCHESTRATION
= 0

UNCONDITIONAL_WHISPER_MODEL_INITIALIZATIONS_IN_ORCHESTRATION
= 0

FASTER_WHISPER_HANDLER_IMPORT
= selected-path only

FASTER_WHISPER_WHEEL_IMPORT
= selected-path only

CTRANSLATE2_IMPORT
= selected-path transitive only
```

The fake-provider test blocks both `faster_whisper` and `ctranslate2` with
import sentinels. It then constructs a non-Whisper provider through the real
pipeline selector and verifies turn identity preservation.

## Regression Evidence

Targeted regression and provider-boundary suite:

```text
pytest tests/test_stt_provider_boundary.py \
  tests/test_elevenlabs_arguments.py \
  tests/test_elevenlabs_integration.py \
  tests/test_elevenlabs_tts_handler.py \
  tests/test_elevenlabs_wiring.py

RESULT
= 35 passed, 2 skipped
```

Provider-boundary suite:

```text
pytest tests/test_stt_provider_boundary.py

RESULT
= 3 passed
```

Full local Python suite:

```text
RESULT
= 105 passed, 2 skipped, 5 pre-existing failures
```

The five failures were reproduced against the frozen base in an isolated
temporary worktree before delivery closure. They are confined to
`turn_id`/`extra_body` observability expectations in:

```text
tests/test_cc1_c3_canonical_id_observability.py
tests/test_rmd3g_observability.py
```

No file in that LLM request path was changed by G1. The failures are therefore
not attributable to this STT boundary change.

## Acceptance

```text
STT_PROVIDER_BOUNDARY
= ESTABLISHED

FASTER_WHISPER_PATH
= REGRESSION PASS

GPU_STT_IMPORT
= SELECTED-PATH ONLY

WHISPER_MODEL_INITIALIZATION
= SELECTED-PATH ONLY

NON_GPU_PROVIDER_TEST_PIPELINE
= PASS

CUDA_VISIBLE_DEVICES_EMPTY_ORCHESTRATION
= PASS

BRAIN_CONTRACT_CHANGED
= NO

CORE_CONTRACT_CHANGED
= NO

TTS_PATH_CHANGED
= NO

CANONICAL_SEMANTICS_CHANGED
= NO

SOURCE_CODE_CHANGED
= YES

PACKAGES_CHANGED
= NO
```

## Disposition

```text
RESULT
= G1_STT_PROVIDER_BOUNDARY_PASS
```

Stop here. ElevenLabs Scribe Realtime integration is not authorized by G1 and
must wait for Owner + Mira architecture review.
