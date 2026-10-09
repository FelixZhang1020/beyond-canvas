#!/bin/sh
# Send the temple showpiece's demos to the Spark: the five recorded runs its one-press buttons
# play (`recorded-*`, 684 MB, no file over 17 MB) and the models its 3D view shows
# (`runs/models/*.glb`, 18 MB). Run on the Mac; DATA names the checkout whose .studio holds
# them (a worktree has none, so point it at the main folder). Safe while the studio runs: the
# page lists runs by reading the folder.
#
# Only what the page shows goes — never the 58 timestamped run folders or the rest of the
# 8.8 GB (operator decision). The temple's .blend files do not go this way: the
# Spark has its own Blender (deploy/spark/Dockerfile.blender) and v22-v25 were sent
# once to ~/beyond-canvas/output/foguang-east-hall/ with `sync.sh <file>`; live runs made there stay
# there, and deploy/spark/fetch-model.sh brings any model home to look at.
set -eu
HOST=${BEYOND_CANVAS_SPARK:-spark@203.0.113.10}
PORT=${BEYOND_CANVAS_SPARK_PORT:-22}
KEY=${BEYOND_CANVAS_SPARK_KEY:-$HOME/.ssh/spark}
DATA=${DATA:-$(git rev-parse --show-toplevel)}
SSH="ssh -i $KEY -o BatchMode=yes -o ConnectTimeout=30 -o ServerAliveInterval=15 -o ServerAliveCountMax=4 -p $PORT"
RUNS=$DATA/.studio/showpiece/runs
$SSH "$HOST" 'mkdir -p ~/beyond-canvas/.studio/showpiece/runs/models'
for run in "$RUNS"/recorded-*; do
    rsync -a --partial --timeout=120 -e "$SSH" "$run" "$HOST:beyond-canvas/.studio/showpiece/runs/"
    echo "sent $(basename "$run")"
done
rsync -a --partial --timeout=120 -e "$SSH" "$RUNS"/models/*.glb "$HOST:beyond-canvas/.studio/showpiece/runs/models/"
echo "sent the temple model; the page's demo buttons and 3D view read them on the next load"
