#!/usr/bin/env bash
set -Eeuo pipefail

sync_root="${1:?usage: sync-models.sh ROOT_DIR}"
hf_bin="$sync_root/venv/bin/hf"
models_root="$sync_root/models"

if [[ ! -x "$hf_bin" ]]; then
  echo "Hugging Face CLI not found: $hf_bin" >&2
  exit 1
fi

mkdir -p "$models_root"

export HF_HOME="$sync_root/hf-cache"
export HF_ENDPOINT="${HF_ENDPOINT:-https://hf-mirror.com}"
export HF_HUB_DISABLE_XET=1

download_model() {
  local repo="$1"
  local revision="$2"
  local directory="$3"

  echo "[$(date -Is)] START $repo@$revision"
  "$hf_bin" download "$repo" \
    --repo-type model \
    --revision "$revision" \
    --local-dir "$models_root/$directory"
  printf '%s\n' "$revision" > "$models_root/$directory/.pinned-revision"
  echo "[$(date -Is)] DONE  $repo@$revision"
}

download_model \
  "Wan-AI/Wan2.2-TI2V-5B" \
  "921dbaf3f1674a56f47e83fb80a34bac8a8f203e" \
  "wan2.2-ti2v-5b"

echo "[$(date -Is)] ALL MODELS DOWNLOADED"
