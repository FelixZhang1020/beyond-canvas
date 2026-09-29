# A colour painting's toy: three writings instead of two

**Question.** The first night of 2D to 3D ([overnight-2d-to-3d.md](overnight-2d-to-3d.md)) measured one change
above the luck band: a third writing before a toy is held back. Measured once, it proved nothing. Does it hold
up when measured several times against the unchanged code in the same night?

**Setup.** The same kind of runner on the node (under `~/spark-tests/`, not in this repository), 18:00 to 07:30
node time, pausing while a class worked. Every round put the 68 colour sample paintings through
`painting-to-figure` in its own copy of the code, six at a time, and scored each toy shown 1 to 5 for likeness
with Step 3.7 Flash, twice, with one fixed question kept outside the code under test (from 1444e0a). "Poor" is a
score of 2 or less. Three copies:

- **A**: main at ba14aa1, as the class ran it.
- **B**: A with three writings (`WRITINGS = 3` in `studio/making/figure.py`), nothing else.
- **C**: A without the change that makes a busy painting's toy its one main subject.

A, B and C took turns for twelve rounds; after that A ran alone until the stop, to show how far luck alone moves
the scores. The last round was cut off at the stop, 46 of 68 done, and is left out.

## Results

| Code | Rounds | Toys shown (of 67–68) | Poor among them | Shown and not poor | Likeness |
|---|---|---|---|---|---|
| A, today's | 13 | 47–55, mean 49.3 | 10–22, mean 15.5 | 33.8 | 2.64–3.06 |
| B, three writings | 4 | 52–59, mean 55.5 | 12–23, mean 16.8 | 38.8 | 2.80–2.91 |
| C, no one main subject | 4 | 33–39, mean 35.5 | 5–10, mean 8.5 | 27.0 | 2.88–3.06 |

- **Three writings show about six more toys a class**, about five of them good. Three of B's four rounds
  equal or beat the best of A's thirteen. The poor ones rise by about one, inside A's own swing of 10 to 22,
  and likeness stays in A's band. 20 of B's 222 shown toys came from the third writing.
- **The one-main-subject change earns its place.** Without it every round fell below every round of A.

## How long a toy takes

All toys, shown and held back, from each toy's `result.json`:

| Code | Toys | Median | 9 in 10 within | Slowest | Over 5 min | Over 6 min |
|---|---|---|---|---|---|---|
| A | 884 | 127 s | 240 s | 381 s | 2% | 0% |
| B | 272 | 119 s | 315 s | 477 s | 11% | 6% |

The third writing is spent on the toys that were failing, so the typical wait is unchanged and the long ones
grow: a toy held back after three writings took a median 292 s, against 194 s after two.

## What changed because of this run

- `WRITINGS = 3` in `studio/making/figure.py`, and the skill's bounds say three writings and six looks.
- The page's wait for a toy says about two to six minutes, not two to five.
