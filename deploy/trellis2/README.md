# TRELLIS.2 deployment

This directory contains two deliberately separate targets:

- Dockerfile and compose.yaml preserve the upstream-compatible RTX 4090 D
  reference build: x86_64, PyTorch 2.6, CUDA 12.4 and compute capability 8.9.
- Dockerfile.runtime-fix layers the pinned OpenEXR reader and compatible app
  entrypoint over that reference image. Compose uses this thin layer because
  the base OpenCV wheel cannot decode TRELLIS.2's HDR environment maps.
- Dockerfile.dgx-spark and compose.dgx-spark.yaml are the DGX Spark port:
  ARM64, the NVIDIA NGC PyTorch 26.08 image, CUDA 13 and GB10 compute
  capability 12.1.

The Spark path is not claimed as hardware-verified until it is run on a real
DGX Spark. The reference 4090 is useful for source and functional diagnosis,
but it cannot prove ARM64 or GB10 extension compatibility.

The Spark installer prepares the shared `gpu.lock` bind source before its first
container run, preserving an existing lock file. The Spark override publishes
the classroom bridge on loopback port 7240; the 4090 base intentionally leaves
that host port to the separate media worker.

## Before installation

Read LICENSES.md. DINOv3 and RMBG-2.0 are gated, RMBG-2.0 is non-commercial
without a separate BRIA agreement, and the two NVIDIA renderer dependencies
have non-commercial use limitations. Browser approval does not authenticate a
DGX command line; use a read-only Hugging Face token from the approved account.

The installer defaults to the official Hugging Face endpoint. A mirror is
rejected for gated downloads unless the operator deliberately sets
ALLOW_HF_MIRROR_FOR_GATED=1 after reviewing how that mirror handles tokens.

## One-click DGX Spark install

From the repository root on a DGX Spark:

    export HF_TOKEN='your-read-token'
    export TRELLIS2_LICENSES_ACKNOWLEDGED=1
    ./deploy/trellis2/install-dgx-spark.sh

The token is passed to a short-lived download container, is not written to the
repository, and is not passed to the offline application container.

A safe small preflight is available:

    export HF_TOKEN='your-read-token'
    export TRELLIS2_LICENSES_ACKNOWLEDGED=1
    ./deploy/trellis2/install-dgx-spark.sh --preflight-only

The complete script checks architecture, GB10 visibility, Docker GPU access,
disk space and all four pinned model repositories before it clones, builds or
downloads large artifacts. It then pins the source, builds CUDA extensions,
prepares a relocatable offline model tree, runs CUDA imports, starts the
loopback-only service, and waits for readiness.

Validate the material set itself without contacting a GPU host:

    ./deploy/trellis2/verify-materials.sh

Useful variations:

    ./deploy/trellis2/install-dgx-spark.sh --no-start
    ./deploy/trellis2/install-dgx-spark.sh --skip-build
    ./deploy/trellis2/install-dgx-spark.sh --skip-models

Only use a skip flag when the corresponding pinned artifact already exists.
The script never installs host packages, invokes sudo, changes Docker groups,
deletes caches, exposes the service publicly, or stores credentials.

## Operation

The Gradio service is bound to http://127.0.0.1:7040/. The bounded classroom
bridge is bound to http://127.0.0.1:7240/ and accepts one server-to-server job at
a time. `deploy/gpu-media/tunnel.sh` carries the bridge to the classroom Mac;
neither endpoint is exposed to the LAN. From this directory, after exporting
the values in versions.env:

    docker compose -f compose.yaml -f compose.dgx-spark.yaml logs --tail 100 trellis2
    docker compose -f compose.yaml -f compose.dgx-spark.yaml down

Stopping the service does not delete models. Immutable source/model pins are in
versions.env. The full component, license, dependency and verification record
is in ../../docs/deployment/trellis2-dgx-spark.md.
