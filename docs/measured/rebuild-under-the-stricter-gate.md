# The fourth rebuild, under the stricter gate: adopted on its last repair lap

Operator's go. The three earlier rebuilds
(`docs/measured/from-nothing-rebuild.md`) ran under a gate of four checks. Since then the
gate gained three: the hall must be built like the temple's frame, no column may carry more than its
timber can bear with snow and slenderness counted, and nothing may come down when the ground shakes
and the hall is pulled sideways (`skills/hall-carpenter/references/method.md`). Nobody
had asked a model to get a hall through it. The purpose, as before, is to find what the harness does
badly.

```bash
uv run python -m evalkit.fromzero --profile stepfun --slot vlm.studio     # cap 80, 6 repair laps, 3 refusals
```

Step 3.7 Flash, reasoning effort low, on the StepFun subscription; the picture judge inside the run
went through profile `api`, its built-in default. Run folder
`.studio/showpiece/rebuilds/20260921-134852-5fb51a/`, which does not leave this machine. The
expectation written down before the run: about even odds of a hand-over, 15 to 25 minutes, 250 to
550 thousand tokens.

## Result

| | run 3 (old gate) | **run 4 (stricter gate)** |
|---|---|---|
| Result | adopted | **adopted, on lap 6 of 6** |
| Hanging / fell / shifted | 0 / 0 / 0 of 2,119 | 0 / 0 / 0 of 4,255 |
| Came down when shaken and pulled | not checked | **0**, most drift 0.06 m |
| Heaviest column, by the standard's sum | 3.59 MPa (measured afterwards) | **8.08 MPa** of 10 allowed; 1,190 kN |
| Frame like the temple's | measured afterwards: yes | 36 of 36 tie spans, 36 of 36 bracket sets, 6 rings, ridge, rafters |
| Shadows front / side / above | 0.944 / 0.908 / 0.986 | 0.949 / 0.902 / 0.983 |
| Actions (placing / reads / failed) | 45 (15 / 3 / 3) | 71 of 80 (17 / 5 / 3) |
| Repair laps | 5 of 6 | **6 of 6** |
| Looks by the eyes | 3 (fail, fail, pass) | 1 (pass) |
| Hand-overs refused | 0 | 0 |
| Tokens | 466,467 | **1,005,308** |
| Time in tools / in all | 347 s / 680 s | **1,724 s / 2,193 s** |

**Checked afterwards, by hand.** The six program checks were run again on a copy of `hall.blend` in a
fresh folder, outside the run: 4,327 pieces, 0 floating, every column within 10 MPa, fell 0 shifted 0,
0 came down, alike with the same three shadow figures. They agree with the run's own files to the
digit. The side-by-side picture was looked at by a person's eyes as well: no timber through the roof,
bracket sets under the eaves, a hipped roof with its two finials. **Nothing was handed over wrongly.**

Both estimates were wrong on the low side: 37 minutes and a million tokens.

## What the new checks did

They never failed. Weights, settle and shake passed on the first lap and on every lap after it, seven
times each. They were not idle, though: the heaviest column works at 8.08 MPa, four fifths of what
is allowed, where the real temple's works at 4.03. See "the survey's rafter spacing" below for why this
hall is that heavy.

## What the harness did badly

1. **Five of the six laps went on one fault, and the fault is the same one as in runs 2 and 3.** Two
   king posts stand out through the hipped ends of the roof unless `frames` is told its end lines.
   Likeness caught it, as it has since run 2. The repair is where the laps went: the model gave
   `end-lines` as a list and `end-beams` as a matching list (`"3,3"`), and `end-beams` takes one whole
   number. The tool answered twice with its usage text, which says nothing a model can act on. The
   model then mended one end per call; placing a part again replaces it, so each call put the other
   end's post back: −12.49, +12.49, −12.49, +12.49, one full lap each. On its last lap it gave both
   lines with one number, and the hall passed. One lap fewer and this run reads "not adopted".
2. **A lap now costs four minutes, and the failing check was the last and cheapest.** Bearing 45 s,
   settle 75 s, shake 100 s, then likeness, 6 s. The model followed the order the protocol lists,
   so every lap proved the physics again before reaching the six-second check that was failing:
   about 18 of the run's 37 minutes. The gate does not need that order: likeness only has to be newer
   than the last change. Nothing tells the model to run the check that failed first.
3. **The survey's rafter spacing is wrong.** It reports rafters 0.36 m thick at 0.05 m spacing, which
   cannot be. The model asked for 0.05, was refused by the placing tool's range (0.2 to 5 m), and
   took the smallest allowed: 2,684 rafters 0.36 m thick every 0.2 m. The hall weighs 12.6 MN against
   run 3's 10.2, and that is why a column reached 8 MPa. A refusal at the door kept a bad number from
   becoming a bad hall, and the strength check had room to spare; the measuring step is still wrong.
4. **The brake was not exercised again.** No hand-over was refused in any of the four live runs; the
   model has always run every check before asking. The refusal is proven by tests and a scripted
   rehearsal only.
