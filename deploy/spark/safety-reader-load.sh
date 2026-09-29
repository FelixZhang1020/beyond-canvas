#!/bin/sh
# Start the safety reader's container and wait until it answers (/health answers only once the model
# is loaded). safety-reader.sh runs this holding the GPU lock. The server listens on 127.0.0.1 only,
# looks at one picture at a time and logs nothing about one (skills/studio-safety/scripts/nemotron_server.py).
# Its ~11 GiB is never taken below the jobs' 24 GiB floor (memory_guard.py): this box freezes rather
# than failing when memory runs out, and other work on it does not take our lock.
NAME=nemotron-safety
available=$(awk '/^MemAvailable:/ {print int($2 / 1048576)}' /proc/meminfo)
if [ "${available:-0}" -lt 35 ]; then
    echo "$(date '+%F %T') not loading the safety reader: ${available} GiB available, it needs 11 above the 24 GiB floor"
    exit 1
fi
docker rm -f "$NAME" > /dev/null 2>&1
docker run -d --rm --name "$NAME" --gpus all --network host --memory 40g \
    -e HF_HUB_OFFLINE=1 -e TRANSFORMERS_OFFLINE=1 \
    -v "$HOME/models/nemotron-3.5-content-safety:/model:ro" -v "$HOME/beyond-canvas:/src:ro" \
    --entrypoint python beyond-canvas/spark-diffusers:1 \
    /src/skills/studio-safety/scripts/nemotron_server.py /model --port 7140 > /dev/null || exit 1
tries=0
until curl -sf --max-time 2 http://127.0.0.1:7140/health > /dev/null 2>&1; do
    docker inspect "$NAME" > /dev/null 2>&1 || exit 1
    tries=$((tries + 1))
    [ "$tries" -ge 180 ] && { docker rm -f "$NAME" > /dev/null 2>&1; exit 1; }
    sleep 1
done
# Something else answering on 7140 (a server started by hand) is not ours: ours must still be running.
[ "$(docker inspect -f '{{.State.Running}}' "$NAME" 2>/dev/null)" = true ] || exit 1
