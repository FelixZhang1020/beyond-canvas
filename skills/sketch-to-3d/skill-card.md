# Skill card: sketch-to-3d

| Field | Value |
|---|---|
| Description | Stands a child's line drawing up as a solid form the teacher can turn and relight: a head or plaster bust and fruit-only studies go through a local image-to-3D route (TRELLIS.2, or Pixal3D as the alternative); mixed geometric studies use bounded CPU fitting. Readiness: demo. |
| Owner | beyond-canvas team |
| License | Apache-2.0 |
| Use case | A children's art centre, sketch class: after the drawing has been talked about, the teacher presses 把形体立起来 and the class sees the form rotate, moves the light, and compares it with the drawing. |
| Deployment geography | Global; Chinese and English interface |
| Requirements | The sketch entrance; Python 3.13 with uv; WebGL in the browser; a mesh worker on the `mesh.portrait` slot (a private 4090, or the hosted DGX Spark) and optionally `mesh.alternative` |
| Known risks | The back of a form and any occluded part are estimates, never drawn; the viewer says so. A busy mesh worker made the classroom voice slow when the voice shared the 4090 under Local First (measured 118 s for one sentence during a reconstruction, 15 s idle); StepFun First, now the only deployment, buys the voice from StepFun, so this no longer applies. A reconstruction takes four to five minutes and can be stopped; a stopped job is recorded as stopped by the teacher. |
| References | SKILL.md; evals/evals.json; docs/specs/3d-model-selection.md; docs/measured/sketch-to-3d.md; docs/measured/portrait-relighting.md |
| Skill output | A GLB scene with a saved camera, opened in the classroom light study. The drawing passes studio-safety before any model runs; the generated mesh itself is not safety-screened, only checked that its geometry stays within bounds |
| Skill version | 0.3 |
| Ethical considerations | The form is shown beside the child's own drawing and never replaces it. Nothing about the child is stored with the mesh. A photograph of a real object or person is refused before any model runs. |
