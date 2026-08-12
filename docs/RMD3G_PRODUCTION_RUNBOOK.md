# Julia Voice RCP Production Runbook

Last updated: 2026-08-11

This runbook describes the current production operation model for Julia Voice S2S + Frontend on AutoDL under RCP (Release Control Plane).

## 1. Current production authority

### RCP: Unified Release (CANONICAL)

RCP replaces the split-release RMD3G model. Frontend (:7860) and S2S (:8765) are deployed from a SINGLE immutable artifact. Split-brain deployment is structurally impossible.

- Build authority: `scripts/build_s2s_release.py` (deterministic, git-provenance)
- Activation authority: `deploy/autodl/bin/julia-release-activate` (atomic current symlink)
- Verification authority: `deploy/autodl/bin/julia-runtime-attest` (runtime attestation gate)
- Source branch: `codex/bugfix/workbench-intelligence-binding`
- Release root: `/root/julia_voice_v2/releases/current`
- Run root: `/root/julia_voice_v2/run/current`
- Target Python: `/root/miniconda3/bin/python`
- S2S port: `0.0.0.0:8765`
- Frontend port: `0.0.0.0:7860`
- Realtime endpoint: `ws://<server>:8765/v1/realtime`

### Release structure

```
/root/julia_voice_v2/releases/
├── current → speech_to_speech-obs-<hash>/   (atomic symlink)
├── .previous                                  (rollback target)
└── speech_to_speech-obs-<hash>/
    ├── manifest.json                          (complete file manifest with SHA256)
    ├── speech_to_speech-obs-<hash>.tar.gz     (sealed archive)
    └── release/                               (PYTHONPATH — extracted archive)
        ├── speech_to_speech/                  (S2S code)
        └── frontend/                          (served by :7860)
```

### Build provenance chain

```
SOURCE COMMIT (remote, pushed)
  → build_s2s_release.py (reads exact git commit, never ambient worktree)
  → speech_to_speech-obs-<hash>.tar.gz (deterministic, reproducible)
  → manifest.json (SHA256 of every file)
```

### Deployment chain

```
ARTIFACT → Extract → julia-release-activate (read-only seal, atomic symlink)
  → supervisor restarts from current/
  → julia-runtime-attest (PID bytes vs manifest — ALL SAME = YES)
```

### Key invariants

1. CODE → GIT → ARTIFACT → SERVER → PID must ALL match
2. Same release root for :7860 and :8765 — split-brain structurally prevented
3. Releases are content-addressed, immutable after seal
4. Atomic `current` symlink swap — no partial deploys
5. Runtime attestation gate must PASS before any E2E testing

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
| `deploy/autodl/bin/julia-release-activate` | `/opt/julia/bin/julia-release-activate` | Atomic release activation (symlink swap, read-only seal) |
| `deploy/autodl/bin/julia-runtime-attest` | `/opt/julia/bin/julia-runtime-attest` | Runtime attestation gate (PID bytes vs manifest) |
| `deploy/autodl/supervisor/julia-voice.conf` | `/etc/supervisor/conf.d/julia-voice.conf` | Process supervisor config |
| `deploy/autodl/boot.sh` | `/root/boot.sh`, `/root/autodl_boot.sh` | AutoDL boot hook |
| `deploy/autodl/start_frontend.sh` | `/opt/julia/bin/start-julia-frontend` | :7860 frontend launcher |

Do not edit these files directly on the server except during an approved deployment from the version-controlled repo.

## 4. Canonical environment

Production environment is defined by `/etc/julia/julia-voice.env`. Under RCP, this file is generated by `julia-release-activate` and uses the `current` symlink:

```bash
JULIA_S2S_CURRENT=/root/julia_voice_v2/releases/current
JULIA_S2S_RUN_ROOT=/root/julia_voice_v2/run/current
JULIA_S2S_LOG=/root/julia_voice_v2/run/current/s2s.log
JULIA_S2S_PYTHON=/root/miniconda3/bin/python
JULIA_S2S_CONSOLE=/root/miniconda3/bin/speech-to-speech

HF_HOME=/root/autodl-tmp/huggingface
HF_ENDPOINT=https://hf-mirror.com
PYTHONDONTWRITEBYTECODE=1
PYTHONPATH=/root/julia_voice_v2/releases/current/release
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
├── /root/miniconda3/bin/python /root/miniconda3/bin/speech-to-speech ...   (:8765 S2S)
├── /root/miniconda3/bin/python3 /opt/julia/bin/julia-voice-watchdog        (watchdog)
└── /root/miniconda3/bin/python -m uvicorn server:app ...                   (:7860 frontend)
```

Key behavior:

- S2S process death: supervisor restarts it.
- S2S alive but unhealthy: watchdog observes health failures and terminates the supervised S2S PID; supervisor restarts it.
- Frontend process (:7860) is also supervisor-managed.
- Watchdog does not spawn S2S directly.
- Exactly one process may own `:8765`; exactly one may own `:7860`.
- Qwen3-TTS cold initialization may take 10+ minutes.
- Watchdog startup grace: `900s`.
- Supervisor `startsecs`: `900s`.

