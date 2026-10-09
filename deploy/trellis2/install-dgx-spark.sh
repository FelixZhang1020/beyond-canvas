#!/usr/bin/env bash
set -Eeuo pipefail

script_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$script_root/versions.env"

preflight_only=0
skip_models=0
skip_build=0
no_start=0

usage() {
  cat <<'EOF'
Usage: install-dgx-spark.sh [options]

Installs the pinned TRELLIS.2 runtime, models and loopback-only service.

Options:
  --preflight-only  Check the host and gated model access; make no large download.
  --skip-models     Reuse an already prepared, pinned model cache.
  --skip-build      Reuse the existing pinned container image.
  --no-start        Install and verify imports, but do not start the web service.
  -h, --help        Show this help.

Required environment:
  HF_TOKEN=...                         Read token for the accepted gated models.
  TRELLIS2_LICENSES_ACKNOWLEDGED=1     Confirms the operator reviewed LICENSES.md.

Optional:
  HF_ENDPOINT=https://huggingface.co   Official endpoint is the safe default.
EOF
}

while (($#)); do
  case "$1" in
    --preflight-only) preflight_only=1 ;;
    --skip-models) skip_models=1 ;;
    --skip-build) skip_build=1 ;;
    --no-start) no_start=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done

die() {
  echo "ERROR: $*" >&2
  exit 1
}

command -v docker >/dev/null 2>&1 || die "Docker is required and is preinstalled on a normal DGX Spark."
docker compose version >/dev/null 2>&1 || die "Docker Compose v2 is required."
docker info >/dev/null 2>&1 || die "Docker is not usable by this account. Configure Docker access; this script will not change user groups or use sudo."
command -v nvidia-smi >/dev/null 2>&1 || die "nvidia-smi was not found."

[[ "$(uname -s)" == "Linux" ]] || die "DGX Spark installation requires Linux."
[[ "$(uname -m)" == "aarch64" ]] || die "Expected DGX Spark ARM64 (aarch64); found $(uname -m)."

gpu_name="$(nvidia-smi --query-gpu=name --format=csv,noheader | head -n 1)"
[[ "$gpu_name" == *GB10* ]] || die "Expected the DGX Spark GB10 GPU; found: $gpu_name"

free_kib="$(df -Pk "$script_root" | awk 'NR==2 {print $4}')"
minimum_kib=$((70 * 1024 * 1024))
((free_kib >= minimum_kib)) || die "At least 70 GiB free is required for source, image, build layers and model cache."

[[ "${TRELLIS2_LICENSES_ACKNOWLEDGED:-0}" == "1" ]] || die "Review deploy/trellis2/LICENSES.md, then set TRELLIS2_LICENSES_ACKNOWLEDGED=1."
[[ -n "${HF_TOKEN:-}" ]] || die "HF_TOKEN is required. Use a read token from the Hugging Face account already granted DINOv3 and RMBG-2.0 access."

export HF_ENDPOINT="${HF_ENDPOINT:-https://huggingface.co}"
if [[ "$HF_ENDPOINT" != "https://huggingface.co" && "${ALLOW_HF_MIRROR_FOR_GATED:-0}" != "1" ]]; then
  die "A non-official HF_ENDPOINT is blocked for gated downloads. See README.md before overriding."
fi

hf_helper_image="python:3.11-slim"
run_hf_sync() {
  local mode="$1"
  docker run --rm --user "$(id -u):$(id -g)" -e HOME=/tmp -e HF_TOKEN -e HF_ENDPOINT -e ALLOW_HF_MIRROR_FOR_GATED -v "$script_root:/deployment" "$hf_helper_image" bash -c "python -m venv /tmp/hf && /tmp/hf/bin/pip install -q huggingface-hub==$HF_CLI_VERSION && HF_CLI=/tmp/hf/bin/hf /deployment/sync-weights.sh /deployment $mode"
}

echo "== DGX Spark preflight =="
echo "GPU: $gpu_name"
echo "Architecture: $(uname -m)"
echo "Free disk: $((free_kib / 1024 / 1024)) GiB"
echo "Hugging Face endpoint: $HF_ENDPOINT"
docker run --rm --gpus all nvcr.io/nvidia/cuda:13.0.1-devel-ubuntu24.04 nvidia-smi >/dev/null
run_hf_sync check-access

if ((preflight_only)); then
  echo "Preflight and all gated repository checks passed. No large model download or build was started."
  exit 0
fi

# Dockerfile.dgx-spark builds from vendor/, every GitHub input at its pinned
# revision. A Spark that can reach GitHub fetches it here; one that cannot (the
# hackathon's hosted node) gets it from a Mac through deploy/spark/sync.sh.
if [[ ! -f "$script_root/vendor/VENDORED" ]]; then
  python3 "$script_root/../spark/vendor_sources.py" "$script_root/vendor"
fi
[[ "$(cat "$script_root/vendor/trellis2/.vendored")" == "$TRELLIS2_SOURCE_REVISION" ]] || die "Vendored TRELLIS.2 is not the pinned revision."

set -a
# shellcheck disable=SC1091
source "$script_root/versions.env"
set +a
compose=(docker compose -f "$script_root/compose.yaml" -f "$script_root/compose.dgx-spark.yaml" --project-directory "$script_root")
"${compose[@]}" config --quiet

if ((!skip_build)); then
  "${compose[@]}" build trellis2
fi

if ((!skip_models)); then
  run_hf_sync download
fi

[[ -f "$script_root/models/runtime/trellis2/pipeline.json" ]] || die "Pinned runtime pipeline is missing; do not use --skip-models until sync-weights.sh has completed."

echo "== Container and CUDA import smoke test =="
bash "$script_root/prepare-runtime.sh" "$script_root"
"${compose[@]}" run --rm --no-deps --entrypoint python trellis2 -c 'import torch, flash_attn, o_voxel; assert torch.cuda.is_available(); cc=torch.cuda.get_device_capability(); assert cc == (12, 1), cc; print("CUDA", torch.version.cuda, "GPU", torch.cuda.get_device_name(), "CC", cc, "flash-attn", flash_attn.__version__)'

evidence_root="$script_root/models/install-evidence"
mkdir -p "$evidence_root"
nvidia-smi --query-gpu=name,driver_version --format=csv,noheader > "$evidence_root/gpu.txt"
"${compose[@]}" images --format json > "$evidence_root/compose-images.json"
"${compose[@]}" run --rm --no-deps --entrypoint python trellis2 -m pip freeze > "$evidence_root/python-packages.txt"
cp "$script_root/versions.env" "$evidence_root/versions.env"
echo "Installation evidence written to $evidence_root"

if ((no_start)); then
  echo "TRELLIS.2 is installed and import checks passed; the service was not started."
  exit 0
fi

"${compose[@]}" up -d trellis2
deadline=$((SECONDS + 1200))
until python3 -c 'import urllib.request; urllib.request.urlopen("http://127.0.0.1:7040/", timeout=5)' >/dev/null 2>&1; do
  if ((SECONDS >= deadline)); then
    "${compose[@]}" logs --tail 160 trellis2 >&2
    die "TRELLIS.2 did not become ready within 20 minutes."
  fi
  if [[ "$("${compose[@]}" ps --status exited -q trellis2)" != "" ]]; then
    "${compose[@]}" logs --tail 160 trellis2 >&2
    die "TRELLIS.2 exited before becoming ready."
  fi
  sleep 10
done

echo "TRELLIS.2 is ready at http://127.0.0.1:7040/"
echo "Keep it loopback-only; use an SSH tunnel for remote access."
