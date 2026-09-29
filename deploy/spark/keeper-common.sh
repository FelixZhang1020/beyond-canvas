# Shared by the three keepers that hold a model loaded between jobs (safety-reader.sh, trellis-resident.sh,
# qwen-front.sh); sourced, not run. Standard sh.

# True while a class job (a clip or a 3D model) is waiting for the GPU lock: the media service writes
# ~/spark-media/resident/waiting-<its pid>-<thread> while it waits and removes it when the job ends
# (media_spark.SparkHandler). A keeper then leaves the lock alone, so a job queued behind a clip is not
# kept waiting by three reloads in a row: the first voice's alone holds the lock about four minutes, and
# the job's own time limit is already running. A flag whose process is gone has lapsed and is removed.
job_waiting() {
    for flag in "$RESIDENT"/waiting-*; do
        [ -e "$flag" ] || continue
        if kill -0 "$(cat "$flag" 2>/dev/null)" 2>/dev/null; then
            return 0
        fi
        rm -f "$flag"
    done
    return 1
}

# True when the named container is already running: a keeper started again (restart.sh) adopts the model
# that is loaded instead of loading a second copy or removing a healthy one.
already_up() {
    [ "$(docker inspect -f '{{.State.Running}}' "$1" 2>/dev/null)" = true ]
}

# Take the GPU lock without queueing for it, and run the load script under it. Exit 75 means the lock was
# busy: a job has it, and the keeper looks again shortly rather than queueing ahead of the next job.
load_under_lock() {
    flock -n -E 75 "$MEDIA/gpu.lock" sh "$1"
}
