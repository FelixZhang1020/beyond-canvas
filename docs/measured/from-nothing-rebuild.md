# The temple rebuilt from nothing, three times: what the harness let through and what it stopped

Step 3.7 Flash (`vlm.studio` in profile `api`, via StepFun, reasoning effort low) was
given an empty Blender file, the standing East Hall (`foguang-east-hall-v25.blend`) to measure, and
the new `hall-carpenter` skill. The harness, not the model, decided whether what came back was
adopted. The purpose was to find what the harness does badly; the hall is the means.

```bash
uv run python -m evalkit.fromzero --profile api --slot vlm.studio     # cap 80, 6 repair laps, 3 refusals
```

Each run writes `scorecard.json` into `.studio/showpiece/rebuilds/<run>/`, read from the run
folder's own files and never from what the model said. `.studio/` does not leave this machine.

## What "adopted" means

All of, each newer than the last change to the hall: nothing hangs in mid-air (`bearing`); nothing
fell or shifted when every piece was let go for three seconds (`settle`); each of the three shadows
shares 0.90 of the temple's outline, a column stands within 15 cm of each of the temple's 36 and
none extra (`likeness`); since run 3, no timber stands out through the roof; and a separate pair
of eyes passed the picture (`shot-judge`). The model never writes 3D code: it chooses which part
to place and with which numbers.

The temple's own numbers placed by hand (no model) give 0 hanging, fell 0 shifted 0 of 3,289,
shadows 0.957 / 0.934 / 0.991, in 185 joined bodies and 58 loose pieces.

## The three runs

| | run 1 `…160856` | run 2 `…162700` | run 3 `…163925` |
|---|---|---|---|
| Result | **not adopted** | adopted, **wrongly** | **adopted** |
| Hanging pieces | 6 | 0 | 0 |
| Gravity: fell / shifted | 26 / 0 of 2,378 | 0 / 0 of 2,265 | 0 / 0 of 2,119 |
| Bodies: joined / loose / largest | 144 / 82 / 39% | 153 / 58 / 34% | 97 / 36 / 55% |
| Shadows front / side / above | never reached | 0.953 / 0.913 / 0.958 | 0.944 / 0.908 / 0.986 |
| Columns in place | 36 of 36 | 36 of 36 | 36 of 36 |
| Timber through the roof | not checked | **2 king posts** (found afterwards) | 0 |
| Actions (placing / reads / failed) | 35 (14 / 9 / 1) | 27 (10 / 5 / 4) | 45 (15 / 3 / 3) |
| Repair laps | 2 | 0 real | 5 of 6 |
| Tokens | 510,181 | 224,466 | 466,467 |
| Time in tools / in all | 125 s / 785 s | 134 s / 364 s | 347 s / 680 s |

For scale, the standing temple (v25) settles as 339 joined bodies and 329 loose pieces, its largest
body (the roof) holding 53% of its 6,264 pieces.

**Run 1** ended when the model spent 12,000 tokens thinking and returned nothing. It never asked to
hand over, so the brake never had to act; no live run was refused by it. The refusal is proven by
`tests/showpiece/test_adoption.py` and by a scripted rehearsal, not by these three runs. Before that it
had given the frames' cross lines as ys instead of xs, so its frames stood over no column; it read
the fault report, lowered the wrong roof ring (the report counted rings from 0, the model from 1),
made things worse, read a stale `faults.json`, and read `settle.json` three times, whose digest
showed the first sixty pieces, none of which had moved. **Nothing was handed over.**

**Run 2** was adopted in six minutes, and should not have been: two king posts stood out through
the roof at x = ±12.49. The shadows barely changed and the eyes wrote "no extra protruding
elements". Found by looking at the picture, then by the check written because of it:
`NOT alike: 2 timber pieces stand out through the roof: Frame -12.49 | king post, Frame 12.49 | king post`.

**Run 3**, under the stricter gate, was told about the posts by `likeness`, repaired them with
`end-lines`, and then spent three of its five laps on the eyes, which failed the same hall twice
for opposite reasons ("remove the roof ornaments", then "include the same finials") and passed it
the third time unchanged.

## What was changed between runs, and why

Every change is to the harness or the skill; the model itself was never changed. Ten of the fifteen
have a test of their own (1, 2, 3, 4, 6, 8, 9, 10, 12, 13); 5, 7, 11, 14 and 15 do not yet. Change 14
does give the model more numbers: measurements of the standing temple, which is the survey's job.

Before any model ran (found by placing the temple's numbers by hand, and by a scripted rehearsal):

1. Every piece was drawn 2 cm into its neighbour, and the whole hall settled as **one body**: a
   gravity test nothing could fail. Now only joints a carpenter cuts are let in.
2. The stage's render defaults filled `width 960` into the beam tool: beams 960 m wide, and a
   bearing check that ran for ten minutes. Placing tools no longer get render defaults, and refuse
   a timber section outside 2 cm to 5 m.
3. A tool's verdict line (`SETTLE … fell 0 shifted 0`) was printed above thirty lines of Blender's
   progress and never reached the model. Verdict lines are now repeated last. This was true of the
   exhibit's runs too.

After run 1:

4. A frame line where no column stands is refused at the door, in a sentence that says what a line is.
5. Roof rings are counted from 1 everywhere.
6. The fault report looks to the ground instead of 0.3 m, and calls a check older than the hall old.
7. Every check's answer comes back with the fault report's line under it; the model no longer has to ask.
8. Inputs the run folder already holds (`anatomy.json`, `bearing.json`, `survey.json`) are filled in.
9. A file read more than eight events ago is shown as a stub, so the prompt stops growing.
10. The digest of a gravity result leads with what moved.
11. The measuring step gave the platform top as 1.31 m (the commonest stone, a lower terrace); it is 1.62 m.

After run 2:

12. `likeness` finds timber standing out through the roof, and the hall is then not alike.
13. The eyes get the two pictures one above the other (twice the size), and retry once when they
    return nothing.
14. The measuring step reports rafter size and spacing, wall thickness and the eave overhang,
    which the model had gone looking for in the wrong places.
15. Only a check that can find a fault opens a repair lap; an inventory between two parts did.

## What is still weak

- **The eyes.** Wrong in both directions in two runs: passed a hall with posts through its roof,
  failed a good hall twice with contradictory reasons, then passed it unchanged. Everything the
  gate can measure is measured; the eyes are the one check that shares a model with the builder.
- **Reading a fault and choosing the repair** is where the model struggles, as predicted: it
  finds the right part and changes the wrong number. Run 3 had one lap left.
- The hall is a plain one (boxes and round columns, no carving, doors, tiles, curved eaves), and
  likeness is three outlines and a column count. A concrete box with the temple's outline and 36
  columns inside would pass likeness and gravity; only bearing's piece count and the eyes stand
  in its way. *Closed later:* likeness now measures the hall's frame with the survey's own
  functions (tie beams, roof rings, ridge, rafters, a bracket set on every column), and the gate
  reads load-path's column stress; run 3's hall passes both
  (`docs/measured/rebuild-under-the-stricter-gate.md`).
- The measuring step knows the temple's pieces by their English names.
- One model, three runs, no repeat of any configuration: these are observations, not rates.
