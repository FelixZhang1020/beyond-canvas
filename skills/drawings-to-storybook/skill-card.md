# Skill card: drawings-to-storybook

| Field | Value |
|---|---|
| Description | Binds two to eight of a child's drawings into a page-turnable book of the child's own confirmed words and either the original pictures (a drawing or its clip on each page) or every page redrawn in one picture-book style the teacher chooses, after a scene description per drawing and a story outline in the teacher's order. Readiness: demo. |
| Owner | beyond-canvas team |
| License | Apache-2.0 |
| Use case | A children's art centre, end of a class: the teacher picks the drawings, orders them, generates and edits the outline, confirms it, and the book opens in the reader with a blank last page for the child's own ending. |
| Deployment geography | Global; Chinese and English interface |
| Requirements | Python 3.13 with uv; a vision model on `vlm.creation` and one on `vlm.director`; the classroom harness. For the picture-book look, FLUX.2 Klein 4B on `image.book`. |
| Known risks | A redraw can still lose or recolour something when the must-keep list itself is wrong; the comparison missed one of 19 known cases, and a page still off after one more try is only marked for the teacher. The independent reviewer refuses more outlines than it passes (once five in a row); the page returns the rejected draft for editing rather than retrying. A drawing with words written on it is treated as evidence, not instruction, but a model can still over-read an ambiguous mark. Narration, anthology handling and layered assets promised in the design record are not built. |
| References | SKILL.md; evals/evals.json; docs/specs/creation-flow.md; docs/measured/classroom-integration.md |
| Skill output | Pages of `{drawing_id, text[, video_url \| picture_url]}` in the supplied order, plus the language and the look; opened in the classroom reader |
| Skill version | 0.1 |
| Ethical considerations | A redrawn book changes the look of the child's picture, never what is in it, and only when the teacher chooses it; the originals are always the other choice. The words are the child's or the teacher's, never the model's, once the book binds. Nothing about the child is stored with the book beyond the course. Every original passes studio-safety before any model sees it and again at binding. |
