# Julia Voice RMD-3G Production Runbook

Last updated: 2026-08-11

This runbook describes the current production operation model for Julia Voice S2S on AutoDL after RMD-3G C1 recovery.

## 1. Current production authority

### Voice / S2S

- Source authority: `1552470f3f8f4e33a9cb90181daa1353f0702eb2`
- Artifact authority: `b18d1e42ca2e1383829b6d5f0670652efa066944ba92823a815a35253291c9ac`
- Immutable release: `/root/julia_voice_v2/releases/rmd3g-c1-b18d1e42`
- Release import root: `/root/julia_voice_v2/releases/rmd3g-c1-b18d1e42/release`
- Target Python: `/root/miniconda3/bin/python`
- Service port: `0.0.0.0:8765`
- Realtime endpoint: `ws://<server>:8765/v1/realtime`

Critical runtime file hashes:

| File | SHA256 |
|---|---|
| `speech_to_speech/LLM/base_openai_compatible_language_model.py` | `2f904a05128d5b11c92e6a2bd04769cd12c6e06f3a66e7d23dbb09b7eb34004c` |
| `speech_to_speech/LLM/chat_completions_language_model.py` | `725db87b6313a2cc601173be751ea8bca258eb2c601450ac4a0e273f92acb621` |
| `speech_to_speech/api/openai_realtime/websocket_router.py` | `12769ece09b8da10f6ea7be06064cb37dc58d8a41026d8d47bfe1d6ecd0c033c` |

### Brain

- Brain authority: `9c8764af35c702a60d778b2148846d7728794f30`
- Runtime endpoint used by S2S: `http://127.0.0.1:8089/v1`
- Current bridge: AutoDL local `:8089` reaches Brain `:18089` through SSH tunnel.

Note: Brain runtime convergence should be verified separately by loaded module path/SHA, not only by repository HEAD.

## 2. External runtime assets

These assets are runtime dependencies, not S2S source files.

| Asset | Path / identity | SHA256 / revision |
|---|---|---|
| Ref audio | `/root/julia_voice_v2/golden/julia_ref.wav` | `48d65eba7f4c76259dcd3d5106fd6579cb80c3e8621c08c2ab13ba60460324fc` |
| Silero cache | `/root/.cache/torch/hub/snakers4_silero-vad_master` | JIT `e1122837f4154c511485fe0b9c64455f7b929c96fbb8d79fbdb336383ebd3720` |
| Smart Turn | `/root/autodl-tmp/huggingface/hub/models--pipecat-ai--smart-turn-v3/snapshots/f766f81d3cfdf7737ac64aad813d91bbfd56bf93` | ONNX `2bb026316b14a660486a75b1733cd3fbab8c2fd0314dc9af7be49f8cca967e4f` |
| Qwen3-TTS | `/root/autodl-tmp/huggingface/hub/models--Qwen--Qwen3-TTS-12Hz-1.7B-Base/snapshots/fd4b254389122332181a7c3db7f27e918eec64e3` | config `b4f01752d15a488abde3e1ab44723ae4f4b9e68a4037257b098b3737893cc1f9`; model `38fc7fc51c5e776e840414b6fd443962e9411b9654888fd7913e4da643cb857c` |

Production boot must use existing cache/assets. It must not download models during normal service startup.

## 3. Production lifecycle files

Version-controlled templates live under `deploy/autodl/` and are deployed to AutoDL as follows:

| Repo path | Server path | Purpose |
|---|---|---|
| `deploy/autodl/julia-voice.env` | `/etc/julia/julia-voice.env` | Canonical non-interactive runtime environment |
| `deploy/autodl/bin/julia-voice-preflight` | `/opt/julia/bin/julia-voice-preflight` | Fail-fast asset/config validation |
| `deploy/autodl/bin/start-julia-voice` | `/opt/julia/bin/start-julia-voice` | Canonical S2S launcher; `exec`s real Python process |
| `deploy/autodl/bin/julia-voice-health` | `/opt/julia/bin/julia-voice-health` | Local readiness check |
| `deploy/autodl/bin/julia-voice-watchdog` | `/opt/julia/bin/julia-voice-watchdog` | Health watchdog; terminates unhealthy supervised S2S PID |
| `deploy/autodl/bin/bootstrap-julia-voice-supervisor` | `/opt/julia/bin/bootstrap-julia-voice-supervisor` | Detached supervisor bootstrap |
| `deploy/autodl/supervisor/julia-voice.conf` | `/etc/supervisor/conf.d/julia-voice.conf` | Process supervisor config |
| `deploy/autodl/boot.sh` | `/root/boot.sh`, `/root/autodl_boot.sh` | AutoDL boot hook |

