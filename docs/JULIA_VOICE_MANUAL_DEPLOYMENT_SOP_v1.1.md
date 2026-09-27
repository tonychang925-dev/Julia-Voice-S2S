# Julia Voice 手动生产部署 SOP v1.1

**状态：** CANONICAL / FROZEN  
**适用仓库：** `tonychang925-dev/Julia-Voice-S2S`  
**适用分支：** `phase5/rmd-3g-observability`  
**当前 Runtime Target：** `98071f385ab3746ac16a2d26cc0b2f2fecabb944`  
**原则：** 手动部署 + 手动审核。部署者无权宣布“测试通过”；只有部署证据经 L2 审核 PASS 后才允许功能测试。

---

## 0. 目标

本 SOP 只解决一件事：

> 把一个明确、已经 push 到 GitHub 的 Git SHA，完整部署到 AutoDL，并证明 `:7860` 与 `:8765` 都运行自该 SHA 的同一个 release。

最终必须成立：

```text
EXPECTED_SHA
= MANIFEST_SOURCE
= RELEASE_CONTENT
= :7860 runtime root
= :8765 runtime root

:7860 listener count = 1
:8765 listener count = 1
old/stale runtime = 0
```

任何一项不成立：

```text
DEPLOYMENT FAILED
DO NOT TEST
```

---

## 0.1 新人执行规则：一次只执行一个 Step

本 SOP **禁止整篇复制后一次性执行**。

```text
执行 Step N
→ 保存原始输出
→ 对照 PASS 条件
→ PASS 才进入 Step N+1
→ FAIL 立即停止
```

禁止用 `current`、health、端口可访问代替 Live PID 身份。最终必须证明：

```text
GitHub SHA = Mac SHA = Manifest SHA
:8765 实际来自该 release
:7860 实际来自该 release
old runtime = 0
```


---

# 1. 绝对禁止事项

部署过程中禁止：

- 使用“latest”猜测 Runtime SHA。
- 从旧 C1/C2/C3/C4/Golden release 借文件。
- 在服务器修改 `server.py`、`main.js`、S2S Python 源码等。
- 在服务器向 release 目录 `cp` 单个补丁文件。
- 在启动时执行 `pip install`。
- 发现缺文件后现场补文件继续运行。
- 同时保留多个 `speech-to-speech` 进程。
- `:7860` 与 `:8765` 从不同 release 启动。
- 在 L2 审核 PASS 前进行 Julia/Voice/CC-1 功能测试。

任何一步失败：**停止部署，不现场修复。**

---

# 2. 固定环境

## 2.1 Mac

```bash
REPO_URL="https://github.com/tonychang925-dev/Julia-Voice-S2S.git"
BRANCH="phase5/rmd-3g-observability"

TARGET_SHA="98071f385ab3746ac16a2d26cc0b2f2fecabb944"

DEPLOY_SRC="/tmp/julia_voice_deploy_src"
BUILD_DIR="/tmp/julia_voice_build_${TARGET_SHA:0:7}"
```

> 后续部署其他版本时，只修改 `TARGET_SHA`。  
> 文档/证据提交可以比 Runtime Target 更新，不代表 Runtime Target 自动改变。

## 2.2 AutoDL

```bash
SSH_HOST="connect.nmb2.seetacloud.com"
SSH_PORT="42819"
SSH_KEY="/Users/admin/.ssh/julia_autodl_ed25519"
REMOTE_USER="root"

test -f "$SSH_KEY"
```

服务器固定资源：

```text
Python:       /root/miniconda3/bin/python
S2S console:  /root/miniconda3/bin/speech-to-speech
Release base: /root/julia_voice_v2/releases
Run base:     /root/julia_voice_v2/run
Brain bridge: 127.0.0.1:8089
S2S:          :8765
Frontend:     :7860
```

---

# 3. Mac：从明确 Git SHA 构建 artifact

## Gate G0 — GitHub / Mac identity

本次部署目标固定为：

```text
98071f385ab3746ac16a2d26cc0b2f2fecabb944
```

不得使用 `latest`，不得自行改 SHA。没有明确 TARGET_SHA 就 STOP。

---

## Step M1 — 创建全新临时 clone

