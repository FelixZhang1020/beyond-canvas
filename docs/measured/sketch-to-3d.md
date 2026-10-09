# Standing a sketch up, and why it kept failing

Measured on `Image Sample/B&W Sketch/04-geometry-excellent.png` — a
graphite study of a cube, a sphere and a cylinder. Three models were tried and
all three failed differently. Between them they locate the fault precisely, and
it is not where anyone was looking.

**The finding in one line: `mesh.fast` does not need replacing. Its input does.**

## What the box was asked to reconstruct

A photograph of a pencil drawing on paper. That sentence is the whole problem,
and it took three failures to see it.

## Test one — InstantMesh on the photograph: two forms of three

`camenduru/instantmesh` on Replicate, the slot's own model and the one the Spark
will load. 16 seconds of compute, a valid mesh of 28,196 vertices and 56,308
triangles.

The sphere and the cylinder came back solid and correctly proportioned. **The
cube did not come back at all** — a faint ghost in all six generated views.

### Why, measured rather than guessed

Mean tone of each region, 0 to 255, against paper at 231:

| Region | Mean | vs paper |
|---|---:|---:|
| paper, top-left | 231 | — |
| **cube, top face** | 232 | **+1** |
| **cube, left face** | 227 | **−4** |
| cube, right face | 165 | −66 |
| sphere, lit side | 240 | +9 |
| **sphere, shadow side** | 119 | **−112** |
| cylinder, lit | 232 | +1 |
| **cylinder, shadow side** | 130 | **−101** |

Two of the cube's three visible faces are within four levels of the paper. The
two survivors each carry a shadow side more than a hundred levels darker. The
cube is present in that drawing **only as an outline**; it has no tonal body at
all.

Contrast enhancement cannot rescue it — tried, and it moves paper and cube
together: 252 against 254 afterwards, still inseparable. There is no tonal
difference to amplify.

## The component all three models share

`TencentARC/InstantMesh` segments the foreground with `rembg`/u2net, and exposes
`--no_rembg` for callers who supply their own alpha channel.

Reading the source rather than the README, **Hi3DGen does the same thing**: its
Space calls `pipeline.preprocess_image`, which is Microsoft TRELLIS's, which runs
`rembg.new_session('u2net')` before anything else. Hi3DGen's normal-map
reconstruction — the part that sounds like it would help — happens *after* that
step.

So InstantMesh, TRELLIS and Hi3DGen share the component that lost the cube.
**Switching between them cannot fix this.** Every one of them also ships the same
escape hatch: bring your own mask and their segmentation is skipped.

## Test two — TripoSG-scribble on the photograph: a lattice

`VAST-AI/TripoSG-scribble`, 4.38 GB, MIT, the only open-weight model found
anywhere whose model card names sketch input as its designed use. Its
HuggingFace Space is live and callable.

Fed the same photograph it returned 416,748 vertices arranged as **a repeating
three-dimensional grid of blobs**, filling a full ±0.95 cube in every axis. Not a
reconstruction of anything.

The likely reason is the same one: a scribble model expects strokes on a clean
ground, and the paper's grain reads as strokes everywhere, so it built geometry
everywhere.

## Test three — TripoSG-scribble on clean line art: flat slabs

The photograph was reduced to outlines — Gaussian blur at 1.6 to suppress the
grain, then an edge filter thresholded at the 99th percentile, giving 1.18%
strokes. **The cube is clearly visible in that line art**, which is the first
time any stage of this pipeline could see it.

The result was a large improvement and still wrong: **flat plates**, plus a ring
where the cylinder should be. It extruded the outlines rather than building
solids.

The reason is the obvious one in hindsight. Stripping to line art removes the
shading, and **the shading was the only cue for volume.**

## What the three tests bracket

