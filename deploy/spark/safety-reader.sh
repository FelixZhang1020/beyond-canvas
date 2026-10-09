#!/bin/sh
# Keep NVIDIA's safety model (Nemotron 3.5 Content Safety) loaded on the Spark for the class's second
# look at the door and on the way out (operator's go). start.sh runs this in tmux as
# `safety-reader`; the studio reaches it at 127.0.0.1:7140 (the safety.reader slot in stepfun.yaml).
#
# It loads while holding the jobs' GPU lock (safety-reader-load.sh), so a load never overlaps a job's
# memory use, and then holds ~11 GiB but not the lock. It is always loaded (operator): no job asks it to
# step aside, so a look can be taken at any moment, a clip's way-out look included; a job that does not fit
# beside it asks the other kept-loaded models for room instead (media_spark.room_for). If it ever dies it is
# started again, as soon as the node has the room.
MEDIA=$HOME/spark-media
RESIDENT=$MEDIA/resident
WEIGHTS=$HOME/models/nemotron-3.5-content-safety
mkdir -p "$RESIDENT"
. "$HOME/beyond-canvas/deploy/spark/keeper-common.sh"
[ -f "$WEIGHTS/.complete" ] || echo "$(date '+%F %T') waiting for the weights at $WEIGHTS"
while :; do
    if [ ! -f "$WEIGHTS/.complete" ]; then
        sleep 5
        continue
    fi
    if job_waiting; then
        sleep 5
        continue
    fi
    if already_up nemotron-safety; then
        echo "$(date '+%F %T') found it already loaded; watching it"
        docker wait nemotron-safety > /dev/null 2>&1
        continue
    fi
    load_under_lock "$HOME/beyond-canvas/deploy/spark/safety-reader-load.sh"
    loaded=$?
    if [ "$loaded" -eq 75 ]; then
        sleep 5
        continue
    fi
    if [ "$loaded" -eq 0 ]; then
        echo "$(date '+%F %T') safety reader loaded"
        docker wait nemotron-safety > /dev/null 2>&1
        echo "$(date '+%F %T') safety reader stopped"
        sleep 5
    else
        sleep 30    # no room, or it would not start: try again, not every few seconds
    fi
done
