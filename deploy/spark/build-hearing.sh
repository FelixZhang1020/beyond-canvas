#!/bin/sh
# Build beyond-canvas/hearing:1 (Dockerfile.hearing) on the node and fetch Whisper's weights, so
# transcription can run on the node's chip instead of going to StepFun. Run on the Spark.
#
# The weights are openai-mirror/whisper-large-v3-turbo from ModelScope (1.5 GiB), fetched by
# fetch_weights.py at its capped rate, like every other model here; the operator allowed this
# download. Nothing starts by itself: start it when a profile names it, with
#     docker run --rm --gpus all --network host -v ~/models/whisper:/models/whisper:ro \
#         -v ~/beyond-canvas/deploy/spark:/work:ro beyond-canvas/hearing:1 \
#         python /work/hearing_worker.py --port 7290
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
MODEL=${MODEL:-$HOME/models/whisper}
python3 "$HERE/memory_guard.py" --floor 24 -- docker build -t beyond-canvas/hearing:1 \
    -f "$HERE/Dockerfile.hearing" "$HERE"
if [ ! -f "$MODEL/.complete" ]; then
    "$HOME/tools/bin/python" "$HERE/fetch_weights.py" openai-mirror/whisper-large-v3-turbo "$MODEL" --rate 6
fi
du -sh "$MODEL"
