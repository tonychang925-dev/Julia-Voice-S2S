#!/usr/bin/env bash
# =============================================================================
#  start_frontend.sh — Launch Julia Voice frontend (:7860) from RCP release
#
#  Frontend and S2S come from the SAME RCP release (current symlink).
#  Split-brain deployment is structurally impossible.
#  Mac accesses via SSH tunnel: localhost:7860 → AutoDL:7860
# =============================================================================
set -euo pipefail

CURRENT="${JULIA_S2S_CURRENT:-/root/julia_voice_v2/releases/current}"
FRONTEND="$CURRENT/release/frontend"
VENV="${VENV:-/root/miniconda3}"
WEB_PORT="${WEB_PORT:-7860}"
S2S_URL="${S2S_URL:-ws://localhost:8765/v1/realtime}"

C_OK=$'\033[32m'; C_E=$'\033[31m'; C_R=$'\033[0m'
say() { echo "${C_OK}▸${C_R} $*"; }
die() { echo "${C_E}✗${C_R}  $*" >&2; exit 1; }

[[ -d "$FRONTEND" ]] || die "Frontend not found: $FRONTEND (check current symlink)"
[[ -d "$VENV" ]]     || die "Python venv not found: $VENV"

# Install frontend requirements if needed
if [[ ! -f "$FRONTEND/requirements.txt.installed" ]]; then
  say "Installing frontend dependencies..."
  source "$VENV/bin/activate"
  cd "$FRONTEND"
  [[ -f requirements.txt ]] && pip install -r requirements.txt -i http://mirrors.aliyun.com/pypi/simple --trusted-host mirrors.aliyun.com 2>&1 | tail -3
  touch requirements.txt.installed
fi

say "Starting frontend (port $WEB_PORT)..."
say "Release: $(readlink -f "$CURRENT")"
say "S2S URL: $S2S_URL"

source "$VENV/bin/activate"
cd "$FRONTEND"
export SPEECH_TO_SPEECH_URL="$S2S_URL"

exec uvicorn server:app --host 0.0.0.0 --port "$WEB_PORT"
