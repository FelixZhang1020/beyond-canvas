#!/usr/bin/env bash
set -Eeuo pipefail
root="${1:-$HOME/beyond-canvas-deploy}"
service="$root/media-extra"
if [[ -s "$service/voice.pid" ]] && kill -0 "$(cat "$service/voice.pid")" 2>/dev/null; then
  exit 0
fi
nohup python3 "$service/runner/media_server.py" --kind voice --root "$root" --port 7280 \
  > "$service/voice-server.log" 2>&1 < /dev/null &
echo $! > "$service/voice.pid"