Do not edit these files directly on the server except during an approved deployment from the version-controlled repo.

## 4. Canonical environment

Production environment is defined by `/etc/julia/julia-voice.env`.

Required values include:

```bash
JULIA_S2S_RELEASE_ROOT=/root/julia_voice_v2/releases/rmd3g-c1-b18d1e42
JULIA_S2S_RUN_ROOT=/root/julia_voice_v2/run/rmd3g-c1-b18d1e42
JULIA_S2S_PYTHON=/root/miniconda3/bin/python
JULIA_S2S_CONSOLE=/root/miniconda3/bin/speech-to-speech

HF_HOME=/root/autodl-tmp/huggingface
HF_ENDPOINT=https://hf-mirror.com
PYTHONDONTWRITEBYTECODE=1
PYTHONPATH=/root/julia_voice_v2/releases/rmd3g-c1-b18d1e42/release
LANG=en_US.UTF-8

BRAIN_BASE_URL=http://127.0.0.1:8089/v1
S2S_HOST=0.0.0.0
S2S_PORT=8765
REF_AUDIO=/root/julia_voice_v2/golden/julia_ref.wav
```

Do not rely on interactive shell files such as `.bashrc` or manual `export` commands.

## 5. Supervisor and watchdog model

AutoDL container PID 1 is not systemd. Julia Voice uses a dedicated supervisord instance:

```text
/usr/bin/supervisord -c /etc/supervisor/conf.d/julia-voice.conf
```

Expected process tree:

```text
supervisord
├── /root/miniconda3/bin/python /root/miniconda3/bin/speech-to-speech ...
└── /root/miniconda3/bin/python3 /opt/julia/bin/julia-voice-watchdog
```

Key behavior:

- S2S process death: supervisor restarts it.
- S2S alive but unhealthy: watchdog observes health failures and terminates the supervised S2S PID; supervisor restarts it.
- Watchdog does not spawn S2S directly.
- Exactly one process may own `:8765`.
- Qwen3-TTS cold initialization may take 10+ minutes.
- Watchdog startup grace: `900s`.
- Supervisor `startsecs`: `900s`.

## 6. Normal operations

### Connect to AutoDL

```bash
ssh -i /Users/admin/.ssh/autodl_ed25519.BACKUP -p 42819 root@connect.nmb2.seetacloud.com
```

### Check current health

```bash
/opt/julia/bin/julia-voice-health
```

Expected:

```text
READY
```

### Check process status

```bash
ps -ef | grep -E 'julia-voice|speech-to-speech|supervisord' | grep -v grep
cat /tmp/julia-voice-supervisor/supervisord.pid
cat /tmp/julia-voice-supervisor/s2s.pid
```

Expected:

- one dedicated supervisord process using `/etc/supervisor/conf.d/julia-voice.conf`
- one S2S process
- one watchdog process

### Check port owner

```bash
/root/miniconda3/bin/python3 - <<'PY'
import os
owners=[]
for line in open('/proc/net/tcp'):
    p=line.split()
    if len(p)>9 and p[1].endswith(':223D') and p[3]=='0A':
        inode=p[9]
        for pid in filter(str.isdigit, os.listdir('/proc')):
            try: fds=os.listdir(f'/proc/{pid}/fd')
            except Exception: continue
            for fd in fds:
                try: t=os.readlink(f'/proc/{pid}/fd/{fd}')
                except Exception: continue
                if t==f'socket:[{inode}]': owners.append((pid, fd, inode))
print(owners)
PY
```