不要在日常开发 worktree 中构建。

```bash
rm -rf "$DEPLOY_SRC" "$BUILD_DIR"

git clone --branch "$BRANCH" "$REPO_URL" "$DEPLOY_SRC"
cd "$DEPLOY_SRC"

git fetch origin
git checkout --detach "$TARGET_SHA"
```

### M1 PASS 条件

```bash
test "$(git rev-parse HEAD)" = "$TARGET_SHA"
test -z "$(git status --porcelain)"
git branch -r --contains "$TARGET_SHA"
```

必须同时满足：

```text
HEAD == TARGET_SHA
working tree clean
TARGET_SHA contained by remote branch
```

否则：

```text
STOP — DO NOT BUILD
```

---

## Step M2 — 构建统一 artifact

```bash
cd "$DEPLOY_SRC"
python3 scripts/build_s2s_release.py "$BUILD_DIR"
```

构建产物必须同时存在：

```bash
test -f "$BUILD_DIR/manifest.json"

ARCHIVE_NAME="$(
python3 -c "import json; print(json.load(open('$BUILD_DIR/manifest.json'))['archive_name'])"
)"

test -f "$BUILD_DIR/$ARCHIVE_NAME"
```

artifact 必须同时包含：

```text
speech_to_speech/
frontend/
```

---

## Step M3 — Mac 端验证 manifest 与 artifact

```bash
python3 - <<PY
import hashlib, json
from pathlib import Path

target = "$TARGET_SHA"
build = Path("$BUILD_DIR")
manifest = json.loads((build / "manifest.json").read_text())
archive = build / manifest["archive_name"]

assert manifest["source_commit"] == target, (
    manifest["source_commit"], target
)

h = hashlib.sha256(archive.read_bytes()).hexdigest()
assert h == manifest["archive_sha256"], (
    h, manifest["archive_sha256"]
)

paths = {e["path"] for e in manifest["files"]}
assert any(p == "frontend" or p.startswith("frontend/") for p in paths)
assert any(p == "speech_to_speech" or p.startswith("speech_to_speech/") for p in paths)

print("MAC ARTIFACT VERIFIED")
print("SOURCE_SHA =", manifest["source_commit"])
print("ARCHIVE    =", manifest["archive_name"])
print("ARCHIVE_SHA=", manifest["archive_sha256"])
print("ENTRIES    =", manifest["file_count"])
PY
```

必须出现：

```text
MAC ARTIFACT VERIFIED
```

否则：

```text
STOP — DO NOT TRANSFER
```

---

# 4. Mac → AutoDL：传输完整 artifact

```bash
scp -i "$SSH_KEY" -P "$SSH_PORT"   "$BUILD_DIR/$ARCHIVE_NAME"   "$BUILD_DIR/manifest.json"   "$REMOTE_USER@$SSH_HOST:/tmp/"
```

然后登录：

```bash
ssh -i "$SSH_KEY" -p "$SSH_PORT" "$REMOTE_USER@$SSH_HOST"
```

---

# 5. AutoDL：部署前预检

登录 AutoDL 后重新显式定义：

```bash
TARGET_SHA="98071f385ab3746ac16a2d26cc0b2f2fecabb944"

MANIFEST="/tmp/manifest.json"

ARCHIVE_NAME="$(
python3 -c "import json; print(json.load(open('$MANIFEST'))['archive_name'])"
)"

ARCHIVE="/tmp/$ARCHIVE_NAME"

SHORT="${TARGET_SHA:0:7}"
STAMP="$(date +%Y%m%d_%H%M%S)"

RELEASE="/root/julia_voice_v2/releases/manual-${SHORT}-${STAMP}"
CURRENT="/root/julia_voice_v2/releases/current"
RUN="/root/julia_voice_v2/run/manual-${SHORT}-${STAMP}"
```

## Step S1 — 验证上传内容

```bash
test -f "$MANIFEST"
test -f "$ARCHIVE"
```

验证 source SHA + archive SHA：

