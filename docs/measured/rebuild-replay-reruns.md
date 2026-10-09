# The rebuild replay's tests, re-run on the Spark: nothing fell in any round

The replay page (`/showpiece/rebuild.html`) plays the adopted from-nothing rebuild (run 4,
`20260921-134852-5fb51a`) on a 3D hall, and shows each of its seven tested rounds
letting every piece go and shaking the ground. The run itself kept only its last gravity video and
three tracked points of its last shake, so every round's gravity and shake test was run again on the
DGX Spark, on that round's own model, and every piece's position was kept. This note says what that
re-run found and how far it can be trusted.

## What was run

- **The models.** The seventeen stage models rebuilt on the Spark from the run's logged placement calls
  (`studio/showpiece/rebuild_demo.py`) were joined into one GLB of 4,331 pieces:
  a piece that is the same in two stages is kept once, and a piece a repair moved is kept once per
  shape it had (`studio/showpiece/rebuild_bake.py`, union).
- **The tests.** For each round the agent tested (the models after steps 32, 54, 68, 82, 96, 110 and
  126), the load-path skill's own `settle` and `shake` were run again through `settle.py`'s own build
  and bake, with that round's `anatomy.json` and `bearing.json`, **for as long and at as many frames a
  second as the run's own call asked**: its logged command, kept in the replay record. The settle calls
  all asked for `--seconds 3 --fps 10`; the shake calls gave neither, so they ran at the skill's
  defaults (6 s at 24 frames a second, ground 0.20 g at 2.5 Hz, then a 0.07 g pull). Every tracked
  piece's position was sampled every second frame.

The first pass ran the settle tests at the skill's defaults (4 s at 24 frames a second)
while the page said "re-run with the original settings". Writing this note found it; the seven settle
tests were run again at the run's own settings, and
`tests/showpiece/test_rebuild_record.py::test_every_spark_re_run_lasted_as_long_as_the_runs_own_call_asked`
now holds every re-run to its round's command (it failed on the first pass's data: 96 frames at 24
against the asked 30 at 10). The results did not change.

## Result

Each row below is `rebuild-hall.json`'s `rounds` entry for that round, printed by the command under
the table; "original" is what the run's own log said at the time (the replay record's evidence).

| Round (model after step) | Settle: fell / shifted, most movement | Original settle | Shake: came down, drift | Original shake |
|---|---|---|---|---|
| 32 | 0 / 0, 5.8 mm | 0 / 0 | 0, 0.063 m | 0, 0.06 m |
| 54 | 0 / 0, 6.8 mm | 0 / 0 | 0, 0.064 m | 0, 0.06 m |
| 68 | 0 / 0, 5.7 mm | 0 / 0 | 0, 0.061 m | 0, 0.06 m |
| 82 | 0 / 0, 5.8 mm | 0 / 0 | 0, 0.062 m | 0, 0.06 m |
| 96 | 0 / 0, 5.7 mm | 0 / 0 | 0, 0.065 m | 0, 0.06 m |
| 110 | 0 / 0, 5.8 mm | 0 / 0 | 0, 0.062 m | 0, 0.06 m |
| 126 | 0 / 0, 5.8 mm | 0 / 0 | 0, 0.069 m | 0, 0.06 m |

```bash
python3 -c "import json; d=json.load(open('studio/showpiece/page/rebuild-hall.json'))
for k,r in d['rounds'].items(): s,h=r['settle'],r['shake']; print(k,s['fell'],s['shifted'],s['max_moved_mm'],h['shake']['came_down'],h['shake']['drift_m'])"
```

The re-runs agree with the run: in no round did anything fall, shift more than 10 cm, or come down,
and the shake's level drift is the log's 0.06 m to within a centimetre. The most any piece moved when
let go is about 6 mm, which the page magnifies 50 times to be seen; the shake's movement is magnified
20 times.

## The newer check on an earlier run

Run 2 (`20260919-162700-85568a`) was handed over before the check that finds timber through
the roof existed. The replay page names what is wrong with it from the **newer** `likeness.py`, run on
run 2's own final `hall.blend` against a fresh survey of the temple (`~/beyond-canvas-demo-work/old/make.sh`
on the Spark): NOT alike, 4 pieces through the roof, `Frame -12.49 | king post`, `Frame 12.49 | king post`,
`Purlin ring 1 | end x-`, `Purlin ring 1 | end x+`. The note written at the time of run 2 found the two
king posts by looking at the picture; the newer check also finds the two purlin ends. The page says the
check is the newer one, not the run's own.

## What this does not show

- **Positions only.** A piece's turn is not kept, so the page moves pieces without rotating them.
- **Not the run's own frames.** These are the same tests on the same models with the same settings,
  run again; the run's own gravity and shake footage beyond its last round was never kept.
- **The stage models are rebuilt, not the run's own files.** The run left only its final `hall.blend`;
  the earlier stages were rebuilt from its logged placement calls with the placing tool as it stands
  on the Spark, which may differ from the tool as it was when the run was made, in ways the logged arguments do not show.
