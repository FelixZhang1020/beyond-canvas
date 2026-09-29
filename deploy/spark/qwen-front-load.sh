#!/bin/sh
# Start the first voice's container and wait until it answers (/health answers only once the model is
# loaded, about four minutes). qwen-front.sh runs this holding the GPU lock. Measured on the node:
# the node's used memory rose by 50 GB, and no share below 0.38 starts at all
# (docs/measured/chat-speed-and-front-voice.md). It is never taken below the jobs' 24 GiB
# floor (memory_guard.py): this box freezes rather than failing when memory runs out, and loading passes
# through a peak above what it keeps, so a watcher stops it the moment the floor is reached. The measured
# load started from 82 GiB available, never went below 30 during the load and settled at about 32: it
# takes up to ~52 at its peak, so 76 available leaves the floor intact.
NAME=qwen-front
FLOOR=24
available() { awk '/^MemAvailable:/ {print int($2 / 1048576)}' /proc/meminfo; }
if [ "$(available)" -lt 76 ]; then
    echo "$(date '+%F %T') not loading the first voice: $(available) GiB available, it needs about 52 above the ${FLOOR} GiB floor"
    exit 1
fi
docker rm -f "$NAME" > /dev/null 2>&1
docker run -d --rm --name "$NAME" --gpus all --network host --ipc host --memory 56g \
    -e HF_HUB_OFFLINE=1 -e TRANSFORMERS_OFFLINE=1 \
    -e VLLM_USE_FLASHINFER_MOE_FP4=1 -e VLLM_FLASHINFER_MOE_BACKEND=throughput \
    -v "$HOME/models/qwen3.6-35b-a3b-nvfp4:/model:ro" nvcr.io/nvidia/vllm:26.08-py3 \
    vllm serve /model --served-model-name qwen3.6-35b-a3b --host 127.0.0.1 --port 7160 --trust-remote-code \
      --gpu-memory-utilization 0.38 --max-model-len 16384 --max-num-seqs 4 \
      --kv-cache-dtype fp8 --safetensors-load-strategy eager --reasoning-parser qwen3 > /dev/null || exit 1
tries=0
until curl -sf --max-time 2 http://127.0.0.1:7160/health > /dev/null 2>&1; do
    docker inspect "$NAME" > /dev/null 2>&1 || exit 1
    if [ "$(available)" -lt "$FLOOR" ]; then
        echo "$(date '+%F %T') stopping the first voice's load: $(available) GiB available, under the floor"
        docker rm -f "$NAME" > /dev/null 2>&1
        exit 1
    fi
    tries=$((tries + 1))
    [ "$tries" -ge 600 ] && { docker rm -f "$NAME" > /dev/null 2>&1; exit 1; }
    sleep 1
done
# Something else answering on 7160 (a server started by hand) is not ours: ours must still be running.
[ "$(docker inspect -f '{{.State.Running}}' "$NAME" 2>/dev/null)" = true ] || exit 1
