---
name: structure-tour
description: Films a moving-camera tour of a 3D building model, around the outside, in through the front, up under the ceiling among the brackets, and over the top with the roof peeled off to show the timber frame. Use it for any request to see, tour, fly through, look inside or look down on the building, or to show its structure as a whole.
allowed-tools: structure-tour/tour
license: Apache-2.0
compatibility: Blender 5.2 headless with EEVEE; ffmpeg for the video; Python 3.13. Needs model-anatomy's anatomy.json. Sixteen seconds of the Foguang hall at 1280 x 720 is about 40 minutes on an Apple M-series Mac; run it in the background.
metadata:
  author: beyond-canvas
  version: "0.1"
---

# Structure tour

One tool. `blender -b <model.blend> --python-exit-code 1 --python skills/structure-tour/scripts/tour.py -- <out_dir> --anatomy <anatomy.json> [--segments outside,door,inside,overhead] [--seconds-per 4] [--fps 30] [--style daylight|studio]`

Four segments, each a camera move: `outside` orbits the whole building; `door` approaches the
front; `inside` walks in with the walls hidden and tilts up to the ceiling; `overhead` looks down
with the roof covering and rafters hidden so the frame shows. Pick a subset with `--segments`
for a request about one place ("show only the roof from below" is `inside`; "the frame from
above" is `overhead`). Outputs, all in out_dir: `tour.mp4`, one still per segment `tour-<segment>.png`
(`tour-outside.png`, `tour-door.png`, `tour-inside.png`, `tour-overhead.png`) for the judge, and
`tour.json`; the folder `tour/` holds only the video frames.

Judge each still: "the whole hall from outside with its roof", "the front of the hall with the
doors ahead", "the ceiling and brackets from inside", "the timber frame from above, roof removed".
A fail on `outside` usually wants a wider radius; on `inside`, a lower camera.

It never saves the model and never changes a piece; it only hides roles per segment.
