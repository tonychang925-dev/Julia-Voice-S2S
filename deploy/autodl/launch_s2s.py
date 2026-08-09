#!/usr/bin/env python3
import subprocess, os
from datetime import datetime

os.environ["PATH"] = "/root/miniconda3/bin:" + os.environ.get("PATH", "")
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
os.environ["HF_HOME"] = "/root/autodl-tmp/huggingface"
os.environ["LANG"] = "en_US.UTF-8"
os.chdir("/root/julia_voice_v2/golden")

subprocess.run(["pkill", "-f", "speech-to-speech"], capture_output=True)

cmd = [
    "speech-to-speech", "--mode", "realtime",
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
with open("logs/s2s.log", "w") as log:
    log.write(f"{datetime.now()}: GOLDEN S2S + Julia ElevenLabs voice ref\n")
    subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT)
print("S2S restarting")
