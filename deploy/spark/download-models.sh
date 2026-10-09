#!/bin/bash
# Pull every media weight the Spark runs onto the node, capped, then check it.
#
# Run on the node inside tmux:
#     tmux new -d -s downloads "sh ~/beyond-canvas/deploy/spark/download-models.sh"
# The list, where each file lands and how it is checked all live in
# weights_manifest.py. The organisers forbid copying anything over 1 GB to the
# node and GitHub and huggingface.co are blocked from it, so everything comes
# from ModelScope, capped (RATE, MB/s) so the frp relay that carries every login
# keeps half the line — fetch_weights.py has the measurement. Re-running resumes.
#
# A failed fetch or a failed check ends the script with status 1, after the log
# line saying which: both used to print their line and exit 0, so
# anything waiting on this script read an incomplete or corrupt set as finished.
set -u
export RATE=${RATE:-6}
HERE=$HOME/beyond-canvas/deploy/spark
echo "=== $(date '+%F %T') fetch"
if ! "$HOME/tools/bin/python" "$HERE/weights_manifest.py" fetch; then
    echo "=== $(date '+%F %T') FETCH FAILED"
    exit 1
fi
echo "=== $(date '+%F %T') check"
if ! python3 "$HERE/weights_manifest.py" check; then
    echo "=== $(date '+%F %T') CHECK FAILED"
    exit 1
fi
echo "=== ALL DONE"
