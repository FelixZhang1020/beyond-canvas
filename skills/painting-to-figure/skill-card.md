# Skill card: painting-to-figure

| Field | Value |
|---|---|
| Description | A small 3D toy figure inspired by a child's colour painting, built from simple parts the model lists, settled under gravity and checked before it is shown. |
| Owner | spark-art-studio team |
| License | Apache-2.0 |
| Use case | On the colour entrance, a teacher offers the child a toy of what they painted to turn in 3D, beside the original. |
| Deployment geography | Chinese and English classroom UI; under StepFun First the model runs on the StepFun subscription. |
| Requirements | vlm.figure (Step 3.7 Flash; vlm.creation where a profile has none), Python 3.13, Pillow, and a browser with WebGL for the page's viewer. |
| Known risks | The toy is the model's reading of the painting, not the child's strokes, and can simplify or miss details. The look check is a model and can be wrong both ways; a held-back figure gives the class nothing that time. Blocky parts for small subjects. |
| References | ../../docs/measured/painting-to-figure.md |
| Skill output | JSON parts (shape, centre, size, turn, colour) for the page's three.js viewer; no model code, no prose. |
| Skill version | 0.1 |
| Ethical considerations | Labelled as inspired by the painting, never as a correction. Input screened by studio-safety, preview screened again and looked at by a second model call before any child sees it. Class end drops drawings and cached outputs. |