| Input | Shading | Segmentation | Result |
|---|---|---|---|
| Photograph | kept | automatic | cube lost — no tonal contrast to segment |
| Photograph | kept | automatic | lattice of blobs — grain read as strokes |
| Line art | removed | n/a | flat slabs — no volume cue left |
| **Photograph + supplied alpha mask** | **kept** | **skipped** | **untested** |

The fourth row is the only combination that keeps the shading *and* avoids the
segmentation, and it is exactly what `--no_rembg` exists for. It needs a mask
made by something that reads edges rather than tone — SAM 2.1-tiny is 0.29 GB and
Apache-2.0, which would run on the Mac and the box alike.

It can be tested for nothing: `TencentARC/InstantMesh`'s Space is live and its
`/preprocess` endpoint takes a `do_remove_background` flag.

## The survey of alternatives, and what it is worth

Two research passes covered the sketch-to-3D field and the current open-source
image-to-3D state of the art. The short version is that **the sketch-specific
field is a graveyard** and the general field is mostly a licence minefield.

Sketch-trained projects, all unusable:

| Project | Why not |
|---|---|
| Sketch2Model | Unmaintained since 2021; README demands "black background, white strokes" |
| Sketch2Mesh | Real `handdrawn` mode, but cars and chairs only; pinned to CUDA 10.2, which predates Blackwell |
| Deep3DSketch / Deep3DSketch+ | No public code exists |
| SketchDream | 80 GB VRAM, per-object optimisation |
| S3D | Faces only, and no licence file at all |
| jiaqi404/SketchModeling | Wraps InstantMesh and adds a *second* background removal |

Licence casualties among the general models, checked against the licence files
rather than summaries:

| Model | Problem |
|---|---|
| Hunyuan3D 2.0, 2.1, 3.0, -Part | Tencent community licence, verbatim unchanged across versions: no EU, UK or South Korea; 1M monthly-user cap; attribution; no using output to improve another model. 3.0 has no open weights at all |
| CraftsMan3D | **No licence file.** GitHub returns `null`, `/LICENSE` 404s — default all-rights-reserved |
| MeshAnythingV2 | S-Lab 1.0, non-commercial only |
| Era3D | AGPL-3.0 — anything embedding it must be open-sourced |
| SF3D | Stability community licence: $1M revenue cap, mandatory attribution |

Clean and worth keeping in mind:

| Model | Size | Licence | Note |
|---|---:|---|---|
| InstantMesh | 6.8 GB | Apache-2.0 | the incumbent, and still the right one |
| TripoSR | 1.68 GB | MIT | tiny, no exotic build |
| TripoSG | 7.40 GB | MIT | untextured geometry |
| TripoSG-scribble | 4.38 GB | MIT | sketch-native, 64 downloads — almost nobody uses it |
| TRELLIS.2 | 14.86 GB | MIT | textured PBR; the only candidate with any DGX Spark port attempted, a 19-star community Docker, unverified |

**Weight size is never the constraint.** Every clean candidate fits the 90 GB
ceiling easily. The constraint is compiling CUDA extensions on ARM64, and no
project publishes an aarch64 wheel or a test matrix.

## What this changes

1. **`mesh.fast` stays InstantMesh.** Nothing found beats it once licence and
   build risk are counted, and the failure was never its fault.
2. **The work is a masking stage before the slot**, not a model swap.
3. **Hosted 3D testing is useful after all**, which reverses the verdict in
   `media-models-on-real-drawings.md`. That note was written after a
   thirty-minute cold start on Hunyuan3D and concluded "stop testing 3D online."
   Warm, the same class of call takes 16 to 19 seconds of compute, and the free
   HuggingFace Spaces make the decisive test cost nothing.

## What this does not settle

- **The masked run has not been done.** Row four of the table above is a
  prediction, not a result.
- **One drawing.** These six studies are AI-generated teaching material, not
  student work — the centre's own `教学说明.md` says so — so nothing here
  describes what a real child's pencil study would do.
- **Nothing was run on a Spark.** Every number above is a hosted GPU.
