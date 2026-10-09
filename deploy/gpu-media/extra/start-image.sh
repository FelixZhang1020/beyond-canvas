#!/usr/bin/env bash
set -Eeuo pipefail
root="${1:-$HOME/beyond-canvas-deploy}"
service="$root/media-extra"
if [[ -s "$service/image.pid" ]] && kill -0 "$(cat "$service/image.pid")" 2>/dev/null; then
  exit 0
fi
nohup python3 "$service/runner/media_server.py" --kind image --root "$root" --port 7270 \
  > "$service/image-server.log" 2>&1 < /dev/null &
echo $! > "$service/image.pid"
