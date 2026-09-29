#!/usr/bin/env bash
set -Eeuo pipefail

root="${1:-$HOME/beyond-canvas-deploy}"
pixal="$root/pixal3d"
run_id="${2:-official-samples-20260908}"
out="$pixal/outputs/$run_id"
mkdir -p "$out"

exec 9>"$root/gpu.lock"
flock 9

nvidia-smi \
  --query-gpu=timestamp,memory.used,utilization.gpu,temperature.gpu,power.draw \
  --format=csv,noheader,nounits \
  --loop=1 >"$out/gpu.csv" &
monitor_pid=$!
cleanup() {
  kill "$monitor_pid" 2>/dev/null || true
}
trap cleanup EXIT

printf 'sample\tstatus\telapsed_seconds\tbytes\n' >"$out/results.tsv"

samples=(
  0_img.png
  1_img.png
  3_img.webp
  4_img.png
  9_img.png
  17_img.png
)

for sample in "${samples[@]}"; do
  stem="${sample%.*}"
  output="$out/$stem.glb"
  log="$out/$stem.log"
  start="$(date +%s)"
  status=failed

  if docker run --rm --gpus all --name "pixal3d-$stem" \
      -e NAF_REPO_PATH=/models/torch/hub/valeoai_NAF_main \
      -e TORCH_HOME=/models/torch \
      -e HF_HUB_OFFLINE=1 \
      -e TRANSFORMERS_OFFLINE=1 \
      -e ATTN_BACKEND=flash_attn \
      -v "$pixal/source/smoke_rgba.py:/opt/pixal3d/smoke_rgba.py:ro" \
      -v "$pixal/models/Pixal3D:/models/Pixal3D:ro" \
      -v "$pixal/models/dinov3:/models/dinov3:ro" \
      -v "$pixal/models/torch-host:/models/torch:ro" \
      -v "$pixal/source/assets/images:/samples:ro" \
      -v "$out:/outputs" \
      beyond-canvas/pixal3d:f7cf384 \
      --image "/samples/$sample" \
      --output "/outputs/$stem.glb" \
      --model-path /models/Pixal3D \
      --dino-path /models/dinov3 \
      --seed 42 >"$log" 2>&1; then
    status=ok
  fi

  end="$(date +%s)"
  bytes=0
  if [[ -f "$output" ]]; then
    bytes="$(stat -c %s "$output")"
  fi
  printf '%s\t%s\t%s\t%s\n' "$sample" "$status" "$((end-start))" "$bytes" \
    | tee -a "$out/results.tsv"
done
