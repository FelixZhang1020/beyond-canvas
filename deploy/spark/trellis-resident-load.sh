#!/bin/sh
# Start the resident TRELLIS.2 container and wait until it answers (its socket appears only once the
# model is loaded). trellis-resident.sh runs this holding the GPU lock, so a load never overlaps a
# job's memory use. Mounts and settings are the 3D job's (media_spark.command) plus the job folders
# and the socket folder; it runs as our own user so the socket and the models it writes are ours.
MEDIA=$HOME/spark-media
RESIDENT=$MEDIA/resident
NAME=beyond-canvas-trellis-resident
# Since the first voice (~50 GiB) is kept loaded too, this can reload into far less room than it used to,
# and nothing measured its load. So as qwen-front-load.sh does: 38 GiB is the most a 3D job was ever seen to
# hold (media_spark.PEAK_GIB), the jobs' floor is 24, and a watcher stops the load at the floor.
FLOOR=24
available() { awk '/^MemAvailable:/ {print int($2 / 1048576)}' /proc/meminfo; }
if [ "$(available)" -lt 62 ]; then
    echo "$(date '+%F %T') not loading TRELLIS.2: $(available) GiB available, it needs about 38 above the ${FLOOR} GiB floor"
    exit 1
fi
docker rm -f "$NAME" > /dev/null 2>&1
docker run -d --rm --name "$NAME" --gpus all --shm-size 16g -u "$(id -u):$(id -g)" -e HOME=/tmp \
    -e HF_HUB_OFFLINE=1 -e TRANSFORMERS_OFFLINE=1 -e HF_MODULES_CACHE=/tmp/hf-modules \
    -e PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
    -e TRELLIS_LOW_VRAM=0 -e ATTN_BACKEND=flash_attn -e SPARSE_ATTN_BACKEND=flash_attn \
    -e HF_HOME=/models/huggingface -v "$HOME/trellis/models:/models:ro" \
    -v "$HOME/beyond-canvas/deploy/trellis2/patches/image_feature_extractor.py:/app/trellis2/modules/image_feature_extractor.py:ro" \
    -v "$HOME/beyond-canvas/deploy/gpu-media/extra:/runner:ro" \
    -v "$HOME/beyond-canvas/deploy/spark:/spark:ro" \
    -v "$MEDIA/media-extra/jobs:/jobs" -v "$RESIDENT:/resident" \
    --entrypoint python beyond-canvas/trellis2:dgx-spark /spark/trellis_resident.py > /dev/null || exit 1
tries=0
until [ -S "$RESIDENT/trellis.sock" ]; do
    docker inspect "$NAME" > /dev/null 2>&1 || exit 1
    if [ "$(available)" -lt "$FLOOR" ]; then
        echo "$(date '+%F %T') stopping TRELLIS.2's load: $(available) GiB available, under the floor"
        docker rm -f "$NAME" > /dev/null 2>&1
        exit 1
    fi
    tries=$((tries + 1))
    [ "$tries" -ge 300 ] && { docker rm -f "$NAME" > /dev/null 2>&1; exit 1; }
    sleep 1
done
