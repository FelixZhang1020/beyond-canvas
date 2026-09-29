# Skill card: shot-judge

| Field | Value |
|---|---|
| Description | Judges whether a rendered picture shows what an agent meant it to show: visible, centred, readable, a pass or fail, and one instruction for the next attempt. Readiness: demo. |
| Owner | beyond-canvas team |
| License | Apache-2.0 |
| Use case | Every showpiece render: the agent cannot see, so each shot it keeps or reasons from is judged first. |
| Deployment geography | Global; English verdicts, the `seen` sentence in the model's language |
| Requirements | A vision slot: Step 3.7 Flash through the StepFun API on the Mac, the same model on llama-server on the Spark; Python 3.13; uv |
| Known risks | The judge can approve a wrong shot or reject a right one, and it reads the intention literally. Mitigated by showing every verdict beside its picture on the dashboard, and by the pass rule requiring all three flags. An unreadable answer is a fail, never a pass. |
| References | assets/prompts/judge.txt; evals/evals.json; BENCHMARK.md |
| Skill output | One JSON verdict per picture |
| Skill version | 0.1 |
| Ethical considerations | The pictures are renders of building models, never photographs of people; the prompt tells the model to judge only what is in the frame. |
