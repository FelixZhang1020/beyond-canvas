#!/usr/bin/env bash
set -Eeuo pipefail

root="${1:-$HOME/beyond-canvas-deploy}"
service="$root/gpu-media"
mkdir -p "$service/jobs"

if [[ -s "$service/wan.pid" ]] && kill -0 "$(cat "$service/wan.pid")" 2>/dev/null; then
  exit 0
fi

nohup python3 "$service/wan_server.py" \
  --model-root "$root/model-sync/models/wan2.2-ti2v-5b" \
  --jobs-root "$service/jobs" \
  --lock "$root/gpu.lock" \
  --port 7260 \
  >"$service/wan.log" 2>&1 &
echo $! > "$service/wan.pid"
