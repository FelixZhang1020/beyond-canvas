# BENCHMARK: painting-to-animation

**Why there is no "with skill / without skill" table here.** Wan 2.2 makes the clip. The skill
decides what should move, writes the instruction the video model is given, and screens the result
before a teacher sees it. A bare model asked to animate a drawing returns no clip at all, so that
row would be empty against everything.

What this skill is responsible for — the instruction and the check — **has** been measured against
alternatives, on the same drawings, with the same seed. Those comparisons are below, and they are
the closest thing to a with-and-without column that this skill can honestly produce.

## The clips themselves

41 clips overnight on the Spark, 734–776 s each, through the class's own code, each scored 1 to 5
against its drawing by Step 3.7 Flash with the scoring question held apart from the code under test
([evidence](../../docs/measured/overnight-2d-to-3d.md)).

| | Result |
|---|---|
| Clips shown to the teacher (English) | **31 of 35** |
| Likeness to the drawing, 1–5, by batch | **4.0 to 4.88** |
| One clip on the Spark | 81 frames (~5 s) in 1,082 s ([trial](../../docs/measured/clip-length-trial.md)); ceiling 1500 s. Earlier the class made 49 frames in ~691 s, 711 s through the class page |

**This is the strongest part of the studio.** The 3D toy of a colour painting scores around 3; these
score above 4.

One clip was shown that should not have been. Painting 96, a house by a canal with no animals, came
back with dark shapes entering from the bottom in frames 2 to 4, which the judge read as hands or
added animals and scored 2. The cause is named: the standing action asked for "one foreground
animal" because the child had said nothing, and that painting has no animal. The fix is to stop
asking for an animal that is not there, not to add another check.

## The instruction earns its place: 18 clips, three wordings

Same six drawings, same requests, same seed, three different instructions
([evidence](../../docs/measured/clip-hands-and-check.md)):

- **A** — the wording classes used earlier, which merely lists "human hands" among things
  not to add. **Produced two human hands holding paintbrushes** reaching into the corgi drawing, as
  if someone were still painting it.
- **B** — says the painting is finished, that nobody is painting it, that only the painted figures
  move and that nothing enters the frame. **No hands. Adopted**, and now `VIDEO_PROMPT` in
  `studio/making/animation.py`.
- **C** — never mentions hands, and bans them in the video model's negative prompt instead. Produced
  a white hand with fingers on one drawing and an extra figure on another.

That is the skill's instruction measured against two alternatives and winning on the evidence, which
is what a skill is for.

## The check earns its place, and its limits are published

`scripts/clip_check.py` shows the drawing and five decoded frames to the screening model and reads a
JSON answer of closed codes. Three versions were run against all 18 clips:

| Version | Bad clips held back | Good clips held back | No answer |
|---|---|---|---|
| 1 | 1 of 3 | 1 | 1 |
| 2 | 2 of 3 | **5** | 1 |
| **3, adopted** | corgi A, on both passes | **1 in 34** | none |

Version 3 ran twice and 17 of 18 answers were identical, at 3–25 s a call. The stricter version 2
caught more bad clips and held back five good ones, which in a classroom is the worse failure: a
child waits and is shown nothing.

**The check is not blind, it is inconsistent, and that is published rather than hidden.** Asked three
times each on clips the night had passed, it cried wolf twice in nine — on clips that were clean to
the eye and scored 5.0. A second look on every clip would therefore hold back good clips more often
than it would catch a bad one.

## What the eval cases assert, and what proves them

The four cases in `evals/evals.json` test `scripts/choreograph.py`, the plan: JSON only, at most
three layers, every box real and inside the picture, every move from the closed vocabulary
(`drift`, `sway`, `rise`, `grow`, `breathe`), layer names describing appearance rather than
identity. Held by **44 tests** (`tests/making/test_animation.py`, `tests/classroom/test_choreography.py`,
`tests/making/test_video_animation.py`), run on the Spark.

## What is not measured

No real child's drawing and no real class; the paintings are the studio's samples, AI-made or the owner's
own. The likeness scores are one night on one sample set. The plan's own quality — whether the
three regions it picks are the right three — has never been scored against a human choice.
