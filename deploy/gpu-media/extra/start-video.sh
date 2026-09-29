#!/usr/bin/env bash
set -Eeuo pipefail
root="${1:-$HOME/beyond-canvas-deploy}"
service="$root/media-extra"
if [[ -s "$service/video.pid" ]] && kill -0 "$(cat "$service/video.pid")" 2>/dev/null; then
  exit 0
fi
nohup python3 "$service/runner/media_server.py" --kind video --root "$root" --port 7260 \
  > "$service/video-server.log" 2>&1 < /dev/null &
echo $! > "$service/video.pid"