Expected: exactly one owner, matching `/tmp/julia-voice-supervisor/s2s.pid`.

### Start supervisor manually if boot hook did not run

```bash
/opt/julia/bin/bootstrap-julia-voice-supervisor
```

This starts the supervisor detached. Do not manually run `speech-to-speech`.

### Stop Julia Voice cleanly

```bash
kill "$(cat /tmp/julia-voice-supervisor/supervisord.pid)"
```

This stops the dedicated supervisor and its managed S2S/watchdog processes.

### Restart Julia Voice cleanly

```bash
kill "$(cat /tmp/julia-voice-supervisor/supervisord.pid)"
sleep 5
rm -f /tmp/julia-voice-supervisor/supervisord.pid /tmp/julia-voice-supervisor/s2s.pid
/opt/julia/bin/bootstrap-julia-voice-supervisor
```

Then wait for health:

```bash
while true; do date; /opt/julia/bin/julia-voice-health && break; sleep 30; done
```

Do not treat `UNHEALTHY ConnectionRefusedError` during the first several minutes as failure; cold model initialization can take 10+ minutes.

## 7. Logs

Primary logs:

```bash
tail -f /var/log/julia/julia-voice.log
tail -f /var/log/julia/julia-voice.err
tail -f /var/log/julia/julia-voice-watchdog.log
tail -f /var/log/julia/supervisord.log
tail -f /var/log/julia/bootstrap-supervisord.log
```

Important startup milestones in logs:

- `PRECHECK OK`
- `Loaded Smart Turn v3.2 ...`
- `Using cache found in /root/.cache/torch/hub/snakers4_silero-vad_master`
- `ChatCompletionsApiModelHandler warmed up`
- `Qwen3-TTS model loaded`
- `Qwen3TTSHandler warmed up`
- `OpenAI Realtime API starting on ws://0.0.0.0:8765/v1/realtime`
- `Uvicorn running on http://0.0.0.0:8765`

Watchdog milestones:

- During cold start: `watchdog startup grace: service not READY yet; no restart (.../900s)`
- After ready: `watchdog observed READY; failure counting enabled`

## 8. Preflight and asset validation

Run preflight manually:

```bash
/opt/julia/bin/julia-voice-preflight
```

Expected:

```text
PRECHECK OK
```

If preflight fails, do not start S2S. Fix the missing runtime asset/config through the normal deployment process.

## 9. Loaded code verification

Run from AutoDL:

```bash
REL=/root/julia_voice_v2/releases/rmd3g-c1-b18d1e42/release
sha256sum \
  "$REL/speech_to_speech/LLM/base_openai_compatible_language_model.py" \
  "$REL/speech_to_speech/LLM/chat_completions_language_model.py" \
  "$REL/speech_to_speech/api/openai_realtime/websocket_router.py"
```

Expected:

```text
2f904a05128d5b11c92e6a2bd04769cd12c6e06f3a66e7d23dbb09b7eb34004c  base_openai_compatible_language_model.py
725db87b6313a2cc601173be751ea8bca258eb2c601450ac4a0e273f92acb621  chat_completions_language_model.py
12769ece09b8da10f6ea7be06064cb37dc58d8a41026d8d47bfe1d6ecd0c033c  websocket_router.py
```

To inspect the running process environment:

```bash
PID=$(cat /tmp/julia-voice-supervisor/s2s.pid)
tr '\0' '\n' < /proc/$PID/environ | grep -E '^(PYTHONPATH|HF_HOME|HF_ENDPOINT|PYTHONDONTWRITEBYTECODE|LANG|PATH)='
```

## 10. Boot behavior

AutoDL boot hooks installed:

- `/root/boot.sh`
- `/root/autodl_boot.sh`

Both execute:

```bash
/opt/julia/bin/bootstrap-julia-voice-supervisor
```

After server/container boot, expected lifecycle:

```text
boot hook
→ detached supervisord
→ preflight
→ S2S cold model loading
→ watchdog grace, no restart
→ :8765 binds
→ health READY
→ Electron can connect
```

## 11. Watchdog acceptance test

