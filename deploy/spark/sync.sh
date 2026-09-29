#!/bin/sh
# Copy the studio to the hosted DGX Spark: what a class runs, plus the one key it needs.
#
# Run on the Mac, from the checkout you want the Spark to run. The node has no
# GitHub, so this is how code gets there.
#
#   sh deploy/spark/sync.sh              # the class's code, refused if behind main
#   sh deploy/spark/sync.sh --anyway     # send it even so
#   sh deploy/spark/sync.sh FOLDER       # one folder instead; checked unless it holds no tracked file
#
# The file list is git's own (tracked, plus new files not ignored), so nothing
# gitignored travels here: not `Training Docs/` and not `.env`. The class data —
# the Portfolio in `.studio/` and the sample drawings in `Image Sample/` (AI-made
# or the operator's own public data, operator decision) — goes by
# send-class-data.sh instead, and every run of this one ends by bringing a copy
# of the Spark's Portfolio back (pull-portfolio.sh). Of the code, only what a
# class runs is sent, about 8 MB compressed against 35 MB for the whole project:
# docs, tests, design files and 3D texture assets stay behind. The texture rule
# names the PNGs rather than their folder: `assets/materials/scanned.js` sits
# among them and the 3D viewer imports it, so excluding the folder left every
# 3D panel on the node blank — the module 404'd, so nothing in the viewer ran.
# Found on the class page; it is 5 KB and loads textures lazily.
#
# Only what changed crosses the relay, and the node packs the send itself (operator:
# "build everything on Spark"). The node keeps one mirror of each checkout's files, filled the first
# time from the class's own code, and rsync sends only the differences into it; the node then packs
# exactly the files this checkout lists and hands them to receive.sh as before. The
# Mac used to pack the whole ~8 MB and send it as 256 KB pieces every time, which the organisers' relay
# (once as slow as 5 KB/s; it has also cut anything past ~512 KB) turned into an hour a send.
# rsync writes each file whole before it replaces the old one, and is retried as a whole: a rerun sends
# only what did not arrive. RATE caps it, in Kbit/s as before.
#
# `.env` never leaves the Mac. Two keys are the exceptions, each an operator decision: the
# StepFun key, which StepFun First on the Spark calls for everything it buys, and
# the DashScope key, for the teacher's 10-second online clip from Wan 3.0. They are
# written into a fresh file on the node, alone; no other line of `.env` is ever read for it.
set -eu

HOST=${BEYOND_CANVAS_SPARK:-spark@203.0.113.10}
PORT=${BEYOND_CANVAS_SPARK_PORT:-22}
KEY=${BEYOND_CANVAS_SPARK_KEY:-$HOME/.ssh/spark}
RATE=${BEYOND_CANVAS_SPARK_RATE:-400}
ROOT=$(git rev-parse --show-toplevel)
ENV_FILE=${BEYOND_CANVAS_ENV:-$ROOT/.env}
# ServerAlive: one 5 MB transfer once stalled silently for six minutes;
# these make a stalled connection fail in a minute so the retry takes over.
ALIVE="-o ServerAliveInterval=15 -o ServerAliveCountMax=4"
SSH="ssh -i $KEY -o BatchMode=yes -o ConnectTimeout=30 $ALIVE -p $PORT"
# A full template, not `mktemp -t PREFIX`: that is BSD syntax, and GNU coreutils
# refuses it ("too few X's"), so the script died on its second line under Linux.
# It only ever runs on the Mac, so nothing noticed until its own tests were run
# on the Spark.
TMP=${TMPDIR:-/tmp}
LIST=$(mktemp "${TMP%/}/beyond-canvas-sync.XXXXXX")
trap 'rm -f "$LIST" "$LIST.0" "$LIST.ancestors"' EXIT

retry() {
    for try in 1 2 3 4 5 6; do
        "$@" && return 0
        sleep $((try * 10))
    done
    echo "gave up after six tries: $*" >&2
    return 1
}
send_key() {
    { printf 'STEPFUN_API_KEY=%s\n' "$value"
      [ -z "$online" ] || printf 'DASHSCOPE_API_KEY=%s\n' "$online"; } \
        | $SSH "$HOST" 'umask 077; cat > beyond-canvas/.env'
}
# Read a line the way studio/core/env.py does: an optional `export`, spaces around `=` or `:`, and
# quotes around the value are all allowed.
key_in_env() {
    sed -nE "s/^[[:space:]]*(export[[:space:]]+)?$1[[:space:]]*[=:][[:space:]]*//p" "$ENV_FILE" \
        | head -n 1 | sed -E "s/^[\"']//; s/[\"'][[:space:]]*$//; s/[[:space:]]*$//"
}

