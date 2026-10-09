#!/bin/sh
# Bring the two local models up, on the ports the profiles expect.
#
#   sh studio/ops/localmodels.sh          start both, in the background
#   sh studio/ops/localmodels.sh stop     stop both
#   sh studio/ops/localmodels.sh status   say what is answering
#
# This exists because the start command is four lines long, names three files
# in three different places, and lived only in a comment. Once the
# binary and the projector were sitting in a temporary scratchpad belonging to
# an editor session; when that is cleaned the model stops starting and the
# error reads like a model fault rather than a missing file. Both now live
# under ~/.local/share/beyond-canvas, and this script is the only place that
# needs to know where.
#
# Why not Homebrew's llama-server: the released bottle cannot load a step3vl
# vision projector. This is a build from llama.cpp master, relocated here with
# its own libraries and its rpath repointed at @executable_path so it runs from
# wherever it sits. See docs/measured/local-studio-model.md.

set -eu

HOME_DIR="${BEYOND_CANVAS_HOME:-$HOME/.local/share/beyond-canvas}"
SERVER="$HOME_DIR/bin/llama-server"
PROJECTOR="$HOME_DIR/models/mmproj-step3vl.gguf"
WEIGHTS="${STEP3VL_GGUF:-$HOME/.cache/huggingface/hub/models--seanbailey518--Step3-VL-10B-GGUF/snapshots/4e88ea55358ca8091e495a59414fd4a5d43d6932/Step3-VL-10B-Q4_K_M.gguf}"
WHISPER_MODEL="${WHISPER_GGML:-$HOME/.cache/whisper/ggml-small-q5_1.bin}"

# The port convention: 7000-7700, always ending in a zero. tests/server/test_ports.py
# holds it, and these two must match studio/profiles/local.yaml.
STUDIO_PORT=7100
SPEECH_PORT=7130

say() { printf '%s\n' "$*"; }

missing() {
    say "Missing: $1"
    say "  $2"
    exit 1
}

check() {
    [ -x "$SERVER" ] || missing "$SERVER" \
        "The llama.cpp build. Rebuild from master and move build/bin here."
    [ -f "$PROJECTOR" ] || missing "$PROJECTOR" \
        "The vision projector, from JamePeng2023 or Vastined. NOT the one beside the weights."
    [ -f "$WEIGHTS" ] || missing "$WEIGHTS" \
        "The Step3-VL weights. Set STEP3VL_GGUF if they live elsewhere."
}

start() {
    check
    if curl -sf -m 2 "http://127.0.0.1:$STUDIO_PORT/health" >/dev/null 2>&1; then
        say "Studio model already up on $STUDIO_PORT."
    else
        "$SERVER" -m "$WEIGHTS" --mmproj "$PROJECTOR" \
            --port "$STUDIO_PORT" -c 8192 --jinja >/dev/null 2>&1 &
        say "Studio model starting on $STUDIO_PORT (about 20 seconds to load)."
    fi

    start_transcription

    say "Watch them come up: uv run python -m studio.ops.modelboard"
}

start_transcription() {
    if curl -sf -m 2 "http://127.0.0.1:$SPEECH_PORT/health" >/dev/null 2>&1; then
        say "Transcription already up on $SPEECH_PORT."
    elif [ -f "$WHISPER_MODEL" ]; then
        # No --convert: it shells out to ffmpeg on every upload and that call
        # failed on all of them, including a correct 16 kHz mono WAV. The page
        # encodes that format itself. See docs/measured/hearing-the-child.md.
        whisper-server -m "$WHISPER_MODEL" --port "$SPEECH_PORT" >/dev/null 2>&1 &
        say "Transcription starting on $SPEECH_PORT."
    else
        say "No whisper model at $WHISPER_MODEL, so transcription stays down."
    fi

}

stop() {
    pkill -f "llama-server -m $WEIGHTS" 2>/dev/null || true
    pkill -f "whisper-server -m $WHISPER_MODEL" 2>/dev/null || true
    say "Stopped both."
}

status() {
    for pair in "studio:$STUDIO_PORT" "speech:$SPEECH_PORT"; do
        name=${pair%%:*}
        port=${pair##*:}
        if curl -sf -m 2 "http://127.0.0.1:$port/health" >/dev/null 2>&1; then
            say "up    $name on $port"
        else
            say "down  $name on $port"
        fi
    done
}

case "${1:-start}" in
    start) start ;;
    speech) start_transcription ;;
    stop) stop ;;
    status) status ;;
    *) say "Usage: sh studio/ops/localmodels.sh [start|speech|stop|status]"; exit 2 ;;
esac
