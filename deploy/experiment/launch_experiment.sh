#!/bin/sh
# VOICE-EL-P0D-1 — repository-owned experimental launcher (Workstream I).
#
# Runs an ElevenLabs experiment release from its OWN namespace. It exists so
# that starting an experiment is a repository-defined command rather than a
# sequence of things a human types into a server shell.
#
# It does NOT:
#   install packages · edit files · switch the Golden `current` symlink ·
#   invoke the production supervisor · reuse production pidfiles ·
#   reuse production logs · write outside the experiment namespace
#
# Governing rule: VOICE SERVER IMMUTABILITY RULE v1
#
# Usage:
#   ./launch_experiment.sh --expected-sha <40-char sha> [--dry-run] [-- <extra args>]

set -eu

EXP_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
RELEASE_ROOT=$(CDPATH= cd -- "$EXP_DIR/.." && pwd)
RELEASE_TREE="$RELEASE_ROOT/release"

EXPECTED_SHA=""
DRY_RUN=0
EXTRA_ARGS=""

while [ $# -gt 0 ]; do
    case "$1" in
        --expected-sha) EXPECTED_SHA="${2:-}"; shift 2 ;;
        --dry-run)      DRY_RUN=1; shift ;;
        --)             shift; EXTRA_ARGS="$*"; break ;;
        *)              echo "unknown argument: $1" >&2; exit 64 ;;
    esac
done

if [ -z "$EXPECTED_SHA" ]; then
    echo "usage: $0 --expected-sha <40-char sha> [--dry-run] [-- extra args]" >&2
    exit 64
fi

# ---- namespace contract (repository-defined, shipped beside this script) ----
# shellcheck disable=SC1091
. "$EXP_DIR/namespace.env"

# ---- 1. refuse the Golden production release, implicitly ----
case "$RELEASE_ROOT" in
    */releases/current|*/releases/current/*)
        echo "REFUSED: refusing to launch from the Golden 'current' symlink ($RELEASE_ROOT)." >&2
        exit 65 ;;
esac
RELEASE_BASENAME=$(basename "$RELEASE_ROOT")
case "$RELEASE_BASENAME" in
    manual-*)
        echo "REFUSED: $RELEASE_ROOT is a Golden-style release (manual-*). Experiments run only from exp-*." >&2
        exit 65 ;;
    exp-*) ;;
    *)
        echo "REFUSED: $RELEASE_ROOT is not an experiment release (expected exp-*)." >&2
        exit 65 ;;
esac

# ---- 2. namespaces, derived from the repository contract ----
SHA_SHORT=$(printf '%s' "$EXPECTED_SHA" | cut -c1-7)
STAMP=$(date -u +%Y%m%d_%H%M%S)
RUN_ROOT=$(printf '%s' "$EXPERIMENT_RUN_ROOT_TEMPLATE"  | sed "s/%SHA%/$SHA_SHORT/g; s/%STAMP%/$STAMP/g")
LOG_ROOT=$(printf '%s' "$EXPERIMENT_LOG_ROOT_TEMPLATE"  | sed "s/%SHA%/$SHA_SHORT/g; s/%STAMP%/$STAMP/g")
TMP_ROOT=$(printf '%s' "$EXPERIMENT_TMP_ROOT_TEMPLATE"  | sed "s/%SHA%/$SHA_SHORT/g; s/%STAMP%/$STAMP/g")

for root in "$RELEASE_ROOT" "$RUN_ROOT" "$LOG_ROOT" "$TMP_ROOT"; do
    case "$root" in
        /tmp|/tmp/*) echo "REFUSED: refusing a generic /tmp namespace ($root)." >&2; exit 66 ;;
    esac
done

# ---- 3. repository-defined runtime argument vector ----
ARGS_FILE="$EXP_DIR/runtime.args"
if [ ! -f "$ARGS_FILE" ]; then
    echo "DEPLOYMENT_ARTIFACT_INCOMPLETE: missing $ARGS_FILE" >&2
    exit 67
fi
LAUNCH_ARGS=$(grep -v '^[[:space:]]*#' "$ARGS_FILE" | grep -v '^[[:space:]]*$' \
    | sed "s/%S2S_HOST%/$EXPERIMENT_S2S_HOST/g; s/%S2S_PORT%/$EXPERIMENT_S2S_PORT/g")

# ---- 4. the artifact's own gate must pass before anything starts ----
echo "== native gate =="
if [ "$DRY_RUN" -eq 1 ]; then
    echo "  (dry run: gate would execute $EXP_DIR/run_tests --expected-sha $EXPECTED_SHA)"
else
    if ! "$EXP_DIR/run_tests" --expected-sha "$EXPECTED_SHA"; then
        echo "REFUSED: native gate failed. RESULT = DEPLOYMENT_ARTIFACT_INCOMPLETE." >&2
        echo "Return to the repository. Do NOT repair on the server." >&2
        exit 68
    fi
fi

# ---- 5. plan ----
PYTHONPATH_VALUE="$RELEASE_TREE"
ENTRYPOINT="$EXPERIMENT_PYTHON -m speech_to_speech"

echo "== experiment launch plan =="
echo "  release     : $RELEASE_ROOT"
echo "  expected sha: $EXPECTED_SHA"
echo "  PYTHONPATH  : $PYTHONPATH_VALUE"
echo "  run root    : $RUN_ROOT"
echo "  log root    : $LOG_ROOT"
echo "  tmp root    : $TMP_ROOT"
echo "  s2s         : $EXPERIMENT_S2S_HOST:$EXPERIMENT_S2S_PORT"
echo "  frontend    : $EXPERIMENT_FRONTEND_HOST:$EXPERIMENT_FRONTEND_PORT"
echo "  entrypoint  : $ENTRYPOINT"
echo "  secret iface: \$$EXPERIMENT_API_KEY_ENV / \$$EXPERIMENT_VOICE_ID_ENV (values never printed)"

if [ "$DRY_RUN" -eq 1 ]; then
    echo "  args        : $(printf '%s' "$LAUNCH_ARGS" | tr '\n' ' ')"
    echo ""
    echo "DRY RUN — nothing created, nothing started."
    exit 0
fi

# ---- 6. start (repository-defined roots only) ----
# The interpreter is only required for a real launch; a dry run validates the
# plan and must be runnable anywhere.
if [ ! -x "$EXPERIMENT_PYTHON" ]; then
    echo "REFUSED: interpreter not executable: $EXPERIMENT_PYTHON" >&2
    exit 69
fi

mkdir -p "$RUN_ROOT" "$LOG_ROOT" "$TMP_ROOT"

# shellcheck disable=SC2086
nohup env \
    PYTHONPATH="$PYTHONPATH_VALUE" \
    TMPDIR="$TMP_ROOT" \
    $ENTRYPOINT $LAUNCH_ARGS $EXTRA_ARGS \
    >"$LOG_ROOT/s2s.log" 2>&1 &

S2S_PID=$!
printf '%s\n' "$S2S_PID" > "$RUN_ROOT/s2s.launch.pid"
echo "started pid=$S2S_PID log=$LOG_ROOT/s2s.log"
