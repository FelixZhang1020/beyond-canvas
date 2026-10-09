#!/bin/sh
# Start the first voice's container and wait until it answers (/health answers only once the model is
# loaded, about four minutes). qwen-front.sh runs this holding the GPU lock. Measured on the node:
# the node's used memory rose by 50 GB, and no share below 0.38 starts at all
# (docs/measured/chat-speed-and-front-voice.md). It is taken only while the node stays under the jobs'
# ceiling (memory_guard.py --room): this box freezes rather than failing when memory runs out, and loading
# passes through a peak above what it keeps, so a watcher stops it the moment the stop level is reached
# (memory_guard.py --low). The measured load started from 82 GiB available, never went below 30 during the
# load and settled at about 32: it takes up to ~52 at its peak, so 52 GiB of room keeps the ceiling.
NAME=qwen-front
GUARD="python3 $(dirname "$0")/memory_guard.py"
room=$($GUARD --room)
if [ "${room:-0}" -lt 52 ]; then
    echo "$(date '+%F %T') not loading the first voice: ${room} GiB of room under the ceiling, it needs about 52"
    exit 1
fi
docker rm -f "$NAME" > /dev/null 2>&1
# No --rm: a container that exits on its own keeps its log until the next load removes it, so qwen-front.sh
# can save its last lines (once it exited with status 0 in the middle of a class and nothing said why).
docker run -d --name "$NAME" --gpus all --network host --ipc host --memory 56g \
    -e HF_HUB_OFFLINE=1 -e TRANSFORMERS_OFFLINE=1 \
    -e VLLM_USE_FLASHINFER_MOE_FP4=1 -e VLLM_FLASHINFER_MOE_BACKEND=throughput \
    -v "$HOME/models/qwen3.6-35b-a3b-nvfp4:/model:ro" nvcr.io/nvidia/vllm:26.08-py3 \
    vllm serve /model --served-model-name qwen3.6-35b-a3b --host 127.0.0.1 --port 7160 --trust-remote-code \
      --gpu-memory-utilization 0.38 --max-model-len 16384 --max-num-seqs 4 \
      --kv-cache-dtype fp8 --safetensors-load-strategy eager --reasoning-parser qwen3 > /dev/null || exit 1
tries=0
until curl -sf --max-time 2 http://127.0.0.1:7160/health > /dev/null 2>&1; do
    docker inspect "$NAME" > /dev/null 2>&1 || exit 1
    if $GUARD --low; then
        echo "$(date '+%F %T') stopping the first voice's load: available memory under the stop level"
        docker rm -f "$NAME" > /dev/null 2>&1
        exit 1
    fi
    tries=$((tries + 1))
    [ "$tries" -ge 600 ] && { docker rm -f "$NAME" > /dev/null 2>&1; exit 1; }
    sleep 1
done
# Something else answering on 7160 (a server started by hand) is not ours: ours must still be running.
[ "$(docker inspect -f '{{.State.Running}}' "$NAME" 2>/dev/null)" = true ] || exit 1
