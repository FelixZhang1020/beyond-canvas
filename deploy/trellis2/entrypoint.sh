#!/usr/bin/env bash
set -Eeuo pipefail

python /app/trellis_bridge.py --lock /worker/gpu.lock --port 7240 &
bridge_pid=$!
cleanup() {
  kill "$bridge_pid" 2>/dev/null || true
}
trap cleanup EXIT INT TERM
if [[ -f /runner/trellis_display.py ]]; then
  exec python /runner/trellis_display.py
fi
exec python app.py
