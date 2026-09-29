#!/usr/bin/env bash
#
# Whisper on the 4090, always on. Port 7290 — the 72x0 band is the resident
# media models, and unlike every other worker here this one is never torn down
# between jobs: transcription happens while a child is still in front of the
# teacher, so a 20 s model load per utterance would be worse than not offering it.
#
#   sh start-hearing.sh              start it, and keep it started
#   docker stop beyond-canvas-hearing    stop it until the next boot
#   docker rm -f beyond-canvas-hearing   stop it for good
#
# CPU only, deliberately. Whisper small is small and this box has 32 cores, and
# a resident CUDA context would be counted by the guard in media_server.py that
# refuses a job when another process holds more than 1536 MiB — which would make
# every image, video and 3D request fail for as long as hearing was up.
#
# --restart unless-stopped is what "always on" means here: it survives a crash
# and it survives a reboot of the box, without anything on the Mac watching it.
set -Eeuo pipefail

root="${1:-$HOME/beyond-canvas-deploy}"
extra="$root/media-extra"
source_dir="$extra/whisper-source"
model="$extra/whisper-model/ggml-small-q5_1.bin"
name='beyond-canvas-hearing'
port=7290

[ -x "$source_dir/build/bin/whisper-server" ] || { echo "No whisper-server build at $source_dir/build/bin"; exit 1; }
[ -f "$model" ] || { echo "No model at $model"; exit 1; }

if [ "$(docker inspect -f '{{.State.Running}}' "$name" 2>/dev/null)" = 'true' ]; then
  echo "Hearing already up on $port."
  exit 0
fi
docker rm -f "$name" >/dev/null 2>&1 || true

docker run -d --name "$name" --restart unless-stopped \
  -p "127.0.0.1:$port:$port" \
  -v "$source_dir":/whisper:ro -v "$extra/whisper-model":/models/whisper:ro \
  -e LD_LIBRARY_PATH=/whisper/build/src:/whisper/build/ggml/src:/whisper/build/bin \
  --entrypoint /whisper/build/bin/whisper-server \
  beyond-canvas/voxcpm2:f772e498 \
  -m /models/whisper/ggml-small-q5_1.bin --host 0.0.0.0 --port "$port" -t 8 >/dev/null
echo "Hearing starting on $port (model loads once, then stays)."
