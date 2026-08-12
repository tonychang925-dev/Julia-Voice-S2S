# Julia Voice Production Runbook

Last updated: 2026-08-12

## 1. Deployment model

Deployment is **manual**. There is no automated deployment tool.

The only automated piece is the verification gate: `verify_deployment <sha>`.

### Deploy steps

1. Build sealed artifact from exact remote commit (on Mac):
   ```bash
   cd /Users/admin/Julia-Voice-S2S
   python3 scripts/build_s2s_release.py /tmp/s2s_rcp
   ```

2. Transfer to AutoDL:
   ```bash
   scp -P 42819 /tmp/s2s_rcp/speech_to_speech-obs-*.tar.gz \
                /tmp/s2s_rcp/manifest.json \
                root@connect.nmb2.seetacloud.com:/tmp/
   ```

3. On AutoDL, extract to a new release directory:
   ```bash
   ARCHIVE_NAME="speech_to_speech-obs-<hash>"
   RELEASE="/root/julia_voice_v2/releases/${ARCHIVE_NAME}"
   mkdir -p "$RELEASE/release"
   cd "$RELEASE/release"
   tar xzf /tmp/${ARCHIVE_NAME}.tar.gz
   cp /tmp/manifest.json "$RELEASE/"
   cp /tmp/${ARCHIVE_NAME}.tar.gz "$RELEASE/"
   ```

4. Stop old services:
   ```bash
   pkill -f "8765.*uvicorn" || true
   pkill -f "7860.*uvicorn" || true
   ```

5. Start both services **from the same release directory**:
   ```bash
   # S2S (:8765)
   cd "$RELEASE/release"
   /root/miniconda3/bin/python -m speech_to_speech \
     --mode realtime --ws_host 0.0.0.0 --ws_port 8765 \
     ... (full args)

   # Frontend (:7860)
   cd "$RELEASE/release/frontend"
   /root/miniconda3/bin/python -m uvicorn server:app --host 0.0.0.0 --port 7860
   ```

6. Set `current` symlink:
   ```bash
   ln -sfn "$RELEASE" /root/julia_voice_v2/releases/current
   ```

7. Verify:
   ```bash
   /opt/julia/bin/verify_deployment <expected_git_sha>
   ```

### Verification gate

`verify_deployment <sha>` checks 5 things:

| # | Check | What it proves |
|---|---|---|
| 1 | manifest source_commit = expected SHA | Release content matches Git |
| 2 | :7860 cwd = current/release/frontend | Frontend runs from this release |
| 3 | :7860 served main.js SHA = manifest | Browser bytes match sealed release |
| 4 | :8765 PYTHONPATH = current/release | S2S loads code from this release |
| 5 | 0 stale processes from old releases | No old code still running |

Output:
```
DEPLOYMENT VERIFIED
```
or:
```
DEPLOYMENT MISMATCH
DO NOT TEST
```

**Rule: never test Julia until DEPLOYMENT VERIFIED.**

---

## 2. External runtime assets

| Asset | Path | SHA256 |
|---|---|---|
| Ref audio | `/root/julia_voice_v2/golden/julia_ref.wav` | `48d65eba7f4c76259dcd3d5106fd6579cb80c3e8621c08c2ab13ba60460324fc` |
| Silero VAD | `/root/.cache/torch/hub/snakers4_silero-vad_master` | JIT `e1122837f...` |
| Smart Turn | `/root/autodl-tmp/huggingface/hub/models--pipecat-ai--smart-turn-v3/snapshots/f766f81d` | ONNX `2bb02631...` |
| Qwen3-TTS | `/root/autodl-tmp/huggingface/hub/models--Qwen--Qwen3-TTS-12Hz-1.7B-Base/snapshots/fd4b2543` | config `b4f01752...` |

---

## 3. Connect to AutoDL

```bash
ssh -i /Users/admin/.ssh/autodl_ed25519.BACKUP -p 42819 root@connect.nmb2.seetacloud.com
```

## 4. Check health

```bash
curl -s http://127.0.0.1:8765/health
```

## 5. Check release identity

```bash
readlink -f /root/julia_voice_v2/releases/current
python3 -c "import json; print(json.load(open('/root/julia_voice_v2/releases/current/manifest.json'))['source_commit'][:12])"
```

## 6. Logs

```bash
tail -f /var/log/julia/julia-voice.log
tail -f /var/log/julia/julia-voice.err
```

## 7. Prohibited

- Do not start :7860 and :8765 from different release directories
- Do not test Julia until `verify_deployment <sha>` returns DEPLOYMENT VERIFIED
- Do not edit source files on the server
- Do not pip install during startup
