# VOICE-GOLDEN-C0.1 — Live Runtime Attestation

**Date**: 2026-08-09T17:02+08:00
**Host**: autodl-container-4d7d449e0f-15b65960

## :8765 S2S (speech-to-speech)

- **PID**: 1124
- **exe**: `/root/miniconda3/bin/python3.10`
- **cwd**: `/root/julia_voice_v2/golden`
- **import path**: `/root/miniconda3/lib/python3.10/site-packages/speech_to_speech/__init__.py`
- **version**: 0.2.12 (PyPI)
- **package_tree_sha256**: `53e38870859a94c9ce08b53c788f9d98cdeef7f47222c0fa446f9f2a2c83b7fb`
- **py_file_count**: 94

### Cmdline
```
speech-to-speech --mode realtime --ws_host 0.0.0.0 --ws_port 8765
  --stt faster-whisper --faster_whisper_stt_model_name large-v3
  --faster_whisper_stt_gen_language zh --language zh
  --llm_backend chat-completions --model_name baseline
  --responses_api_base_url http://127.0.0.1:8089/v1 --responses_api_stream
  --tts qwen3 --qwen3_tts_model_name Qwen/Qwen3-TTS-12Hz-1.7B-Base
  --qwen3_tts_language zh --qwen3_tts_backend torch
  --qwen3_tts_ref_audio /root/julia_voice_v2/golden/julia_ref.wav
  --thresh 0.6 --min_speech_ms 500 --min_silence_ms 800 --speech_pad_ms 300
```

## :7860 Frontend (hf-realtime-voice)

- **PID**: 1330
- **exe**: `/root/miniconda3/bin/python3.10`
- **cwd**: `/root/julia_voice_v2/golden/frontend`
- **commit**: `17e7387577b1b2208c5bd2a246e44e6814a5f2a0`
- **upstream**: `https://huggingface.co/spaces/smolagents/hf-realtime-voice`
- **dirty**: 1 untracked file (`requirements.txt.installed`)

### Key file hashes (live process cwd)
| File | SHA256 |
|------|--------|
| main.js | `12234f68b52a15f714e28756aca2d77ef6249689cbed83dd29fb50249d8e52f1` |
| ws/s2s-ws-client.js | `27beec2be4e946d87c97c33bedad1f3ecfa54eebd30ad064ce8fb53b22c8cb20` |
| server.py | `4b07dff3e55b7aa78d13f60779e88ba4b7ff241023276b73d5bd1461bef8924d` |

## Verification Gates

### Gate 1 — :7860 Live Process → Imported Source
- [x] Live PID 1330 → cwd `/root/julia_voice_v2/golden/frontend`
- [x] Imported `frontend/` from same path
- [x] Key file hashes match between live disk and imported Git

### Gate 2 — :8765 Live Process → Imported Source
- [x] Live PID 1124 → exe `/root/miniconda3/bin/python3.10`
- [x] Live Python import path = `/root/miniconda3/lib/python3.10/site-packages/speech_to_speech`
- [x] Imported `s2s/` from same path
- [x] package_tree_sha256 `53e38870...` match

### Gate 3 — Launcher Identity
- [x] launch_s2s.py SHA256 `ef5e9ada...` match
- [x] start_frontend.sh SHA256 `d911b8be...` match

### Gate 4 — Dirty Production Modifications
- [x] `requirements.txt.installed` preserved in imported frontend/

## Conclusion
```
ALL FOUR GATES PASS — this is a verified live runtime Golden Baseline.
The imported source in b2c7567 is proven to match the running processes.
```
