# TRELLIS.2 deployment license and access gate

Review this file before running install-dgx-spark.sh. It is an engineering
inventory, not legal advice, and does not replace the linked license texts.

## Blocking facts

- The TRELLIS.2 code and primary Microsoft weights are MIT licensed.
- facebook/dinov3-vitl16-pretrain-lvd1689m is gated. Access is already
  granted to the project's Hugging Face account, but use remains governed by
  Meta's custom DINOv3 license, including redistribution, trade-control and
  prohibited-use conditions.
- briaai/RMBG-2.0 is gated. Its Hugging Face distribution is licensed for
  non-commercial use; commercial use requires a separate BRIA agreement.
- nvdiffrast and the nvdiffrec renderer used by this build have NVIDIA
  source-code licenses whose use limitation is non-commercial research or
  evaluation. These constraints apply even though the top-level project is MIT.
- The NVIDIA NGC PyTorch base image has the NVIDIA Deep Learning Container
  License.

Consequently, this exact bundle must not be represented as generally cleared
for commercial deployment. Obtain legal review and any required commercial
licenses before changing the intended use.

## Primary license sources

| Component | Source | License/access |
|---|---|---|
| TRELLIS.2 code | <https://github.com/microsoft/TRELLIS.2/blob/75fbf0183001ed9876c8dbb35de6b68552ee08bd/LICENSE> | MIT |
| TRELLIS.2-4B weights | <https://huggingface.co/microsoft/TRELLIS.2-4B/tree/af44b45f2e35a493886929c6d786e563ec68364d> | MIT |
| TRELLIS image decoder | <https://huggingface.co/microsoft/TRELLIS-image-large/tree/25e0d31ffbebe4b5a97464dd851910efc3002d96> | MIT |
| DINOv3 | <https://github.com/facebookresearch/dinov3/blob/main/LICENSE.md> | Custom DINOv3 license; gated |
| RMBG-2.0 | <https://huggingface.co/briaai/RMBG-2.0> | BRIA non-commercial license; gated |
| nvdiffrast | <https://github.com/NVlabs/nvdiffrast/blob/253ac4fcea7de5f396371124af597e6cc957bfae/LICENSE.txt> | NVIDIA Source Code License, non-commercial use limitation |
| nvdiffrec renderer fork | <https://github.com/JeffreyXiang/nvdiffrec/blob/b296927cc7fd01c2ac1087c8065c4d7248f72da4/LICENSE.txt> | NVIDIA Source Code License, non-commercial use limitation |
| CuMesh | <https://github.com/JeffreyXiang/CuMesh/blob/12289e1062f0603f2f0d0771b02e1395d247f26f/LICENSE> | MIT |
| FlexGEMM | <https://github.com/JeffreyXiang/FlexGEMM/blob/6dd94a859c26ee8246888502eada3dd8ad85532e/LICENSE> | MIT |
| utils3d | <https://github.com/EasternJournalist/utils3d/blob/9a4eb15e4021b67b12c460c7057d642626897ec8/LICENSE> | MIT |
| FlashAttention | <https://github.com/Dao-AILab/flash-attention/blob/main/LICENSE> | BSD 3-Clause |
| NGC PyTorch container | <https://developer.download.nvidia.com/licenses/NGC-DL-CONTAINER-LICENSE> | NVIDIA Deep Learning Container License |

The Python packages in requirements-dgx-spark.txt also retain their own
licenses. Capture a final software bill of materials from the built image
before redistributing it.