## 6. Runtime attestation (NEW — RCP gate)

After any deployment or restart, run the attestation gate:

```bash
/opt/julia/bin/julia-runtime-attest
```

This verifies:
- :7860 cwd in current release
- :7860 served main.js SHA matches manifest
- :7860 served s2s-ws-client.js SHA matches manifest
- :8765 PYTHONPATH in current/release
- :8765 health = READY
- No stale processes

Expected output:

```text
=== RUNTIME ATTESTATION ===
release: /root/julia_voice_v2/releases/speech_to_speech-obs-<hash>
  ✅ :7860 cwd in current
  ✅ :7860 served main.js
  ✅ :7860 disk main.js
  ✅ :7860 served s2s-ws-client.js
  ✅ :8765 PYTHONPATH in current
  ✅ :8765 health
  ✅ stale processes
✅ RUNTIME ATTESTATION: PASS
```

ANY mismatch → FAIL. Do not proceed to E2E testing on FAIL.

## 7. Normal operations

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
ps -ef | grep -E 'julia-voice|speech-to-speech|supervisord|uvicorn' | grep -v grep
cat /tmp/julia-voice-supervisor/supervisord.pid
cat /tmp/julia-voice-supervisor/s2s.pid
```

Expected:

- one dedicated supervisord process using `/etc/supervisor/conf.d/julia-voice.conf`
- one S2S process (:8765)
- one frontend uvicorn process (:7860)
- one watchdog process

### Check port owners

```bash
ss -tlnp | grep -E '8765|7860'
```

Expected: `:8765` owned by S2S PID, `:7860` owned by uvicorn PID.

### Start supervisor manually if boot hook did not run

```bash
/opt/julia/bin/bootstrap-julia-voice-supervisor
```

This starts the supervisor detached. Do not manually run `speech-to-speech` or `uvicorn`.

### Stop Julia Voice cleanly

```bash
kill "$(cat /tmp/julia-voice-supervisor/supervisord.pid)"
```

This stops the dedicated supervisor and its managed S2S/watchdog/frontend processes.

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

## 8. Deployment: Activating a new RCP release

### Build (on Mac)

```bash
cd /Users/admin/Julia-Voice-S2S
python3 scripts/build_s2s_release.py /tmp/s2s_rcp
```

### Transfer to AutoDL

```bash
scp -i /Users/admin/.ssh/autodl_ed25519.BACKUP -P 42819 \
  /tmp/s2s_rcp/speech_to_speech-obs-*.tar.gz \
  /tmp/s2s_rcp/manifest.json \
  root@connect.nmb2.seetacloud.com:/tmp/
```

### Extract and activate (on AutoDL)

```bash
# Extract
ARCHIVE_NAME="speech_to_speech-obs-<hash>"
mkdir -p /root/julia_voice_v2/releases/${ARCHIVE_NAME}/release
cd /root/julia_voice_v2/releases/${ARCHIVE_NAME}/release
tar xzf /tmp/${ARCHIVE_NAME}.tar.gz
cp /tmp/manifest.json /root/julia_voice_v2/releases/${ARCHIVE_NAME}/
cp /tmp/${ARCHIVE_NAME}.tar.gz /root/julia_voice_v2/releases/${ARCHIVE_NAME}/

# Copy frontend for :7860 serving (if needed)
cp -r /root/julia_voice_v2/releases/${ARCHIVE_NAME}/release/frontend \
     /root/julia_voice_v2/releases/${ARCHIVE_NAME}/frontend

# Atomic activation
/opt/julia/bin/julia-release-activate /root/julia_voice_v2/releases/${ARCHIVE_NAME}
```

### Verify

```bash
/opt/julia/bin/julia-runtime-attest
```

Must output `✅ RUNTIME ATTESTATION: PASS` before any E2E testing.

## 9. Logs

Primary logs:

```bash
tail -f /var/log/julia/julia-voice.log          # S2S stdout
tail -f /var/log/julia/julia-voice.err           # S2S stderr
tail -f /var/log/julia/julia-voice-watchdog.log  # Watchdog
tail -f /var/log/julia/julia-voice-frontend.log  # Frontend (:7860) stdout
tail -f /var/log/julia/supervisord.log           # Supervisor
tail -f /var/log/julia/bootstrap-supervisord.log # Bootstrap
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
- `Uvicorn running on http://0.0.0.0:7860` (frontend)
- `RUNTIME ATTESTATION: PASS`

Watchdog milestones:

- During cold start: `watchdog startup grace: service not READY yet; no restart (.../900s)`
- After ready: `watchdog observed READY; failure counting enabled`

## 10. Preflight and asset validation

Run preflight manually:

```bash
/opt/julia/bin/julia-voice-preflight
```

Expected:

```text
PRECHECK OK
```

If preflight fails, do not start S2S. Fix the missing runtime asset/config through the normal deployment process.

## 11. Loaded code verification

Run from AutoDL:

