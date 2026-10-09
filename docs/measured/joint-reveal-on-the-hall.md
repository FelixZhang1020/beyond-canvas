# joint-reveal on the Foguang East Hall v25

The three tools of `skills/joint-reveal` on the hall's front-left corner column, on this Mac
(Blender 5.2.1, Apple M-series), with `shot-judge` judging through the `api` profile's
`vlm.studio` slot (Step 3.7 Flash, low reasoning effort).

## The joints

```bash
OUT=.studio/showpiece/joint-v25; B=/Applications/Blender.app/Contents/MacOS/Blender; M=output/foguang-east-hall/foguang-east-hall-v25.blend
$B -b $M --python-exit-code 1 --python skills/joint-reveal/scripts/joints.py -- "$OUT" \
   --tenon "Perimeter timber column.002" "Column -12.50 -8.83 | Ludou foot" \
   --crosslap "Column -12.50 -8.83 | Hua 1 - touxin" "Column -12.50 -8.83 | Nidao gong" \
   --dovetail "Perimeter tie beam" "Perimeter timber column.002" max \
   --dovetail "Perimeter tie beam.001" "Perimeter timber column.002" min
```

`JOINTS 4`, 3.9 s, a 47 MB derived model beside a `joints.json`. The source model is untouched
(its checksum is the one recorded in the physics check's scratch folder).

## The tenon close-up, four attempts

| Attempt | Camera and scene | Judge |
|---|---|---|
| 1 | above the lifted foot, foot alone lifted 45 cm | fail: nothing parsed, the model's hidden thinking ran past the 1,500-token budget (fixed: low effort, 4,000) |
| 2 | below the foot, foot alone lifted 30 cm | fail: "a floating dark sloped wooden plank above a small weathered wooden cube placed on a cut tree stump" |
| 3 | same, with the new underside light | fail: "a floating angled light wood plank suspended above a square wooden block" |
| 4 | the whole block lifted 30 cm (foot, seat, four ears), the two crossing arms hidden | **pass**: "a round timber column top with a small square wooden tenon centered on its flat surface, and a larger wooden bracket block with four projecting ears floating closely and centered directly above the tenon" |

The judge described each picture accurately; the first three were wrong pictures, not wrong
verdicts. A lone lifted foot reads as a plank; the block reads as a block only with its ears.

```bash
P="Column -12.50 -8.83"
$B -b "$OUT/foguang-east-hall-v25-joints.blend" --python-exit-code 1 --python skills/joint-reveal/scripts/closeup.py -- "$OUT/tenon-4.png" \
   --at=-11.4,-10.1,6.95 --look=-12.5,-8.83,6.72 --lens 55 --hide-beyond 3 --hide-above 7.0 \
   --hide "$P | Hua 1 - touxin | JOINT" --hide "$P | Nidao gong | JOINT" \
   --move "$P | Ludou foot | JOINT=0,0,0.3" --move "$P | Ludou seat=0,0,0.3" --move "$P | Ludou ear=0,0,0.3" \
   --move "$P | Ludou ear.001=0,0,0.3" --move "$P | Ludou ear.002=0,0,0.3" --move "$P | Ludou ear.003=0,0,0.3"
```

Each close-up renders in about three seconds with 16 to 23 pieces kept.

## The pull-apart, four renders

```bash
$B -b "$OUT/foguang-east-hall-v25-joints.blend" --python-exit-code 1 --python skills/joint-reveal/scripts/explode.py -- "$OUT" \
   --anatomy "$OUT/anatomy.json" --assembly "Column -12.50 -8.83" --joints "$OUT/joints.json" --seconds 6 --fps 30
```

78 pieces, 24 tiers, 180 frames, `explode.mp4` six seconds at 1280 × 720.

| Render | Framing | Wall time | What it showed |
|---|---|---|---|
| 1 | camera from the assembly's bounding box | 240 s | the roof still over the set; pieces rose through the tiles; 18 m away because the set's inward beams inflate its box |
| 2 | focus on the median of piece centres, roof peeled above the set | 133 s | rafters below the set's top still occluded it from above |
| 3 | rafter and covering roles hidden, camera lower | 108 s | pieces rose 8 m (35 cm per tier over 24 tiers), camera inside the hall above the ceiling |
| 4 | 18 cm per tier, camera at eave level outside | 128 s | **judge pass**: "an exploded, separated view of individual wooden timber bracket components, with each piece spaced apart" |

The lessons are in the tool now: hide-by-distance uses each piece's world bounding box (the
hall's object origins are not at the geometry), the frame is the median of the group's piece
centres and the 80th-percentile distance from it, the roof roles are hidden, and the camera
stands at eave height outside.
