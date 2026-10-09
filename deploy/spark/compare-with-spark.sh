#!/bin/sh
# Does the Spark hold the code this checkout holds? Run on the Mac, from the checkout the node is
# meant to be running. It compares, file by file, every file sync.sh sends, and says one of:
#   - the Spark matches this checkout;
#   - these files differ, are missing there, or are left over there from an older version.
#
#   sh deploy/spark/compare-with-spark.sh               # look, and say; changes nothing
#   sh deploy/spark/compare-with-spark.sh --mend --yes  # then send the code again, remove leftovers
#
# The plain look sends nothing and changes nothing, so it is safe during a class. --mend needs
# --yes with it, because it is the one thing here that deletes on the node. Left-over files are
# real: sync.sh only unpacks over the tree, so a file deleted from git lives on there until someone
# removes it. The node has no GitHub, so what it runs is whatever was last sent; this also says
# whether the checkout it is compared against is clean and on origin/main, because "the Spark
# matches main" only means something when both halves are known.
#
# The node's own working files are not ours to judge and are left out: its environment, caches, the
# vendored model sources that travel by `sync.sh <folder>`, and the class's data.
set -eu
HOST=${BEYOND_CANVAS_SPARK:-spark@203.0.113.10}
PORT=${BEYOND_CANVAS_SPARK_PORT:-22}
KEY=${BEYOND_CANVAS_SPARK_KEY:-$HOME/.ssh/spark}
SSH="ssh -i $KEY -o BatchMode=yes -o ConnectTimeout=30 -o ServerAliveInterval=15 -o ServerAliveCountMax=4 -p $PORT"
ROOT=$(git rev-parse --show-toplevel)
# A full template, not `mktemp -d -t PREFIX`: that is BSD syntax, and GNU coreutils refuses it
# ("too few X's in template"), so this script died on its second line under Linux. It only ever ran
# on the Mac, so nothing noticed until its own tests were run on the Spark -- the same defect
# sync.sh used to carry, found the same way.
TMP=${TMPDIR:-/tmp}
WORK=$(mktemp -d "${TMP%/}/beyond-canvas-compare.XXXXXX")
trap 'rm -rf "$WORK"' EXIT
MEND=no
YES=no
for word in "$@"; do
    case "$word" in
        --mend) MEND=yes ;;
        --yes) YES=yes ;;
        *) echo "unknown argument: $word" >&2; exit 2 ;;
    esac
done

cd "$ROOT"
# The same files sync.sh sends, and the same folders it puts them in.
FOLDERS="pyproject.toml uv.lock studio skills evalkit deploy/spark deploy/gpu-media deploy/trellis2 deploy/archive/pixal3d"
# What the node may hold that sync.sh never sends, so it is not "left over": its own working files,
# and the heavy 3D assets and models the sender leaves behind and other scripts put there. Calling
# those left over would have had --mend delete the showcase's own materials.
SKIP='(^|/)(__pycache__|[.]venv|vendor|node_modules)/|[.]pyc$|^studio/showcase_3d/assets/|[.](glb|blend)$'
# shellcheck disable=SC2086 - the folder list is meant to split into words
git ls-files -z --cached --others --exclude-standard -- $FOLDERS \
    ':!studio/showcase_3d/assets' ':!**/*.glb' ':!**/*.blend' > "$WORK/paths"
xargs -0 shasum -a 256 < "$WORK/paths" | LC_ALL=C sort -k2 > "$WORK/mine"
cut -d' ' -f3- "$WORK/mine" | LC_ALL=C sort > "$WORK/mine.names"
echo "comparing $(wc -l < "$WORK/mine.names" | tr -d ' ') files with $HOST:beyond-canvas"

# One visit: the node hashes the paths it is handed, then lists what it actually holds there.
$SSH "$HOST" "cd beyond-canvas || exit 1
xargs -0 sha256sum 2>/dev/null | LC_ALL=C sort -k2
echo '=== holds'
find $FOLDERS -type f 2>/dev/null | sed 's|^[.]/||' | grep -vE '$SKIP' | LC_ALL=C sort" \
    < "$WORK/paths" > "$WORK/answer"
sed -n '1,/^=== holds$/p' "$WORK/answer" | sed '$d' > "$WORK/theirs"
sed -n '/^=== holds$/,$p' "$WORK/answer" | sed '1d' | LC_ALL=C sort > "$WORK/theirs.names"
cut -d' ' -f3- "$WORK/theirs" | LC_ALL=C sort > "$WORK/theirs.hashed"