This intentionally interrupts service and may require another cold model load. Only run when Tony approves a service interruption.

```bash
PID=$(cat /tmp/julia-voice-supervisor/s2s.pid)
kill "$PID"
```

Expected:

- supervisor starts a new S2S PID
- watchdog remains single-instance
- `:8765` eventually returns
- `/opt/julia/bin/julia-voice-health` returns `READY`
- no duplicate `:8765` listener

## 12. Clean reboot acceptance test

This interrupts service and may take 10+ minutes before READY. Only run when Tony approves a reboot/restart test.

Expected acceptance:

1. Server/container restarts through normal AutoDL lifecycle.
2. No SSH manual export.
3. No manual Python command.
4. Boot hook starts supervisor.
5. Supervisor starts S2S.
6. Models initialize from existing caches.
7. `:8765` becomes READY.
8. Tony opens Electron and hears Julia reply.

## 13. Troubleshooting

### Electron cannot connect

Check:

```bash
/opt/julia/bin/julia-voice-health
ps -ef | grep -E 'julia-voice|speech-to-speech|supervisord' | grep -v grep
tail -80 /var/log/julia/julia-voice.err
```

If service has been started recently, wait through cold model initialization. Do not restart during the first 10+ minutes unless logs show a fatal exception.

### Watchdog repeatedly restarts during startup

Expected config:

- `JULIA_VOICE_WATCHDOG_STARTUP_GRACE="900"`
- `startsecs=900`

Verify:

```bash
grep -E 'STARTUP_GRACE|startsecs' /etc/supervisor/conf.d/julia-voice.conf
tail -80 /var/log/julia/julia-voice-watchdog.log
```

If grace is missing, deploy the current version-controlled supervisor/watchdog files.

### S2S attempts model download

This indicates environment/cache binding drift. Verify:

```bash
cat /etc/julia/julia-voice.env
echo "$HF_HOME"
ls -ld /root/autodl-tmp/huggingface /root/.cache/torch /root/.cache/torch/hub
```

Do not allow production startup to create a new unreviewed model baseline.

### Brain unreachable from S2S

S2S uses:

```text
BRAIN_BASE_URL=http://127.0.0.1:8089/v1
```

Check SSH tunnel and Brain health on Mac side. Do not change S2S source for tunnel failures.

### Duplicate S2S processes

Expected: exactly one S2S process and exactly one `:8765` listener.

If duplicate processes exist:

1. Identify which PID owns `:8765`.
2. Stop unmanaged/manual S2S processes.
3. Keep only supervisor-managed S2S.
4. Do not start S2S manually.

## 14. Prohibited production actions

Do not:

- edit S2S source directly on AutoDL
- patch site-packages
- manually run `python launch_s2s.py` as production
- use tmux/screen/nohup as production lifecycle authority
- download new model files during normal startup
- point `PYTHONPATH` at a development worktree
- run duplicate S2S services on `:8765`
- treat process existence as readiness

Normal production lifecycle authority is:

```text
AutoDL boot hook
→ /opt/julia/bin/bootstrap-julia-voice-supervisor
→ /usr/bin/supervisord -c /etc/supervisor/conf.d/julia-voice.conf
→ /opt/julia/bin/start-julia-voice
→ immutable Julia Voice release
```

## 15. Final operator checklist

Use this checklist after any production restart or deployment:

```bash
/opt/julia/bin/julia-voice-preflight
/opt/julia/bin/julia-voice-health
ps -ef | grep -E 'julia-voice|speech-to-speech|supervisord' | grep -v grep
cat /tmp/julia-voice-supervisor/supervisord.pid
cat /tmp/julia-voice-supervisor/s2s.pid
tr '\0' '\n' < /proc/$(cat /tmp/julia-voice-supervisor/s2s.pid)/environ | grep -E '^(PYTHONPATH|HF_HOME|HF_ENDPOINT|PYTHONDONTWRITEBYTECODE|LANG|PATH)='
```

Then perform one human E2E check:

```text
Electron → speak one sentence → Julia replies with audio
```

Production is acceptable only when Tony can hear Julia reply after unattended startup.
