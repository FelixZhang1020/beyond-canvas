# Skill card: hall-carpenter

| Field | Value |
|---|---|
| Description | Makes a timber hall from nothing in Blender, part by part from given numbers, to match a standing building; measures that building, says how alike the two are, and groups the checks' findings by the part that caused them. Readiness: demo. |
| Owner | beyond-canvas team |
| License | Apache-2.0 |
| Use case | The hackathon's from-nothing rebuild: proof that the harness, not the model's word, decides when a made thing is handed over. |
| Deployment geography | Global |
| Requirements | Blender 5.2 headless with numpy; model-anatomy, load-path and shot-judge for the checks. The optional review needs a text model on the `llm.engineer` slot (planned: NVIDIA Nemotron 3 Nano 30B-A3B on the DGX Spark) |
| Known risks | The hall is a plain one: boxes and round columns, no carving, doors, tiles or curved eaves. Likeness is three flat outlines, a column count and a frame census (tie beams at the column heads, roof rings, ridge, rafters, a bracket set on every column), not a piece-for-piece comparison. The measuring step reads pieces by their names (column, tie beam, purlin), so a model named otherwise measures badly. Joints a carpenter would cut are drawn let in and are held as one body by the settle test; everything else only sits, so the gravity test is a test of stacking, not of timber strength. The engineer's review is a language model's opinion from a sheet of numbers: it can be wrong in either direction, which is why it is advice and is never read by the hand-over gate. Measured: eight of its first eleven notes misread the sheet, so it is asked by the operator after hand-over and refused during a rebuild. |
| References | references/method.md; evals/evals.json; BENCHMARK.md |
| Skill output | survey.json, temple.png, hall.blend, hall.json, likeness.json, likeness.png, faults.json, review.json |
| Skill version | 0.1 |
| Ethical considerations | Renders and numbers about a building model only; nothing here should be read as advice about a real building. |