# `sync.sh FOLDER` sends one folder of the checkout instead — the gitignored
# deploy/trellis2/vendor, which git's file list leaves out — to the same place
# under ~/beyond-canvas, and touches no key.
ANYWAY=no
if [ "${1:-}" = "--anyway" ]; then
    ANYWAY=yes
    shift
fi
FOLDER=${1:-}
cd "$ROOT"

# Never send a tree that is missing what main already has.
#
# This unpacks over ~/beyond-canvas and never deletes, so whoever sends last
# wins and nothing says otherwise. Once a send from a checkout behind
# main put the class page back two commits: the studio served teachers the old
# page and nothing failed, because the running process kept the reverted server
# code in memory and reads index.html from disk on each request. It went
# backwards quietly, and was found by chance rather than by anything watching.
#
# Being AHEAD of main still sends — a branch in a worktree is how the Spark work
# is tested, and that was never the problem. What is refused is a tree that
# LACKS a commit main already holds, because that send is a silent revert.
# `--anyway` is the deliberate way past.
#
# A folder send is checked on the same terms whenever the folder holds tracked
# files, because such a send can put a commit back just as the whole-checkout
# one can. Only a folder git knows nothing about is exempt — the vendor tree
# folder mode exists for holds no tracked file, which is what makes it safe.
# That exemption was asserted in a comment and never checked until an adversarial
# review asked: `sync.sh studio` from a stale tree walked past the
# guard and would have overwritten the class with older code, the very thing
# this was written to stop. `git ls-files` failing leaves the send checked.
checked=yes
if [ -n "$FOLDER" ]; then
    if listing=$(git ls-files -- "$FOLDER"); then
        [ -n "$listing" ] || checked=no
    fi
fi
refuse_if_behind() {
    if ! git fetch --quiet origin main 2>/dev/null; then
        echo "cannot reach origin to see whether this checkout is behind main." >&2
        echo "Not sending: not knowing is the case this check exists for." >&2
        echo "Once you are sure it is not behind: sh deploy/spark/sync.sh --anyway" >&2
        exit 1
    fi
    git merge-base --is-ancestor FETCH_HEAD HEAD 2>/dev/null && return 0
    echo "$1" >&2
    git log --oneline HEAD..FETCH_HEAD | sed 's/^/  /' >&2
    echo "pull first, then send again; or send it regardless with: sh deploy/spark/sync.sh --anyway" >&2
    exit 1
}
if [ "$checked" = yes ] && [ "$ANYWAY" = no ]; then
    refuse_if_behind "this checkout is behind main, and sending${FOLDER:+ $FOLDER from} it would put these back:"
    echo "this checkout holds everything main holds"
fi
if [ -n "$FOLDER" ]; then
    # Demo images and evaluation sets (140 MB of the vendor tree's 214) stay
    # behind: only the upstream training code reads them, never inference.
    find "$FOLDER" -type f ! -path '*/assets/*' ! -path '*/asset/*' ! -path '*/evaluation/*' > "$LIST"
else
    git -c core.quotepath=off ls-files --cached --others --exclude-standard -- \
        pyproject.toml uv.lock studio skills evalkit deploy/spark deploy/gpu-media deploy/trellis2 deploy/archive/pixal3d \
        ':!studio/showcase_3d/assets/**/*.png' ':!**/*.glb' ':!**/*.blend' > "$LIST"
fi
tr '\n' '\0' < "$LIST" > "$LIST.0"
REV=$(git rev-parse --short HEAD)
MIRROR=beyond-canvas-sync-mirror-$(printf '%s' "$(hostname):$ROOT" | shasum | cut -c1-12)
DIR=beyond-canvas-send-$REV-$$
retry rsync -t --timeout=120 -e "$SSH" "$LIST.0" "$HOST:$DIR.list"
# Every commit this checkout holds, which is how the node tells whether it holds what the class runs
# (receive.sh). The same name each time, so rsync sends only the few lines that are new.
git rev-list HEAD > "$LIST.ancestors"
retry rsync -t -z --timeout=120 -e "$SSH" "$LIST.ancestors" "$HOST:$MIRROR.ancestors"
# A mirror made for the first time starts from the class's own copy of these files, so even the first
# send from a checkout carries only what differs from what the class runs.
retry $SSH "$HOST" "[ -d $MIRROR ] || { rm -rf $MIRROR.new && mkdir $MIRROR.new \
    && { cd beyond-canvas 2>/dev/null && tar --null -T ../$DIR.list --ignore-failed-read -cf - 2>/dev/null; cd; } \
        | tar -xf - -C $MIRROR.new; mv $MIRROR.new $MIRROR; }"
retry rsync -rlt -z --partial --timeout=120 --bwlimit=$((RATE / 8)) --files-from="$LIST" -e "$SSH" . "$HOST:$MIRROR/"
echo "sent what changed among $(wc -l < "$LIST" | tr -d ' ') files to the Spark"

