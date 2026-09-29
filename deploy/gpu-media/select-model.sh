#!/usr/bin/env bash
set -Eeuo pipefail

mode="${1:?usage: select-model.sh wan|trellis|idle}"
root="${2:-$HOME/beyond-canvas-deploy}"
exec 9>"$root/gpu.lock"
flock 9

case "$mode" in
  wan)
    (cd "$root/trellis2" && docker compose stop trellis2)
    "$root/gpu-media/start-wan.sh" "$root"
    ;;
  trellis)
    (cd "$root/trellis2" && docker compose up -d trellis2)
    ;;
  idle)
    (cd "$root/trellis2" && docker compose stop trellis2)
    ;;
  *)
    echo "usage: select-model.sh wan|trellis|idle" >&2
    exit 2
    ;;
esac
