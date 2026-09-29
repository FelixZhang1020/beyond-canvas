# TRELLIS.2: reproducible DGX Spark deployment dossier

This is the canonical deployment record for the project's TRELLIS.2 image-to-3D
stack. It separates confirmed evidence from the DGX Spark work that still needs
real hardware verification.

## Outcome and current boundary

The repository now has an idempotent, fail-early DGX Spark installer at
deploy/trellis2/install-dgx-spark.sh. It validates the host and gated model
access, checks out immutable sources, builds an ARM64/GB10 container, downloads
pinned weights, creates an offline runtime tree, verifies CUDA imports and can
start the service on loopback.

The complete DGX path has not yet run on a physical DGX Spark. No document may
claim Spark latency, memory peak, output quality or successful inference until
that run is recorded. The shared development server is an x86_64 Ubuntu 22.04
machine with an RTX 4090 D, driver 575.64.03, Docker 28.3.2 and Compose 2.38.2.
It had about 270 GB free when inspected. Its existing TRELLIS image contains
PyTorch 2.6.0+cu124, Transformers 5.16.1 and FlashAttention 2.7.3.

The stopped 4090 service exposed a real offline-startup failure: the prepared
cache did not contain the new local runtime manifest, so the pipeline fell back
to mutable Hugging Face resolution while offline. The new sync script fixes
that class of error by verifying files and generating relocatable local paths;
that fix has not yet been deployed to the shared server.

## Dependency flow

    Input image
       |
       +-- RMBG-2.0 background removal (only when usable alpha is absent)
       |
       +-- DINOv3 ViT-L/16 image features
       |
       +-- TRELLIS.2 sparse structure flow
       |      +-- TRELLIS-image-large sparse decoder
       |
       +-- TRELLIS.2 shape and texture structured-latent flows
       |      +-- FlexGEMM sparse convolution
       |      +-- FlashAttention
       |
       +-- O-Voxel mesh/material extraction
              +-- CuMesh remesh, decimation and UV work
              +-- nvdiffrast and nvdiffrec rendering utilities
              +-- utils3d helpers
       |
       +-- GLB and preview output

The application loads the pipeline configuration from the generated local
runtime directory. It starts with HF_HUB_OFFLINE=1, so an undeclared network
dependency fails instead of silently fetching a mutable revision.

## Immutable component inventory

versions.env is the machine-readable source of truth.

| Layer | Source and revision | Why it is present |
|---|---|---|
| TRELLIS.2 source | microsoft/TRELLIS.2, 75fbf0183001ed9876c8dbb35de6b68552ee08bd | Pipeline, model definitions, app and O-Voxel source |
| Main weights | microsoft/TRELLIS.2-4B, af44b45f2e35a493886929c6d786e563ec68364d | Sparse, shape and texture generation weights; repository size reported as 16.2 GB |
| Sparse decoder | microsoft/TRELLIS-image-large, 25e0d31ffbebe4b5a97464dd851910efc3002d96 | The pipeline references ss_dec_conv3d_16l8_fp16 from the earlier TRELLIS repository |
| Image encoder | facebook/dinov3-vitl16-pretrain-lvd1689m, ea8dc2863c51be0a264bab82070e3e8836b02d51 | Image conditioning; gated |
| Background removal | briaai/RMBG-2.0, 5df4c9c76d8170882c34f6986e848ee07fd0ba43 | Foreground matte when input has no alpha; gated |
| utils3d | EasternJournalist/utils3d, 9a4eb15e4021b67b12c460c7057d642626897ec8 | Geometry and rendering helpers |
| nvdiffrast | NVlabs/nvdiffrast, 253ac4fcea7de5f396371124af597e6cc957bfae | Differentiable rasterization |
| nvdiffrec renderer | JeffreyXiang/nvdiffrec renderutils, b296927cc7fd01c2ac1087c8065c4d7248f72da4 | PBR rendering utilities |
| CuMesh | JeffreyXiang/CuMesh, 12289e1062f0603f2f0d0771b02e1395d247f26f | CUDA mesh processing; this revision includes an upstream Blackwell stream fix |
| FlexGEMM | JeffreyXiang/FlexGEMM, 6dd94a859c26ee8246888502eada3dd8ad85532e | Triton sparse convolution |
| NGC base | nvcr.io/nvidia/pytorch:26.08-py3, ARM64 digest 237ecf9ac7373daf91b31bb4f86651ce1ce57b676366ed435aa1aba61dad81d5 | Current signed NVIDIA PyTorch image; ARM64 manifest confirmed in NGC |
| FlashAttention | 2.8.3 | Spark porting variance; community evidence reports this source version builds on GB10 |