# Asked again, now that the upload is done. The check above happened minutes ago:
# a send takes about four, and this script's own notes record transfers stalling
# for six. In that time someone else can land work on main and finish their own
# send, and this one would then arrive last and put their work back -- the same
# rollback, through timing rather than a stale start. Asking again here leaves a
# window of about a second instead of minutes. It is not nothing: only the node
# refusing older code would close it completely, and that is not built.
if [ "$checked" = yes ] && [ "$ANYWAY" = no ]; then
    refuse_if_behind "main moved on while this was uploading, and unpacking now would put these back:"
fi

# One unpacking at a time: two windows sending at once used to unpack over each other. Each send
# packs its own bundle from its checkout's mirror, under its own name, and clears only that.
# The node decides whether to take it, not this script. A session working from
# an old checkout runs the old sync.sh, whose guard is the one in that old file,
# so the sending side cannot be the place this is settled -- see receive.sh. It
# looks the commit the class runs up in this checkout's list of commits; the count
# only goes into its log. A node without receive.sh yet has never had a send
# carrying it, so that first one unpacks the old way and every send after it goes
# through the receiver, which also keeps the class's code locked against anything else.
COUNT=$(git rev-list --count HEAD)
TAKE="sh beyond-canvas/deploy/spark/receive.sh $COUNT $REV $DIR.tgz $MIRROR.ancestors"
# `--anyway` has to reach the node as well. It clears this script's own checks, but the receiver
# keeps its own -- deliberately, because a stale checkout runs a stale sync.sh whose guard cannot be
# trusted -- and at first nothing carried the decision across, so the one documented way to
# put the class back to older code was refused on the node every time and could not be got past.
[ "$ANYWAY" = no ] || TAKE="BEYOND_CANVAS_ANYWAY=1 $TAKE"
[ -z "$FOLDER" ] || TAKE="sh beyond-canvas/deploy/spark/receive.sh --folder $DIR.tgz"
retry $SSH "$HOST" "flock \$HOME/beyond-canvas-sync.lock -c \"touch $MIRROR \
    && { cd $MIRROR && tar --null -T ../$DIR.list -czf ../$DIR.tgz; cd; } \
    && { if [ -f beyond-canvas/deploy/spark/receive.sh ]; then $TAKE; \
         else echo 'no receiver on the node yet; unpacking the old way this once'; \
              mkdir -p beyond-canvas && tar -xzf $DIR.tgz -C beyond-canvas --warning=no-unknown-keyword; fi; } \
    && rm -f $DIR.tgz $DIR.list \
    && find . -maxdepth 1 -name 'beyond-canvas-send-*' -mmin +1440 -delete \
    && find . -maxdepth 1 -type d -name 'beyond-canvas-sync-mirror-*' -mtime +7 -exec rm -rf {} +\""
if [ -n "$FOLDER" ]; then
    echo "sent $FOLDER to $HOST:beyond-canvas/$FOLDER"
    exit 0
fi
# The node's own backups (seven daily Portfolio snapshots) die with it when it is
# wiped after the contest, so every code send also brings a dated copy of its Portfolio home. A failed
# pull never fails the send.
DATA=${DATA:-$ROOT} sh "$ROOT/deploy/spark/pull-portfolio.sh" || echo "the Spark's Portfolio was not pulled back this time" >&2

value=$(key_in_env STEPFUN_API_KEY)
[ -n "$value" ] || { echo "no STEPFUN_API_KEY in $ENV_FILE" >&2; exit 1; }
# Without it the class still opens; only the online clip choice is missing.
online=$(key_in_env DASHSCOPE_API_KEY)
[ -n "$online" ] || echo "no DASHSCOPE_API_KEY in $ENV_FILE: the online clip choice will not work on the Spark" >&2
retry send_key
echo "synced $(git rev-parse --short HEAD) to $HOST:beyond-canvas (StepFun${online:+ and DashScope} keys only)"

# Then look, rather than assume. A send has no way of knowing on its own that
# what it left is what the node now holds -- once a send landed on top
# of another one minutes later and nothing said so; it was noticed by chance.
# The comparison is read-only and safe while a class runs, and it is the one
# place that knows how to compare, so this asks it rather than repeating it.
# -f, not -x: the script is checked in without the executable bit and is meant to
# be run as `sh compare-with-spark.sh`, which is how it is run below. Written as
# -x at first it was simply always false, so the send said it had looked and
# had not -- the silent pass this whole check exists to stop.
if [ -f "$ROOT/deploy/spark/compare-with-spark.sh" ]; then
    sh "$ROOT/deploy/spark/compare-with-spark.sh" || echo "the node could not be compared this time" >&2
else
    echo "no compare-with-spark.sh beside this script; the send was not checked" >&2
fi
