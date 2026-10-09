# Skill card: load-path

| Field | Value |
|---|---|
| Description | Shows where a building model's weight goes, as colour flowing down from the roof to the columns, and runs the settle test in which every piece is let go and what moves is painted. Readiness: demo. |
| Owner | beyond-canvas team |
| License | Apache-2.0 |
| Use case | The hackathon showpiece "gravity and load-bearing", and any request about weight, what carries what, or whether the building stands. |
| Deployment geography | Global |
| Requirements | Blender 5.2 headless with its rigid body world and EEVEE; ffmpeg; model-anatomy's anatomy.json and bearing.json; shot-judge for the stills |
| Known risks | The load split is by contact area, a static estimate, not a structural analysis; the settle test is a rigid-body test of the drawn pieces with joints locked where pieces are drawn through one another, not a certified check. Both outputs say so. Long runs on a large model. |
| References | references/method.md; evals/evals.json; BENCHMARK.md |
| Skill output | loads.json, flow.mp4 and stills, settle.json, settle.mp4 and stills |
| Skill version | 0.1 |
| Ethical considerations | Renders and numbers about a building model only; nothing here should be read as advice about a real building. |
