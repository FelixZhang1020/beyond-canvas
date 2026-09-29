---
name: joint-reveal
description: Takes a bracket set or any group of pieces of a 3D building model apart, piece by piece, and shows how the parts join, with three true mortise-and-tenon joints (column-top tenon, crossing arms cross-lap, tie-beam dovetail) cut into a derived copy for the close-ups. On the Foguang hall the joints are cut on the bracket set `Column -12.50 -8.83`, the second column from the left along the front, and one explode of that set films them. Use it for any request about how the building's pieces fit, join, stack or come apart.
allowed-tools: joint-reveal/closeup, joint-reveal/explode, joint-reveal/joints
license: Apache-2.0
compatibility: Blender 5.2 headless with EEVEE; ffmpeg for the video (frames are written without it); Python 3.13. Needs model-anatomy's anatomy.json for the group and shot-judge for every shot kept. A six-second pull-apart of a 78-piece bracket set is a few minutes on an Apple M-series Mac at 1280 x 720.
metadata:
  author: beyond-canvas
  version: "0.1"
---

# Joint reveal

For how the joints lock on the Foguang hall, one call is enough: explode with
`--assembly "Column -12.50 -8.83"` cuts that set's three joints (`assets/sets.json`) on its copy in
memory and films them close, as `--joints --closeups` would. Otherwise three tools, used in this order
for a joint request, or the last two alone for a plain take-apart.
Write negative coordinates as `--at=-1,2,3`; a bare `-1,2,3` reads as an option.

1. **joints**, real joints on a derived copy (the source model is never saved):
   `blender -b <model.blend> --python-exit-code 1 --python skills/joint-reveal/scripts/joints.py -- <out_dir> [--tenon COLUMN INTO] [--crosslap A B] [--dovetail BEAM INTO min|max]`
   writes `<out_dir>/<stem>-joints.blend` and `joints.json`. Pieces are named from `anatomy.json`;
   on the Foguang hall the joints are cut on one set, the second column from the left along the front
   (assembly `Column -12.50 -8.83`, not the corner set `Corner -17 -8.83`): `--tenon "Perimeter timber column.002" "Column -12.50 -8.83 | Ludou foot"`,
   `--crosslap "Column -12.50 -8.83 | Hua 1 - touxin" "Column -12.50 -8.83 | Nidao gong"`,
   `--dovetail "Perimeter tie beam" "Perimeter timber column.002" max`. Give `joints.json` to
   explode next: it runs on the derived model that file names, and measures the new `| JOINT`
   pieces itself, so the hall's own `anatomy.json` is all it needs.
2. **closeup**, one still for the judge:
   `... --python skills/joint-reveal/scripts/closeup.py -- <out.png> --at=x,y,z --look=x,y,z [--lens 50] [--hide-beyond 7] [--hide-above z] [--move "NAME=dx,dy,dz"] [--hide NAME] [--style studio|daylight]`
   `--hide-above` peels off everything whose bottom is above z; `--move` lifts a piece off its
   joint so the tenon or notch shows. Move `--at` by the judge's `change` (closer: shorten the
   distance to `--look`; orbit: rotate `--at` around `--look`; raise: add to z) and judge again.
   Keep a shot only after a pass.
3. **explode**, the animated pull-apart:
   `... --python skills/joint-reveal/scripts/explode.py -- <out_dir> --anatomy <anatomy.json> (--assembly TAG | --pieces A,B | --near x,y,z R) [--joints joints.json [--closeups]] [--seconds 6] [--fps 30] [--at=... --look=...] [--lang zh|en]`
   writes `explode-closed.png`, `explode-half.png`, `explode-open.png`, `explode.json` and
   `explode.mp4` in out_dir; the folder `explode/` holds only the video frames. Given `--joints`, it
   runs on the derived model. With `--closeups` the film is the joints instead, in Blender's plain
   look with a caption on each shot (`--lang zh|en`): first the bracket set in its hall with its
   joints marked, then each joint close, its two pieces in colour and the rest faint, lifted clear
   of the piece it fits, held open, closed again, `--seconds` each; it writes `joint-<kind>.png` for
   each, held open, in place of the three explode stills. Judge one of those with the intention
   "the joint's two pieces held apart, one orange and one blue, the tenon or notch showing between
   them": each is the joint opened on purpose, never the joint assembled, and the film already shows
   it closing, so a pass there is the answer: give the final answer then, without judging the other
   stills or taking a closeup, which would only write over a still the film made. Otherwise judge
   `explode-open.png`, the end of the pull, with the intention "the pieces separated in the air,
   each visible, the joints open". Never judge `explode-closed.png` for that: it is the model
   before anything moves, and on a roofed model it shows only the roof. The camera frames the
   chosen pieces by itself, from a raised three-quarter view; "from the top down" in a request
   means the order the pieces lift, not a camera straight above. Pass `--at`/`--look` only
   when the judge asks for a move.

## What a good result looks like

The open frame shows every piece with air around it, the tenon standing on the column, the
notches in the crossing arms, the dovetails out of their slots, and the group still recognisable
as one bracket set. The video eases: nothing jumps.

## What it never does

It does not change the building's design, invent pieces beyond the three joints, or save over the
source file. It does not decide whether a shot is good; shot-judge does.
