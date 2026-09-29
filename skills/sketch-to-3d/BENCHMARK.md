# BENCHMARK: sketch-to-3d

**Why there is no "with skill / without skill" table here.** The comparison NVIDIA names for a
verified skill is the same model asked the same thing twice, once with the skill loaded and once
without. That comparison does not apply to this skill, because the model does not make the result.
The mesh comes from TRELLIS.2, or from a clean-solids reading that builds geometry directly; the
skill decides which route a drawing takes, screens it first, and saves the camera so the viewer
opens where the sketch was drawn. A bare model given the same sketch produces no mesh at all, so a
second row would be 0 against everything and would measure nothing. What is measured instead is
what the skill is actually responsible for, and it is measured on real drawings.

## What has been measured

| What | Result | Where |
|---|---|---|
| Every pencil sketch in the sample set, through the class's own code, six times in one night | All 8 came out on every run | [overnight run](../../docs/measured/overnight-2d-to-3d.md) |
| Likeness to the drawing, scored 1–5 by Step 3.7 Flash against the original, twice | **4.25 and 4.31** | same |
| The four geometry sketches through the clean-solids route | 5 of 5 | same |
| Time for one 3D study, model held in memory between jobs | ~69 s, from ~205 s | commit `a3bfdd8`, [evidence](../../docs/measured/trellis-stays-loaded.md) |
| Which 3D model to use at all | TRELLIS.2, chosen from a bake-off of the field | [bake-off](../../docs/measured/3d-model-bakeoff.md), [two-model](../../docs/measured/two-sketch-model-bakeoff.md) |
| Two routes for pencil sketches | Measured and split by drawing kind | [evidence](../../docs/measured/two-routes-for-pencil-sketches.md) |

The sketches are the strongest 3D result in the project. Colour paintings through
`painting-to-figure` score around 3; these score above 4, and nothing in the overnight run needed
fixing.

## What the eval cases assert, and what proves them

The five cases in `evals/evals.json` state pipeline facts rather than model quality — that safety
runs before any model sees the drawing, that the result is a GLB the viewer opens rather than a
picture of one, that a `camera_base` is saved so first open and reset agree, and that the back of a
head is never claimed as drawn. Those are held by **39 tests** (`tests/making/test_sketch.py`,
`tests/providers/test_cloudmesh.py`, `tests/making/test_view_calibration.py`), run on the Spark with the rest of the
suite.

## What is not measured

A fixed seed is not repeatability: the same sketch gives a different file every time, so a single
run proves nothing about the next one. The likeness scores above are from one night on one sample
set of eight sketches, none of them from a real class.
