#!/usr/bin/env bash
# =============================================================================
# snapshot_runtime_provenance.sh — capture current Voice/S2S runtime identity
#
# Run on AutoDL. Produces RUNTIME_PROVENANCE.md with exact source locations,
# git SHAs, working tree status, and package versions.
#
# Usage: bash snapshot_runtime_provenance.sh
# =============================================================================
set -euo pipefail

OUT="RUNTIME_PROVENANCE.md"

cat > "$OUT" << 'HEADER'
# Julia Voice/S2S — Runtime Provenance Snapshot

Generated: $(date -Iseconds)
Host: $(hostname)

HEADER

# ── :7860 Frontend ────────────────────────────────────────────────────────

echo "## :7860 Frontend" >> "$OUT"
echo "" >> "$OUT"

FRONTEND_DIR="/root/julia_voice_v2/golden/frontend"

if [[ -d "$FRONTEND_DIR" ]]; then
  cd "$FRONTEND_DIR"
  echo "- path: \`$FRONTEND_DIR\`" >> "$OUT"
  if git rev-parse HEAD >/dev/null 2>&1; then
    echo "- commit: \`$(git rev-parse HEAD)\`" >> "$OUT"
    echo "- remote: \`$(git remote get-url origin 2>/dev/null || echo 'none')\`" >> "$OUT"
    DIRTY=$(git status --short | wc -l | tr -d ' ')
    echo "- working_tree_dirty: $([ "$DIRTY" -gt 0 ] && echo 'true' || echo 'false')" >> "$OUT"
    if [ "$DIRTY" -gt 0 ]; then
      echo "" >> "$OUT"
      echo '```diff' >> "$OUT"
      git diff >> "$OUT" 2>/dev/null || true
      echo '```' >> "$OUT"
    fi
  else
    echo "- git: NOT A GIT REPO" >> "$OUT"
  fi
else
  echo "- NOT FOUND at $FRONTEND_DIR" >> "$OUT"
fi

# ── :8765 S2S ─────────────────────────────────────────────────────────────

echo "" >> "$OUT"
echo "## :8765 S2S (speech-to-speech)" >> "$OUT"
echo "" >> "$OUT"

python3 - "$OUT" << 'PY'
import sys, os, inspect, importlib.metadata as md

out = sys.argv[1]

try:
    import speech_to_speech as s2s
    print(f"- package_path: `{s2s.__file__}`", file=open(out, "a"))

    try:
        v = md.version("speech-to-speech")
        print(f"- version: `{v}`", file=open(out, "a"))
    except Exception:
        print("- version: UNKNOWN", file=open(out, "a"))

    # Dist info
    try:
        d = md.distribution("speech-to-speech")
        dp = d._path if hasattr(d, "_path") else "unknown"
        print(f"- dist_path: `{dp}`", file=open(out, "a"))

        # Check for direct_url (git/editable install)
        direct = os.path.join(str(dp), "direct_url.json")
        if os.path.exists(direct):
            import json
            du = json.load(open(direct))
            print(f"- install_type: `{du.get('url', du)}`", file=open(out, "a"))
        else:
            print("- install_type: pypi", file=open(out, "a"))
    except Exception as e:
        print(f"- dist_info: error ({e})", file=open(out, "a"))

    # Key file locations
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
            print(f"- {label}: `{f}`", file=open(out, "a"))
        except Exception as e:
            print(f"- {label}: ERROR ({e})", file=open(out, "a"))

except Exception as e:
    print(f"- IMPORT ERROR: {e}", file=open(out, "a"))

PY

# ── Launchers ──────────────────────────────────────────────────────────────

echo "" >> "$OUT"
echo "## Launchers" >> "$OUT"
echo "" >> "$OUT"

for f in /root/julia_voice_v2/golden/launch_s2s.py /root/julia_voice_v2/golden/start_frontend.sh; do
  if [[ -f "$f" ]]; then
    echo "- \`$f\`" >> "$OUT"
  fi
done

# ── SSH Tunnel ─────────────────────────────────────────────────────────────

echo "" >> "$OUT"
echo "## Connectivity" >> "$OUT"
echo "" >> "$OUT"
echo "- frontend_port: 7860" >> "$OUT"
echo "- s2s_port: 8765" >> "$OUT"
echo "- brain_target_port: 8089" >> "$OUT"

echo "" >> "$OUT"
echo "Done. Saved to $OUT"
