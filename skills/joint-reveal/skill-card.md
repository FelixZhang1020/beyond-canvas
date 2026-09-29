# Skill card: joint-reveal

| Field | Value |
|---|---|
| Description | Takes a group of a building model's pieces apart in stacking order and shows three true joints cut into a derived copy: a column-top tenon, a cross-lap of crossing arms, a tie-beam dovetail. Readiness: demo. |
| Owner | beyond-canvas team |
| License | Apache-2.0 |
| Use case | The hackathon showpiece "how the pieces join", and any request about a bracket set, a joint, or taking part of a building apart. |
| Deployment geography | Global; piece names as in the model, verdicts in English |
| Requirements | Blender 5.2 headless with EEVEE; ffmpeg; model-anatomy for the pieces and shot-judge for the shots |
| Known risks | A boolean cut can fail on a non-manifold piece; the tool then raises and names the piece, and nothing is saved. The pull-apart rises pieces by bottom height, which is not the historical assembly order of a bracket set; references/joints.md says what the sources give. The joints illustrate the joint types, not measured ones. |
| References | references/joints.md; evals/evals.json; BENCHMARK.md |
| Skill output | A derived .blend, joints.json, stills, frames, explode.mp4, explode.json |
| Skill version | 0.1 |
| Ethical considerations | Renders of a building model only; the source model is never modified or redistributed by the tool. |
