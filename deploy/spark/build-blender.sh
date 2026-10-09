#!/bin/sh
# Build beyond-canvas/blender:1 (Dockerfile.blender) on the node, under the memory guard like every
# build here, then prove Blender answers through the wrapper the studio and the tools will call.
# The base is Ubuntu 26.04's minimal root filesystem (33.5 MiB), imported once. Its SHA256SUMS comes
# from the same mirror, so the check proves the file arrived whole, not who made it; every package
# apt then installs is signature-checked against Ubuntu's keys inside that base. The operator allowed
# this download and Blender's.
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
BASE=beyond-canvas/ubuntu-base:26.04.1
RELEASE=https://mirrors.tuna.tsinghua.edu.cn/ubuntu-cdimage/ubuntu-base/releases/26.04.1/release
FILE=ubuntu-base-26.04.1-base-arm64.tar.gz
if ! docker image inspect "$BASE" > /dev/null 2>&1; then
    WORK=$(mktemp -d)
    trap 'rm -rf "$WORK"' EXIT
    curl -fsSL --max-time 900 -o "$WORK/$FILE" "$RELEASE/$FILE"
    curl -fsSL --max-time 60 -o "$WORK/SHA256SUMS" "$RELEASE/SHA256SUMS"
    (cd "$WORK" && grep " \*\?$FILE\$" SHA256SUMS | sha256sum -c -)
    docker import "$WORK/$FILE" "$BASE"
fi
python3 "$HERE/memory_guard.py" --floor 24 -- docker build -t beyond-canvas/blender:1 \
    -f "$HERE/Dockerfile.blender" "$HERE"
"$HERE/bin/blender" --version | head -1
"$HERE/bin/blender" -b --factory-startup --python-expr "import bpy; print('BLENDER', bpy.app.version_string)" \
    | grep '^BLENDER'
