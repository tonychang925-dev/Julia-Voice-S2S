#!/usr/bin/env bash
# =============================================================================
# snapshot_runtime_provenance.sh — capture current Voice/S2S runtime identity
#
# Run on AutoDL. Produces RUNTIME_PROVENANCE.md with exact source locations,
# git SHAs, working tree status (staged + unstaged + untracked), process
# identity (PID/cwd/exe/cmdline), source file fingerprints, and launcher
# hashes. Designed to produce a verifiable Golden Baseline import.
#
# Usage: bash snapshot_runtime_provenance.sh
# =============================================================================
set -euo pipefail

OUT="RUNTIME_PROVENANCE.md"

# ── Header (no quotes on heredoc = expansion enabled) ────────────────────

cat > "$OUT" << HEADER
# Julia Voice/S2S — Runtime Provenance Snapshot

**Generated**: $(date -Iseconds)
**Host**: $(hostname)
**Kernel**: $(uname -r)
**Status**: Repository bootstrap complete; runtime Golden baseline pending.

## Tags
- \`voice-repo-bootstrap-20260809\` — repository/governance bootstrap
- \`voice-golden-pre-c1b-20260809\` — pending runtime baseline import
- \`voice-c1b-v1\` — target

HEADER

# ═══════════════════════════════════════════════════════════════════════════
# PROCESS IDENTITY
# ═══════════════════════════════════════════════════════════════════════════

echo "" >> "$OUT"
echo "## Process Identity" >> "$OUT"
echo "" >> "$OUT"

capture_process() {
  local label="$1" port="$2"
  local pid
  pid=$(ss -ltnp "sport = :$port" 2>/dev/null | grep -oP 'pid=\K[0-9]+' | head -1 || true)
  echo "### :$port $label" >> "$OUT"
  echo "" >> "$OUT"
  if [[ -n "$pid" ]]; then
    echo "- pid: $pid" >> "$OUT"
    local cwd; cwd=$(readlink -f "/proc/$pid/cwd" 2>/dev/null || echo "unknown")
    echo "- cwd: \`$cwd\`" >> "$OUT"
    local exe; exe=$(readlink -f "/proc/$pid/exe" 2>/dev/null || echo "unknown")
    echo "- exe: \`$exe\`" >> "$OUT"
    local cmdline; cmdline=$(tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null || echo "unknown")
    echo "- cmdline: \`$cmdline\`" >> "$OUT"
    # Parent chain
    local ppid; ppid=$(awk '{print $4}' "/proc/$pid/stat" 2>/dev/null || echo "?")
    echo "- ppid: $ppid" >> "$OUT"
  else
    echo "- NOT RUNNING" >> "$OUT"
  fi
  echo "" >> "$OUT"
}

capture_process "Frontend" 7860
capture_process "S2S" 8765

# Resolve live :8765 Python interpreter from its PID
S2S_PID=$(ss -ltnp "sport = :8765" 2>/dev/null | grep -oP 'pid=\K[0-9]+' | head -1 || true)
S2S_PYTHON=""
if [[ -n "$S2S_PID" ]]; then
  S2S_PYTHON=$(readlink -f "/proc/$S2S_PID/exe" 2>/dev/null || true)
fi

# ═══════════════════════════════════════════════════════════════════════════
# :7860 FRONTEND SOURCE
# ═══════════════════════════════════════════════════════════════════════════

echo "## :7860 Frontend Source" >> "$OUT"
echo "" >> "$OUT"

FRONTEND_DIR="/root/julia_voice_v2/golden/frontend"

if [[ -d "$FRONTEND_DIR" ]]; then
  echo "- path: \`$FRONTEND_DIR\`" >> "$OUT"

  if git -C "$FRONTEND_DIR" rev-parse HEAD >/dev/null 2>&1; then
    SHA=$(git -C "$FRONTEND_DIR" rev-parse HEAD)
    REMOTE=$(git -C "$FRONTEND_DIR" remote get-url origin 2>/dev/null || echo 'none')
    echo "- commit: \`$SHA\`" >> "$OUT"
    echo "- remote: \`$REMOTE\`" >> "$OUT"

    # ── Full dirty state: staged + unstaged + untracked ──────────────────
    STAGED=$(git -C "$FRONTEND_DIR" diff --cached --name-only | wc -l | tr -d ' ')
    UNSTAGED=$(git -C "$FRONTEND_DIR" diff --name-only | wc -l | tr -d ' ')
    UNTRACKED=$(git -C "$FRONTEND_DIR" ls-files --others --exclude-standard | wc -l | tr -d ' ')
    DIRTY=$((STAGED + UNSTAGED + UNTRACKED))

    echo "- working_tree_dirty: $([ "$DIRTY" -gt 0 ] && echo 'true' || echo 'false')" >> "$OUT"
    echo "- dirty_detail: staged=$STAGED unstaged=$UNSTAGED untracked=$UNTRACKED" >> "$OUT"

    if [ "$STAGED" -gt 0 ]; then
      echo "" >> "$OUT"
      echo "### Staged changes (git diff --cached)" >> "$OUT"
      echo '```diff' >> "$OUT"
      git -C "$FRONTEND_DIR" diff --cached >> "$OUT" 2>/dev/null || true
      echo '```' >> "$OUT"
    fi
    if [ "$UNSTAGED" -gt 0 ]; then
      echo "" >> "$OUT"
      echo "### Unstaged changes (git diff)" >> "$OUT"
      echo '```diff' >> "$OUT"
      git -C "$FRONTEND_DIR" diff >> "$OUT" 2>/dev/null || true
      echo '```' >> "$OUT"
    fi
    if [ "$UNTRACKED" -gt 0 ]; then
      echo "" >> "$OUT"
      echo "### Untracked files" >> "$OUT"
      echo '```' >> "$OUT"
      git -C "$FRONTEND_DIR" ls-files --others --exclude-standard >> "$OUT" 2>/dev/null || true
      echo '```' >> "$OUT"
    fi
  else
    echo "- git: NOT A GIT REPO" >> "$OUT"
  fi

  # Source fingerprint (key files)
  echo "" >> "$OUT"
  echo "### Key file fingerprints" >> "$OUT"
  echo "" >> "$OUT"
  for f in main.js ws/s2s-ws-client.js index.html server.py app.py; do
    fp="$FRONTEND_DIR/$f"
    if [[ -f "$fp" ]]; then
      HASH=$(sha256sum "$fp" | cut -d' ' -f1)
      echo "- \`$f\`: sha256=\`$HASH\`" >> "$OUT"
    fi
  done
