# Skill card: structure-tour

| Field | Value |
|---|---|
| Description | Films a camera tour of a building model in four moves: around, to the door, inside up to the ceiling, and overhead with the roof peeled off. Readiness: demo. |
| Owner | beyond-canvas team |
| License | Apache-2.0 |
| Use case | The hackathon showpiece "the whole building, inside and out", and any request to see a place in the building. |
| Deployment geography | Global |
| Requirements | Blender 5.2 headless with EEVEE; ffmpeg; model-anatomy for the box and roles; shot-judge for the stills |
| Known risks | The camera path is computed from the building box, so a very long or very low building may get an inside segment through a wall; the judge's verdict on the inside still catches it and `--segments` skips it. Sixteen seconds of a large model is a long render. |
| References | evals/evals.json; BENCHMARK.md |
| Skill output | tour.mp4, one still per segment, tour.json |
| Skill version | 0.1 |
| Ethical considerations | Renders of a building model only. |
