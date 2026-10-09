# The engineer's review, first run: two real finds, four misreadings, and neither of the expected

Run on the operator's go. NVIDIA Nemotron 3 Nano 30B A3B (NVFP4) on the hosted DGX Spark, in NVIDIA's
vLLM container (`nvcr.io/nvidia/vllm:26.08-py3`, `~/nemotron/serve-engineer.sh`, loopback 7330, a
0.28 share of memory), reached from this Mac by an SSH tunnel, asked by `hall-carpenter review` with
its own prompt and sheet. Numbers only; no picture, nothing about a child. Stopped afterwards; the
node's memory came back.

```bash
.venv/bin/python skills/hall-carpenter/scripts/review.py FOLDER      # --profile spark --slot llm.engineer
```

| | A: run 4's hall as built | B: the same hall, the temple's true rafters |
|---|---|---|
| What differs | rafters told 0.36 m thick every 0.20 m (the temple: 0.13 every 0.40); heaviest column 8.08 MPa of 10 | rafters as the temple's; heaviest column 6.74 MPa |
| Sheet | 4,994 characters | 4,991 characters |
| Answer | 81 s, 6,381 tokens, read cleanly | 81 s, 6,295 tokens, read cleanly |
| Notes | 2 | 5 |

## Every note, checked against the numbers

| Note | In | Checked | Verdict |
|---|---|---|---|
| "Columns 4.87 m tall, the seat is at 6.49 m: they do not reach it" | A, B | The hall's columns stand on 1.62 and are 4.87 long: their tops are at 6.49, the temple's. It compared a length with a height above ground | **Wrong** |
| "Rings 3 to 6 are set inward (−0.41 … −6.46); make them positive like the temple" | A, B | Those are the temple's own figures: the inner rings stand inside the outer columns, as any roof rising to a ridge does | **Wrong** |
| "Lightest column 0.30 m, thinner than the temple's 0.57" | B | The four "lightest columns" are the roof frame's **king posts**, which the strength check counts as columns | Misleading, but points at the next row |
| "Load figures count 40 columns, 36 were built" | B | True. The strength check judges the four king posts as columns. Harmless here (they carry 3 to 9 kN), but the sheet then shows a 0.30 m "column", and a thin king post carrying more could fail a hall for the wrong reason | **Real** |
| "The hall is 41.45 × 25.86 against the temple's 41.39 × 25.05" | B | True, and caused the night before: the fix that stopped purlin tips showing through the roof also lapped the eave corners, 0.4 m each side. Likeness still passed (side shadow 0.915 against 0.90), so no check had caught it | **Real** |

**Not raised in either review:** the rafters, nearly three times too thick and twice too close in A, both
figures on the sheet side by side; and the heaviest column at 8.08 MPa in A. Those were the two things
written down beforehand as what a useful reviewer would say.

## What was done about it

The deeper footprint was fixed the same morning, tests first: the end slopes' covering now laps over
the hip only above the eave, never at the hall's own corner (`hip_lap` in
`skills/hall-carpenter/scripts/roof_skin.py`; the thin-rafter test in `tests/showpiece/test_carpenter.py`
now holds that the end sheets reach no further than the long slopes' eaves, and was red before the
change). Hall B again: 25.10 m deep against 25.05, nothing through the roof, every check passes.

Not done, each a decision for the operator:

- The strength check counting king posts as columns.
- The sheet invites both misreadings. It gives the temple's columns as foot and top and the hall's as
  foot and height, and it shows the temple's ring figures where a reader takes them for the hall's.
  Giving the measured column tops for both and labelling whose figures are whose is a change to what
  the reviewer is told.
- The sheet gives no temple column loads, so the reviewer could never have said "your heaviest column
  carries twice the temple's".

Two reviews of one hall by one model at one temperature: observations, not a measure of the model.

## Second run, after the three changes (the same morning, operator's go)

What changed between the runs, tests first and each proven able to fail (nine ways):

- **Frame posts are no longer columns.** The strength check lists an upright standing on other timber
  apart, as a `post`, still judged the same way; an overloaded post still fails the hall, and the gate
  says "a frame post's size is fixed, so lighten what stands on it". An upright resting on nothing stays
  a column. The real temple now reads 36 columns and 2 posts (it read 38 columns); the rebuilt hall 36
  and 4 (it read 40).
- **The sheet says how to read itself** (heights above the ground, a column's length is top minus foot,
  whose figures are whose, why inner rings are negative) and gives both buildings' columns the same way.
- **The temple's loads sit beside the hall's**, weighed by the same three tools. The rebuild runner now
  weighs the temple once per temple file (the carrying check takes 81 s on the Foguang hall) and puts
  `temple-loads.json` into every run folder. The temple: heaviest column 518 kN at 4.03 MPa, the middle
  one 230 kN. Hall A: heaviest 1,190 kN. Hall B: 978 kN.

The same model, the same two halls, the same settings:

| | A: as built | B: true rafters |
|---|---|---|
| Sheet | 6,590 characters | 6,584 characters |
| Answer | 96 s, 7,834 tokens | 44 s, 5,686 tokens |
| Notes | 3 | 1 |

| Note | In | Checked | Verdict |
|---|---|---|---|
| "The frames' end lines are at ±12.49, inner columns; move them to ±16.97" | A | The frames stand only on the inner cross lines; ±16.97 carries no frame and the tool would refuse it. End lines are the frames under the sloping ends of the roof, which is exactly ±12.49 | **Wrong** |
| "Purlin overhang 0 where the temple's eave reaches 0.54 m past the columns; set 0.54" | A | 0.54 m is how far the rafters reach past the eave ring, and the hall was told 0.54 there, the temple's figure. The eave ring itself stands 3.18 m outside the outer columns | **Wrong** |
| "Infill top 9.33 is above the wall top 5.83" | A | The infill is the plaster band between the bracket sets, from the wall up to the lowest roof ring, as the temple has and as the skill describes it | **Wrong** |
| "Columns 4.87 m cannot reach the bracket seat at 6.49 m" | B | The same misreading as the first run, although the sheet now opened by saying a column's length is top minus foot and gave both buildings' columns side by side: foot 1.62, top 6.49, length 4.87, identical | **Wrong** |

**Not raised, again:** the rafters in A, and a heaviest column carrying 1,190 kN (A) or 978 kN (B) against
the temple's 518 kN, now on the same sheet, two lines apart.

**Across both runs:** eleven notes; two real finds, both in the first run and both since fixed; eight
misreadings; one misleading note pointing at a real find. The two faults written down beforehand were
never raised, not even with the temple's figure beside the hall's.

**Why it matters beyond the review itself.** The builder is told to act on a note that names a part and a
number it can change, and every wrong note here does. Acted on, they would cost repair laps (the end lines
would be refused) or break a hall that passes: columns 6.49 m long would push the brackets up off the
ties, and an infill top of 5.83 would take away the plaster band the temple has.

Four samples of one small model (3 billion of its 30 billion parameters active a step) at temperature
0.2 on one hall: observations, not a verdict on the model.

**Decided the same morning (operator):** the review is no longer offered to the builder. It is asked by the
operator after hand-over; during a rebuild the harness refuses it before anything runs, and no lap is lost.

