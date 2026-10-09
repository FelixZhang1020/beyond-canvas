FROM beyond-canvas/trellis2:75fbf018

ENV CUDA_HOME=/usr/local/cuda \
    TORCH_CUDA_ARCH_LIST=8.9 \
    NATTEN_CUDA_ARCH=8.9 \
    NATTEN_N_WORKERS=6 \
    MAX_JOBS=6 \
    PIP_NO_CACHE_DIR=1 \
    PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/ \
    PYTHONUNBUFFERED=1 \
    HF_ENDPOINT=https://hf-mirror.com \
    HF_HUB_DISABLE_XET=1 \
    HF_HOME=/models/huggingface \
    TORCH_HOME=/models/torch

WORKDIR /opt/pixal3d
COPY . /opt/pixal3d

RUN python -m pip install \
      transformers==4.57.3 \
      diffusers==0.37.1 \
      accelerate==1.13.0 \
      plyfile==1.1.3 \
    && python -m pip install natten==0.21.0 --no-build-isolation \
    && for attempt in 1 2 3; do \
       python -m pip install \
         https://github.com/LDYang694/Storages/releases/download/20260430/utils3d-0.0.2-py3-none-any.whl \
       && break; \
       if [ "$attempt" = 3 ]; then exit 1; fi; \
       sleep 5; \
    done

RUN python -c "import torch, natten, transformers, pixal3d; print(torch.__version__, natten.__version__, transformers.__version__)"

ENTRYPOINT ["python", "smoke_rgba.py"]
