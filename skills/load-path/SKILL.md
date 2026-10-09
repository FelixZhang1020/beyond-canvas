---
name: load-path
description: Shows where a 3D building model's weight goes, as colour flowing down from the roof to the columns, runs the settle test in which every piece is let go under gravity and whatever moves is painted, runs the shake test in which the ground moves like an earthquake and the building is then pulled sideways, and films the collapse in which one mortise-and-tenon joint is taken out and everything that depends on it comes down link by link. Use it for any request about gravity, load, weight, snow, earthquake, what carries what, whether the building stands, what would fall, or what happens if a joint is taken out. On the Foguang hall the collapse takes out the tenon on the second column from the left along the front, the joint "Perimeter timber column.002" "Column -12.50 -8.83 | Ludou foot".
allowed-tools: load-path/collapse, load-path/flow, load-path/settle, load-path/shake, load-path/weights
license: Apache-2.0
compatibility: Blender 5.2 headless with its rigid body world and EEVEE; ffmpeg; Python 3.13. Needs model-anatomy's anatomy.json and bearing.json. On the Foguang hall the weights take seconds, the flow video about 25 minutes, the settle test about 15 minutes to bake plus 10 to render, and the shake test about 6 minutes on an Apple M-series Mac.
metadata:
  author: beyond-canvas
  version: "0.1"
---

# Load path

Five tools.

1. **weights**, the numbers: `python3 skills/load-path/scripts/weights.py <anatomy.json> <bearing.json> <out_dir>`
   writes `loads.json`: every piece's weight and what it carries, the ground total, and the
   columns' loads for a chart. Each column is judged the way a timber standard judges it: 1.3 times
   what it carries of the building's own weight plus 1.5 times its share of the snow on the roof,
   over its cross-section, reduced for how slender it is, against the 10 MPa timber is allowed in
   compression; the LOADS line names any column over it. An upright that stands on other timber, such
   as a king post on its beam, is a post of the frame: judged the same way, listed apart as `posts`,
   never counted as a column. Read the summary back to say the total, the snow, and the heaviest column.
2. **flow**, the colour coming down: `blender -b <model.blend> --python-exit-code 1 --python skills/load-path/scripts/flow.py -- <out_dir> --anatomy <anatomy.json> --loads <loads.json> [--seconds 6] [--hold 2]`
   writes `flow.mp4`, `flow-start.png`, `flow-half.png`, `flow-end.png`, `flow.json`. Deep blue is
   half a kilonewton, red a thousand. Judge `flow-end.png` with "the timber frame with its pieces
   coloured from blue at the top to red at the columns, roof removed".
3. **settle**, the gravity test: `blender -b <model.blend> --python-exit-code 1 --python skills/load-path/scripts/settle.py -- <out_dir> --anatomy <anatomy.json> [--bearing <bearing.json>] [--seconds 4] [--camera outside|frame] [--style studio|daylight]`
   writes `settle.json` (what fell, what shifted, by how much), `settle.mp4`, `settle-start.png`,
   `settle-end.png`. Red pieces fell, orange shifted. Report the counts and name the pieces.

4. **shake**, the earthquake test: `blender -b <model.blend> --python-exit-code 1 --python skills/load-path/scripts/shake.py -- <out_dir> --anatomy <anatomy.json> [--bearing <bearing.json>] [--video]`
   is the settle test with the ground moving: two seconds of shaking at the design earthquake of the
   Foguang hall's own site (0.20 g at 2.5 Hz, which is 8 mm each way), then a steady sideways pull as
   hard as that site's frequent earthquake (0.07 g). It writes `shake.json`, `shake-start.png` and
   `shake-end.png`, and `shake.mp4` only with `--video`. The SHAKE line says how many pieces came
   down and names them, how many had already moved when the shaking ended, and how far the rest
   drifted. A piece has come down when it dropped 10 cm, tipped 10 degrees or ended a metre away.

5. **collapse**, one joint taken out: `blender -b <model.blend> --python-exit-code 1 --python skills/load-path/scripts/collapse.py -- <out_dir> --anatomy <anatomy.json> --bearing <bearing.json> --joint COLUMN PIECE [--step 0.4] [--lang zh|en]`
   takes out the tenon joint between a column and the piece on it (on the Foguang hall the second
   column from the left along the front: `--joint "Perimeter timber column.002" "Column -12.50 -8.83 | Ludou foot"`). The piece gives
   way, then link by link everything resting on or joined into a piece that gave way; the columns,
   walls and ground stand. The film is Blender's plain solid look with the roof see-through; it opens
   close on the joint, slows the first few links and pulls back as the chain widens, and captions
   count the links. Each piece glows as it goes and falls onto what still stands. It writes
   `collapse.json` (every link, when it goes and its pieces), `collapse.mp4` and three stills. The
   COLLAPSE line says how many pieces in how many links. It is a picture of dependence, not a test:
   the rule is stricter than a real hall, where a piece with another sound support might hang on.

The weights, the settle test and the shake test answer different questions. The first says how the
load is shared as drawn and whether the columns are strong enough for it; the second whether the
drawn pieces hold each other up when let go; the third whether anything is only balanced: a
slender post stood on end stands for ever in still air and is pulled over by the shake.

It never saves the model. The settle and shake tests run on the copy in memory with the physics
check's settings; see `references/method.md` for what it does and does not claim.
