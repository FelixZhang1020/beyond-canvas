FROM pytorch/pytorch:2.6.0-cuda12.4-cudnn9-devel

ARG DEBIAN_FRONTEND=noninteractive
ARG NVDIFFRAST_REVISION=253ac4fcea7de5f396371124af597e6cc957bfae
ARG NVDIFFREC_REVISION=b296927cc7fd01c2ac1087c8065c4d7248f72da4
ARG CUMESH_REVISION=12289e1062f0603f2f0d0771b02e1395d247f26f
ARG FLEXGEMM_REVISION=6dd94a859c26ee8246888502eada3dd8ad85532e
ENV CUDA_HOME=/usr/local/cuda \
    TORCH_CUDA_ARCH_LIST=8.9 \
    MAX_JOBS=6 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        ffmpeg \
        git \
        libgl1 \
        libglib2.0-0 \
        libjpeg-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . /app

RUN python -m pip install --upgrade pip setuptools wheel packaging ninja \
    && python -m pip install \
        imageio imageio-ffmpeg tqdm easydict opencv-python-headless==4.11.0.86 \
        trimesh transformers gradio==6.0.1 tensorboard pandas lpips \
        zstandard kornia timm pillow-simd

# Keep the large PyPI layer cacheable when GitHub has a transient transport
# failure. Force HTTP/1.1 and retry the small pinned source checkout.
RUN git config --global http.version HTTP/1.1 \
    && for attempt in 1 2 3; do \
        git clone https://github.com/EasternJournalist/utils3d.git /tmp/utils3d \
        && git -C /tmp/utils3d checkout 9a4eb15e4021b67b12c460c7057d642626897ec8 \
        && break; \
        rm -rf /tmp/utils3d; \
        if [ "$attempt" = 3 ]; then exit 1; fi; \
        sleep 5; \
    done \
    && python -m pip install /tmp/utils3d \
    && rm -rf /tmp/utils3d

RUN python -m pip install flash-attn==2.7.3 --no-build-isolation

RUN git clone https://github.com/NVlabs/nvdiffrast.git /tmp/nvdiffrast \
    && git -C /tmp/nvdiffrast checkout "$NVDIFFRAST_REVISION" \
    && python -m pip install /tmp/nvdiffrast --no-build-isolation \
    && git clone https://github.com/JeffreyXiang/nvdiffrec.git /tmp/nvdiffrec \
    && git -C /tmp/nvdiffrec checkout "$NVDIFFREC_REVISION" \
    && python -m pip install /tmp/nvdiffrec --no-build-isolation \
    && git clone --recursive https://github.com/JeffreyXiang/CuMesh.git /tmp/CuMesh \
    && git -C /tmp/CuMesh checkout "$CUMESH_REVISION" \
    && git -C /tmp/CuMesh submodule update --init --recursive \
    && python -m pip install /tmp/CuMesh --no-build-isolation \
    && git clone --recursive https://github.com/JeffreyXiang/FlexGEMM.git /tmp/FlexGEMM \
    && git -C /tmp/FlexGEMM checkout "$FLEXGEMM_REVISION" \
    && git -C /tmp/FlexGEMM submodule update --init --recursive \
    && python -m pip install /tmp/FlexGEMM --no-build-isolation \
    && cp -a /app/o-voxel /tmp/o-voxel \
    && python -m pip install /tmp/o-voxel --no-build-isolation \
    && rm -rf /tmp/nvdiffrast /tmp/nvdiffrec /tmp/CuMesh /tmp/FlexGEMM /tmp/o-voxel

# pillow-simd's Linux wheel exposes a WebP extension without the capability
# flags Gradio imports. Replace the upstream optional speedup with the matching
# official Pillow wheel after extension compilation is safely cached.
RUN python -m pip uninstall -y pillow-simd \
    && python -m pip install Pillow==11.3.0

# The runtime is deliberately offline. Let Compose point the pinned upstream
# app at an exact local snapshot instead of asking huggingface_hub to resolve
# the mutable `main` alias without network access.
RUN sed -i \
    "s#from_pretrained('microsoft/TRELLIS.2-4B')#from_pretrained(os.environ.get('TRELLIS2_MODEL_PATH', 'microsoft/TRELLIS.2-4B'))#" \
    /app/app.py

ENV ATTN_BACKEND=flash_attn \
    SPARSE_ATTN_BACKEND=flash_attn \
    GRADIO_SERVER_NAME=0.0.0.0 \
    GRADIO_SERVER_PORT=7860 \
    HF_HOME=/models/huggingface

EXPOSE 7860
CMD ["python", "app.py"]
