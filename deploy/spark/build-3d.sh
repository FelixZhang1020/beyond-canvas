#!/bin/sh
# Build the Spark's two 3D containers, TRELLIS.2 then Pixal3D over it. Run on the node,
# in tmux — flash-attn and natten compile from source for the GB10 and take a long time:
#     tmux new -d -s build3d "sh ~/beyond-canvas/deploy/spark/build-3d.sh 2>&1 | tee -a ~/logs/build-3d.log"
#
# Needs deploy/trellis2/vendor on the node (sent by `sync.sh deploy/trellis2/vendor`)
# and the NVIDIA PyTorch image already pulled. Package indexes are the Tsinghua
# mirrors: pypi.org is too slow from the node and Ubuntu's is slower than Tsinghua's.
set -eu
DEPLOY=$HOME/beyond-canvas/deploy
PYPI=https://pypi.tuna.tsinghua.edu.cn/simple
APT=https://mirrors.tuna.tsinghua.edu.cn/ubuntu-ports
# 4, the recipe's own default. A build at 12 once froze the node 76 s in,
# as flash-attn's compile began (it was compiling for four GPU generations; the
# Dockerfile now asks for the GB10's only). A Spark that runs out of memory
# freezes rather than failing, so every build runs under memory_guard.py, which
# cancels it while 24 GiB is still free and logs the lowest figure it saw.
JOBS=${JOBS:-4}
GUARD="python3 $DEPLOY/spark/memory_guard.py --floor 24 --"

echo "=== $(date '+%F %T') TRELLIS.2"
$GUARD docker build -t beyond-canvas/trellis2:dgx-spark -f "$DEPLOY/trellis2/Dockerfile.dgx-spark" \
    --build-arg BASE_IMAGE=nvcr.io/nvidia/pytorch:26.08-py3 \
    --build-arg PIP_INDEX_URL=$PYPI --build-arg APT_MIRROR=$APT --build-arg MAX_JOBS="$JOBS" \
    "$DEPLOY/trellis2"
docker run --rm --gpus all --entrypoint python beyond-canvas/trellis2:dgx-spark -c \
    'import torch, flash_attn, o_voxel; cc = torch.cuda.get_device_capability(); assert cc == (12, 1), cc; print("TRELLIS.2 image OK", torch.__version__, flash_attn.__version__, cc)'

echo "=== $(date '+%F %T') Pixal3D"
$GUARD docker build -t beyond-canvas/pixal3d:dgx-spark -f "$DEPLOY/pixal3d/Dockerfile.dgx-spark" \
    --build-arg PIP_INDEX_URL=$PYPI "$DEPLOY/trellis2/vendor"
echo "=== $(date '+%F %T') BUILT"
