#!/bin/sh
# Restart named services on the Spark, and nothing else. Run on the Mac.
#
#   sh deploy/spark/restart.sh studio                 # one service
#   sh deploy/spark/restart.sh media-video media-trellis
#   sh deploy/spark/restart.sh --list                 # the names it will accept
#
# Why this exists rather than an ssh command typed each time: a standing permission to run any
# command on the node is a permission to do anything to it, and the node runs children's classes.
# This script is the narrow thing that permission can point at. It accepts only the eight service
# names below, refuses every other word before it opens a connection, and the only commands it
# ever runs there are `tmux kill-session` on a name from that list and the node's own start.sh,
# given those same names so its log can say the restart was asked for.
# There is no argument that makes it run anything else.
#
# A service the node is not currently running is not an error: start.sh brings up whatever is
# down, so asking for a stopped service simply starts it.
#
# `studio` drops whatever a teacher has open, and it and the two media services drop a clip or 3D
# job in flight: those three are refused while a job runs (below; --while-busy overrides). A teacher's
# open page is not something this can see, so look at the studio's log before restarting it. The
# keepers (`qwen-front`, `trellis-resident`, `safety-reader`) adopt the model already loaded when
# restarted (keeper-common.sh), so restarting one reloads nothing.
set -eu

HOST=${BEYOND_CANVAS_SPARK:-spark@203.0.113.10}
PORT=${BEYOND_CANVAS_SPARK_PORT:-22}
KEY=${BEYOND_CANVAS_SPARK_KEY:-$HOME/.ssh/spark}
# ServerAlive: the organisers' relay drops connections silently; these make a stalled one fail in
# about a minute so the retry below takes over instead of hanging.
SSH="ssh -i $KEY -o BatchMode=yes -o ConnectTimeout=30 -o ServerAliveInterval=15 -o ServerAliveCountMax=4 -p $PORT"

# The only names this script will act on. Every one is a tmux session start.sh knows how to bring
# back; a name that is not here is refused, which is the whole safety property.
KNOWN="door media-book media-trellis media-video media-voice qwen-front recorder safety-reader studio trellis-resident"

usage() {
    echo "usage: sh deploy/spark/restart.sh <service>... | --list" >&2
    echo "services: $KNOWN" >&2
}

# A studio or media restart drops a clip or 3D model being made. Once a restart
# whose caller had read the job count and not looked at it cut off a clip 6½ minutes in. So the
# script asks the node itself, and refuses while a job runs; --while-busy is the deliberate way past.
BUSY_OK=no
if [ "${1:-}" = "--while-busy" ]; then
    BUSY_OK=yes
    shift
fi

case "${1:-}" in
    --list) echo "$KNOWN" | tr ' ' '\n'; exit 0 ;;
    -h|--help) usage; exit 0 ;;
    "") usage; exit 2 ;;
esac

# Check every name BEFORE anything is stopped, so a typo in the second name cannot leave the first
# service down. A refusal here never opens a connection.
for want in "$@"; do
    found=no
    for known in $KNOWN; do
        [ "$want" = "$known" ] && found=yes && break
    done
    if [ "$found" = no ]; then
        echo "restart.sh does not know a service called '$want', so it will not touch the node." >&2
        usage
        exit 2
    fi
done

# One connection counts the jobs, stops the named sessions and has start.sh bring up everything that is
# down, all while holding ~/spark-media/restart.lock, which the media service also takes while it makes
# a job's folder: a job is either counted here or made after the restart, never lost in between. Until
# a code review the count and the restart went as two connections with a gap between.
# The names reaching the node are the ones checked above and nothing else. A folder older than 180
# minutes is one a crashed service left, not a job, and start.sh removes it (code review).
GUARD=""
case " $* " in
    *" studio "*)
        [ "$BUSY_OK" = yes ] || GUARD='n=$(find ~/spark-media/media-extra/jobs -mindepth 1 -maxdepth 1 -mmin -180 2>/dev/null | wc -l); [ "$n" -eq 0 ] || exit 3; python3 ~/beyond-canvas/deploy/spark/studio_idle.py || exit 3;' ;;
    *" media-video "*|*" media-trellis "*|*" media-book "*|*" media-voice "*)
        [ "$BUSY_OK" = yes ] || GUARD='n=$(find ~/spark-media/media-extra/jobs -mindepth 1 -maxdepth 1 -mmin -180 2>/dev/null | wc -l); [ "$n" -eq 0 ] || exit 3;' ;;
esac
STOP=""
for want in "$@"; do
    STOP="$STOP tmux kill-session -t $want 2>/dev/null || true;"
done

echo "restarting on $HOST:$*"
# Retried only when the connection itself failed (ssh says 255): a refusal is an answer, not a dropped line.
for try in 1 2 3 4 5 6; do
    status=0
    $SSH "$HOST" "mkdir -p ~/spark-media && flock ~/spark-media/restart.lock sh -c '$GUARD $STOP sh ~/beyond-canvas/deploy/spark/start.sh $*'" \
        || status=$?
    [ "$status" -eq 255 ] || break
    sleep $((try * 5))
done
if [ "$status" -eq 3 ]; then
    echo "a classroom request or media job is still running on the Spark; restarting now would lose it." >&2
    echo "wait for it to finish, or restart regardless: sh deploy/spark/restart.sh --while-busy $*" >&2
    exit 3
fi
[ "$status" -eq 0 ] || { echo "the Spark did not restart it (status $status)" >&2; exit 1; }
echo "asked start.sh to bring back:$(printf ' %s' "$@")"
echo "check it with: sh deploy/spark/compare-with-spark.sh"
