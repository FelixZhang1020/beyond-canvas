# Skill card: model-anatomy

| Field | Value |
|---|---|
| Description | Reads any 3D building model and writes what is in it: pieces with roles, kinds and sizes, what rests on what, the carrying order, the construction stages and camera landmarks. Readiness: demo. |
| Owner | beyond-canvas team |
| License | Apache-2.0 |
| Use case | The first step of every 3D showpiece: an agent asked to take a building apart, tour it, show its loads or build it up needs to know the pieces and what carries what. |
| Deployment geography | Global; JSON output, piece names as in the model |
| Requirements | Blender 5.2 headless; Python 3.13; no network, no model weights |
| Known risks | Roles come from collection names; a model with unusual names gets everything as timber. Mitigated by the default being visible in `by_role` and by `references/roles.md`. Pieces drawn through one another are reported as overlaps, not hidden. |
| References | references/roles.md; evals/evals.json; BENCHMARK.md |
| Skill output | anatomy.json and bearing.json in the output folder |
| Skill version | 0.1 |
| Ethical considerations | None beyond the model's own provenance: the tool reads geometry only and keeps no copy of it. |