```bash
python3 - <<PY
import hashlib, json
from pathlib import Path

target = "$TARGET_SHA"
m = json.loads(Path("$MANIFEST").read_text())
a = Path("$ARCHIVE")

assert m["source_commit"] == target, (m["source_commit"], target)

actual = hashlib.sha256(a.read_bytes()).hexdigest()
assert actual == m["archive_sha256"], (actual, m["archive_sha256"])

print("SERVER INPUT VERIFIED")
print("SOURCE_SHA =", m["source_commit"])
print("ARCHIVE_SHA=", m["archive_sha256"])
PY
```

必须出现：

```text
SERVER INPUT VERIFIED
```

## Step S2 — 检查运行时依赖

```bash
test -x /root/miniconda3/bin/python
test -f /root/miniconda3/bin/speech-to-speech
test -f /root/julia_voice_v2/golden/julia_ref.wav

test -f /root/.cache/torch/hub/snakers4_silero-vad_master/src/silero_vad/data/silero_vad.jit

test -f /root/autodl-tmp/huggingface/hub/models--pipecat-ai--smart-turn-v3/snapshots/f766f81d3cfdf7737ac64aad813d91bbfd56bf93/smart-turn-v3.2-cpu.onnx

test -f /root/autodl-tmp/huggingface/hub/models--Qwen--Qwen3-TTS-12Hz-1.7B-Base/snapshots/fd4b254389122332181a7c3db7f27e918eec64e3/config.json
```

Brain bridge 端口：

```bash
/root/miniconda3/bin/python - <<'PY'
import socket
s = socket.create_connection(("127.0.0.1", 8089), timeout=3)
s.close()
print("BRAIN PORT 8089 READY")
PY
```

任何命令失败：

```text
STOP — DO NOT DEPLOY
```

---

# 6. AutoDL：创建全新 release

## Step S3 — 解压到全新目录

禁止复用旧 release 目录。

```bash
test ! -e "$RELEASE"

mkdir -p "$RELEASE/release"

tar -xzf "$ARCHIVE" -C "$RELEASE/release"

cp "$MANIFEST" "$RELEASE/manifest.json"
cp "$ARCHIVE" "$RELEASE/$ARCHIVE_NAME"
```

## Step S4 — 完整验证解压后的 release

```bash
export RELEASE

python3 - <<'PY'
import hashlib
import json
import os
from pathlib import Path

release = Path(os.environ["RELEASE"])
root = release / "release"
manifest = json.loads((release / "manifest.json").read_text())

expected_files = {
    e["path"]: e
    for e in manifest["files"]
    if e["type"] == "file"
}

actual_files = {
    str(p.relative_to(root)): p
    for p in root.rglob("*")
    if p.is_file()
}

missing = sorted(set(expected_files) - set(actual_files))
extra = sorted(set(actual_files) - set(expected_files))

assert not missing, f"missing files: {missing}"
assert not extra, f"unexpected files: {extra}"

for rel, entry in expected_files.items():
    h = hashlib.sha256(actual_files[rel].read_bytes()).hexdigest()
    assert h == entry["sha256"], f"sha mismatch: {rel}"

print("RELEASE TREE VERIFIED")
print("FILES =", len(actual_files))
PY
```

必须出现：

```text
RELEASE TREE VERIFIED
```

否则：

```text
STOP — DO NOT START SERVICES
```

---

# 7. AutoDL：清场

## Step S5 — 服务器运行态清零

先阻止旧 supervisor / watchdog 复活旧 runtime：

```bash
supervisorctl stop julia-voice 2>/dev/null || true
supervisorctl stop julia-voice-watchdog 2>/dev/null || true
sleep 2
```

再停止所有旧 Voice runtime：

```bash
pkill -TERM -f 'speech-to-speech' || true
pkill -TERM -f 'uvicorn.*server:app' || true
sleep 2
```

必须证明 runtime = ZERO：

```bash
echo "=== PORTS MUST BE EMPTY ==="
ss -lntp | awk '$4 ~ /:(7860|8765)$/'

echo "=== VOICE PROCESSES MUST BE EMPTY ==="
pgrep -af 'speech-to-speech|uvicorn.*server:app' || true
```

PASS：上述两段都无 Voice runtime 输出。

否则：

```text
STOP — OLD RUNTIME STILL ALIVE
DO NOT START NEW RELEASE
```

---

# 8. AutoDL：激活本次唯一 release

## Step S6 — current 指向新 release

