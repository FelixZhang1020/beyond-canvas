#!/bin/sh
# Keep Qwen3.6 loaded on the Spark as the class's first voice (operator): it writes the opening,
# the reply and the smaller question in about a second, where Step 3.7 Flash thinks for about forty. The
# same Qwen judges every line, screens every drawing and writes the drafts (every 7160 slot in stepfun.yaml).
# start.sh runs this in tmux as `qwen-front`; the studio reaches it at 127.0.0.1:7160.
#
# It loads while holding the jobs' GPU lock (qwen-front-load.sh), so a load never overlaps a job's memory
# use, and then holds ~50 GiB but not the lock. It cannot run smaller, so it never fits beside a clip: a
# clip pauses it (~/spark-media/resident/front-paused, media_spark.room_for) after the 3D model, and Step 3.7
# Flash stands in for it (operator; vlm.standin in stepfun.yaml): the class's chat, its checks and the screen go
# to Step, slower but whole, until it has loaded again, about four minutes after the clip.
# If it ever dies it is started again.
MEDIA=$HOME/spark-media
RESIDENT=$MEDIA/resident
WEIGHTS=$HOME/models/qwen3.6-35b-a3b-nvfp4
mkdir -p "$RESIDENT"
. "$HOME/beyond-canvas/deploy/spark/keeper-common.sh"
# True while the pause names a live process; a flag left by a process that is gone has lapsed.
paused_now() {
    [ -e "$RESIDENT/front-paused" ] || return 1
    holder=$(cat "$RESIDENT/front-paused" 2>/dev/null)
    if [ -n "$holder" ] && kill -0 "$holder" 2>/dev/null; then
        return 0
    fi
    rm -f "$RESIDENT/front-paused"
    echo "$(date '+%F %T') the pause was left by a process that is gone; cleared"
    return 1
}
[ -f "$WEIGHTS/config.json" ] || echo "$(date '+%F %T') waiting for the weights at $WEIGHTS"
while :; do
    if paused_now || [ ! -f "$WEIGHTS/config.json" ]; then
        sleep 5
        continue
    fi
    if job_waiting; then
        sleep 5
        continue
    fi
    if already_up qwen-front; then
        echo "$(date '+%F %T') found it already loaded; watching it"
        docker wait qwen-front > /dev/null 2>&1
        continue
    fi
    load_under_lock "$HOME/beyond-canvas/deploy/spark/qwen-front-load.sh"
    loaded=$?
    if [ "$loaded" -eq 75 ]; then
        sleep 5
        continue
    fi
    if [ "$loaded" -eq 0 ]; then
        echo "$(date '+%F %T') first voice loaded"
        docker wait qwen-front > /dev/null 2>&1
        # Its last lines and status, kept until the next exit: the loader runs it without --rm for this.
        docker logs --tail 100 qwen-front > "$HOME/logs/qwen-front-last-exit.log" 2>&1
        echo "$(date '+%F %T') first voice stopped (status $(docker inspect -f '{{.State.ExitCode}}' qwen-front 2>/dev/null)); its last lines are in ~/logs/qwen-front-last-exit.log"
        sleep 5
    else
        sleep 30    # no room, or it would not start: try again, not every few seconds
    fi
done
