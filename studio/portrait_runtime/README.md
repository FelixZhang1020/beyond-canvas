# Local image-to-3D reconstruction

This optional worker reconstructs a single drawn head / plaster bust or a fruit
study with TripoSG. It returns an untextured triangle mesh to the classroom. The browser
handles perspective, orbiting, point-light shading and cast shadows without
calling a model again. This is an approximate reconstruction; hidden surfaces,
facial detail and the initial viewing angle are not recovered exactly.

Geometric solids, including mixed solid-and-fruit studies, use the existing VLM
and CPU fitter. A head or a study consisting entirely of apples, pears and/or
oranges is routed here after image screening. The existing `mesh.portrait` slot
name is retained for configuration compatibility; it now serves both subjects. No cloud mesh
fallback is configured. Other classroom slots retain their own provider choices.

## Prepare once

Use a separate Python 3.11 environment. Do not install these libraries into the
classroom's Python 3.13 environment. From the project root:

```sh
uv venv --python 3.11 .studio/portrait/runtime
git clone https://github.com/VAST-AI-Research/TripoSG.git .studio/portrait/source
git -C .studio/portrait/source checkout fc5c40990181e2a756c4e0b1c2f4d6b5202faf8c
git -C .studio/portrait/source apply "$PWD/studio/portrait_runtime/optional-diso.patch"
```

Install the appropriate PyTorch build first. The tested Mac environment uses:

```sh
uv pip install --python .studio/portrait/runtime/bin/python torch==2.6.0 torchvision==0.21.0
uv pip install --python .studio/portrait/runtime/bin/python -r studio/portrait_runtime/requirements.txt
PYTHONPATH=. .studio/portrait/runtime/bin/python -m studio.portrait_runtime.prepare --root .studio/portrait
```

The last command downloads about 8 GB of pinned TripoSG weights plus U2Net; it
does not send drawings anywhere. Keep the upstream repository's MIT license and
notices with its source. The small patch only makes the unused CUDA `diso`
import optional. This worker uses the upstream dense extractor at depth 7 and
CPU marching cubes, so it needs neither `diso` nor a custom CUDA extension.

On Spark, select a CUDA / PyTorch distribution that supports GB10 and ARM64
instead of using the Mac wheel command. The exact Spark container, CUDA kernels,
runtime compatibility and latency have **not** been verified on hardware.

## Run

```sh
PYTHONPATH=. .studio/portrait/runtime/bin/python -m studio.portrait_runtime.server \
  --source .studio/portrait/source --weights .studio/portrait/weights \
  --masks .studio/portrait/masks --port 7240
```

Start the classroom with the `local` or `spark` profile. Both point
`mesh.portrait` at this loopback worker. `/v1/models` reports `triposg` only after
the model has loaded. A second simultaneous mesh request receives 503 instead of
queuing another GPU job. Missing workers and invalid surfaces produce distinct
classroom messages.

The current development installation uses the same command with the isolated
environment and assets in `scratch/portrait/`; it is not a Spark deployment.

## Resource and quality bounds

- One image and one GPU job at a time; no generation-time downloads.
- Input long edge 1024, 20 diffusion steps, 2048 latent tokens, a 128³ field,
  4096 surface queries per decoder chunk.
- At most 60,000 vertices and 60,000 triangles, 8 MiB response, no baked shading
  texture. Fragmented surfaces and invalid geometry are rejected. Small numerical
  debris is removed; a bounded Taubin pass reduces voxel stair steps (8 iterations
  for heads, 80 for rounded fruit, maximum vertex displacement 0.06 world units).
  It does not reconstruct a separate model for each fruit, and strongly separated
  objects may be rejected by the existing 98% connected-surface requirement.
- MPS uses FP32: this tested FP16 stack fragmented the head even with the same
  initial FP32 noise. CUDA follows the upstream FP16 choice and limits the
  torch allocator to 12 GiB. That limit excludes non-torch / CPU memory and is
  not a measured whole-process ceiling.
- Spark's profile reserves a conservative 20 GB planning allowance for this
  worker, including loading and masking. Measure total memory together with the
  other resident services before treating the classroom budget as validated.
- Browser rendering is capped at one million pixels and six 1024² shadow faces
  (24 MiB colour storage plus depth and mesh buffers). Shadow maps update only
  when the lamp moves. No idle rendering loop; closing releases GPU resources.

Real model quality, timings, negative controls and remaining limits are recorded
in [the portrait verification report](../../docs/measured/portrait-relighting.md)
and [the fruit image-to-3D report](../../docs/measured/fruit-image-to-3d.md).

Run the surface checks in this isolated environment, without adding tensor or
mesh libraries to the ordinary classroom environment:

```sh
PYTHONPATH=. .studio/portrait/runtime/bin/python -m unittest studio.portrait_runtime.test_surface
```