```bash
# Verify release integrity from manifest
python3 -c "
import json
m = json.load(open('/root/julia_voice_v2/releases/current/manifest.json'))
print(f'Source commit: {m[\"source_commit\"]}')
print(f'Archive SHA256: {m[\"archive_sha256\"]}')
print(f'Files: {m[\"file_count\"]}')
"

# Full runtime attestation
/opt/julia/bin/julia-runtime-attest
```

## 12. Boot behavior

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
→ frontend starts (:7860)
→ watchdog grace, no restart
→ :8765 binds, :7860 binds
→ health READY
→ runtime attestation PASS
→ Electron can connect
```

## 13. Watchdog acceptance test

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
- no duplicate `:8765` or `:7860` listener

## 14. Clean reboot acceptance test

This interrupts service and may take 10+ minutes before READY. Only run when Tony approves a reboot/restart test.

Expected acceptance:

1. Server/container restarts through normal AutoDL lifecycle.
2. No SSH manual export.
3. No manual Python command.
4. Boot hook starts supervisor.
5. Supervisor starts S2S and frontend.
6. Models initialize from existing caches.
7. `:8765` and `:7860` become READY.
8. Runtime attestation PASS.
9. Tony opens Electron and hears Julia reply.

## 15. Rollback

If a new release is broken:

```bash
# Read previous release path
cat /root/julia_voice_v2/releases/.previous

# Activate previous release
/opt/julia/bin/julia-release-activate /root/julia_voice_v2/releases/<previous-release>

# Supervisor will restart from new current symlink
kill "$(cat /tmp/julia-voice-supervisor/supervisord.pid)"
/opt/julia/bin/bootstrap-julia-voice-supervisor

# Verify
/opt/julia/bin/julia-runtime-attest
```

## 16. Troubleshooting

### Electron cannot connect

Check:

```bash
/opt/julia/bin/julia-voice-health
/opt/julia/bin/julia-runtime-attest
ps -ef | grep -E 'julia-voice|speech-to-speech|supervisord|uvicorn' | grep -v grep
tail -80 /var/log/julia/julia-voice.err
tail -80 /var/log/julia/julia-voice-frontend.log
```

If service has been started recently, wait through cold model initialization. Do not restart during the first 10+ minutes unless logs show a fatal exception.

### Split-brain: :7860 frontend and :8765 S2S from different releases

RCP makes this structurally impossible because both use the same `current` symlink. If attestation fails on frontend/s2s SHA mismatch, check:

```bash
readlink -f /root/julia_voice_v2/releases/current
tr '\0' '\n' < /proc/$(cat /tmp/julia-voice-supervisor/s2s.pid)/environ | grep PYTHONPATH
readlink -f /proc/$(pgrep -f "7860.*uvicorn")/cwd
```

All three should point to the same release directory.

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

### Duplicate processes

Expected: exactly one S2S process (:8765), one frontend process (:7860), one watchdog.

If duplicate processes exist:

1. Identify which PID owns each port.
2. Stop unmanaged/manual processes.
3. Keep only supervisor-managed processes.
4. Do not start S2S or frontend manually.

## 17. Prohibited production actions

Do not:

- edit S2S or frontend source directly on AutoDL
- patch site-packages
- manually run `python launch_s2s.py` as production
- manually run `uvicorn` as production
- use tmux/screen/nohup as production lifecycle authority
- download new model files during normal startup
- point `PYTHONPATH` at a development worktree
- run duplicate services on `:8765` or `:7860`
- treat process existence as readiness
- deploy frontend and S2S from different releases (RCP prevents this structurally)

Normal production lifecycle authority is:

```text
AutoDL boot hook
→ /opt/julia/bin/bootstrap-julia-voice-supervisor
→ /usr/bin/supervisord -c /etc/supervisor/conf.d/julia-voice.conf
→ /opt/julia/bin/start-julia-voice   (:8765 S2S)
→ /opt/julia/bin/start-julia-frontend (:7860 frontend)
→ immutable Julia Voice RCP release (current symlink)
→ /opt/julia/bin/julia-runtime-attest (verification gate)
```

## 18. Final operator checklist

Use this checklist after any production restart or deployment:

```bash
# Preflight
/opt/julia/bin/julia-voice-preflight

# Health
/opt/julia/bin/julia-voice-health

# Process check
ps -ef | grep -E 'julia-voice|speech-to-speech|supervisord|uvicorn' | grep -v grep
cat /tmp/julia-voice-supervisor/supervisord.pid
cat /tmp/julia-voice-supervisor/s2s.pid

# Environment check
tr '\0' '\n' < /proc/$(cat /tmp/julia-voice-supervisor/s2s.pid)/environ | grep -E '^(PYTHONPATH|HF_HOME|HF_ENDPOINT|PYTHONDONTWRITEBYTECODE|LANG|PATH)='

# Runtime attestation
/opt/julia/bin/julia-runtime-attest
```

Then perform one human E2E check:

```text
Electron → speak one sentence → Julia replies with audio
```

Production is acceptable only when:
1. `julia-runtime-attest` = PASS (ALL SAME = YES)
2. Tony can hear Julia reply after unattended startup
