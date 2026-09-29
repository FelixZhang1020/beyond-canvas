#!/bin/sh
# A daily copy of the class Portfolio, kept on the Spark itself: the newest seven that differ, in
# ~/portfolio-snapshots, outside ~/beyond-canvas so no code send or class-data send can touch them.
# Run on the node by our own user's crontab at 03:00 node time, installed with:
#     (crontab -l 2>/dev/null | grep -v snapshot-portfolio.sh; echo "0 3 * * * sh $HOME/beyond-canvas/deploy/spark/snapshot-portfolio.sh") | crontab -
#
# Why (operator): the node keeps no backups. This guards against a bad write — a class
# that goes wrong, a clean-up that removes too much — and brings a course back from any of the last
# seven states. It does not survive the wipe when the contest ends: the copy off the node is
# pull-portfolio.sh, which every sync.sh runs, and which must run once more before then.
# SQLite's own backup makes the copy, so a class writing at that moment cannot tear it; a copy that
# fails the integrity check is thrown away and the run fails. Log: ~/logs/portfolio-snapshots.log
set -eu
# The four names can be pointed elsewhere, so the script can be tried on a scratch copy.
SOURCE=${SNAPSHOT_SOURCE:-$HOME/beyond-canvas/.studio/portfolio.sqlite3}
OUT=${SNAPSHOT_DIR:-$HOME/portfolio-snapshots}
KEEP=${SNAPSHOT_KEEP:-7}
LOG=${SNAPSHOT_LOG:-$HOME/logs/portfolio-snapshots.log}
mkdir -p "$OUT" "$(dirname "$LOG")"
chmod 700 "$OUT"
say() { echo "$(date '+%F %T') $*" >> "$LOG"; }
[ -f "$SOURCE" ] || { say "no Portfolio at $SOURCE"; exit 0; }
# One run at a time: a run by hand at 03:00 beside cron's would share the half-made copy.
exec 9> "$OUT/.lock"
flock -n 9 || { say "another snapshot is running; this one stopped"; exit 0; }

# Kept copies are named by the minute and second they were made, so the name orders them: a copy
# opened later by some tool would look newest by its file time.
previous=$(ls -1r "$OUT"/portfolio-*.sqlite3 2>/dev/null | head -n 1 || true)
# Made under a name no kept copy can have, and renamed only once it is known to differ: a second
# run in the same minute used to write over the first copy, find it "unchanged" and delete it.
rm -f "$OUT"/incoming.*
NEW=$(mktemp "$OUT/incoming.XXXXXX")
if ! courses=$(python3 - "$SOURCE" "$NEW" 2>> "$LOG" <<'PY'
import sqlite3
import sys

source = sqlite3.connect(sys.argv[1], timeout=60)
copy = sqlite3.connect(sys.argv[2])
source.backup(copy)
verdict = copy.execute('pragma integrity_check').fetchone()[0]
courses = copy.execute('select count(*) from courses').fetchone()[0]
copy.close()
if verdict != 'ok':
    sys.exit(f'integrity check: {verdict}')
print(courses)
PY
); then
    rm -f "$NEW"
    say "FAILED: no snapshot made"
    exit 1
fi
chmod 600 "$NEW"
if [ -n "$previous" ] && cmp -s "$NEW" "$previous"; then
    rm -f "$NEW"
    say "unchanged since $(basename "$previous"); $courses courses"
else
    KEPT=$OUT/portfolio-$(date +%Y%m%d-%H%M%S).sqlite3
    mv "$NEW" "$KEPT"
    say "kept $(basename "$KEPT"): $courses courses, $(du -h "$KEPT" | cut -f1)"
fi
ls -1r "$OUT"/portfolio-*.sqlite3 | tail -n +$((KEEP + 1)) | while read -r old; do rm -f "$old"; done
