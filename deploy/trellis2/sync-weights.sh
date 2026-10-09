#!/usr/bin/env bash
set -Eeuo pipefail

script_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
trellis_root="${1:-$script_root}"
mode="${2:-download}"

# shellcheck disable=SC1091
source "$script_root/versions.env"

if [[ "$mode" != "download" && "$mode" != "check-access" && "$mode" != "prepare" ]]; then
  echo "usage: sync-weights.sh [TRELLIS_ROOT] [download|check-access|prepare]" >&2
  exit 2
fi

# `prepare` builds the runtime from weights already in the HF cache layout, for
# a node that cannot reach huggingface.co: the hosted DGX Spark gets them from
# ModelScope, checked against the pinned revisions by deploy/spark/weights_manifest.py.
if [[ "$mode" == "prepare" ]]; then
  :
elif [[ -n "${HF_CLI:-}" ]]; then
  hf_bin="$HF_CLI"
elif [[ -x "$trellis_root/../model-sync/venv/bin/hf" ]]; then
  hf_bin="$trellis_root/../model-sync/venv/bin/hf"
elif command -v hf >/dev/null 2>&1; then
  hf_bin="$(command -v hf)"
else
  echo "Hugging Face CLI not found. Set HF_CLI or install huggingface-hub==$HF_CLI_VERSION in an isolated environment." >&2
  exit 1
fi

export HF_HOME="$trellis_root/models/huggingface"
export HF_ENDPOINT="${HF_ENDPOINT:-https://huggingface.co}"
export HF_HUB_DISABLE_TELEMETRY=1

if [[ "$HF_ENDPOINT" != "https://huggingface.co" && "${ALLOW_HF_MIRROR_FOR_GATED:-0}" != "1" ]]; then
  echo "Refusing a non-official HF_ENDPOINT for gated repositories: $HF_ENDPOINT" >&2
  echo "Use huggingface.co, or explicitly set ALLOW_HF_MIRROR_FOR_GATED=1 after verifying the mirror's credential handling." >&2
  exit 1
fi

mkdir -p "$HF_HOME"

download_file() {
  local repo="$1"
  local revision="$2"
  local filename="$3"
  "$hf_bin" download "$repo" "$filename" --repo-type model --revision "$revision" >/dev/null
}

if [[ "$mode" != "prepare" ]]; then
  echo "[$(date -Is)] Checking pinned Hugging Face access through $HF_ENDPOINT"
  download_file "$TRELLIS2_MODEL_REPO" "$TRELLIS2_MODEL_REVISION" pipeline.json
  download_file "$TRELLIS2_DECODER_REPO" "$TRELLIS2_DECODER_REVISION" ckpts/ss_dec_conv3d_16l8_fp16.json
  download_file "$TRELLIS2_DINO_REPO" "$TRELLIS2_DINO_REVISION" config.json
  download_file "$TRELLIS2_RMBG_REPO" "$TRELLIS2_RMBG_REVISION" config.json
  echo "[$(date -Is)] Access check passed for all four repositories"
fi

if [[ "$mode" == "check-access" ]]; then
  exit 0
fi

download_snapshot() {
  local repo="$1"
  local revision="$2"
  shift 2
  echo "[$(date -Is)] START $repo@$revision"
  "$hf_bin" download "$repo" --repo-type model --revision "$revision" "$@"
  echo "[$(date -Is)] DONE  $repo@$revision"
}

if [[ "$mode" == "download" ]]; then
  download_snapshot "$TRELLIS2_MODEL_REPO" "$TRELLIS2_MODEL_REVISION"
  download_snapshot "$TRELLIS2_DECODER_REPO" "$TRELLIS2_DECODER_REVISION" --include 'ckpts/ss_dec_conv3d_16l8_fp16.*'
  download_snapshot "$TRELLIS2_DINO_REPO" "$TRELLIS2_DINO_REVISION" \
    config.json model.safetensors preprocessor_config.json LICENSE.md README.md
  download_snapshot "$TRELLIS2_RMBG_REPO" "$TRELLIS2_RMBG_REVISION" \
    BiRefNet_config.py birefnet.py config.json model.safetensors \
    preprocessor_config.json README.md
fi

