#!/bin/sh
# Take a send, on the node, and refuse one that would put the class backwards.
#
# Runs ON the node, called by sync.sh over ssh. It exists because the sending
# side cannot be trusted to check itself: sync.sh's own guard lives in sync.sh,
# and a session working from an old checkout is running the old sync.sh, which
# has no guard. That is not a gap that can be closed from the sending side at
# all -- the check has to be here, where every send arrives whatever sent it.
#
# Once, three sends from stale checkouts overwrote the class in one
# afternoon. Each looked like a success to whoever sent it.
#
# What it compares is ANCESTRY. The send brings its checkout's list of commits (`git rev-list HEAD`),
# and it is taken only when the commit the class runs is on that list: then it holds everything the
# class has. Until a code review it compared commit COUNTS, which do not order two
# branches -- a stale branch with enough commits of its own counted as newer and was taken. The node
# holds no git repository, but it can look a commit up in a list.
#
# And nothing else may write the class's code. The folders a send carries (studio, skills, evalkit,
# deploy) are kept read-only on the node; only this script unlocks them, unpacks, and locks them again.
# An old sync.sh that unpacked straight into ~/beyond-canvas without asking this script
# (review) now fails on the lock and changes nothing.
#
#   sh receive.sh COUNT REV ARCHIVE ANCESTORS   # unpack ARCHIVE as REV (COUNT for the log)
#   BEYOND_CANVAS_ANYWAY=1 sh receive.sh ...    # go back deliberately
#   sh receive.sh --folder ARCHIVE              # one folder (sync.sh FOLDER): unlocked, unpacked, locked
#   sh receive.sh --remove < LIST               # left-over files, one a line (compare-with-spark.sh --mend)
#
# A node with no record yet accepts anything: a fresh machine has to start
# somewhere, and refusing there would mean it could never be set up.
set -eu

RECORD=$HOME/.beyond-canvas-version
TREE=$HOME/beyond-canvas
KEPT=$HOME/.beyond-canvas-accepted.tgz
LOCKED="studio skills evalkit deploy"
# --warning is GNU tar's, which the node has and a Mac does not. Asked for
# rather than assumed, so this script can be run and tested in both places:
# written the other way it worked on the node and failed its own tests.
QUIET=
tar --help 2>&1 | grep -q -- --warning && QUIET=--warning=no-unknown-keyword

lock() {
    for folder in $LOCKED; do
        [ ! -d "$TREE/$folder" ] || chmod -R a-w "$TREE/$folder"
    done
}
unpack() {
    mkdir -p "$TREE"
    for folder in $LOCKED; do
        [ ! -d "$TREE/$folder" ] || chmod -R u+w "$TREE/$folder"
    done
    trap lock EXIT   # locked again however the unpacking ends
    tar -xzf "$1" -C "$TREE" $QUIET
}

if [ "${1:-}" = "--folder" ]; then
    ARCHIVE=${2:?an archive is required}
    [ -f "$ARCHIVE" ] || { echo "receive: no archive at $ARCHIVE" >&2; exit 2; }
    unpack "$ARCHIVE"
    echo "the node took the folder in $ARCHIVE"
    exit 0
fi

# Files the code no longer has, named by compare-with-spark.sh --mend. Its own `rm` failed on the lock
# above from the day the lock came in, so a leftover could only be removed by hand. Every
# path is checked before anything is unlocked: one outside the code folders refuses the whole list.
if [ "${1:-}" = "--remove" ]; then
    LIST=$(mktemp)
    trap 'rm -f "$LIST"' EXIT
    cat > "$LIST"
    while IFS= read -r path; do
        inside=no
        for folder in $LOCKED; do
            case "$path" in "$folder"/*) inside=yes ;; esac
        done
        case "$path" in *..*) inside=no ;; esac
        [ "$inside" = yes ] || { echo "receive: '$path' is not a file in the code folders; nothing removed" >&2; exit 2; }
    done < "$LIST"
    for folder in $LOCKED; do
        [ ! -d "$TREE/$folder" ] || chmod -R u+w "$TREE/$folder"
    done
    trap 'lock; rm -f "$LIST"' EXIT   # locked again however the removal ends
    while IFS= read -r path; do
        rm -f -- "$TREE/$path"
    done < "$LIST"
    echo "the node removed $(wc -l < "$LIST" | tr -d ' ') left-over file(s)"
    exit 0
fi

COUNT=${1:?a commit count is required}
REV=${2:?a revision is required}
ARCHIVE=${3:?an archive is required}
ANCESTORS=${4:-}

case "$COUNT" in ''|*[!0-9]*) echo "receive: '$COUNT' is not a count" >&2; exit 2;; esac
case "$REV" in ''|*[!0-9a-f]*) echo "receive: '$REV' is not a revision" >&2; exit 2;; esac
[ -f "$ARCHIVE" ] || { echo "receive: no archive at $ARCHIVE" >&2; exit 2; }

held=0
held_rev=none
if [ -f "$RECORD" ]; then
    read -r held held_rev < "$RECORD" || true
    case "$held_rev" in ''|*[!0-9a-f]*) held_rev=none;; esac
fi

contains_held=yes
if [ "$held_rev" != none ]; then
    if [ -z "$ANCESTORS" ] || [ ! -f "$ANCESTORS" ]; then
        contains_held=unknown
    elif ! grep -q "^$held_rev" "$ANCESTORS"; then
        contains_held=no
    fi
fi

if [ "$contains_held" != yes ] && [ -z "${BEYOND_CANVAS_ANYWAY:-}" ]; then
    if [ "$contains_held" = unknown ]; then
        echo "REFUSED: this send comes from an older sync.sh, which the node can no longer check." >&2
    else
        echo "REFUSED: this send does not hold what the class is running." >&2
    fi
    echo "  the class runs $held_rev; this send is $REV ($COUNT commits)." >&2
    echo "  Pull main and send again. To go back on purpose:" >&2
    # The flag, not the variable: sync.sh reads `--anyway` and forwards the variable here itself.
    # This line used to name the variable, which sync.sh never read, so the way out of
    # this refusal did not work when it was followed exactly.
    echo "    sh deploy/spark/sync.sh --anyway" >&2
    exit 1
fi

unpack "$ARCHIVE"
cp -f "$ARCHIVE" "$KEPT"
printf '%s %s\n' "$COUNT" "$REV" > "$RECORD"
if [ "$contains_held" != yes ]; then
    echo "took $REV over $held_rev because it was asked for deliberately"
else
    echo "the node now holds $REV ($COUNT commits)"
fi
