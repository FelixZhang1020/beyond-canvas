# The shot judge's first three answers

Profile `api`, slot `vlm.studio`, which resolves to `stepfun step-3.7-flash` (checked with
`studio.slots.resolve`). Two rendered pictures of the eleven-piece test stack, Workbench engine,
960 × 540. The judge script is `skills/shot-judge/scripts/judge.py`.

## The token trap, met on the first call

With `max_tokens` 400 the model returned nothing: `EmptyCompletion: step-3.7-flash returned no
text after spending 400 completion tokens (finish_reason 'length')`. Its hidden thinking is
billed as completion, as `studio/providers/stepfun.py` documents. The budget is now 1,500.

## Answer 1: a misleading intention fails, honestly

```bash
.venv/bin/python skills/shot-judge/scripts/judge.py --image skills/shot-judge/evals/files/stack-front.jpg --meant "the whole stack of boxes on its slab, centred"
```

```json
{"seen": "The rendered image shows a simple grey table-like 3D structure, with no stack of boxes or building slab present.",
 "visible": false, "centred": false, "readable": false, "verdict": "fail",
 "change": "Render the correct subject: a stack of boxes placed on a slab, centred and fully visible in the frame.",
 "parsed": true, "tokens": 974, "latency_s": 4.77}
```

The picture is a post-and-beam frame; "a stack of boxes" is not what a viewer sees, and the
judge said so. The intention, not the picture, was wrong. The SKILL.md now says to describe
the subject as a viewer would see it.

## Answer 2: the same picture, described truthfully, passes

```bash
.venv/bin/python skills/shot-judge/scripts/judge.py --image skills/shot-judge/evals/files/stack-front.jpg --meant "the whole small post-and-beam structure standing on its slab, all of it in frame and centred"
```

```json
{"seen": "the simple grey post-and-beam structure standing on a flat slab base, fully visible against a plain black background",
 "visible": true, "centred": true, "readable": true, "verdict": "pass", "change": "",
 "parsed": true, "tokens": 747, "latency_s": 2.91}
```

## Answer 3: the cropped picture fails for the right reason

```bash
.venv/bin/python skills/shot-judge/scripts/judge.py --image skills/shot-judge/evals/files/stack-cropped.jpg --meant "the ridge beam, whole, on its two lintels"
```

```json
{"seen": "The picture shows a partial view of a roof structure with a horizontal ridge beam at the top and supporting lintels below, but the right side is cropped and the ridge beam is cut off.",
 "visible": true, "centred": false, "readable": false, "verdict": "fail",
 "change": "Move camera back and center the frame to show the complete ridge beam on its two lintels without cropping",
 "parsed": true, "tokens": 1259, "latency_s": 5.91}
```

Three calls, all parsed, 3 to 6 seconds each, about 750 to 1,260 tokens including the hidden
thinking. Cost is a fraction of a cent per call at StepFun's published rate; the provider does
not report it per call.
