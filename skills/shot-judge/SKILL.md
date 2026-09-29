---
name: shot-judge
description: Looks at one rendered picture of a 3D model and says whether it shows what it was meant to show, with a pass or fail and one instruction for the next attempt. Use it after every render an agent intends to keep or to reason from, and never trust a shot that has not been judged.
allowed-tools: shot-judge/judge
license: Apache-2.0
compatibility: Python 3.13 with uv; a vision slot in a studio profile (vlm.studio on the api profile is Step 3.7 Flash through the StepFun API; vlm.director on the Spark is the same model on llama-server). One call per picture, with a 1,500-token budget because the model's hidden thinking is billed as completion.
metadata:
  author: beyond-canvas
  version: "0.1"
---

# Shot judge

The agent's eyes, kept separate from its hands: a fixed prompt, one picture, one intention, one
small JSON verdict. The prompt is in `assets/prompts/judge.txt` and never changes per request.

## Tool

`uv run python skills/shot-judge/scripts/judge.py --image <shot.png> --meant "<what it was meant to show>" [--profile api] [--slot vlm.studio] [--out verdict.json]`

Prints and optionally writes:

```json
{"seen": "what the picture actually shows", "visible": true, "centred": true, "readable": true,
 "verdict": "pass", "change": "", "parsed": true, "tokens": 974, "latency_s": 4.8}
```

`verdict` is `pass` only when `visible`, `centred` and `readable` are all true. On `fail`, `change`
is one instruction: move closer, orbit left, raise the camera, hide the roof. An answer the
script could not read comes back as `fail` with `parsed: false`; try once more, then stop.

## How to write `--meant`

Name the subject as a viewer would see it, and the framing, in plain words: "the corner bracket
set, whole, filling the frame", "the whole hall from the front with the roof visible", "the
ridge beam on its two lintels". The judge takes the words literally: a post-and-beam frame
described as "a stack of boxes" fails, because that is not what the picture shows.

## What it never does

It does not render, move cameras or change the model. It judges the picture it is given and
nothing else, and it does not know what the model contains.
