#!/bin/sh
# Start StepFun First on the hosted Spark. Run on the node; re-running starts only what is down.
#
# Everything listens on 127.0.0.1: the studio on 7060, and the media endpoints on
# the ports studio/profiles/stepfun.yaml already names. The organisers
# require a password on anything published through the node's public doors, so
# the studio asks for the class password (studio/server/serve_door.py) and door.py
# publishes it on node port 7000, which the organisers' relay turns into
# https://203.0.113.10:7100 — a class opens there from any browser, with the
# Mac off. tunnel.sh still reaches the same studio for development.
#
# A media endpoint offers a model only once its weights are complete and its
# container is built; until then it answers 503 and the studio says so.
set -eu

REPO=$HOME/beyond-canvas
MEDIA=$HOME/spark-media
mkdir -p "$MEDIA/media-extra/jobs" "$HOME/logs"
# A job's folder holds its drawing or its voice sample and goes when the job ends, but a service that dies
# mid-job leaves it behind, where it kept the child's material and restart.sh counted it as running for
# ever (code review). A live job sits in its folder for its queue and its run, far under three
# hours (a clip's ceiling is 25 minutes), so anything older is left over and goes at every start.
# restart.sh counts only the younger ones, by the same 180 minutes.
find "$MEDIA/media-extra/jobs" -mindepth 1 -maxdepth 1 -mmin +180 -exec rm -rf {} + 2>/dev/null || true

# ready MODEL FILE IMAGE: offer MODEL only while FILE (its weights' marker) and IMAGE exist.
ready() {
    if [ -f "$2" ] && docker image inspect "$3" >/dev/null 2>&1; then
        touch "$MEDIA/media-extra/$1.ready"
    else
        rm -f "$MEDIA/media-extra/$1.ready"
    fi
}
# Every start leaves a dated line in the service's own log, saying whether restart.sh asked for it
# (it names what it just stopped) or the service was simply found not running. Once the
# studio was down four minutes mid-class and its log said nothing: no stop, and an undated start.
STOPPED=" $* "
up() {
    tmux has-session -t "$1" 2>/dev/null && return 0
    case "$STOPPED" in *" $1 "*) why="restarted by restart.sh" ;; *) why="it was not running" ;; esac
    echo "$(date '+%d/%b/%Y %H:%M:%S') start.sh: starting $1 ($why)" >> "$HOME/logs/$1.log"
    tmux new -d -s "$1" "$2 2>&1 | tee -a $HOME/logs/$1.log"
}
# answering PORT: wait up to 30 s for a media endpoint to answer. The studio's
# start-up check probes every endpoint once and refuses if one is missing, and
# `tmux new -d` returns before the endpoint listens, so without this wait a fresh
# start raced the endpoints and could leave no studio (code review).
# An endpoint that never answers is reported, not fatal: the studio's own check decides.
answering() {
    tries=0
    while [ "$tries" -lt 30 ]; do
        curl -s -o /dev/null --max-time 2 "http://127.0.0.1:$1/v1/models" && return 0
        tries=$((tries + 1))
        sleep 1
    done
    echo "media endpoint on $1 did not answer within 30 s" >&2
}

# The FLUX still pose was retired (operator: Wan makes the real animation). FLUX.2 Klein 4B
# came back later for the storybook's picture-book pages only (media-book, flux_book_worker.py),
# started by a book's first job and kept loaded until ~3 minutes after its last (flux_client.py); the 9B stays
# unused in ~/models.
# No Pixal3D service either: it was archived; ~/pixal3d and its container stay.
ready wan2.2-i2v-a14b "$HOME/models/wan2.2-i2v-a14b-diffusers/.complete" beyond-canvas/spark-diffusers:1
ready flux "$HOME/models/flux2-klein-4b/.complete" beyond-canvas/spark-diffusers:1
ready trellis2 "$HOME/trellis/models/runtime/trellis2/pipeline.json" beyond-canvas/trellis2:dgx-spark
# VoxCPM2 reads a storybook page in a child's copied voice (media-voice, voice_book_worker.py),
# kept loaded like the book's FLUX while pages are read (voice_client.py); build-voice.sh makes both halves.
ready VoxCPM2 "$HOME/models/voxcpm2/.complete" beyond-canvas/voice:1
sh "$REPO/deploy/spark/door-setup.sh"
up recorder "python3 $REPO/deploy/spark/spark_recorder.py"
up media-video "python3 $REPO/deploy/spark/media_spark.py --kind video --root $MEDIA --port 7260"
up media-trellis "python3 $REPO/deploy/spark/media_spark.py --kind trellis --root $MEDIA --port 7240"
up media-book "python3 $REPO/deploy/spark/media_spark.py --kind book --root $MEDIA --port 7270"
up media-voice "python3 $REPO/deploy/spark/media_spark.py --kind voice --root $MEDIA --port 7280"
for port in 7260 7240 7270 7280; do answering "$port"; done
# NVIDIA's safety model kept loaded for the class's second look (~11 GiB); it steps aside while a clip
# needs the memory (safety-reader.sh, media_spark.room_for).
up safety-reader "sh $REPO/deploy/spark/safety-reader.sh"
# TRELLIS.2 kept loaded between 3D jobs: loading is about 40% of a job, and the sketch
# entrance is where a child waits. It steps aside for a clip first, before the safety reader does.
up trellis-resident "sh $REPO/deploy/spark/trellis-resident.sh"
# Qwen3.6 kept loaded as the class's first voice (~50 GiB): it writes the chat lines and
# Step 3.7 Flash checks them. A clip pauses it after the 3D model; chat falls back to Step meanwhile.
up qwen-front "sh $REPO/deploy/spark/qwen-front.sh"
# The studio comes up even while a model is missing — Wan's 126 GB take hours to
# arrive, and after a restart any endpoint can lag — and the page says what is not
# ready. `studio.start` refuses to start at all in that case, so it runs here only
# as the check, into the log, and `studio.serve` starts the classroom itself.
# Until a code review this started through `studio.start`, so the session
# died at once whenever Wan was still downloading and nothing said so.
if ! (cd "$REPO" && .venv/bin/python -m studio.start --check --deployment stepfun) >> "$HOME/logs/studio.log" 2>&1; then
    echo "not every model is ready yet; the page will say which (details in ~/logs/studio.log)"
fi
# deploy/spark/bin first on the PATH: ffmpeg and ffprobe, which the studio checks every clip
# with, run from beyond-canvas/ffmpeg:1 (build-ffmpeg.sh); the node itself has neither.
up studio "cd $REPO && PATH=$REPO/deploy/spark/bin:$PATH BEYOND_CANVAS_DOOR=$HOME/.config/beyond-canvas/door .venv/bin/python -m studio.serve --profile stepfun --deployment stepfun --port 7060"
up door "python3 $REPO/deploy/spark/door.py"
ls "$MEDIA/media-extra/" | grep '\.ready$' || echo "no media model ready yet"
tmux ls
