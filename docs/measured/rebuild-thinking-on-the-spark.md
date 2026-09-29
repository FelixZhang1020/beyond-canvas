# The temple rebuilt with the thinking on the Spark

Operator's go (move 5 of the score plan). Until this run every rebuild's builder thought on
StepFun's servers. This run put it on the hosted DGX Spark: NVIDIA's Nemotron 3 Nano 30B A3B (NVFP4) in
NVIDIA's vLLM container (`nvcr.io/nvidia/vllm:26.08-py3`), a fixed 0.28 share of memory, its reading
window widened from 32,768 to 131,072 tokens for the run, reached from the Mac through an SSH tunnel.
It reads text only, so the driver told it when a picture was made instead of sending it
(`--no-pictures`). Blender 5.2.1 built the hall on the Mac, as every rebuild does (no trusted Blender
for the Spark's Arm chip); the eyes (shot-judge) stayed Step 3.7 Flash. Same gate and limits as run 4:
80 actions, 6 repair laps, 3 refused hand-overs.

```bash
uv run python -m evalkit.fromzero --profile spark --slot llm.engineer --no-pictures \
    --temple output/foguang-east-hall/foguang-east-hall-v25.blend
```

Run folder `.studio/showpiece/rebuilds/20260922-101943-7b40e2/` (this Mac only), scorecard beside it.

## Result: not adopted, at the cap

| | Run 4: Step 3.7 Flash, StepFun | This run: Nemotron 3 Nano, the Spark |
|---|---|---|
| Ended | adopted on lap 6 of 6 | the 80-action cap, never handed over |
| Actions | 71 | 80 |
| Placing | 17 | 8 |
| Reads of a file | 5 | 40 |
| Tool calls that failed | 3 | 22 |
| Repair laps | 6 | 2 |
| Tokens | 1,005,308 | 1,399,641 |
| Wall time | 2,193 s (37 min) | 5,134 s (86 min) |
| In Blender's tools | 1,725 s | 97 s |
| Outline shared with the temple (front / side / above) | 0.95 / 0.90 / 0.98 | 0.76 / 0.78 / 0.30 |
| Size (m) against the temple's 41.39 × 25.05 × 14.65 | 41.53 × 25.17 × 14.65 | 47.06 × 30.74 × 12.64 |

The two runs are one run each, with different builders that also differ in whether they see pictures;
the table compares outcomes, not the models in general.

## What the hall was

It stands: none of 990 pieces fell or shifted when let go, nothing came down in the shake (drift
0.06 m), no column over strength, nothing hanging, all 36 columns in the temple's places with every tie
span tied and a bracket set on every column. It is not the temple: too wide and deep by 5.7 m, 2 m too
low, no rafters running front to back, and a roof that matches the temple's from above in 30 % of its
outline. Six checks were still owed at the end, because the hall had changed after they last ran.

## Where the turns went

Half the actions (40 of 80) were reads of files the builder had already read, often twice in a row;
22 tool calls failed, among them a tool asked for under a name that does not exist
(`load-path/shake/shake`) and 15 calls to `frames`. Only 8 actions placed anything. Almost all the
time was the model's: 5,037 of 5,134 s, at about 44 tokens a second of generation while it worked
(the vLLM log's mean over 543 samples).

## What this shows and does not

The Agent's thinking can run on the Spark end to end: NVIDIA's model in NVIDIA's container drove the
harness's tools for 80 turns, and the harness's gate refused nothing because nothing was handed over.
It does not finish the hall. A text-only 30B model that cannot see its renders spent its turns
re-reading rather than building. Step 3.7 Flash on the Spark itself, the original plan, is untested:
it needs most of the box. While the run held its ~42 GB, a class clip (~85 GiB at its peak) could not
have run on the Spark.