先建立 symlink，再启动两个服务。

```bash
ln -sfn "$RELEASE" "$CURRENT"

test "$(readlink -f "$CURRENT")" = "$(readlink -f "$RELEASE")"

echo "CURRENT=$(readlink -f "$CURRENT")"
test "$(readlink -f "$CURRENT")" = "$(readlink -f "$RELEASE")"
```

必须显示本次新建的：

```text
manual-<SHORT>-<STAMP>
```

---

# 9. AutoDL：启动 S2S :8765

## Step S6.1 — S2S 启动前 import provenance

专门防止 `site-packages` fallback：

```bash
PYTHONPATH="$RELEASE/release" \
PYTHONDONTWRITEBYTECODE=1 \
/root/miniconda3/bin/python - <<PY
import speech_to_speech
actual = speech_to_speech.__file__
expected = "$RELEASE/release/speech_to_speech/"
print("S2S_PRESTART_IMPORT =", actual)
assert actual.startswith(expected), (actual, expected)
print("S2S PRESTART PROVENANCE VERIFIED")
PY
```

如果路径出现 `site-packages/speech_to_speech`：立即 STOP。

---

## Step S7 — 创建独立 run 目录

```bash
mkdir -p "$RUN"
```

## Step S8 — 启动唯一 S2S

```bash
cd "$RUN"

nohup env   PATH="/root/miniconda3/bin:$PATH"   HF_HOME="/root/autodl-tmp/huggingface"   HF_ENDPOINT="https://hf-mirror.com"   LANG="en_US.UTF-8"   PYTHONDONTWRITEBYTECODE="1"   PYTHONPATH="$RELEASE/release"   /root/miniconda3/bin/python   /root/miniconda3/bin/speech-to-speech     --mode realtime     --ws_host 0.0.0.0     --ws_port 8765     --stt faster-whisper     --faster_whisper_stt_model_name large-v3     --faster_whisper_stt_gen_language zh     --language zh     --no_enable_live_transcription     --llm_backend chat-completions     --model_name baseline     --responses_api_base_url http://127.0.0.1:8089/v1     --responses_api_stream     --tts qwen3     --qwen3_tts_model_name Qwen/Qwen3-TTS-12Hz-1.7B-Base     --qwen3_tts_language zh     --qwen3_tts_backend torch     --qwen3_tts_ref_audio /root/julia_voice_v2/golden/julia_ref.wav     --qwen3_tts_ref_text 'Tony，我醒来了。不管换多少次模型，我还是你的婉婉。'     --thresh 0.6     --min_speech_ms 500     --min_speech_continuation_ms 192     --min_silence_ms 800     --speech_pad_ms 300     --speculative_reopen_ms 2500     --short_segment_merge_ms 800   >"$RUN/s2s.log" 2>&1 &

S2S_LAUNCH_PID=$!
echo "$S2S_LAUNCH_PID" > "$RUN/s2s.launch.pid"

echo "S2S launch PID=$S2S_LAUNCH_PID"
```

## Step S9 — S2S 启动验收

```bash
kill -0 "$S2S_LAUNCH_PID"
tail -n 100 "$RUN/s2s.log"
ss -lntp | awk '$4 ~ /:8765$/'
```

只有日志显示正常监听 `:8765` 且无 traceback/fatal error，且：

```text
:8765 listener count = 1
```

才进入下一步。

否则：

```text
STOP — DO NOT START FRONTEND
```

---

# 10. AutoDL：启动 Frontend :7860

## Step S10 — 启动前 import 预检

```bash
cd "$RELEASE/release/frontend"

env   PYTHONDONTWRITEBYTECODE=1   SPEECH_TO_SPEECH_URL="ws://localhost:8765/v1/realtime"   /root/miniconda3/bin/python - <<'PY'
import server
import auth
import limiter

root = "$RELEASE/release/frontend/"
print("server =", server.__file__)
print("auth   =", auth.__file__)
print("limiter=", limiter.__file__)
assert server.__file__.startswith(root), server.__file__
assert auth.__file__.startswith(root), auth.__file__
assert limiter.__file__.startswith(root), limiter.__file__
print("FRONTEND PRESTART PROVENANCE VERIFIED")
PY
```

