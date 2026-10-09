#!/usr/bin/env bash
set -Eeuo pipefail

script_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$script_root/versions.env"

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

for name in TRELLIS2_SOURCE_REVISION TRELLIS2_MODEL_REVISION TRELLIS2_DECODER_REVISION TRELLIS2_DINO_REVISION TRELLIS2_RMBG_REVISION UTILS3D_REVISION NVDIFFRAST_REVISION NVDIFFREC_REVISION CUMESH_REVISION FLEXGEMM_REVISION; do
  value="${!name}"
  [[ "$value" =~ ^[0-9a-f]{40}$ ]] || fail "$name is not a full Git/Hugging Face revision: $value"
done

bash -n "$script_root/install-dgx-spark.sh" "$script_root/sync-weights.sh"

for value in "$UTILS3D_REVISION" "$NVDIFFRAST_REVISION" "$NVDIFFREC_REVISION" "$CUMESH_REVISION" "$FLEXGEMM_REVISION"; do
  grep -Fq "$value" "$script_root/Dockerfile.dgx-spark" || fail "Spark Dockerfile is missing source pin $value"
done

grep -Fq "$DGX_SPARK_BASE_IMAGE" "$script_root/Dockerfile.dgx-spark" || fail "Spark base image does not match versions.env"
grep -Fq 'HF_HUB_OFFLINE: "1"' "$script_root/compose.yaml" || fail "Runtime is not forced offline"
if grep -Eq 'HF_TOKEN[[:space:]]*:' "$script_root/compose.yaml" "$script_root/compose.dgx-spark.yaml"; then
  fail "HF_TOKEN must not be passed to the application service"
fi

if [[ -d "$script_root/source/.git" ]]; then
  [[ "$(git -C "$script_root/source" rev-parse HEAD)" == "$TRELLIS2_SOURCE_REVISION" ]] || fail "Staged source is not at the pinned revision"
  [[ -z "$(git -C "$script_root/source" status --porcelain)" ]] || fail "Staged source checkout is dirty"
fi

set -a
source "$script_root/versions.env"
set +a
docker compose -f "$script_root/compose.yaml" -f "$script_root/compose.dgx-spark.yaml" --project-directory "$script_root" config --quiet

echo "TRELLIS.2 deployment materials passed static validation."
