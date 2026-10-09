# Skill card: studio-safety

| Field | Value |
|---|---|
| Description | Screens an image before a children's art studio acts on it. Readiness: demo. |
| Owner | beyond-canvas team |
| License | Apache-2.0 |
| Use case | Every image entering the studio, ahead of every other skill |
| Deployment geography | Global; reasons returned in the caller's language |
| Requirements | A vision model on the vlm.director slot; Python 3.13; uv. Optional second reader: NVIDIA Nemotron 3.5 Content Safety (4B, OpenMDW 1.1 licence and the Gemma terms) on the safety.reader slot, about 11 GB of GPU memory, PyTorch and Transformers 4.57 |
| Known risks | The four verdicts come from a vision-language model with no calibrated score. The optional second reader, NVIDIA's safety model, has been measured only for not turning children away (seven generated drawings, none refused); whether it catches a truly harmful picture is unmeasured, because no such test set is held. When it cannot be reached it stops nothing and the record says so, which trades its protection for a class that still runs. A false block costs a child their turn, so a frightening drawing is deliberately softened rather than blocked. The filter refuses rather than allowing when it cannot read its own answer, which trades availability for safety on purpose. |
| References | SKILL.md; evals/evals.json; references/childrens-studio-policy.md |
| Skill output | One of allow, soften, block, empty or unsafe, a one-sentence reason, any writing found on the page, and, when the second reader looked, its categories as codes and never its words |
| Skill version | 0.1 |
| Ethical considerations | This decides whether a child's work is refused, so a false block is a real harm and not a neutral failure. Frightening subjects are explicitly not unsafe content. Text found on a drawing is treated as personal data, reported to the operator and never repeated back to the child. |
