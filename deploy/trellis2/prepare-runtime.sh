#!/usr/bin/env bash
set -Eeuo pipefail

root="${1:?usage: prepare-runtime.sh deployment-directory}"
# Compose refuses to create this bind source. Append-open preserves an existing
# file and its inode, including any lock held by another project worker.
if [[ -e "$root/../gpu.lock" && ! -f "$root/../gpu.lock" ]]; then
  echo "gpu.lock must be a regular file" >&2
  exit 1
fi
: >> "$root/../gpu.lock"
