---
name: sketch-to-3d
description: Reconstructs tabletop studies with movable lighting; local image-to-3D handles fruit-only studies and a single head or plaster bust, while mixed geometric studies use bounded CPU fitting.
allowed-tools:
license: Apache-2.0
compatibility: Python 3.13, the existing vision endpoint, and WebGL. Heads and fruit-only studies additionally need the isolated local TripoSG worker.
metadata:
  author: beyond-canvas
  version: "0.3"
---

# Sketch to 3D

The classroom screens the drawing first. `studio/making/sketch.py` asks the existing
vision model for kinds and full bounding boxes in its native 0..1000 xyxy
format, plus cylinder top-face boxes when available. The CPU converts these
to proportions and fits up to six solids on a ground plane. Cylinder ellipses
calibrate the camera jointly with the scene. Without one the initial view is
25 degrees. Box yaw and backside depth are assumptions; the lamp starts on
the upper left. No drawing text is returned or logged.

Pears, apples and oranges have their own kinds. In a study mixing fruit with
geometric solids, pear neck and visible stalk
boxes constrain an approximate rounded surface; they are not mapped to spheres.
If a recognized mixed-study fruit omits a required part field, or the model
returns incomplete / malformed JSON, at most one additional vision call
requests a complete annotation. Continued omissions, syntax errors or invalid parts fail; no
default stalk or unbounded retry is used. A valid mixed still life containing fruit
becomes a small shared triangle mesh via `studio/making/still_life.py`, so all objects
cast shadows on one another. Body asymmetry, exact contours and hidden depth
are not recovered. Real verification of this fast route covers the supplied
sphere, cube and pear study.

A single head / bust or a study consisting only of apples, pears and/or oranges
is routed to the local image-to-3D worker (the compatible slot name remains
`mesh.portrait`). Fruit recognition needs only kinds and bounded boxes; the
original image, not part boxes or a lathe template, drives the generated surface.
One whole-image generation shares the existing single-job / 60,000-face budget.
Fruit surfaces receive bounded CPU smoothing, and the viewer keeps the original
image aspect ratio. The actual apple-and-pear study has been verified; this is
not acceptance of arbitrary fruits or widely separated groups. Fragmented
surfaces still fail. A missing worker or failed generation has no silent
primitive fallback and no automatic image-model retry.
For installation and resource limits,
see `studio/portrait_runtime/README.md`. A head mixed with other independent
objects remains unsupported.

The viewer shows the original beside the approximate reconstruction, with
orbit, light placement, light height, brightness, reset and still export.
Light changes are computed in the browser against untextured solid geometry,
including self-shadow and shadows on neighbouring objects and the ground.

This is not a recovered mesh of arbitrary drawings or an exact representation
of a child's pencil contours. Hidden surfaces, proportions and camera angle are
estimates. Model-declared unsupported or stacked objects, malformed coordinates
and failed fits stop with an explanation. Validation cannot guarantee semantic
recognition accuracy. No standard cube/sphere/cylinder scene is substituted.

Network access follows the configured vision and safety slots. The optional
`vlm.sketch` slot aliases the same resident model endpoint with an assistant
prefill, tested with Step3-VL and llama.cpp, to avoid unbounded reasoning for
simple localization. Other providers fall back to `vlm.studio`. Safety keeps
its normal reasoning path. A cloud profile sends the image to those endpoints;
browser interaction uses no network.
Successful recognition is reused within the current drawing's conversation,
never across classes. This does not claim deletion of the server's event history.

The source contract and validation are in `studio/making/sketch.py`; browser rendering
and its fixed workload limits are in `studio/page/src/27e-relight.js`.
Triangle rendering and shadows are shared with `studio/page/src/27f-mesh.js`.
Measured results and Spark acceptance work are in
`docs/measured/sketch-relighting.md`,
`docs/measured/portrait-relighting.md`, and
`docs/measured/mixed-still-life.md`, and
`docs/measured/fruit-image-to-3d.md`.