# LC_ALL=C on every one of these, because the lists above were sorted that way. Without it a
# UTF-8 locale collates punctuation differently -- "safety-reader.sh" against "spark_recorder.py"
# is enough to disagree -- and comm says "input is not in sorted order" and answers wrongly. The
# Mac happened to agree; Linux does not, so this surfaced only when the script was first run there.
LC_ALL=C join -j 2 -o 0,1.1,2.1 "$WORK/mine" "$WORK/theirs" | awk '$2 != $3 {print $1}' > "$WORK/differ"
LC_ALL=C comm -23 "$WORK/mine.names" "$WORK/theirs.hashed" > "$WORK/missing"
LC_ALL=C comm -13 "$WORK/mine.names" "$WORK/theirs.names" > "$WORK/extra"
# A file git would ignore here is the node's own working file, not a leftover: its inputs folder,
# its caches. sync.sh never sends those, so nothing of ours put them there and nothing of ours
# should take them away.
git check-ignore --stdin < "$WORK/extra" 2>/dev/null | LC_ALL=C sort > "$WORK/ignored" || true
LC_ALL=C comm -23 "$WORK/extra" "$WORK/ignored" > "$WORK/extra.kept" && mv "$WORK/extra.kept" "$WORK/extra"

say() {
    count=$(wc -l < "$2" | tr -d ' ')
    [ "$count" -eq 0 ] && return 0
    echo "$1 ($count):"
    head -40 "$2" | sed 's|^|  |'
    [ "$count" -gt 40 ] && echo "  ... and $((count - 40)) more"
    return 1
}
same=yes
say "different on the Spark" "$WORK/differ" || same=no
say "missing on the Spark" "$WORK/missing" || same=no
say "left over on the Spark, from an older version" "$WORK/extra" || same=no

# Holding the files is not running them. A service reads its code once, when it starts, and keeps
# it in memory: once the fix for a recursion that killed every 3D job and every clip sat on
# the node's disk while the old code ran on, and this script said the Spark matched -- which was
# true, and useless. The same evening a skill's declared tools were deployed and enforced by
# nothing, because the studio had started before they arrived. Both were found by reading
# timestamps by hand. This is that reading, done every time.
#
# Only what a service loads once and keeps counts. `__pycache__` is written by the running service
# itself and is newer than it by definition; the page's html, css and js are read from disk on each
# request, so a new page needs no restart. Files a job runs in its own process (trellis_client.py,
# wan_i2v_worker.py) are read per job and are left out for the same reason.
# Both `dir/*.py` and `dir/**/*.py`: git's `**` matches only where a directory stands, so
# `studio/**/*.py` alone matched none of the 52 python files at the top of studio/ -- serve.py,
# classroom.py, conversation.py, harness.py among them. A check that quietly covered almost nothing
# is worse than none, because it reports all-clear either way. Its own test is what found this.
#
# The studio's entry reaches outside studio/, to the code it keeps loaded from elsewhere: the rubric
# it grades by (evalkit/rubric, imported at start), the skill scripts conversation.py loads on the
# first drawing and keeps (with nemotron.py, which safety.py loads the same way), and the monitor's
# dashboard_jobs.py, loaded on the console's first poll and kept. Not art-feedback's prompts, read on
# each call, nor evalkit's runner or signing, nor the showpiece's skill scripts, which run in processes
# of their own. It used to stop at studio/, and a rule-12 change in evalkit/rubric/loop.py
# was reported as nothing stale. Its test imports the studio, makes the loads it makes later, follows
# every import written in all of that, and fails when code it reaches is missing here.
#
# Data the studio reads once and keeps counts too. It once watched code only, and a picture-book
# style's instruction changed several times in a few days while the class went on drawing with the
# old one. So the entry also names the storybook's picture-styles.json and picture-talk.json, the
# six showpiece skills' SKILL.md (their allowed-tools are enforced from the copy read when /showpiece
# is first opened), the words in studio/conversation/strings.json, and the profile the class is built
# from. The price, chosen (operator): now and then a restart nobody needed, such as a SKILL.md change
# when nobody has opened /showpiece since the start. Its test keeps the six in step with the showpiece's
# catalog. A backslash at a line's end joins it to the next, inside the quotes.
SERVICES="studio:studio/*.py studio/**/*.py evalkit/__init__.py evalkit/rubric/*.py \
    skills/art-feedback/scripts/feedback.py skills/studio-safety/scripts/safety.py \
    skills/studio-safety/scripts/nemotron.py skills/painting-to-animation/scripts/choreograph.py \
    skills/painting-to-animation/scripts/clip_check.py deploy/spark/dashboard_jobs.py \
    skills/drawings-to-storybook/assets/picture-styles.json skills/drawings-to-storybook/assets/picture-talk.json \
    skills/model-anatomy/SKILL.md skills/shot-judge/SKILL.md skills/joint-reveal/SKILL.md \
    skills/structure-tour/SKILL.md skills/raise-the-hall/SKILL.md skills/load-path/SKILL.md \
    studio/conversation/strings.json studio/profiles/stepfun.yaml
