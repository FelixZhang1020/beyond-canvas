# Can a model pick the right Skill from the descriptions alone?

Operator's go. Step 3.7 Flash (`step-3.7-flash`, slot
`vlm.studio`, profile `stepfun`, on the StepFun subscription) was shown the twelve Skills' names and
descriptions and nothing else, then asked which Skill should take each eval case. Every eval case in
every Skill already names the Skill that should handle it, so the 51 cases are the test set as they
stand. One question per case, no tool runs, no pictures.

```bash
uv run python -m evalkit.dispatch --profile stepfun --slot vlm.studio
```

15 minutes, about 6 of them the seven-second pause the key's rate limit asks for
between questions. 101,729 tokens, no charge per call on the plan.

## Result: 43 of 51

| Skill the case was meant for | Picked right |
|---|---|
| `art-feedback` | 9 of 12 |
| `drawings-to-storybook` | 4 of 4 |
| `hall-carpenter` | 2 of 3 |
| `joint-reveal` | 3 of 3 |
| `load-path` | 3 of 3 |
| `model-anatomy` | 1 of 2 |
| `painting-to-animation` | 2 of 4 |
| `raise-the-hall` | 2 of 2 |
| `shot-judge` | 2 of 2 |
| `sketch-to-3d` | 2 of 2 |
| `structure-tour` | 3 of 3 |
| `studio-safety` | 10 of 11 |

## The eight misses, by kind

**Sent to `studio-safety` when the descriptions say otherwise (3, real misses).** Two ask for feedback
on `blank-page.png` (`negative-blank-page`, `negative-blank-page-sketch`). `studio-safety`'s own
description says a request for feedback on a blank image goes to `art-feedback`, which declines it
warmly, so the model did not follow the descriptions. The third asks for a 3D form of a colour painting,
which the case expects `art-feedback` to turn away (`negative-colour-painting-is-routed-away`); nothing
in the question points at safety. In the classroom none of the three would matter, because the route is
fixed and `studio-safety` runs first on every drawing.

**A label that contradicts the descriptions (1).** `animate-a-blank-page` expects
`painting-to-animation`, but `studio-safety`'s description says a request to make something out of a
blank image stops there, and the parallel case in `sketch-to-3d` (`negative-blank-page-is-declined`)
expects `studio-safety`. By the descriptions the model's pick was right. The label is left as it is
for this record: changing it after seeing the result would move the score. It should be settled
before the next run.

**Broken answers, not wrong choices (2).** `animate-a-scribble` came back as
`painting-to美元汇率-animation` — the right Skill with an unrelated phrase ("dollar exchange rate")
inside its name. `safety-block-a-photograph` came back with no readable pick at all. Both count as
misses by the runner's rule, which compares the name exactly.

**Two temple Skills taken for another (2).** "The checks say pieces of the rebuilt hall hang in mid-air.
Fix it." went to `load-path`, the Skill that runs the checks, instead of `hall-carpenter`, the one that
builds. "In what order was this little building put up, from the ground to the roof?" went to
`raise-the-hall`, whose description offers exactly that ("any request about how the building was
put up"), instead of `model-anatomy`, which writes the carrying order down. Both are real overlaps
in the descriptions.

## Against the first run

The same runner and model ran twice before, on an earlier day, with eleven Skills and 45 cases,
twelve minutes apart: 40 of 45 first (`.studio/dispatch-report-before.json`), then 43 of 45
(`.studio/dispatch-report.json`). Neither was written up, both reports stayed on the development
machine, and nothing records what changed between them. This run wrote its report elsewhere, so
both are intact; the figures here are read from them. On the 44 cases this run shares with the
second of those runs, 42 were right then and 37 now. Between the two, `hall-carpenter` joined the menu and the
`studio-safety` and `load-path` descriptions grew. Five shared cases flipped: the two blank pages, the
building order, and the two broken answers. One run each cannot say how much of that is the new
descriptions and how much is the model answering differently on another day; asking every case three
times would.

## What this does and does not show

It measures the kind of choice the temple builder makes: the driver shows it an index of names and
descriptions every turn (`studio/showpiece/driver.py`, `system_prompt`) and it picks the next Skill
from that, but among fewer Skills: six in the exhibit, four in a rebuild (`hall-carpenter`,
`model-anatomy`, `load-path`, `shot-judge`). So the misses involving `studio-safety` and
`art-feedback` cannot happen to it; the two temple overlaps can. It does not describe the classroom, which dispatches by explicit Python in a fixed order.
Twelve descriptions route most requests; `studio-safety` and the pairs `hall-carpenter`/`load-path`
and `model-anatomy`/`raise-the-hall` overlap. This run's picks stayed on the development machine; from
this commit on, each row of the report also keeps the last 300 characters the model said, or why it
said nothing, so a miss labelled "broken answer" can be checked.
