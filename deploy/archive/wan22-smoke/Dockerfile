FROM pytorch/pytorch:2.6.0-cuda12.4-cudnn9-devel

ARG DEBIAN_FRONTEND=noninteractive
ENV CUDA_HOME=/usr/local/cuda \
    TORCH_CUDA_ARCH_LIST=8.9 \
    MAX_JOBS=6 \
    PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/ \
    PIP_NO_CACHE_DIR=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        ffmpeg \
        git \
        libgl1 \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /wan

COPY requirements-smoke.txt /tmp/requirements-smoke.txt
RUN python -m pip install --upgrade pip setuptools wheel packaging ninja \
    && python -m pip install -r /tmp/requirements-smoke.txt \
    && python -m pip install flash-attn==2.7.3 --no-build-isolation

# Imported unconditionally by wan/__init__.py via the S2V module.
RUN python -m pip install decord

COPY . /wan
COPY wan-init-ti2v.py /wan/wan/__init__.py

ENTRYPOINT ["python", "generate.py"]