else
  echo "- NOT FOUND at \`$FRONTEND_DIR\`" >> "$OUT"
fi

# ═══════════════════════════════════════════════════════════════════════════
# :8765 S2S PYTHON PACKAGE
# ═══════════════════════════════════════════════════════════════════════════

echo "" >> "$OUT"
echo "## :8765 S2S (speech-to-speech)" >> "$OUT"
echo "" >> "$OUT"

# Use the live :8765 Python executable, not shell's default python3
if [[ -x "$S2S_PYTHON" ]]; then
  PYTHON_BIN="$S2S_PYTHON"
else
  PYTHON_BIN="python3"
fi

"$PYTHON_BIN" - "$OUT" << 'PYEOF'
import sys, os, inspect, hashlib, importlib.metadata as md
from pathlib import Path

out = sys.argv[1]

try:
    import speech_to_speech as s2s
    pkg_path = s2s.__file__
    print(f"- package_path: `{pkg_path}`", file=open(out, "a"))
    if pkg_path.endswith("__init__.py"):
        pkg_dir = os.path.dirname(pkg_path)
    else:
        pkg_dir = pkg_path
    print(f"- package_dir: `{pkg_dir}`", file=open(out, "a"))

    # Version
    try:
        v = md.version("speech-to-speech")
        print(f"- version: `{v}`", file=open(out, "a"))
    except Exception:
        print("- version: UNKNOWN", file=open(out, "a"))

    # Distribution info
    try:
        d = md.distribution("speech-to-speech")
        dp = str(d._path) if hasattr(d, "_path") else "unknown"
        print(f"- dist_path: `{dp}`", file=open(out, "a"))
        direct = os.path.join(str(dp), "direct_url.json")
        if os.path.exists(direct):
            import json
            du = json.load(open(direct))
            print(f"- install_type: git/editable → `{du}`", file=open(out, "a"))
        else:
            print("- install_type: pypi", file=open(out, "a"))
    except Exception as e:
        print(f"- dist_info: error ({e})", file=open(out, "a"))

    # Key module locations
    print("", file=open(out, "a"))
    print("### Key module locations", file=open(out, "a"))
    print("", file=open(out, "a"))
    for mod_path, label in [
        ("speech_to_speech.api.openai_realtime.websocket_router", "websocket_router"),
        ("speech_to_speech.api.openai_realtime.runtime_config", "runtime_config"),
        ("speech_to_speech.api.openai_realtime.service", "service"),
        ("speech_to_speech.LLM.chat_completions_language_model", "chat_completions_handler"),
        ("speech_to_speech.LLM.base_openai_compatible_language_model", "base_llm_handler"),
    ]:
        try:
            mod = __import__(mod_path, fromlist=["_"])
            f = inspect.getfile(mod)
            h = hashlib.sha256(open(f, "rb").read()).hexdigest()
            print(f"- {label}: `{f}`  ", file=open(out, "a"))
            print(f"  sha256=`{h}`", file=open(out, "a"))
        except Exception as e:
            print(f"- {label}: ERROR ({e})", file=open(out, "a"))

    # Whole package tree fingerprint
    print("", file=open(out, "a"))
    print("### Package tree fingerprint", file=open(out, "a"))
    print("", file=open(out, "a"))
    try:
        digest = hashlib.sha256()
        py_files = sorted(Path(pkg_dir).rglob("*.py"))
        for fp in py_files:
            digest.update(str(fp.relative_to(pkg_dir)).encode())
            digest.update(fp.read_bytes())
        print(f"- package_tree_sha256: `{digest.hexdigest()}`", file=open(out, "a"))
        print(f"- py_file_count: {len(py_files)}", file=open(out, "a"))
    except Exception as e:
        print(f"- package_tree_sha256: ERROR ({e})", file=open(out, "a"))

