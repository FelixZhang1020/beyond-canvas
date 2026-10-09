#!/usr/bin/env bash
set -Eeuo pipefail
root="${1:-$HOME/beyond-canvas-deploy}"
service="$root/media-extra"
if [[ -s "$service/trellis.pid" ]] && kill -0 "$(cat "$service/trellis.pid")" 2>/dev/null; then
  exit 0
fi
nohup python3 "$service/runner/media_server.py" --kind trellis --root "$root" --port 7240 \
  > "$service/trellis-server.log" 2>&1 < /dev/null &
echo $! > "$service/trellis.pid"
