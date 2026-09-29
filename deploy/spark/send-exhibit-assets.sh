#!/bin/sh
# Send the four-model comparison's display files to the Spark: the 3D models it shows, the
# sketches they were made from, and the material textures the light study offers. Run on the
# Mac. DATA names the checkout whose files move (default: this one); the models and sketches
# are gitignored, so a worktree has none — point it at the main folder, the way
# send-class-data.sh is pointed.
#
# Why these need their own send. sync.sh carries code, and deliberately not this: the models
# alone are 31 MB and the textures 23, against about 8 MB for everything a class runs, and
# every send goes through the organisers' frp relay, which our own bulk transfers have starved
# before. So the page's code has always reached the node and its models never have, and at
# first neither did `assets/materials/scanned.js` — which the viewer imports, so every 3D
# panel in the studio was blank. sync.sh now carries that file; the heavy media is this script.
#
# What stays on the Mac: `studio/showcase_3d/originals/`, 411 MB. It backs only the "download
# the original model" links, not anything the page draws.
#
# Files, not a database, so this is safe while a class runs: nothing here is read by a class,
# and rsync writes each file whole. --partial resumes a transfer the relay cuts.
set -eu
HOST=${BEYOND_CANVAS_SPARK:-spark@203.0.113.10}
PORT=${BEYOND_CANVAS_SPARK_PORT:-22}
KEY=${BEYOND_CANVAS_SPARK_KEY:-$HOME/.ssh/spark}
RATE=${BEYOND_CANVAS_SPARK_RATE:-400}
DATA=${DATA:-$(git rev-parse --show-toplevel)}
SSH="ssh -i $KEY -o BatchMode=yes -o ConnectTimeout=30 -o ServerAliveInterval=15 -o ServerAliveCountMax=4 -p $PORT"
FOLDERS="assets/portrait assets/geometry assets/fruit assets/materials inputs"

for folder in $FOLDERS; do
    if [ ! -d "$DATA/studio/showcase_3d/$folder" ]; then
        echo "no $folder in $DATA — point DATA at the checkout that holds it" >&2
        exit 1
    fi
done

$SSH "$HOST" 'mkdir -p ~/beyond-canvas/studio/showcase_3d/assets ~/beyond-canvas/studio/showcase_3d/inputs'
for folder in $FOLDERS; do
    echo "sending $folder"
    rsync -a --partial --timeout=180 --bwlimit="$RATE" -e "$SSH" \
        "$DATA/studio/showcase_3d/$folder/" "$HOST:beyond-canvas/studio/showcase_3d/$folder/"
done
echo "sent; the comparison page is https://203.0.113.10:7100/showcase/3d/"
