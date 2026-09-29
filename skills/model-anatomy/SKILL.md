---
name: model-anatomy
description: Reads any 3D building model in Blender and writes what is in it, every piece with its role (ground, wall, timber, rafter, covering), size and kind, what rests on what, the order pieces carry each other in, and named places a camera can look from. Use it first, before any showpiece tool, and whenever a request names a part of the building.
allowed-tools: model-anatomy/bearing, model-anatomy/inventory
license: Apache-2.0
compatibility: Blender 5.2 headless (bpy and the standard library only); Python 3.13; no network. macOS and Linux, x86_64 or arm64. The Foguang East Hall (6,264 pieces) takes a few minutes for both tools.
metadata:
  author: beyond-canvas
  version: "0.1"
---

# Model anatomy

Every other showpiece skill asks this one first: which pieces exist, what each is, and what
carries what. Both tools read a `.blend` and write JSON into an output folder; the model is
never changed.

## Tools

1. **Inventory**, what is in the model:
   `blender -b <model.blend> --python-exit-code 1 --python skills/model-anatomy/scripts/inventory.py -- <out_dir>`
   writes `<out_dir>/anatomy.json`: `model` (box, size, height, counts by role, collections),
   `pieces` (per name: role, collections, kind block|column|beam|sheet, centre, axis, extents
   along/across/deep in metres, box, volume) and `landmarks` (centre, front, back, left, right,
   above, inside; each a camera position `at` and the point it `look`s at).
2. **Bearing**, what rests on what (run after inventory, same folder):
   `blender -b <model.blend> --python-exit-code 1 --python skills/model-anatomy/scripts/bearing.py -- <out_dir>`
   writes `<out_dir>/bearing.json`: `rests_on` (per piece, the seats it stands on with area and
   place), `floating` (pieces with nothing under them), `overlaps` (pieces drawn into another),
   `order` (highest first, every piece before what carries it), `stages` (bottom-up construction
   sequence; the last stage is the roof covering) and `ground`.

## Reading the result

- A request that names a part ("the corner bracket set", "the ridge") is answered by searching
  piece names and collections in `anatomy.json`; the hall names its pieces in English with the
  Chinese term romanised (dou, gong, ang, fang, rufu).
- `stages` is the construction order for raise-the-hall; `order` reversed is the same thing one
  piece at a time.
- A piece in `floating` is a modelling fault, not a fact about the building; say so rather than
  animating it.

## Roles, by collection name

See `references/roles.md`. A model with no recognisable collection names gets every piece as
timber and nothing as ground; add a ground piece before asking for stages.

## What it never does

It does not modify, save or export the model. It does not judge whether the building stands;
that is load-path's job.
