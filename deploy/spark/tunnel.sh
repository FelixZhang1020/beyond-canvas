#!/bin/sh
# Open the Spark's classroom on this Mac at http://localhost:7070/ — keep it running.
#
# The studio on the node listens only on its own 127.0.0.1:7060; this forwards a
# Mac port to it over ssh. Nothing is published on the node's public doors, and
# `localhost` is what lets the page use the camera and microphone at all:
# browsers allow them only on a secure origin. 7070 rather than 7060 so the
# Mac's own studio can run beside it.
set -eu
HOST=${BEYOND_CANVAS_SPARK:-spark@203.0.113.10}
PORT=${BEYOND_CANVAS_SPARK_PORT:-22}
KEY=${BEYOND_CANVAS_SPARK_KEY:-$HOME/.ssh/spark}
LOCAL=${BEYOND_CANVAS_SPARK_LOCAL:-7070}
echo "Spark classroom on http://localhost:$LOCAL/"
exec ssh -N -i "$KEY" -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -p "$PORT" \
    -L "$LOCAL:127.0.0.1:7060" "$HOST"