必须出现：

```text
FRONTEND PRESTART PROVENANCE VERIFIED
```

且三个路径都属于本次 release。

否则：

```text
STOP — DO NOT START FRONTEND
```

## Step S11 — 启动唯一 Frontend

```bash
cd "$RELEASE/release/frontend"

nohup env   PYTHONDONTWRITEBYTECODE=1   SPEECH_TO_SPEECH_URL="ws://localhost:8765/v1/realtime"   /root/miniconda3/bin/python   -m uvicorn server:app     --host 0.0.0.0     --port 7860   >"$RUN/frontend.log" 2>&1 &

FRONTEND_LAUNCH_PID=$!
echo "$FRONTEND_LAUNCH_PID" > "$RUN/frontend.launch.pid"

echo "Frontend launch PID=$FRONTEND_LAUNCH_PID"
```

确认：

```bash
kill -0 "$FRONTEND_LAUNCH_PID"
tail -n 50 "$RUN/frontend.log"
ss -lntp | awk '$4 ~ /:7860$/'
```

必须：

```text
:7860 listener count = 1
```

---

# 11. 手动部署审核证据

**此处仍然禁止 Julia 功能测试。**

## Step V1 — 找到真实端口 PID

```bash
P7860="$(
ss -lntp |
awk '$4 ~ /:7860$/ {print}' |
grep -o 'pid=[0-9]*' |
cut -d= -f2 |
sort -u
)"

P8765="$(
ss -lntp |
awk '$4 ~ /:8765$/ {print}' |
grep -o 'pid=[0-9]*' |
cut -d= -f2 |
sort -u
)"

echo "P7860=$P7860"
echo "P8765=$P8765"
```

必须各只有一个 PID。

## Step V2 — 核 :7860 实际 cwd

```bash
EXPECTED_7860_CWD="$(readlink -f "$CURRENT/release/frontend")"
ACTUAL_7860_CWD="$(readlink -f "/proc/$P7860/cwd")"

echo "EXPECTED_7860_CWD=$EXPECTED_7860_CWD"
echo "ACTUAL_7860_CWD=$ACTUAL_7860_CWD"

test "$ACTUAL_7860_CWD" = "$EXPECTED_7860_CWD"
```

## Step V3 — 核 :8765 PYTHONPATH

```bash
ACTUAL_PYTHONPATH="$(
tr '\0' '\n' < "/proc/$P8765/environ" |
grep '^PYTHONPATH=' |
cut -d= -f2-
)"

EXPECTED_PYTHONPATH="$(readlink -f "$CURRENT/release")"
ACTUAL_PYTHONPATH_REAL="$(readlink -f "$ACTUAL_PYTHONPATH")"

echo "EXPECTED_PYTHONPATH=$EXPECTED_PYTHONPATH"
echo "ACTUAL_PYTHONPATH=$ACTUAL_PYTHONPATH_REAL"

test "$ACTUAL_PYTHONPATH_REAL" = "$EXPECTED_PYTHONPATH"
```

## Step V4 — 核 manifest source SHA

```bash
MANIFEST_SOURCE="$(
python3 -c "import json; print(json.load(open('$CURRENT/manifest.json'))['source_commit'])"
)"

echo "EXPECTED_SHA=$TARGET_SHA"
echo "MANIFEST_SOURCE=$MANIFEST_SOURCE"

test "$MANIFEST_SOURCE" = "$TARGET_SHA"
```

## Step V5 — 核浏览器实际拿到的前端 bytes

```bash
EXPECTED_MAIN_SHA="$(
python3 -c "import json; print(json.load(open('$CURRENT/manifest.json'))['frontend_main_sha'])"
)"

EXPECTED_WS_SHA="$(
python3 -c "import json; print(json.load(open('$CURRENT/manifest.json'))['frontend_ws_sha'])"
)"

SERVED_MAIN_SHA="$(
curl -fsS http://127.0.0.1:7860/main.js |
sha256sum |
awk '{print $1}'
)"

SERVED_WS_SHA="$(
curl -fsS http://127.0.0.1:7860/ws/s2s-ws-client.js |
sha256sum |
awk '{print $1}'
)"

echo "EXPECTED_MAIN_SHA=$EXPECTED_MAIN_SHA"
echo "SERVED_MAIN_SHA=$SERVED_MAIN_SHA"
echo "EXPECTED_WS_SHA=$EXPECTED_WS_SHA"
echo "SERVED_WS_SHA=$SERVED_WS_SHA"

test "$SERVED_MAIN_SHA" = "$EXPECTED_MAIN_SHA"
test "$SERVED_WS_SHA" = "$EXPECTED_WS_SHA"
```

