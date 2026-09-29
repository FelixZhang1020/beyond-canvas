#!/bin/sh
# Run every test suite on the hosted Spark, never on the Mac: operator rule, "only keep
# dev env in local Mac, all service and testing only can be running on remote Spark".
#
# Run on the Mac, from the checkout to test. It sends that checkout's tracked files, tests included
# (sync.sh leaves them behind), to ~/beyond-canvas-test on the node — a folder apart from the live
# class in ~/beyond-canvas, which this never touches — and runs there, while the class keeps running:
#   - the Python suite, in its own environment (~/beyond-canvas-test-venv) built by uv from uv.lock
#     with the dev group — never the live class's ~/beyond-canvas/.venv, which lacks model-signing;
#   - the page build and its checks, with Node.js from ~/tools/node (user-local, no system change);
#   - the skill packaging check and the signature check of every skill.
# ffmpeg, ffprobe and Blender come from the copy's own deploy/spark/bin, container wrappers like the
# class's, so a wrapper is tested before it reaches the class.
# The copy is made a git repository only so the signature check can ask which files ship; it holds
# exactly the tracked files, so the answer is the same as on the Mac.
#
#   sh deploy/spark/test-on-spark.sh                                  # every suite
#   sh deploy/spark/test-on-spark.sh python -m studio.ops.dayzero         # one command instead
#
# Given a command, it runs that instead of the suites, in the same copy and environment, with the
# StepFun key the class uses (~/beyond-canvas/.env on the node; the Mac's .env is never read): the
# benchmark, the first-hour script, the readiness check. Only StepFun's models can answer there,
# because that is the only key the node holds. Every file the command writes or changes inside the
# checkout, gitignored ones apart, comes back into this checkout so it can be committed (BENCHMARK.md
# is the usual one); a file it deletes is not deleted here.
#
# One run at a time: the copy and its environment are shared, and once a run from another
# window replaced the copy under one already testing it (427 failed, 200 errors, the code blameless).
# Each run now uploads under its own name and takes ~/beyond-canvas-test.lock on the node before it
# touches the copy; a second run says it is waiting and starts when the first is done. A copy of this
# script from before the lock takes none, so it can still replace the copy under a locked run. Each
# run's logs on the node carry its name too: they used to be four fixed names, so a second
# window read this window's failures as its own.
#
# A full run also waits while the class is making something (class-busy.sh, from the copy being sent),
# because it shares the class's chip; it gives up after an hour. A run given a command does not wait: one
# test file is over in seconds. BEYOND_CANVAS_TEST_WHILE_BUSY=1 runs everything at once, deliberately.
set -eu
HOST=${BEYOND_CANVAS_SPARK:-spark@203.0.113.10}
PORT=${BEYOND_CANVAS_SPARK_PORT:-22}
KEY=${BEYOND_CANVAS_SPARK_KEY:-$HOME/.ssh/spark}
ROOT=$(git rev-parse --show-toplevel)
SSH="ssh -i $KEY -o BatchMode=yes -o ConnectTimeout=30 -o ServerAliveInterval=15 -o ServerAliveCountMax=4 -p $PORT"
RESULTS=$(mktemp -t beyond-canvas-results)
LIST=$(mktemp -t beyond-canvas-test-list)
RUN=beyond-canvas-test-$(date +%Y%m%d-%H%M%S)-$$
RATE=${BEYOND_CANVAS_SPARK_RATE:-400}
trap 'rm -rf "$RESULTS" "$LIST"' EXIT

cd "$ROOT"
git -c core.quotepath=off ls-files --cached --others --exclude-standard -- ':!studio/showcase_3d/assets/**/*.png' \
    > "$LIST"
retry() {   # the relay drops single connections now and then, as sync.sh found
    for try in 1 2 3 4 5 6; do
        "$@" && return 0
        sleep $((try * 10))
    done
    return 1
}
# Only what changed crosses the relay. Every run used to send the whole project, packed on the
# Mac (~10 MB), and one evening the relay ran at about 5 KB/s: each run sat in its upload for most of an
# hour, every window's queued behind it, for a change of a few lines. The node now keeps one mirror of
# each checkout, filled the first time from the last test copy, and rsync sends only the differences;
# the node packs the run from the mirror itself, taking only the files this checkout lists, so a file
# deleted here is left out there too. The mirror is shared by runs from the same checkout, which send
# the same files; rsync writes each file whole before it replaces the old one.
MIRROR=beyond-canvas-test-mirror-$(printf '%s' "$(hostname):$ROOT" | shasum | cut -c1-12)
retry $SSH "$HOST" "[ -d $MIRROR ] || { rm -rf $MIRROR.new && mkdir $MIRROR.new \
    && { [ ! -d beyond-canvas-test ] || { cp -a beyond-canvas-test/. $MIRROR.new/ && rm -rf $MIRROR.new/.git; }; } \
    && mv $MIRROR.new $MIRROR; }" || { echo "the Spark could not be reached" >&2; exit 1; }
