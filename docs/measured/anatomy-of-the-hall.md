# model-anatomy on the Foguang East Hall v25

The two tools of `skills/model-anatomy`, run on `output/foguang-east-hall/foguang-east-hall-v25.blend`
(this Mac only, 6,264 timber and rafter pieces by the physics check's count). Blender 5.2.1, Apple M-series.

```bash
OUT=.studio/showpiece/anatomy-v25; mkdir -p "$OUT"
time /Applications/Blender.app/Contents/MacOS/Blender -b output/foguang-east-hall/foguang-east-hall-v25.blend --python-exit-code 1 --python skills/model-anatomy/scripts/inventory.py -- "$OUT"
time /Applications/Blender.app/Contents/MacOS/Blender -b output/foguang-east-hall/foguang-east-hall-v25.blend --python-exit-code 1 --python skills/model-anatomy/scripts/bearing.py -- "$OUT"
```

| Tool | Wall time | Printed |
|---|---:|---|
| inventory | 10 s | `ANATOMY 8170 pieces {'ground': 1048, 'timber': 4412, 'wall': 152, 'rafter': 1852, 'covering': 706} 70 assemblies` |
| bearing | 81 s | `BEARING 6264 pieces 22 floating 36 stages` |

Timber plus rafter is 6,264, the physics check's count exactly. The 22 floating pieces are the
22 suspended between-column arms (`Inter hua 1`) the physics check also found; nothing else floats.
3,089 pieces are drawn into another, the model's way of drawing joints.

## What it took to get the stages right

The construction stages went through seven runs in one afternoon, each fixed on the hall, not
on the test stack, which passed every time:

1. Kahn's order on every contact: pieces drawn into one another form loops, and a cut loop put
   tip blocks at stage 1.
2. Lowest bottom first: the sloping arms, which pass through the tie fang above them, still had
   no seat below and landed at stage 1.
3. Near misses count (the gaps-closed reading `statics.py` uses): an arm whose head sits 4 cm
   above its block is carried by it.
4. A seat sunk deeper than a seating is a joint, not a seat: then rafters sunk into their
   purlins and lintels drawn into their columns lost their carriers.
5. "Body lies below the contact" as the tie-breaker: fails for a rafter sunk to a purlin's centre.
6. "Contact nearer the top than the bottom": same failure at the margin.
7. **A drawn-through holder carries when its body extends below the piece's bottom** (a purlin
   under a rafter, a column under a lintel), never when it starts above it (a bearing over an
   arm's tail); stages assigned lowest bottom first so any loop breaks at the lower piece.

Result of run 7: stage 1 is the 36 columns and the 22 suspended arms and nothing else; stage 2
the tie beams, lintels and the between-column blocks' feet; stage 3 the big blocks' feet; the
first rafter-majority stage is 24 of 36; the covering is the last stage alone. Stage sizes:

```
58, 58, 58, 146, 270, 150, 236, 266, 162, 190, 248, 306, 152, 374, 208, 136, 484, 166, 116, 97,
239, 68, 34, 196, 303, 285, 290, 264, 268, 188, 135, 76, 20, 13, 4, 706
```

## Two things the inventory got wrong first

- The courtyard holds a 2,000 m ground plane, so the model box and the camera landmarks were
  computed 3 km out. The building box now comes from the non-ground pieces (x ±20.7, y ±12.5,
  z 1.37 to 16.03; height 14.66 m); the ground has its own `ground_box`.
- The hall's author left `assembly` (74 values, one per bracket set, 78 to 81 pieces each),
  `component` (84 part kinds) and `construction_phase` (1 to 4, on the 3,522 bracket pieces) on the
  objects. The inventory now records every such tag under `tags`, and the model's cameras.