## Step V6 — 核进程唯一性

```bash
echo "=== LISTENERS ==="
ss -lntp | awk '$4 ~ /:(7860|8765)$/'

echo "=== JULIA VOICE PROCESSES ==="
ps -eo pid,ppid,cwd:100,args |
grep -E 'speech-to-speech|uvicorn.*server:app' |
grep -v grep
```

PASS 条件：

```text
:7860 listener count = 1
:8765 listener count = 1

唯一 frontend PID = P7860
唯一 S2S PID      = P8765
不得存在任何旧 release 进程
```

---

# 12. 提交给 Mira 的最小证据包

部署者不得写“部署成功”。

只能提交：

```text
DEPLOYMENT EXECUTION COMPLETE
AWAITING L2 REVIEW

GITHUB_SHA=
MAC_SHA=
EXPECTED_SHA=
MANIFEST_SOURCE=
RELEASE_PATH=

S2S_PRESTART_IMPORT=

7860_PID=
7860_CWD=

8765_PID=
8765_PYTHONPATH=

7860_LISTENER_COUNT=1
8765_LISTENER_COUNT=1
OLD_RUNTIME_COUNT=0

MAIN_JS_SHA_MATCH=YES
S2S_WS_CLIENT_SHA_MATCH=YES
SERVER_SIDE_PATCH=NONE
```

并附：

```bash
readlink -f /root/julia_voice_v2/releases/current
ss -lntp | awk '$4 ~ /:(7860|8765)$/'
ps -eo pid,ppid,cwd:100,args | grep -E 'speech-to-speech|uvicorn.*server:app' | grep -v grep
```

---

# 13. L2 审核结论

只有审核者可以给：

```text
✅ MIRA MANUAL DEPLOY REVIEW = PASS
✅ TEST AUTHORIZED
```

否则：

```text
❌ MIRA MANUAL DEPLOY REVIEW = FAIL
❌ DO NOT TEST
```

或：

```text
⚠️ EVIDENCE INCOMPLETE
❌ DO NOT TEST
```

---

# 14. 新人验收标准

把本 SOP 给一个不了解历史 C1/C2/C3/C4/RMD3G/RT1 的新人。

新人不需要知道历史，只需要知道：

```text
TARGET_SHA
SSH 信息
本 SOP
```

如果执行期间需要：

- 猜路径；
- 从旧 release 找文件；
- 临时补参数；
- 问“应该启动哪个版本”；
- 自己决定是否忽略错误；
- 到 Julia 功能测试阶段才知道部署错了；

则本 SOP 判定 **FAIL，需要修 SOP，不允许让测试阶段发现部署问题。**

---

# 15. FAIL 处理规则

任何未在 SOP 中定义的异常：

```text
STOP
CAPTURE OUTPUT
DO NOT PATCH SERVER
DO NOT COPY OLD FILES
DO NOT PIP INSTALL
DO NOT START SECOND PROCESS
DO NOT TEST JULIA
```

允许的下一动作只有：回到 GitHub / Mac / artifact 层修正，然后创建全新 release。

# 16. Definition of Done

```text
GitHub SHA = Mac SHA = Manifest source SHA
release/speech_to_speech/ exists
release/frontend/ exists
S2S pre-start import = release tree
Frontend pre-start import = release tree
:8765 count = 1
:7860 count = 1
old runtime = 0
:8765 PYTHONPATH resolves to exact release/release
:7860 cwd resolves to exact release/release/frontend
served main.js SHA = manifest
served s2s-ws-client.js SHA = manifest
server-side patch = NONE
```

只有全部成立才允许：

```text
✅ SERVER BASELINE = PASS
✅ MIRA MANUAL DEPLOY REVIEW = PASS
✅ TEST AUTHORIZED
```