5. **Tokens doubled.** 71 turns, the prompt growing from 3,400 to 23,400 tokens a turn; most of the
   extra turns are the four wasted laps of finding 1.

## What worked

- The stricter gate let a good hall through and the checks done afterwards agree with it.
- The lap limit is a real limit: this run ended on it, and would have been stopped by it one lap later.
- The engineer's review was asked once, said it was not available, and held nothing up, as designed
  (the model is not on the Spark yet).
- The eyes passed the hall on the first look. Their description was loose ("a cutaway perspective"
  of a hall that is not cut away), which fits what is already written about them: the weak check.

## What would fix the findings (not done; each is small)

| Finding | Fix |
|---|---|
| 1 | `frames` answers a bad `end-beams` in a sentence ("one whole number, used for every end line; give all end lines in one call, because placing again replaces"); the likeness fault line for timber through the roof names the same remedy |
| 2 | The builder's protocol says: after a repair, run the check that failed first, then the rest |
| 3 | Find why `survey.py` measures 0.05 m between rafters, tests first, on the real temple |
| 4 | None needed; say plainly on the board that the brake is proven by tests, not by a live run |

One model, one run of this configuration: an observation, not a rate.

## The three fixes, straight after the run (operator's go)

Tests first; each was broken once on purpose afterwards and a test went red (six ways).

| Finding | What was changed | Held by |
|---|---|---|
| 1 | `frames` takes `end-beams` as one whole number for every end line **or** one per end line ("3,3" now works); anything else is refused in a sentence that says to name every end line in one call, because placing again replaces. Any flag a placing tool cannot read is now answered `REFUSED …` in a sentence, never with usage text. The PLACED line says which lines were treated as ends. The likeness fault for timber through the roof names the same remedy | `tests/showpiece/test_carpenter.py` (three cases) |
| 2 | The builder is told to run the check that failed first after a repair, and which checks depend on order (inventory, bearing, then weights, settle, shake) and which do not (likeness, the eyes). The gate needed no change: a test now holds that likeness-first is accepted | `tests/showpiece/test_adoption.py` |
| 3 | The rafter arithmetic moved to `skills/hall-carpenter/scripts/measures.py`, free of Blender. Spacing is taken within a tier of one slope; size is the narrowest box several rafters share | `tests/showpiece/test_measures.py` |

**Why the survey said 5 cm.** Measured on the temple (`Blender -b foguang-east-hall-v25.blend`, a probe
script): 1,848 rafters, each 0.13 m across and about 2.4 m long, in six tiers up each slope, fanned
toward the corners. 340 run front to back. Read as one row, tiers a few centimetres out of step give
gaps of 0.05, 0.04, 0.09; within the eave tier the gaps are 0.40 and 0.41. A fanned rafter's box is up
to 0.76 m wide, and 0.36 happened to be the commonest box. The survey now reports **0.13 m thick,
0.40 m apart**, which is what the model's own dimensions say.

**What that is worth, without a model.** Run 4's hall with only its rafters placed again at the true
figures (and the roof set back on them): 2,991 pieces instead of 4,327, 9.3 MN instead of 12.6, nothing
hanging, and the heaviest column at **6.74 MPa instead of 8.08**. That column still carries 986 kN where
the temple's heaviest carries 518; the rebuilt hall gathers its roof onto fewer columns than the
temple does. Nothing in the gate asks about that, and it is a fair first question for the engineer's
review.

Not measured: whether a model now gets through in fewer laps. That needs another live run.

## What the true rafter size uncovered (before any further run)

Run 4's hall with its rafters placed again at the temple's true 0.13 m failed likeness: **twelve purlin
ends stood out through the roof**, and nothing a builder can say to the tools would have mended it.
The purlins across the ends of the roof lie on top of the long ones, a purlin's depth (0.30 m) higher,
so at each hip the end slope's covering is that much higher than the long slope's and the end purlins'
tips stand in the step. Rafters 0.36 m thick lifted the covering over them in all four live runs. A
fifth run, told the truth by the corrected survey, would have met a fault with no remedy.

- `roof` now laps the end slopes' covering over each hip far enough to lie over those tips, as a hip
  ridge does (`hip_lap` in `scripts/roof_skin.py`). Held by
  `test_rafters_as_thin_as_the_temples_do_not_leave_purlin_ends_showing_at_the_hips`, which was red
  before the change and still red with a fixed 0.25 m lap.
- The "through the roof" fault gives the end-lines remedy only when a frame's piece stands out, and
  says what can be changed when it is a purlin or a beam end (`tests/showpiece/test_measures.py`).

Run 4's hall with true rafters and the roof laid again, all six program checks by hand: 2,991 pieces,
0 hanging, 9.56 MN, every column within 10 MPa, fell 0 shifted 0, 0 came down (drift 0.06 m), alike
(0.954 / 0.915 / 0.991). The picture was looked at: the hips read as hip ridges.
