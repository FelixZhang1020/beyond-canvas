# Skill card: art-feedback

| Field | Value |
|---|---|
| Description | Writes encouraging, specific feedback on a child's drawing, on the entrance the teacher chose: colour, where the child tells the story inside the picture and nothing is corrected, or sketch, where light, proportion and structure get a technical read. Readiness: demo. |
| Owner | spark-art-studio team |
| License | Apache-2.0 |
| Use case | A children's art centre, mid-class: the teacher photographs a drawing and picks the colour or the sketch entrance for the whole class. Age is not modelled. |
| Deployment geography | Global; Chinese and English output |
| Requirements | A vision model on the vlm.studio slot; Python 3.13; uv |
| Known risks | The model may assert what an ambiguous shape is, which can contradict the child's intent. Mitigated by rule 4 and its grader check. The model may read a name written on a drawing; mitigated by an explicit prompt instruction and a negative eval case. |
| References | references/rubric.md; evals/evals.json; BENCHMARK.md |
| Skill output | Plain text, two to four sentences plus one question, in the requested language |
| Skill version | 0.1 |
| Ethical considerations | Feedback reaches children. It must never rank a child against others, never correct their work on the colour entrance, give a correction on the sketch entrance only as something to try, and never repeat personal data found in a drawing. Not a substitute for a teacher and not a psychological assessment. |
