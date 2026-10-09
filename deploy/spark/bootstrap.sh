#!/bin/sh
# Give the studio its Python on the hosted Spark. Run on the node, after sync.sh.
#
# The node cannot reach GitHub or pypi.org, and has no sudo, so Python 3.13 comes
# from the NJU mirror of python-build-standalone and packages from the Tsinghua
# PyPI mirror, both through a user-level uv in ~/tools. Nothing is installed
# system-wide: the organisers forbid changes to the host.
set -eu

UV=${UV:-$HOME/tools/bin/uv}
if [ ! -x "$UV" ]; then
    python3 -m venv "$HOME/tools"
    "$HOME/tools/bin/pip" install -q -i https://pypi.tuna.tsinghua.edu.cn/simple uv
fi
export UV_PYTHON_INSTALL_MIRROR=https://mirror.nju.edu.cn/github-release/astral-sh/python-build-standalone
export UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple

cd "$HOME/beyond-canvas"
"$UV" python install 3.13
"$UV" venv --allow-existing --python 3.13 .venv
"$UV" pip install --python .venv/bin/python -e . pytest pytest-mock
.venv/bin/python -m studio.start --check --deployment stepfun