cache_root="$HF_HOME/hub"
main_snapshot="$cache_root/models--microsoft--TRELLIS.2-4B/snapshots/$TRELLIS2_MODEL_REVISION"
decoder_snapshot="$cache_root/models--microsoft--TRELLIS-image-large/snapshots/$TRELLIS2_DECODER_REVISION"
dino_snapshot="$cache_root/models--facebook--dinov3-vitl16-pretrain-lvd1689m/snapshots/$TRELLIS2_DINO_REVISION"
rembg_snapshot="$cache_root/models--briaai--RMBG-2.0/snapshots/$TRELLIS2_RMBG_REVISION"

required_files=(
  "$main_snapshot/pipeline.json"
  "$main_snapshot/ckpts/ss_flow_img_dit_1_3B_64_bf16.json"
  "$main_snapshot/ckpts/ss_flow_img_dit_1_3B_64_bf16.safetensors"
  "$decoder_snapshot/ckpts/ss_dec_conv3d_16l8_fp16.json"
  "$decoder_snapshot/ckpts/ss_dec_conv3d_16l8_fp16.safetensors"
  "$dino_snapshot/config.json"
  "$dino_snapshot/model.safetensors"
  "$dino_snapshot/preprocessor_config.json"
  "$rembg_snapshot/config.json"
  "$rembg_snapshot/BiRefNet_config.py"
  "$rembg_snapshot/birefnet.py"
  "$rembg_snapshot/model.safetensors"
  "$rembg_snapshot/preprocessor_config.json"
)
for required_file in "${required_files[@]}"; do
  if [[ ! -f "$required_file" ]]; then
    echo "Required model artifact is missing: $required_file" >&2
    exit 1
  fi
done

runtime="$trellis_root/models/runtime/trellis2"
mkdir -p "$runtime/external/trellis-image-large"
ln -sfn "../../huggingface/hub/models--microsoft--TRELLIS.2-4B/snapshots/$TRELLIS2_MODEL_REVISION/ckpts" "$runtime/ckpts"
ln -sfn "../../../../huggingface/hub/models--microsoft--TRELLIS-image-large/snapshots/$TRELLIS2_DECODER_REVISION/ckpts/ss_dec_conv3d_16l8_fp16.json" "$runtime/external/trellis-image-large/ss_dec_conv3d_16l8_fp16.json"
ln -sfn "../../../../huggingface/hub/models--microsoft--TRELLIS-image-large/snapshots/$TRELLIS2_DECODER_REVISION/ckpts/ss_dec_conv3d_16l8_fp16.safetensors" "$runtime/external/trellis-image-large/ss_dec_conv3d_16l8_fp16.safetensors"
cp --remove-destination "$main_snapshot/pipeline.json" "$runtime/pipeline.json"

python3 - "$runtime/pipeline.json" "$trellis_root/models" "$dino_snapshot" "$rembg_snapshot" <<'PY'
import json
import pathlib
import sys

pipeline_path = pathlib.Path(sys.argv[1])
models_root = sys.argv[2]
dino_path = sys.argv[3]
rembg_path = sys.argv[4]
document = json.loads(pipeline_path.read_text())
args = document["args"]
args["models"]["sparse_structure_decoder"] = "external/trellis-image-large/ss_dec_conv3d_16l8_fp16"
args["image_cond_model"]["args"]["model_name"] = dino_path.replace(models_root, "/models")
args["rembg_model"]["args"]["model_name"] = rembg_path.replace(models_root, "/models")
pipeline_path.write_text(json.dumps(document, indent=2) + "\n")
PY

cat > "$trellis_root/models/runtime-manifest.json" <<JSON
{
  "generated_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "source": {"repository": "$TRELLIS2_SOURCE_URL", "revision": "$TRELLIS2_SOURCE_REVISION"},
  "models": [
    {"repository": "$TRELLIS2_MODEL_REPO", "revision": "$TRELLIS2_MODEL_REVISION", "license": "MIT", "gated": false},
    {"repository": "$TRELLIS2_DECODER_REPO", "revision": "$TRELLIS2_DECODER_REVISION", "license": "MIT", "gated": false},
    {"repository": "$TRELLIS2_DINO_REPO", "revision": "$TRELLIS2_DINO_REVISION", "license": "DINOv3 custom license", "gated": true},
    {"repository": "$TRELLIS2_RMBG_REPO", "revision": "$TRELLIS2_RMBG_REVISION", "license": "BRIA non-commercial license unless separately licensed", "gated": true}
  ]
}
JSON
printf '%s\n' "$TRELLIS2_MODEL_REVISION" > "$trellis_root/models/.pinned-revision"
echo "[$(date -Is)] Runtime prepared at $runtime"