The upstream TRELLIS.2 instructions are tested on Linux A100/H100 with at least
24 GB GPU memory, recommend CUDA 12.4, PyTorch 2.6.0 and FlashAttention 2.7.3,
and leave several Git dependencies on moving branches. The reference 4090 build
preserves that combination. DGX Spark instead uses ARM64, CUDA 13 and compute
capability 12.1, so the Spark image uses the NGC framework and FlashAttention
2.8.3. This is a deliberate port, not an upstream-supported configuration.

Direct Python packages are pinned in requirements-dgx-spark.txt. Transitive
packages provided by the NGC image remain part of that image's signed manifest.
Before distributing the final image, export an SBOM or package inventory from
the built artifact and archive the image digest.

## Access and license gate

The browser account was observed to show “You have been granted access” for
both DINOv3 and RMBG-2.0, and both repositories exposed their file listings.
That does not authenticate another machine. The DGX must receive a read-only
HF_TOKEN for the same approved account.

The installer performs small authenticated downloads of config files from all
four repositories before any large model transfer. A 401/403 at this stage is
reported as an access problem. It never clicks acceptance forms and never
prints or persists the token.

Review deploy/trellis2/LICENSES.md before installation. Material constraints:

- TRELLIS.2 code and Microsoft weights are MIT.
- DINOv3 is a gated custom Meta license with redistribution, trade-control and
  prohibited-use conditions.
- RMBG-2.0's Hugging Face grant is non-commercial unless BRIA separately
  licenses the intended use.
- nvdiffrast and nvdiffrec have non-commercial research/evaluation use
  limitations despite the top-level MIT license.
- The NGC framework image uses NVIDIA's Deep Learning Container License.

The installer therefore requires TRELLIS2_LICENSES_ACKNOWLEDGED=1. This records
an operator checkpoint, not legal approval and not commercial-use permission.

## DGX Spark platform assumptions

NVIDIA documents DGX Spark as Ubuntu 24.04 on a 20-core ARM64 CPU and GB10
Blackwell GPU with 128 GB unified memory. Docker and NVIDIA Container Runtime
are normally preinstalled. The current NVIDIA porting guide specifies CUDA 13,
cuDNN 9.11 or newer, Container Toolkit 1.17.7 or newer, and compute capability
121-real for native builds.

The installer verifies Linux, aarch64, a GPU name containing GB10, working
Docker Compose, GPU access from NVIDIA's CUDA 13 test container and at least
70 GiB free. It deliberately does not install host packages, change groups,
invoke sudo, modify NVIDIA drivers or alter network services.

Unified memory is not equivalent to 128 GB of dedicated VRAM. During real
validation, record system memory pressure as well as nvidia-smi output.

## Installation and data flow

Run from a repository checkout on the DGX:

    export HF_TOKEN='read-token-for-the-approved-account'
    export TRELLIS2_LICENSES_ACKNOWLEDGED=1
    ./deploy/trellis2/install-dgx-spark.sh

The sequence is:

1. Verify host, disk, Docker, GPU runtime and the license checkpoint.
2. Pull a small multi-architecture Python helper and test authenticated access.
3. Clone or verify the official source and detach at the pinned commit with
   recursive submodules.
4. Build the Spark image from the pinned NGC base and pinned CUDA extensions.
5. Resume/download immutable Hugging Face snapshots into models/huggingface.
6. Generate models/runtime/trellis2 with only relative cache links and absolute
   in-container /models paths.
7. Start in offline mode and bind Gradio only to 127.0.0.1:7040.

