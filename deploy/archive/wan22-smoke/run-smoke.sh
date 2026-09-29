#!/usr/bin/env bash
set -Eeuo pipefail

runtime_root="${1:?usage: run-smoke.sh RUNTIME_ROOT}"
model_root="${2:?usage: run-smoke.sh RUNTIME_ROOT MODEL_ROOT}"
output_root="${3:?usage: run-smoke.sh RUNTIME_ROOT MODEL_ROOT OUTPUT_ROOT}"

mkdir -p "$output_root"

docker run --rm --gpus all \
  --shm-size 16g \
  -e PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
  -v "$model_root:/models/wan2.2-ti2v-5b:ro" \
  -v "$output_root:/output" \
  beyond-canvas/wan22-smoke:42bf4cfa \
  --task ti2v-5B \
  --size '1280*704' \
  --frame_num 17 \
  --sample_steps 10 \
  --ckpt_dir /models/wan2.2-ti2v-5b \
  --offload_model True \
  --convert_model_dtype \
  --t5_cpu \
  --image /wan/examples/i2v_input.JPG \
  --prompt 'A white cat wearing sunglasses rests on a colorful surfboard at a bright tropical beach. Gentle ocean waves move behind it, sunlight glints across the water, and the cat slowly looks toward the camera. Preserve the vivid blue sky, turquoise water, green hills, and warm summer colors.' \
  --base_seed 42 \
  --save_file /output/wan22-ti2v-5b-color-smoke.mp4
