#!/bin/sh
# Keep NVIDIA's safety model (Nemotron 3.5 Content Safety) loaded on the Spark for the class's second
# look at the door and on the way out (operator's go). start.sh runs this in tmux as
# `safety-reader`; the studio reaches it at 127.0.0.1:7140 (the safety.reader slot in stepfun.yaml).
#
# It loads while holding the jobs' GPU lock (safety-reader-load.sh), so a load never overlaps a job's
# memory use, and then holds ~11 GiB but not the lock. It is the one model the Spark keeps loaded (the
# picture model that also was is retired). While a job that needs its memory has paused it
# (media_spark.room_for: the clip does), nothing is started, and a look the class asks for meanwhile
# stops nothing and is recorded as unavailable; the clip's own check waits for it to load again.
# If it ever dies it is started again.
MEDIA=$HOME/spark-media
RESIDENT=$MEDIA/resident
WEIGHTS=$HOME/models/nemotron-3.5-content-safety
mkdir -p "$RESIDENT"
. "$HOME/beyond-canvas/deploy/spark/keeper-common.sh"
# True while ~/spark-media/resident/paused names a live process: a job that needs the memory set it and
# stopped the reader (media_spark.room_for). A flag left by a process that is gone has lapsed; cleared.
paused_now() {
    [ -e "$RESIDENT/paused" ] || return 1
    holder=$(cat "$RESIDENT/paused" 2>/dev/null)
    if [ -n "$holder" ] && kill -0 "$holder" 2>/dev/null; then
        return 0
    fi
    rm -f "$RESIDENT/paused"
    echo "$(date '+%F %T') the pause was left by a process that is gone; cleared"
    return 1
}
[ -f "$WEIGHTS/.complete" ] || echo "$(date '+%F %T') waiting for the weights at $WEIGHTS"
while :; do
    if paused_now || [ ! -f "$WEIGHTS/.complete" ]; then
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
