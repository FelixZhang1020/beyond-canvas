#!/bin/sh
# Build beyond-canvas/ffmpeg:1 (Dockerfile.ffmpeg) on the node, under the memory guard like every
# build here, then prove both tools answer through the wrappers the studio will call.
set -eu
DEPLOY=$HOME/beyond-canvas/deploy
python3 "$DEPLOY/spark/memory_guard.py" --floor 24 -- docker build -t beyond-canvas/ffmpeg:1 \
    -f "$DEPLOY/spark/Dockerfile.ffmpeg" --build-arg APT_MIRROR=https://mirrors.tuna.tsinghua.edu.cn/ubuntu-ports \
    "$DEPLOY/spark"
"$DEPLOY/spark/bin/ffprobe" -version | head -1
"$DEPLOY/spark/bin/ffmpeg" -hide_banner -encoders | grep libx264
