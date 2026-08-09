# Julia Voice/S2S — Runtime Provenance Snapshot

**Generated**: 2026-08-09T17:00:24+08:00
**Host**: autodl-container-4d7d449e0f-15b65960
**Kernel**: 5.15.0-94-generic
**Status**: Repository bootstrap complete; runtime Golden baseline pending.

## Tags
- `voice-repo-bootstrap-20260809` — repository/governance bootstrap
- `voice-golden-pre-c1b-20260809` — pending runtime baseline import
- `voice-c1b-v1` — target


## Process Identity

### :7860 Frontend

- NOT RUNNING

### :8765 S2S

- NOT RUNNING

## :7860 Frontend Source

- path: `/root/julia_voice_v2/golden/frontend`
- commit: `17e7387577b1b2208c5bd2a246e44e6814a5f2a0`
- remote: `https://huggingface.co/spaces/smolagents/hf-realtime-voice`
- working_tree_dirty: true
- dirty_detail: staged=0 unstaged=0 untracked=1

### Untracked files
```
requirements.txt.installed
```

### Key file fingerprints

- `main.js`: sha256=`12234f68b52a15f714e28756aca2d77ef6249689cbed83dd29fb50249d8e52f1`
- `ws/s2s-ws-client.js`: sha256=`27beec2be4e946d87c97c33bedad1f3ecfa54eebd30ad064ce8fb53b22c8cb20`
- `index.html`: sha256=`cff913bd4646fd69d6afe802309dc6b286f062720ce02868ca9c1c259858390a`
- `server.py`: sha256=`4b07dff3e55b7aa78d13f60779e88ba4b7ff241023276b73d5bd1461bef8924d`

## :8765 S2S (speech-to-speech)

- package_path: `/root/miniconda3/lib/python3.10/site-packages/speech_to_speech/__init__.py`
- package_dir: `/root/miniconda3/lib/python3.10/site-packages/speech_to_speech`
- version: `0.2.12`
- dist_path: `/root/miniconda3/lib/python3.10/site-packages/speech_to_speech-0.2.12.dist-info`
- install_type: pypi

### Key module locations

- websocket_router: `/root/miniconda3/lib/python3.10/site-packages/speech_to_speech/api/openai_realtime/websocket_router.py`  
  sha256=`4e962f6dcdcb3f05486857db34557393332d8ae9e22c06478ed814001530bc93`
- runtime_config: `/root/miniconda3/lib/python3.10/site-packages/speech_to_speech/api/openai_realtime/runtime_config.py`  
  sha256=`7f7974a9908f2559c4af9129840122790314c5fc84f490b5caf2f8c213f5d44c`
- service: `/root/miniconda3/lib/python3.10/site-packages/speech_to_speech/api/openai_realtime/service.py`  
  sha256=`31b622c287c946a9604abd56e3531a898084cbd9ab7f53292db9d7146c63a7c2`
- chat_completions_handler: `/root/miniconda3/lib/python3.10/site-packages/speech_to_speech/LLM/chat_completions_language_model.py`  
  sha256=`4aef412253731a83f649bc79895e233faafc0874638e5efc923a44a49d56e90a`
- base_llm_handler: `/root/miniconda3/lib/python3.10/site-packages/speech_to_speech/LLM/base_openai_compatible_language_model.py`  
  sha256=`4718f762d3f45bb001296595f588610c0432057039b7de08f2636e0418901c59`

### Package tree fingerprint

- package_tree_sha256: `53e38870859a94c9ce08b53c788f9d98cdeef7f47222c0fa446f9f2a2c83b7fb`
- py_file_count: 94

## Launchers

- `/root/julia_voice_v2/golden/launch_s2s.py`  
  sha256=`ef5e9ada7e6fa466f5e74577e4a278a1a304ac172e0cd2541966b358ef0c5aef`
- `/root/julia_voice_v2/golden/start_frontend.sh`  
  sha256=`d911b8be377e75f6bf2dc8abb574adf5cbcd01a638c5f8d3572b62f5e5cffd77`

## Session


## Connectivity

- frontend_port: 7860
- s2s_port: 8765
- brain_target_port: 8089
- brain_local_port: 18089

## Verification Gates

- [ ] :7860 live PID → exact frontend runtime source → imported frontend/ → identical source/hash
- [ ] :8765 live PID → exact Python executable → exact speech_to_speech import path → imported s2s/ → identical source/hash
- [ ] Launcher live command → imported launcher → identical hash
- [ ] Dirty production modifications → preserved exactly

All four gates PASS → commit VOICE-GOLDEN-C0 → tag voice-golden-pre-c1b-20260809