door:deploy/spark/door.py
recorder:deploy/spark/spark_recorder.py
media-video:deploy/spark/media_spark.py deploy/spark/memory_guard.py deploy/gpu-media/extra/*.py deploy/gpu-media/extra/**/*.py
media-trellis:deploy/spark/media_spark.py deploy/spark/memory_guard.py deploy/gpu-media/extra/*.py deploy/gpu-media/extra/**/*.py
media-book:deploy/spark/media_spark.py deploy/spark/memory_guard.py deploy/gpu-media/extra/*.py deploy/gpu-media/extra/**/*.py
media-voice:deploy/spark/media_spark.py deploy/spark/memory_guard.py deploy/gpu-media/extra/*.py deploy/gpu-media/extra/**/*.py
safety-reader:deploy/spark/safety-reader.sh
trellis-resident:deploy/spark/trellis-resident.sh deploy/spark/trellis_resident.py"
# What "changed" means here is git's last commit touching those files, NOT their mtime on the node.
# Every send unpacks the whole archive, so mtime there is the time of the last send whatever the
# content, and reading it would call a service stale whenever anyone deployed anything.
#
# Its blind spot, named so nobody trusts it further than it goes: a service started between a commit
# and the send that carried it looks current, because only the two times are compared and not what
# the process actually loaded. Restarting after a send, which is what the line below asks for, is
# what closes it.
: > "$WORK/stale"
running=$($SSH "$HOST" "tmux list-sessions -F '#{session_name} #{session_created}' 2>/dev/null" 2>/dev/null || true)
printf '%s\n' "$SERVICES" | while IFS=: read -r name paths; do
    [ -n "$name" ] || continue
    started=$(printf '%s\n' "$running" | awk -v n="$name" '$1 == n {print $2}')
    [ -n "$started" ] || continue            # not running is not stale; start.sh is the answer to that
    # shellcheck disable=SC2086 - the path list is meant to split into words
    changed=$(git log -1 --format=%ct -- $paths 2>/dev/null)
    [ -n "$changed" ] || continue
    # An `if`, not `test && printf`: under `set -e` the second form leaves the loop -- and so the
    # whole pipeline -- with status 1 whenever the last service checked is current, which is the
    # ordinary case. Written that way it took the script out before it could report anything.
    if [ "$changed" -gt "$started" ]; then
        # shellcheck disable=SC2086
        printf '%s  last changed by %s\n' "$name" \
            "$(git log -1 --format='%h %s' -- $paths 2>/dev/null | cut -c1-58)" >> "$WORK/stale"
    fi
done

if [ -s "$WORK/stale" ]; then
    echo "running code older than the node holds ($(wc -l < "$WORK/stale" | tr -d ' ')):"
    sed 's|^|  |' "$WORK/stale"
    echo "  restart them: sh deploy/spark/restart.sh $(cut -d' ' -f1 "$WORK/stale" | tr '\n' ' ')"
fi

git fetch -q origin 2>/dev/null || true
behind=$(git rev-list --count HEAD..origin/main 2>/dev/null || echo 0)
ahead=$(git rev-list --count origin/main..HEAD 2>/dev/null || echo 0)
place="level with origin/main"
[ "$behind" -eq 0 ] || place="$behind commit(s) behind origin/main"
[ "$ahead" -eq 0 ] || place="$place, $ahead not pushed"
echo "this checkout: $(git rev-parse --short HEAD), $(git diff --quiet HEAD && echo clean || echo 'with uncommitted changes'), $place"
if [ "$same" = yes ]; then
    echo "the Spark matches this checkout"
    exit 0
fi
[ "$MEND" = yes ] || { echo "run again with --mend --yes to send the code again and remove what is left over"; exit 1; }
[ "$YES" = yes ] || { echo "--mend also needs --yes: it removes files on the Spark" >&2; exit 2; }

if [ -s "$WORK/differ" ] || [ -s "$WORK/missing" ]; then
    echo "sending the code again"
    sh "$ROOT/deploy/spark/sync.sh" > /dev/null
fi
if [ -s "$WORK/extra" ]; then
    echo "removing $(wc -l < "$WORK/extra" | tr -d ' ') left-over file(s) there"
    # The code folders are read-only on the node and only receive.sh unlocks them, so the list goes to
    # it, one path a line on its input; it removes nothing unless every path is inside those folders.
    # A plain `rm` here failed on that lock from the day the lock came in, until someone noticed.
    $SSH "$HOST" "sh beyond-canvas/deploy/spark/receive.sh --remove" < "$WORK/extra"
fi
echo "mended; run the plain look again to confirm"
