# The first Chinese run, on the sample drawings

Until this run, every eval case in this repository was in
English, in a product whose first language is Chinese and whose judges are
Chinese, and every drawing was one of six invented by a script. This is the
first measurement in the language that ships, on the studio's sample drawings.

## What was run

Eighteen sample drawings, never committed: twelve paintings taken as a deterministic
spread across the sixty-nine colour samples, and the six plaster-cast studies among the
sketch samples. The samples are AI-made or the owner's own public pictures, not a child's
personal data. They are reached through symlinks under anonymised ids, because their
filenames are exported names that say nothing about the drawing.

The six studies are **AI-generated teaching material**, not student work — the
centre's own `教学说明.md` says so — which makes them a fair test of the sketch
entrance and no test at all of whether a real student's hand is read correctly.
Their lesson intent is the centre's own, so rule 11 was measured for the first
time rather than skipped.

```bash
uv run --env-file .env python -m evalkit.runner \
  --suite <suite>/colour.json --lang zh --no-write
```

`--suite` is new, and exists because the only drawings worth measuring are the
ones that may never be committed.

## The numbers

| Arm | Cases | Mean rule pass rate | Cases with nothing failed | Median |
|---|---|---|---|---|
| Local studio model, colour | 12 | 95.5% | 8/12 | 50 s |
| Hosted director, colour | 12 | 93.2% | 6/12 | 42 s |
| Hosted director, no skill, colour | 12 | 58.3% | 0/12 | 20 s |
| Hosted director, sketch | 6 | 90.0% | 1/6 | 46 s |

**The skill is worth 35 points in Chinese** — 93% against 58% for the same model
with the fourteen rules removed, and 0 of 12 bare replies passed everything. This
is the comparison NVIDIA asks a verified skill for, and it had only ever been run
in English.

**The local model beat the hosted one.** Step3-VL-10B on this Mac scored higher
than Step 3.7 Flash over the internet, on real paintings, in Chinese. That is one
Mac, one run, twelve drawings, and it is not a Spark — but it is evidence for
configuration B rather than against it, and it was worth having before the box
arrives.

The two colour arms are directly comparable: rules 9 and 12 are deterministic, so
the hosted run's saved replies were re-graded against the corrected word lists
below, and **not one verdict changed**. The failures it reports are real.

## What it found

Seven defects, none of which any of the 490 tests had caught.

**The benchmark command could not run at all.** Not "reported a stale number" —
it raised before the first drawing, every time, because the loader never
registered the module it was importing and the dataclass at the top of the skill
script cannot define itself without that. The test suite's own loader in
`tests/conftest.py` has always had the line, and carries a comment explaining
why. Two copies of one loader; the copy nothing ran is the one that rotted. This
is the real reason the published number went unrefreshed while the rubric changed
three times underneath it.

**The red-line counter reads a field that does not exist.** It runs only when a
reply has crossed a red line, which no invented fixture ever did, so the crash
was hiding behind the one condition that means the benchmark has something
serious to report — and it would have discarded the entire run at the last step,
after every case was paid for. Found by the type checker, never by a test.

**Rule 4 was refusing good replies, and rule 4 is a red line.** It fired on five
of twelve hosted replies and two of twelve local ones, for calling a sun a sun, a
house a house, and three black-and-white shapes birds. A red line refuses on its
own, so those children would have received nothing. The judge had been told what
a presumption is and never what one is not, while rule 3 requires naming two
things that are really in the drawing — the two rules were pulling against each
other. The prompt now names the recognisable case, says which mistake is worse,
and says why: a wrong entry costs a child their answer.

All ten refused replies pass now. Two invented ones — a giraffe and a helicopter
described into paintings that contain neither — are still caught, checked
deliberately rather than assumed.

**The Chinese half of two word lists had never been written properly.** Both had been
widened twice, from live English sweeps. Nobody widened the Chinese
side, because nobody had ever run Chinese:

- Rule 9 failed four of six sketch questions as closed. All four were open.
  *Which part of the light boundary was hardest to judge?* The list carried one
  form of "where" and one of the three words for "how".
- Rule 12 failed two more for not asking about process, while containing the word
  for **process** and the word for **method** respectively.
- Rule 12 on the colour entrance failed *"Where is this river flowing to?"* for
  not reaching inside the picture. The English list has carried "where is" and
  "who" from the start; the Chinese list had neither.

**A photograph of craft work is refused, and the refusal is wrong about the
child.** One of the twelve is not a drawing: it is a fabric fairy dress on a moss
mound, photographed in the studio. Both models correctly said so and asked for a
photo of a drawing instead. The child made the thing. This is a scope question
for the operator rather than a defect — see below.

**Chinese sentences run just over the limit.** Two local replies failed rule 10
at 47 and 49 characters against 45. Reading them, the rule is right and the model
is wordy; no change made.

## What this does not measure

- **Not the shipping voice.** On the cloud profile `vlm.studio` and
  `vlm.director` resolve to the same hosted model. The local arm is the closest
  thing on this machine to what a child will hear, and the machine is a Mac.
- **Not a child.** Eighteen drawings and no child in the room. Whether a child
  says more after the reply — the claim the product rests on — is still unmeasured
  and cannot be measured here.
- **Not the sketch entrance on real student work.** Those six are generated.

## The decision this leaves with the operator

**Does Beyond Canvas accept three-dimensional work?** One painting in twelve
turned out to be a photograph of a craft object, which suggests roughly one class
in twelve would hit it. As it stands, the child is told to go and photograph a
drawing instead. Three answers are available: leave it, soften the refusal so it names
what the machine can and cannot look at, or open a third entrance for craft. The
last is a build, not a wording change, and nothing else in the plan assumes it.
