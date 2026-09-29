# structure-tour, raise-the-hall and load-path on the Foguang East Hall v25

All on this Mac (Blender 5.2.1 EEVEE, Apple M-series), 1280 × 720, with three renders often
running at once, so the wall times are upper bounds. Inputs: `.studio/showpiece/anatomy-v25/`
(`anatomy.json`, `bearing.json` from `docs/measured/anatomy-of-the-hall.md`). Judge:
`shot-judge` through the `api` profile's `vlm.studio` (Step 3.7 Flash, low effort).

## The tour

```bash
$B -b $M --python-exit-code 1 --python skills/structure-tour/scripts/tour.py -- .studio/showpiece/tour-v25 --anatomy $A/anatomy.json --seconds-per 4 --fps 30
```

`TOUR 4 segments 480 frames`, 1,353 s, `tour.mp4` 16 s (9.4 MB).

| Still | Intention | Verdict |
|---|---|---|
| outside | the whole timber hall from outside, roof and columns visible | pass |
| door | the front of the hall seen close from the courtyard, red columns and open doors | pass |
| inside | the ceiling and the bracket sets seen from inside, looking up | **fail**: "brighten the lighting to make the ceiling structure and bracket details clearly visible" |
| overhead | the timber frame from directly above with the roof removed | pass |

The inside segment looked straight up at the lattice ceiling in the model's own dim light. The
tool now adds a soft interior light and tilts the end of the move so the brackets show; the
segment alone re-rendered in 551 s and passed: "a view looking up at a ceiling with a grid
pattern surrounded by wooden bracket sets".

## The construction sequence

```bash
.venv/bin/python skills/raise-the-hall/scripts/stages.py $A/bearing.json $A/anatomy.json .studio/showpiece/raise-v25
$B -b $M --python-exit-code 1 --python skills/raise-the-hall/scripts/raise.py -- .studio/showpiece/raise-v25 --scenes .studio/showpiece/raise-v25/scenes.json --anatomy $A/anatomy.json
```

`SCENES 24 from 36 stages`; the first render `RAISE 24 scenes 311 frames` in 826 s, `raise.mp4`
10 s (4.6 MB). Scene 12 (half built) shows the columns, the wall-top tie beams, the bracket
sets and the first purlins with no roof. The last scene's still failed the judge: "pan the
camera slightly right and/or move it backward to ensure the entire hall is fully within the
frame" (the orbit stood at 1.15 times the building's size). The tool now orbits at 1.45; the
re-render and its verdict are at the end.

## Where the weight goes

```bash
.venv/bin/python skills/load-path/scripts/weights.py $A/anatomy.json $A/bearing.json .studio/showpiece/load-v25
$B -b $M --python-exit-code 1 --python skills/load-path/scripts/flow.py -- .studio/showpiece/load-v25 --anatomy $A/anatomy.json --loads .studio/showpiece/load-v25/loads.json
```

Weights, against the physics check's v25 numbers:

| | This tool | Physics check |
|---|---:|---:|
| total | 9.23 MN | 9.83 MN |
| roof covering | 7.20 MN | 7.80 MN |
| timber | 1.73 MN | 2.03 MN |
| reaching the ground | 8.30 MN | 9.83 MN |
| on pieces with nothing under them | 0.86 MN | 0 (it dropped them onto what was within 30 cm) |
| heaviest column | 518 kN | 487 kN |

The covering is weighed at 7 kN per square metre of footprint (the first attempt weighed the
tile arrays by volume and got 241 MN: they are open meshes). The uncarried 0.86 MN sits on the
22 suspended between-column arms and the pieces they hold, a fault of the model the physics
check papered over and this tool reports.

`FLOW 6264 pieces 240 frames` in 750 s, `flow.mp4` 8 s (2.6 MB). The end still passed the judge:
"a rendered timber hall model with its structural pieces color-coded by the weight they carry,
featuring blue roof rafters, lower columns in orange and red tones".

## The settle test

```bash
$B -b $M --python-exit-code 1 --python skills/load-path/scripts/settle.py -- .studio/showpiece/load-v25 --anatomy $A/anatomy.json
```

The first run crashed on the four ridge pieces, which are bevelled curves, not meshes; the
geometry helper now takes a curve as its evaluated tube. The re-run: `SETTLE 6264 pieces fell 82
shifted 334`, 277 groups, 96 frames, 622 s, `settle.mp4` (0.3 MB). The physics check's own run
on the same model reported 0 fallen and 2 shifted.

Every fallen piece and every shifted piece over 15 cm is a block ear (`dou ear`) on a bracket
set, the small lips on the sides of a block. The physics check glued each bracket set into one
body from the `assembly` property, so the ears travelled with their block. This tool's groups
come from pieces drawn through each other, and an ear sits on its block without being drawn
into it, so it becomes a loose piece and the solver drops it. The rest of the hall (columns,
beams, purlins, rafters, roof) did not move.

That was the story until a probe of one fallen ear showed the real cause: the ear's centre of
mass was computed 23 cm away from the ear. Blender's vector maths is single precision, and the
tool summed the signed tetrahedra about the world origin, 15 m away, so the 6 cm ear lost its
volume to rounding and its centre drifted; the easing step (each piece shrunk 3 mm about its
centre so exact fits survive the solver) then slid the ear 2 cm off its seat, and it fell. The
physics check has the same sum but never noticed, because it also glued every block's ear to its
seat through its supports map. Two changes: the centre is now summed about the piece's own vertex
mean (a probe test puts a 6.5 cm box 15 m out and asks for its centre to a millimetre), and
settle takes `--bearing` so a block's foot, seat and ears are one body, as the physics check had.

```bash
$B -b $M --python-exit-code 1 --python skills/load-path/scripts/settle.py -- .studio/showpiece/settle2-v25 --anatomy $A/anatomy.json --bearing $A/bearing.json
```

`SETTLE 6264 pieces fell 0 shifted 0`, 339 groups, 566 s; the largest movement of any piece over
the four seconds is 5 cm, below the 10 cm that counts as shifted. The physics check reported 0
fallen and 2 shifted on this model.

## The construction still at the wider orbit

`RAISE 24 scenes 296 frames` in 799 s. `raise-24.png` passed: "a 3D rendered traditional timber
hall with a dark tiled hip roof, placed on a raised stone platform with surrounding paved ground,
captured from a raised corner perspective", no change asked.

## Open

- the 22 suspended arms remain a fault of the model, reported by anatomy, weights and settle alike;
- these times are the Mac's; the Spark's are to be measured on the machine.
