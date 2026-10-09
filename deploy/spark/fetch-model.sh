#!/bin/sh
# Bring one Blender model from the Spark to the Mac and open it in the Blender app. Operator
# decision: every Blender job runs on the Spark; the Mac downloads a model only to look at it.
#
#   sh deploy/spark/fetch-model.sh --list                                      # models on the Spark, newest first
#   sh deploy/spark/fetch-model.sh output/foguang-east-hall/foguang-east-hall-v25.blend
#   sh deploy/spark/fetch-model.sh .studio/showpiece/runs/<run>/hall.blend     # what a live run built
#
# The path is inside ~/beyond-canvas on the node. The copy lands under output/from-spark/ in the
# main folder (gitignored), at the same relative path, from whichever worktree this runs in; nothing
# goes back, so a change made on the Mac stays on the Mac, and fetching again keeps the Mac's copy
# beside the new one rather than replacing it silently. The node is wiped when the contest ends: a model
# made there that matters must be brought home with this before then.
set -eu
HOST=${BEYOND_CANVAS_SPARK:-spark@203.0.113.10}
PORT=${BEYOND_CANVAS_SPARK_PORT:-22}
KEY=${BEYOND_CANVAS_SPARK_KEY:-$HOME/.ssh/spark}
SSH="ssh -i $KEY -o BatchMode=yes -o ConnectTimeout=30 -o ServerAliveInterval=15 -o ServerAliveCountMax=4 -p $PORT"
DATA=${DATA:-$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")}
USAGE="usage: fetch-model.sh --list | <path inside ~/beyond-canvas on the Spark,
    e.g. output/foguang-east-hall/foguang-east-hall-v25.blend>"

if [ "${1:-}" = --list ]; then
    $SSH "$HOST" 'cd ~/beyond-canvas && find output .studio/showpiece -name "*.blend" \
        -printf "%TY-%Tm-%Td %TH:%TM  %6k KB  %p\n" 2>/dev/null | sort -r | head -40'
    exit 0
fi
MODEL=${1:?$USAGE}
case "$MODEL" in
    /* | *..*) echo "$USAGE" >&2; exit 1 ;;
esac
OUT=$DATA/output/from-spark/$MODEL
mkdir -p "$(dirname "$OUT")"
# A copy already here that differs (changed on the Mac, or an older state) is kept beside it.
rsync -a --partial --timeout=120 --backup --suffix=".before-$(date +%Y%m%d-%H%M%S)" \
    -e "$SSH" "$HOST:beyond-canvas/$MODEL" "$OUT"
echo "downloaded to $OUT"
# A new Blender window (-n), so a model never lands in one already open with unsaved work.
if [ -d /Applications/Blender.app ]; then open -n -a Blender "$OUT"; fi
