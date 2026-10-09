# BENCHMARK: painting-to-figure

**Why there is no "with skill / without skill" table here.** The model does not make the toy. It
reads the painting and writes the parts; the figure is built from those parts and then checked
before a child sees it. A bare model asked for a 3D toy returns words, not a figure, so a second
row would measure the absence of a pipeline rather than the value of the skill. What this skill is
responsible for is choosing what to build and refusing to show what came out wrong, and both have
been measured on real sample paintings, overnight, on the box.

## What has been measured

The class's own code put 68 colour paintings through this skill repeatedly through one night —
**819 figure attempts, 447 toys scored** — each result scored 1 to 5 against its painting by Step
3.7 Flash, twice, with the scoring question held apart from the code under test
([evidence](../../docs/measured/overnight-2d-to-3d.md)).

The same commit, run six times:

| Run began | 20:53 | 03:36 | 04:19 | 05:03 | 05:46 | 06:29 |
|---|---|---|---|---|---|---|
| Shown to the teacher | 26 of 62 | 37 of 68 | 34 of 68 | 33 of 67 | 41 of 67 | 32 of 68 |
| Likeness, 1–5 | 3.00 | 2.77 | 2.85 | 3.00 | 3.09 | 3.03 |
| Poor ones shown anyway (≤ 2) | 5 | 12 | 11 | 7 | 7 | 7 |
| Median seconds | 159 | 158 | 155 | 145 | 153 | 137 |

**The honest reading of that table is the point of publishing it.** The same code, unchanged, shows
between 42 % and 61 % of paintings and scores between 2.77 and 3.09. Six candidate improvements
were each measured once against that band, and only one ("three writings", commit `8403b91`, 46 of
68) landed outside it. Anything measured a single time here is noise.

Of the 36 held back in the first run, the commonest reason was eyes missing on a main character,
then crowded scenes. A held-back figure is not hidden: the studio says so in words a child can hear
(`studio/conversation/strings.json`, `figure_held_back`) and the original drawing stays on screen.

An earlier run through the real classroom on four colour paintings, with the safety screen on both
the painting and the preview, is in
[painting-to-figure on the four colour samples](../../docs/measured/painting-to-figure.md).

## What the eval cases assert, and what proves them

The two cases in `evals/evals.json` state pipeline facts — safety before any model sees the
painting, a figure held back rather than shown when the check fails. Those are held by **44 tests**
(`tests/making/test_figure.py`, `tests/making/test_figure_classroom.py`), run on the Spark.

## What is not measured

No real child's painting and no real class. The sample paintings are the operator's own public
data. A likeness of 3 out of 5 is not good, and this file says so rather than reporting the best
of the six runs.
