# How long one child takes, measured through the page

Measured on the first six requests ever made through the studio page
against the real model. Cloud profile: both slots are `stepfun/step-3.7-flash`
on OpenRouter, provider pinned to StepFun, reasoning effort low. Read from
`.studio/ledger.jsonl`, which is where every number below came from.

## What was measured

| Stage | Gate | Seconds | What it was |
|---|---|---:|---|
| screen | pass | 10.9 | allow: a drawing of a house, tree and sun |
| opening | pass | 97.7 | 100%, clean |
| screen | pass | 11.0 | the same drawing, a second class |
| opening | pass | 228.2 | 91%, rule 4 |
| reply | fail | 94.2 | 80%, rules 3 and 4 |
| reply | fail | 57.4 | the retry, same two rules |

A stage's seconds are wall time for everything it did: the skill's own call plus
every judge the gate ran. An opening runs one writer call and two judge calls; a
reply ran three judges before the scoping fix and runs two after it.

## What it means

**Safety is fast and stable: about 11 seconds, twice, on the same image.** It is
one call with one short JSON answer and nothing else.

**The opening is slow and unstable: 98 seconds once, 228 the next.** Same
drawing, same prompt, same profile. The variance is the model's hidden thinking,
already recorded as a long-tailed distribution in the judge token budget note;
this is that distribution showing up as time rather than tokens.

**Two minutes is too long for a child standing next to a teacher.** The hero
scenario is a child waiting for someone to say what they see. This is the first
number that says the cloud profile is a development tool and not a demo: the
demo needs the box, where a small resident model answers a fraction of a
second's worth of tokens locally and no judge sits between the child and the
reply.

## What this does not measure

Nothing here is a Spark number. The whole point of Phase 0 is that the models
are hosted and the latency is somebody else's network. The comparable
measurement — a resident Step3-VL-10B on the box, no cloud hop, no per-request
judge — is a day-zero measurement and belongs in its own note.

## What could be done about it before the box arrives

The gate is two judge calls in series after the writer. They are independent of
each other, so they could run at the same time and cut roughly a third off the
opening. That is a real change to `run_rubric` and is not made here, because the
number that matters is the one from the box and it may make the question moot.
