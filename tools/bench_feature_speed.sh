#!/bin/sh
# Run only through deploy/spark/test-on-spark.sh. Borrow the existing online
# video key for a public-fixture test without printing or copying the env file.
set -eu
if [ -z "${DASHSCOPE_API_KEY:-}" ]; then
    DASHSCOPE_API_KEY=$(sed -n 's/^DASHSCOPE_API_KEY=//p' "$HOME/beyond-canvas/.env" 2>/dev/null | head -n 1)
    export DASHSCOPE_API_KEY
fi
exec python tools/bench_feature_speed.py
