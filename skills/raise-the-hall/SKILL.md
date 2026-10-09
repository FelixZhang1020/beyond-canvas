---
name: raise-the-hall
description: Shows a 3D building model being built from its platform to its roof in the true carrying order, scene by scene, each piece arriving from above once what carries it is in place. Use it for any request about how the building was put up, assembled, constructed, or what goes first.
allowed-tools: raise-the-hall/raise, raise-the-hall/stages
license: Apache-2.0
compatibility: Blender 5.2 headless with EEVEE; ffmpeg; Python 3.13. Needs model-anatomy's anatomy.json and bearing.json. The Foguang hall's ten-second sequence at 1280 x 720 is about 25 minutes on an Apple M-series Mac; run it in the background.
metadata:
  author: beyond-canvas
  version: "0.1"
---

# Raise the hall

Two tools, in order.

1. **stages**, the scenes: `python3 skills/raise-the-hall/scripts/stages.py <bearing.json> <anatomy.json> <out_dir> [--max-scenes 24]`
   merges the bearing stages into at most 24 scenes and names each (columns, tie beams, bracket
   blocks, beams, rafters, roof covering). Read `scenes.json` back to narrate the sequence.
2. **raise**, the video: `blender -b <model.blend> --python-exit-code 1 --python skills/raise-the-hall/scripts/raise.py -- <out_dir> --scenes <scenes.json> --anatomy <anatomy.json> [--drop 3.0] [--scene-seconds 0.4] [--settle-seconds 0.6] [--orbit-degrees 90]`
   writes `raise.mp4`, one still per scene `raise-<index>.png`, and `raise.json`.

The order is the bearing order model-anatomy measured, not a guess: a piece never arrives before
what carries it. Judge the last still with "the finished hall with its roof from the front
corner" and one middle still with "the timber frame half built, columns and brackets up, no roof".

It never saves the model and never changes a piece's final place.