except Exception as e:
    print(f"- IMPORT ERROR: {e}", file=open(out, "a"))

PYEOF

# ═══════════════════════════════════════════════════════════════════════════
# LAUNCHERS
# ═══════════════════════════════════════════════════════════════════════════

echo "" >> "$OUT"
echo "## Launchers" >> "$OUT"
echo "" >> "$OUT"

for f in /root/julia_voice_v2/golden/launch_s2s.py \
         /root/julia_voice_v2/golden/start_frontend.sh \
         /root/julia_voice_v2/golden/start-voice.sh; do
  if [[ -f "$f" ]]; then
    HASH=$(sha256sum "$f" | cut -d' ' -f1)
    echo "- \`$f\`  " >> "$OUT"
    echo "  sha256=\`$HASH\`" >> "$OUT"
  fi
done

# Also capture the active tmux/screen session if any
echo "" >> "$OUT"
echo "## Session" >> "$OUT"
echo "" >> "$OUT"
if command -v tmux &>/dev/null && tmux ls &>/dev/null; then
  echo '```' >> "$OUT"
  tmux ls 2>/dev/null >> "$OUT" || true
  echo '```' >> "$OUT"
fi

# ═══════════════════════════════════════════════════════════════════════════
# CONNECTIVITY
# ═══════════════════════════════════════════════════════════════════════════

echo "" >> "$OUT"
echo "## Connectivity" >> "$OUT"
echo "" >> "$OUT"
echo "- frontend_port: 7860" >> "$OUT"
echo "- s2s_port: 8765" >> "$OUT"
echo "- brain_target_port: 8089" >> "$OUT"
echo "- brain_local_port: 18089" >> "$OUT"

echo "" >> "$OUT"
echo "## Verification Gates" >> "$OUT"
echo "" >> "$OUT"
cat >> "$OUT" << 'GATES'
- [ ] :7860 live PID → exact frontend runtime source → imported frontend/ → identical source/hash
- [ ] :8765 live PID → exact Python executable → exact speech_to_speech import path → imported s2s/ → identical source/hash
- [ ] Launcher live command → imported launcher → identical hash
- [ ] Dirty production modifications → preserved exactly

All four gates PASS → commit VOICE-GOLDEN-C0 → tag voice-golden-pre-c1b-20260809
GATES

echo "" >> "$OUT"
echo "Done. Saved to $OUT"
