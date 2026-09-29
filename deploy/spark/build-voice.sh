#!/bin/sh
# Build beyond-canvas/voice:1 (Dockerfile.voice) on the node and fetch VoxCPM2's weights, so a storybook can
# be read in a child's own voice on the Spark's chip (operator). Run on the Spark.
#
# The weights are OpenBMB/VoxCPM2 from ModelScope (4.96 GB), fetched by fetch_weights.py at its capped rate,
# like every other model here. start.sh offers the voice (media-voice, 7280) once both are in.
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
MODEL=${MODEL:-$HOME/models/voxcpm2}
python3 "$HERE/memory_guard.py" --floor 24 -- docker build -t beyond-canvas/voice:1 \
    -f "$HERE/Dockerfile.voice" "$HERE"
if [ ! -f "$MODEL/.complete" ]; then
    "$HOME/tools/bin/python" "$HERE/fetch_weights.py" OpenBMB/VoxCPM2 "$MODEL" --rate 5
fi
du -sh "$MODEL"
