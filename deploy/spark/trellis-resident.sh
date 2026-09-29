#!/bin/sh
# Keep TRELLIS.2 loaded on the Spark (trellis_resident.py), so a 3D model from a sketch takes about
# half as long: loading is roughly 40% of a job (operator decision). start.sh runs this
# in tmux as `trellis-resident`.
#
# The model loads while this holds the jobs' shared GPU lock (trellis-resident-load.sh), so a load
# never overlaps a job's memory use; afterwards it holds the weights but not the lock. While
# ~/spark-media/resident/trellis-paused exists — a clip, which needs that memory, sets it and stops
# the container (media_spark.room_for) — nothing is started; once the clip is done the flag goes and
# the model loads again. If the process ever dies, it is started again; 3D jobs meanwhile fall back
# to a one-off container (media_spark.command), which is what every job did before this existed.
MEDIA=$HOME/spark-media
RESIDENT=$MEDIA/resident
mkdir -p "$RESIDENT"
. "$HOME/beyond-canvas/deploy/spark/keeper-common.sh"
while :; do
    if [ -e "$RESIDENT/trellis-paused" ]; then
        # The flag names the media service that paused us. If that process is gone (killed before it
        # could clear the flag), the pause has lapsed — the picture model found this out first.
        holder=$(cat "$RESIDENT/trellis-paused" 2>/dev/null)
        if [ -n "$holder" ] && kill -0 "$holder" 2>/dev/null; then
            sleep 5
            continue
        fi
        rm -f "$RESIDENT/trellis-paused"
        echo "$(date '+%F %T') the pause was left by a process that is gone; cleared"
    fi
    if [ ! -d "$HOME/trellis/models/runtime/trellis2" ]; then
        sleep 5
        continue
    fi
    if job_waiting; then
        sleep 5
        continue
    fi
    if already_up beyond-canvas-trellis-resident; then
        echo "$(date '+%F %T') found it already loaded; watching it"
        docker wait beyond-canvas-trellis-resident > /dev/null 2>&1
        continue
    fi
    rm -f "$RESIDENT/trellis.sock"
    load_under_lock "$HOME/beyond-canvas/deploy/spark/trellis-resident-load.sh"
    loaded=$?
    if [ "$loaded" -eq 75 ]; then
        sleep 5
        continue
    fi
    if [ "$loaded" -eq 0 ]; then
        echo "$(date '+%F %T') resident TRELLIS.2 loaded"
        docker wait beyond-canvas-trellis-resident > /dev/null 2>&1
        echo "$(date '+%F %T') resident TRELLIS.2 stopped"
    else
        sleep 25    # no room, or it would not start: try again, not every few seconds
    fi
    rm -f "$RESIDENT/trellis.sock"
    sleep 5
done
