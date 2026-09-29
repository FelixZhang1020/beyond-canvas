#!/bin/sh
# Send the class data to the Spark: the Portfolio (course history, with its drawings inside the
# database) and the sample drawings the page offers. Run on the Mac. DATA names the checkout
# whose data moves (default: this one); a worktree has none of its own, so point it at the
# main folder.
#
# Operator decision: the sample drawings are AI-generated or the operator's own
# public data, so they may be stored on the node, and the Portfolio lives where classes run.
# The Mac keeps its copies — the node has no backups and is wiped when the contest ends — and
# pull-portfolio.sh brings the Spark's Portfolio back.
#
# The Portfolio goes as a consistent snapshot (sqlite's own backup), never as the live file,
# and only while the Spark's studio is stopped: replacing a database under a running server
# loses whatever it writes next. The node's previous Portfolio is kept beside it, renamed.
set -eu
HOST=${BEYOND_CANVAS_SPARK:-spark@203.0.113.10}
PORT=${BEYOND_CANVAS_SPARK_PORT:-22}
KEY=${BEYOND_CANVAS_SPARK_KEY:-$HOME/.ssh/spark}
DATA=${DATA:-$(git rev-parse --show-toplevel)}
SSH="ssh -i $KEY -o BatchMode=yes -o ConnectTimeout=30 -o ServerAliveInterval=15 -o ServerAliveCountMax=4 -p $PORT"
if $SSH "$HOST" 'tmux has-session -t studio 2>/dev/null'; then
    echo "the Spark's studio is running; stop it when no class is open (tmux kill-session -t studio), then rerun" >&2
    exit 1
fi
STAGE=$(mktemp -d)
python3 -c "import sqlite3, sys; s = sqlite3.connect(sys.argv[1]); d = sqlite3.connect(sys.argv[2]); s.backup(d); d.close()" \
    "$DATA/.studio/portfolio.sqlite3" "$STAGE/portfolio.sqlite3"
$SSH "$HOST" 'mkdir -p ~/beyond-canvas/.studio && cd ~/beyond-canvas/.studio && { [ ! -f portfolio.sqlite3 ] || mv portfolio.sqlite3 "portfolio-before-$(date +%Y%m%d-%H%M).sqlite3"; }'
rsync -a --partial --timeout=120 -e "$SSH" "$STAGE/portfolio.sqlite3" "$HOST:beyond-canvas/.studio/portfolio.sqlite3"
# The node's shell reads the far path, so its space is escaped: unescaped, the first run
# put the drawings in ~/beyond-canvas/Image. The Mac's rsync (openrsync, 2.6.9)
# has no --protect-args. class-data-exclude.txt names files that never go: a classroom photo
# showing children's faces sat among the drawings (operator) — the organisers
# forbid personal data on the node, and it stays on the Mac only.
rsync -a --partial --timeout=120 --exclude-from="$(dirname "$0")/class-data-exclude.txt" -e "$SSH" \
    "$DATA/Image Sample/" "$HOST:beyond-canvas/Image\ Sample/"
rm -rf "$STAGE"
echo "sent; start the studio again on the node: sh ~/beyond-canvas/deploy/spark/start.sh"