retry rsync -rlt -z --partial --timeout=120 --bwlimit=$((RATE / 8)) --files-from="$LIST" -e "$SSH" . "$HOST:$MIRROR/" \
    || { echo "the test copy did not reach the Spark" >&2; exit 1; }
retry rsync -t --timeout=120 -e "$SSH" "$LIST" "$HOST:$RUN.list" \
    && retry $SSH "$HOST" "touch $MIRROR && cd $MIRROR && tr '\\n' '\\0' < ../$RUN.list \
        | tar --null -T - -czf ../$RUN.tgz && rm -f ../$RUN.list" \
    || { echo "the test copy could not be packed on the Spark" >&2; $SSH "$HOST" "rm -f $RUN.list $RUN.tgz"; exit 1; }
VERSION="$(git rev-parse --short HEAD)$(git diff --quiet HEAD || echo ' plus uncommitted changes')"
if [ $# -gt 0 ]; then echo "running '$*' on the Spark, on $VERSION"; else echo "testing $VERSION on the Spark"; fi

# The command reaches the node as words the remote shell reads back unchanged: each one in single
# quotes, with any single quote inside it closed, escaped and reopened.
ARGS=""
for word in "$@"; do
    ARGS="$ARGS '$(printf '%s' "$word" | sed "s/'/'\\\\''/g")'"
done
status=0
WHILE_BUSY=$([ -z "${BEYOND_CANVAS_TEST_WHILE_BUSY:-}" ] || echo 1)
$SSH "$HOST" "RUN=$RUN MIRROR=$MIRROR WHILE_BUSY=$WHILE_BUSY bash -s --$ARGS" <<'REMOTE' || status=$?
set -u
# Before the lock, so a run with a command queued behind this one is not held up by the wait.
if [ $# -eq 0 ] && [ -z "$WHILE_BUSY" ]; then
    waited=0
    while sh "$HOME/$MIRROR/deploy/spark/class-busy.sh"; do
        [ "$waited" -gt 0 ] || echo "the class is making something; the full run waits until it is done"
        [ "$waited" -lt 3600 ] || { echo "FAILED: the class stayed busy for an hour; run again later"; exit 1; }
        sleep 30
        waited=$((waited + 30))
    done
fi
# Held until this shell ends, which is after the copy's last use.
exec 9> "$HOME/beyond-canvas-test.lock"
if ! flock -n 9; then
    echo "another run is using the Spark's test copy; waiting for it to finish"
    flock -w 3600 9 || { echo "FAILED: the test copy stayed busy for an hour"; exit 1; }
    # A run cancelled on the Mac while it waited has nobody to write to any more: it stops here,
    # before it touches the copy or spends a model call.
    echo "the copy is free; starting" || exit 1
fi
# Uploads left by runs that never reached this point, and yesterday's logs.
find "$HOME" -maxdepth 1 -name 'beyond-canvas-test-*.tgz' -mmin +1440 -delete
# Pieces of an upload cut off before they were joined (review): nothing else removes them.
find "$HOME" -maxdepth 1 -type d -name 'beyond-canvas-test-*-parts' -mmin +1440 -exec rm -rf {} +
# Mirrors of checkouts that have sent nothing for a week, a worktree long removed (each run touches its own).
find "$HOME" -maxdepth 1 -type d -name 'beyond-canvas-test-mirror-*' -mtime +7 -exec rm -rf {} +
find "$HOME" -maxdepth 1 -name 'beyond-canvas-test-*.list' -mmin +1440 -delete
find /tmp -maxdepth 1 -name 'beyond-canvas-test-*.log' -mmin +1440 -delete 2>/dev/null
rm -rf beyond-canvas-test && mkdir beyond-canvas-test \
    && tar -xzf "$RUN.tgz" -C beyond-canvas-test --warning=no-unknown-keyword \
    && rm -f "$RUN.tgz" && cd beyond-canvas-test && git init -q && git add -A \
    || { echo "FAILED: the test copy could not be unpacked on the Spark"; exit 1; }
export PATH="$PWD/deploy/spark/bin:$HOME/tools/node/bin:$PATH" STEPFUN_API_KEY=placeholder-for-test
# The same mirrors bootstrap.sh uses; the environment lives outside the copy, so a re-run only syncs changes.
export UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple \
    UV_PYTHON_INSTALL_MIRROR=https://mirror.nju.edu.cn/github-release/astral-sh/python-build-standalone \
    UV_PROJECT_ENVIRONMENT="$HOME/beyond-canvas-test-venv"
if ! "$HOME/tools/bin/uv" sync --frozen --group dev -q > /tmp/$RUN-env.log 2>&1; then
    echo "FAILED: the test environment could not be built"; tail -5 /tmp/$RUN-env.log; exit 1
fi
PY="$HOME/beyond-canvas-test-venv/bin/python"
if [ $# -gt 0 ]; then
    STEPFUN_API_KEY=$(sed -n 's/^STEPFUN_API_KEY=//p' "$HOME/beyond-canvas/.env" 2>/dev/null | head -n 1)
    [ -n "$STEPFUN_API_KEY" ] || { echo "FAILED: no StepFun key on the Spark; sync.sh puts it there"; exit 1; }
    export STEPFUN_API_KEY PATH="$HOME/beyond-canvas-test-venv/bin:$PATH"
    # Drawings an evaluation case names that git does not carry — the studio's samples, kept out of
    # the repository — wait on the node in ~/eval-files and are laid over the copy at the paths the
    # cases name. Without them the benchmark measured 8 of its 11 cases and said so. The suites
    # never see this: a test has to pass from the checkout alone.
    [ -d "$HOME/eval-files" ] && cp -R "$HOME/eval-files/." .
    # This script reaches bash on its standard input; a command reading it would eat the lines below.
    # Nor does the command get the lock: something it left running would hold it for good.
    "$@" < /dev/null 9>&-
    ran=$?
    git ls-files -z --modified --others --exclude-standard \
        | while IFS= read -r -d '' file; do [ -e "$file" ] && printf '%s\0' "$file"; done \
        | tar --null -T - -czf "$HOME/$RUN-results.tgz" \
        || { echo "FAILED: the files the command wrote could not be packed"; rm -f "$HOME/$RUN-results.tgz"; }
    exit $ran
fi
failed=""
$PY -m pytest -p no:cacheprovider -o addopts="-m 'not live'" tests deploy/gpu-media/extra/test_media_server.py \
    > /tmp/$RUN-python.log 2>&1 || failed="$failed python"
grep -E "^(FAILED|ERROR)" /tmp/$RUN-python.log | head -20
echo "python: $(tail -1 /tmp/$RUN-python.log)"
sh studio/page/build.sh > /tmp/$RUN-build.log 2>&1 || failed="$failed build"
echo "page build: $(tail -1 /tmp/$RUN-build.log)"
node --test tests/page/*.test.mjs > /tmp/$RUN-page.log 2>&1 || failed="$failed page"
grep -E "^not ok" /tmp/$RUN-page.log | head -10
echo "page: $(grep -E '^# (pass|fail) ' /tmp/$RUN-page.log | tr '\n' ' ')"
$PY -m evalkit.packaging skills > /tmp/$RUN-packaging.log 2>&1 || failed="$failed packaging"
echo "packaging: $(tail -1 /tmp/$RUN-packaging.log)"
$PY -m evalkit.signing verify skills > /tmp/$RUN-signing.log 2>&1 || failed="$failed signing"
echo "signing: $(grep -c '^verified' /tmp/$RUN-signing.log) verified, $(grep -c '^FAILED' /tmp/$RUN-signing.log) failed"
if [ -n "$failed" ]; then echo "FAILED:$failed (logs in /tmp/$RUN-*.log on the Spark)"; exit 1; fi
echo "all suites passed on the Spark"
REMOTE

[ $# -gt 0 ] || exit $status
if ! scp -q -i "$KEY" -o BatchMode=yes -o ConnectTimeout=30 -P "$PORT" \
        "$HOST:$RUN-results.tgz" "$RESULTS"; then
    echo "no files came back from the Spark" >&2
    exit $((status ? status : 1))
fi
$SSH "$HOST" "rm -f $RUN-results.tgz" || true
listing=$(tar -tzf "$RESULTS") || { echo "the files that came back could not be read" >&2; exit 1; }
if [ -n "$listing" ]; then
    tar -xzf "$RESULTS" -C "$ROOT"
    echo "brought back into this checkout:"
    printf '%s\n' "$listing" | sed 's/^/  /'
else
    echo "the command changed no file in the checkout"
fi
exit $status