Run only the safe preflight with:

    ./deploy/trellis2/install-dgx-spark.sh --preflight-only

The model and build cache are intentionally retained between runs. No cleanup
or deletion is performed automatically.

## Verification ladder

The installer proves the first three levels automatically when successful:

| Level | Required evidence |
|---|---|
| Host | ARM64 GB10, Docker/Compose and CUDA 13 test container succeed |
| Access | Pinned config files from main, decoder, DINOv3 and RMBG repositories download under the approved token |
| Build | Every CUDA extension compiles for capability 12.1 and Python dependency checks pass |
| Runtime | PyTorch sees CUDA capability 12.1; FlashAttention and O-Voxel import; offline app reaches HTTP readiness |
| Functional | A small representative RGBA input avoids RMBG and generates a valid GLB |
| Full path | A representative RGB sketch exercises RMBG, DINOv3, TRELLIS generation and GLB export |
| Operational | Cold offline restart, peak unified memory, latency, output hashes/metadata, restart behavior and SSH-tunnel access are recorded |

Levels Functional through Operational require a real DGX run and are not
claimed by this document. Start with 512 resolution and one sample. Do not use
cloud timings or the 4090's 24 GB behavior as Spark performance evidence.

## Failure handling

- Gated 401/403: confirm the token belongs to the browser-approved account and
  has read scope. Do not re-accept terms or paste the token into logs.
- Official Hugging Face unreachable: diagnose DNS, proxy and firewall first.
  A mirror override requires ALLOW_HF_MIRROR_FOR_GATED=1 because it sends the
  token to a different endpoint.
- NGC pull rejected: authenticate to nvcr.io using NVIDIA's documented flow;
  do not place the NGC key in repository files.
- CUDA extension compile failure: preserve the full build log and identify the
  exact component. Do not remove O-Voxel, CuMesh, FlexGEMM or renderer stages
  merely to make imports pass.
- Service offline lookup: inspect models/runtime/trellis2/pipeline.json and
  runtime-manifest.json. Any attempt to resolve main is a packaging defect.
- Out of memory: stop after capturing the stage and system/GPU telemetry. Retry
  at 512 resolution or lower token limits only as an explicit performance test.

## Primary technical sources

- TRELLIS.2 repository and upstream installation:
  <https://github.com/microsoft/TRELLIS.2>
- TRELLIS.2-4B pinned files:
  <https://huggingface.co/microsoft/TRELLIS.2-4B/tree/af44b45f2e35a493886929c6d786e563ec68364d>
- NVIDIA DGX Spark system overview:
  <https://docs.nvidia.com/dgx/dgx-spark/system-overview.html>
- NVIDIA DGX Spark dependency support:
  <https://docs.nvidia.com/dgx/dgx-spark-porting-guide/porting/dependencies.html>
- NVIDIA native compilation guidance and capability 121-real:
  <https://docs.nvidia.com/dgx/dgx-spark-porting-guide/porting/compilation.html>
- NVIDIA container-runtime validation:
  <https://docs.nvidia.com/dgx/dgx-spark/nvidia-container-runtime-for-docker.html>
- NVIDIA NGC PyTorch container:
  <https://catalog.ngc.nvidia.com/orgs/nvidia/containers/pytorch>
- DINOv3 license:
  <https://github.com/facebookresearch/dinov3/blob/main/LICENSE.md>
- FlashAttention releases and GB10 work:
  <https://github.com/Dao-AILab/flash-attention/releases>

## Release checklist

- [ ] Run preflight on the target DGX with the approved Hugging Face account.
- [ ] Confirm intended use is compatible with every license, or obtain separate
      commercial agreements/replacements.
- [ ] Record DGX OS, driver, Docker, Container Toolkit, NGC image digest,
      PyTorch, CUDA, cuDNN and all extension versions.
- [ ] Complete 512-resolution RGBA and RGB functional tests.
- [ ] Measure peak unified memory and end-to-end latency.
- [ ] Prove a cold start with outbound network disabled.
- [ ] Export an SBOM and archive models/runtime-manifest.json.
- [ ] Keep port 7040 loopback-only and test the documented SSH tunnel.
