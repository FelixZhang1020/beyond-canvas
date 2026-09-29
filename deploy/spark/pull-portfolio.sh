#!/bin/sh
# Bring the Spark's Portfolio back to the Mac as $DATA/.studio/spark-portfolio/latest.sqlite3,
# plus a dated copy whenever it changed, keeping the newest three. The node has no backups and
# is wiped when the contest ends, so this is the Portfolio's copy off the node.
# sync.sh runs it after every code send; it is never a background job on the Mac.
#
# rsync sends only the parts of the database that changed since the last pull, measured
# against latest.sqlite3: through the organisers' relay a whole 263 MB copy took about 15
# minutes, which every code send would otherwise have paid.
set -eu
HOST=${BEYOND_CANVAS_SPARK:-spark@203.0.113.10}
PORT=${BEYOND_CANVAS_SPARK_PORT:-22}
KEY=${BEYOND_CANVAS_SPARK_KEY:-$HOME/.ssh/spark}
DATA=${DATA:-$(git rev-parse --show-toplevel)}
SSH="ssh -i $KEY -o BatchMode=yes -o ConnectTimeout=30 -o ServerAliveInterval=15 -o ServerAliveCountMax=4 -p $PORT"
SNAPSHOT=/tmp/beyond-canvas-portfolio.sqlite3
OUT=$DATA/.studio/spark-portfolio
# umask 077: the staged copy in /tmp holds children's drawings, readable by nobody else on the node.
if ! $SSH "$HOST" "umask 077; cd ~/beyond-canvas/.studio 2>/dev/null && [ -f portfolio.sqlite3 ] && python3 -c \"import sqlite3; s = sqlite3.connect('portfolio.sqlite3'); d = sqlite3.connect('$SNAPSHOT'); s.backup(d); d.close()\""; then
    echo "no Portfolio on the Spark yet"
    exit 0
fi
mkdir -p "$OUT"
rsync -a --partial --timeout=120 --remove-source-files -e "$SSH" "$HOST:$SNAPSHOT" "$OUT/latest.sqlite3"
newest=$(ls -1t "$OUT"/portfolio-*.sqlite3 2>/dev/null | head -n 1 || true)
if [ -z "$newest" ] || ! cmp -s "$OUT/latest.sqlite3" "$newest"; then
    cp "$OUT/latest.sqlite3" "$OUT/portfolio-$(date +%Y%m%d-%H%M).sqlite3"
fi
ls -1t "$OUT"/portfolio-*.sqlite3 | tail -n +4 | while read -r old; do rm -f "$old"; done
echo "the Spark's Portfolio is in $OUT/latest.sqlite3"
