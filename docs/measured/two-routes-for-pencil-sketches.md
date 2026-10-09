# Do pencil sketches need two routes to 3D?

**Question (operator).** The classroom sends a geometry sketch to clean solids (Step 3.7 Flash reads the
shapes, the CPU builds them) and everything else to TRELLIS.2. Is the second route really needed?

**Setup.** The eight sketches in `Image Sample/B&W Sketch/`: four geometry sketches (one arrangement — box,
ball, cylinder — at four skill levels), two plaster heads, two fruit still lifes. Each sent as a class sends
it (`studio.images.to_data_uri`, 1024-pixel PNG). StepFun First:

- **Step 3.7 Flash** — `vlm.sketch` on the subscription, the class's own `sketch.clean_solids` steps; every
  sketch three times.
- **TRELLIS.2** — on the hosted DGX Spark, the class's container, weights and pinned settings. The class
  worker's seed is fixed at 42 (a fixed seed is not repeatability: the same sketch built four times on the
  node gave four different files, docs/measured/trellis-stays-loaded.md); the geometry sketches were
  also run at seeds 1 and 7 (a copy of the worker with only the seed changed). Heads and fruit at seed 42.

Seed-42 geometry models are the ones made through the class service earlier the same day
([clean solids](geometry-sketches-to-clean-solids.md)); the rest were run by a scratch runner
that took the shared GPU lock like any job. Models were judged by eye from four sides.

## Results

| Sketch | Step 3.7 Flash (3 looks) | TRELLIS.2 seed 42 (the class's) | seed 1 | seed 7 |
|---|---|---|---|---|
| 01 geometry, beginner | clean solids ×3 | three shapes plus stray pieces, box partly hollow | box an open shell | **all solid** |
| 02 geometry, basic | clean solids ×3 | **no ball**, a paper sheet | **all solid** | **all solid** |
| 03 geometry, proficient | clean solids ×3 | **no ball**, a curved sheet | box hollow with an arch, a stray piece | **all solid** |
| 04 geometry, excellent | clean solids ×3 | half-cylinder shell, three-wall box | **all solid** | **all solid** |
| 05 head, basic | declined ×3 → TRELLIS.2 | **faithful head and plinth** | — | — |
| 06 head, excellent | declined ×3 → TRELLIS.2 | **faithful head and plinth** | — | — |
| Fruits 1 | declined ×3 → TRELLIS.2 | **faithful apple and pear** | — | — |
| Fruits 2 | declined ×3 → TRELLIS.2 | **faithful apple and pear** | — | — |

- Step 3.7 Flash: 24 of 24 looks routed correctly; all 12 geometry looks built box, ball and cylinder, fit
  error 0.015–0.050 against the class's reject line of 0.09, in 11–29 s.
- TRELLIS.2: 206–329 s a model (most near 230 s), 38 GB of the Spark's memory while it runs.
- Geometry through TRELLIS.2: 6 of 12 (sketch, seed) pairs came out clean — a solid box, ball and cylinder
  and nothing else: 0 of 4 at the class's seed, 2 of 4 at seed 1, 4 of 4 at seed 7. At seed 42 three were
  broken (hollow, or no ball) and the beginner's was mostly solid with stray pieces — the earlier note's
  "基本是实体，背后多一片"; it is counted as not clean here.

## What it means

- **Heads and fruit need TRELLIS.2.** Clean solids have no shape for them, and Step 3.7 Flash passed every
  one on. TRELLIS.2 made all four well.
- **Geometry does not strictly need clean solids** — TRELLIS.2 at seed 7 made all four — but on this
  evidence clean solids are the better route: every look right against half of TRELLIS.2's tries, about
  20 s against about 4 minutes, and no GPU. Which seed works is luck per drawing; seed 7's four successes
  are four drawings of one arrangement.
- Clean solids show the correct forms placed where the child drew them; TRELLIS.2 keeps more of the drawing
  itself (the pencil texture shows on the seed-7 models).

## Seed 7 on heads and fruit, and the decision

The four heads and fruit were then run at seed 7 (201–247 s each): both heads faithful with their plinths,
both fruit a whole apple and pear — as good as seed 42, judged side by side from two sides.

**Operator decision:** keep both routes, and make seed 7 the class's TRELLIS.2 seed
(`deploy/gpu-media/extra/trellis_worker.py`, held by `tests/test_trellis_settings.py`). TRELLIS.2 is what a
geometry sketch gets whenever the clean-solids reading cannot answer, and at seed 42 that fallback failed
the geometry sketches.

## Not proven

- Seed 7 on any other geometry arrangement (prism, cone, pyramid), or on other heads and fruit.
- Phone photos of real sketches; all eight are clean scans.
