#!/usr/bin/env bash
set -Eeuo pipefail
root="${1:-$HOME/beyond-canvas-deploy}"
service="$root/media-extra"
if [[ -s "$service/mesh.pid" ]] && kill -0 "$(cat "$service/mesh.pid")" 2>/dev/null; then
  exit 0
fi
nohup python3 "$service/runner/media_server.py" --kind mesh --root "$root" --port 7250 \
  > "$service/mesh-server.log" 2>&1 < /dev/null &
echo $! > "$service/mesh.pid"
