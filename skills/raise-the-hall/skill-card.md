# Skill card: raise-the-hall

| Field | Value |
|---|---|
| Description | Shows a building model going up in its measured carrying order, scene by scene, each piece dropping into place once what carries it is there. Readiness: demo. |
| Owner | beyond-canvas team |
| License | Apache-2.0 |
| Use case | The hackathon showpiece "from zero to the finished hall", and any request about assembly order. |
| Deployment geography | Global; scene labels in English |
| Requirements | Blender 5.2 headless with EEVEE; ffmpeg; model-anatomy's anatomy.json and bearing.json; shot-judge for the stills |
| Known risks | The order is the model's bearing order, which can differ from the historical build (all columns arrive together; the roof covering arrives as one scene). Pieces the bearing tool found floating arrive in the first scene. Long renders on a large model. |
| References | references/order.md; evals/evals.json; BENCHMARK.md |
| Skill output | scenes.json, raise.mp4, one still per scene, raise.json |
| Skill version | 0.1 |
| Ethical considerations | Renders of a building model only. |
