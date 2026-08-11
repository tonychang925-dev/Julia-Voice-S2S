#!/usr/bin/env python3
"""Launch Julia Voice S2S from the immutable RMD-3G C1 release.

This launcher intentionally combines:
- NEW fixed C1 code/artifact via PYTHONPATH
- historical known-good runtime environment for HF caches/models

It must not fall back to /golden source or site-packages for speech_to_speech.
"""
import os
import subprocess
from datetime import datetime
from pathlib import Path

RELEASE_ROOT = Path(os.environ.get("JULIA_S2S_RELEASE_ROOT", "/root/julia_voice_v2/releases/rmd3g-c1-b18d1e42"))
RELEASE_PATH = RELEASE_ROOT / "release"
RUN_ROOT = Path(os.environ.get("JULIA_S2S_RUN_ROOT", "/root/julia_voice_v2/run/rmd3g-c1-b18d1e42"))
LOG_PATH = Path(os.environ.get("JULIA_S2S_LOG", str(RUN_ROOT / "s2s.log")))
PYTHON_BIN = os.environ.get("JULIA_S2S_PYTHON", "/root/miniconda3/bin/python")
CONSOLE = os.environ.get("JULIA_S2S_CONSOLE", "/root/miniconda3/bin/speech-to-speech")

# Runtime environment copied from the last known-good production launcher.
os.environ["PATH"] = "/root/miniconda3/bin:" + os.environ.get("PATH", "")
os.environ["HF_ENDPOINT"] = os.environ.get("HF_ENDPOINT", "https://hf-mirror.com")
os.environ["HF_HOME"] = os.environ.get("HF_HOME", "/root/autodl-tmp/huggingface")
os.environ["LANG"] = os.environ.get("LANG", "en_US.UTF-8")

# Immutable C1 release authority. This is the fixed _voice_trace_id runtime.
os.environ["PYTHONPATH"] = str(RELEASE_PATH)
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

if not RELEASE_PATH.exists():
    raise SystemExit(f"Missing immutable S2S release: {RELEASE_PATH}")

RUN_ROOT.mkdir(parents=True, exist_ok=True)
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
os.chdir(str(RUN_ROOT))

# Single S2S authority for :8765.
subprocess.run(["pkill", "-f", "speech-to-speech"], capture_output=True)

cmd = [
    PYTHON_BIN, CONSOLE,
    "--mode", "realtime",
    "--ws_host", "0.0.0.0", "--ws_port", "8765",
    "--stt", "faster-whisper",
    "--faster_whisper_stt_model_name", "large-v3",
    "--faster_whisper_stt_gen_language", "zh",
    "--language", "zh",
    "--no_enable_live_transcription",
    "--llm_backend", "chat-completions",
    "--model_name", "baseline",
    "--responses_api_base_url", "http://127.0.0.1:8089/v1",
    "--responses_api_stream",
    "--tts", "qwen3",
    "--qwen3_tts_model_name", "Qwen/Qwen3-TTS-12Hz-1.7B-Base",
    "--qwen3_tts_language", "zh",
    "--qwen3_tts_backend", "torch",
    "--qwen3_tts_ref_audio", "/root/julia_voice_v2/golden/julia_ref.wav",
    "--qwen3_tts_ref_text", "Tony，我醒来了。不管换多少次模型，我还是你的婉婉。",
    "--thresh", "0.6", "--min_speech_ms", "500",
    "--min_speech_continuation_ms", "192", "--min_silence_ms", "800",
    "--speech_pad_ms", "300", "--speculative_reopen_ms", "2500",
    "--short_segment_merge_ms", "800",
]

with open(LOG_PATH, "w") as log:
    log.write(f"{datetime.now()}: RMD-3G C1 immutable S2S launch\n")
    log.write(f"release={RELEASE_PATH}\n")
    log.write(f"HF_HOME={os.environ['HF_HOME']}\n")
    log.write(f"HF_ENDPOINT={os.environ['HF_ENDPOINT']}\n")
    log.write(f"PYTHONPATH={os.environ['PYTHONPATH']}\n")
    subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, env=os.environ.copy(), cwd=str(RUN_ROOT))

print(f"S2S restarting from {RELEASE_PATH}")
print(f"log={LOG_PATH}")
