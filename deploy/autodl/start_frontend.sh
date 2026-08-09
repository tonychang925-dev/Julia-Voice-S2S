#!/usr/bin/env bash
# =============================================================================
#  start_frontend.sh — Launch hf-realtime-voice frontend for Golden Baseline
#
#  The frontend connects to S2S via WebSocket at ws://localhost:8765/v1/realtime
#  Mac accesses it via SSH tunnel: localhost:7860 → AutoDL:7860
# =============================================================================
set -euo pipefail

GOLDEN_ROOT="${GOLDEN_ROOT:-/root/julia_voice_v2/golden}"
FRONTEND="$GOLDEN_ROOT/frontend"
VENV="${VENV:-/root/miniconda3}"
WEB_PORT="${WEB_PORT:-7860}"
S2S_URL="${S2S_URL:-ws://localhost:8765/v1/realtime}"

C_OK=$'\033[32m'; C_E=$'\033[31m'; C_R=$'\033[0m'
say() { echo "${C_OK}▸${C_R} $*"; }
die() { echo "${C_E}✗${C_R}  $*" >&2; exit 1; }

[[ -d "$FRONTEND" ]] || die "找不到前端目录: $FRONTEND"
[[ -d "$VENV" ]]     || die "找不到 venv: $VENV"

# Install frontend requirements if needed
if [[ ! -f "$FRONTEND/requirements.txt.installed" ]]; then
  say "安装前端依赖..."
  source "$VENV/bin/activate"
  cd "$FRONTEND"
  [[ -f requirements.txt ]] && pip install -r requirements.txt -i http://mirrors.aliyun.com/pypi/simple --trusted-host mirrors.aliyun.com 2>&1 | tail -3
  touch requirements.txt.installed
fi

say "启动前端 (port $WEB_PORT)..."
say "S2S URL: $S2S_URL"

source "$VENV/bin/activate"
cd "$FRONTEND"
export SPEECH_TO_SPEECH_URL="$S2S_URL"

exec uvicorn server:app --host 0.0.0.0 --port "$WEB_PORT"
