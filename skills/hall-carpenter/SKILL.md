---
name: hall-carpenter
description: Makes a timber hall from nothing in Blender, part by part, to match a building that already stands or to answer a written brief. It measures the standing building into a sheet of numbers, places the platform, columns, tie beams, walls, bracket sets, roof frame, purlins, rafters and roof covering by the numbers it is given, says how alike the two buildings are or how the hall answers its brief, and groups what the checks found wrong by the part that caused it. Use it when the request is to build, rebuild, reconstruct or repair a hall rather than to look at one.
allowed-tools: hall-carpenter/brackets, hall-carpenter/brief, hall-carpenter/columns, hall-carpenter/faults, hall-carpenter/frames, hall-carpenter/likeness, hall-carpenter/platform, hall-carpenter/purlins, hall-carpenter/rafters, hall-carpenter/review, hall-carpenter/roof, hall-carpenter/survey, hall-carpenter/ties, hall-carpenter/walls
license: Apache-2.0
compatibility: Blender 5.2 headless (bpy, numpy and the standard library only); Python 3.13; no network, except the optional `review` tool, which sends one sheet of numbers to the model on the `llm.engineer` slot. Needs model-anatomy and load-path to check what it makes, and shot-judge to look at it. Placing every part of a 3,300-piece hall takes seconds; the checks take two to three minutes.
metadata:
  author: beyond-canvas
  version: "0.1"
---

# Hall carpenter

You never write 3D code. Every tool places one part from the numbers you give it, and places it
where it is told, not where it would fit: a height given right seats the piece, a height given
wrong leaves it hanging or sunk, and the checks will find it. Placing a part again replaces it,
so a repair is the same tool with better numbers. All numbers are metres; z is height, x runs
along the front, y from front to back, the building is centred on x = 0, y = 0.

## Tools

Every tool's first argument is `out_dir` (give "."). A list of numbers is one string, "a,b,c".

| tool | arguments | what it makes |
|---|---|---|
| `survey` | — | measures the standing temple: `survey.json`, its picture `temple.png`, its three shadows |
| `platform` | `size` "x,y", `top`, `thickness` | the stone platform the columns stand on |
| `columns` | `xs`, `ys`, `rings`, `foot`, `height`, `diameter` | a column at every crossing of xs and ys, keeping only the outer `rings` rings of that grid |
| `ties` | `top`, `depth`, `width` | tie beams from column to column around each ring, tenoned into the columns |
| `walls` | `sides`, `foot`, `top`, `thickness`, `infill-top` | walls between the outer columns, and the plaster band between the bracket sets up to `infill-top` |
| `brackets` | `seat`, `tiers`, `rise`, `reach`, `block`, `arm` "width,depth", `inter` yes/no, `outrigger` ["reach,top", ...] | a bracket set on every column, and between columns on the outer ring |
| `frames` | `seat`, `beam` ["top,halfspan", ...], `king`, `width`, `depth`, `end-lines`, `end-beams`, (`lines`) | the roof frame on every cross line of inner columns; a line is an **x**. Leave `lines` out: it is every inner x already |
| `purlins` | `ring` ["half_x,half_y,underside", ...], `ridge` "half_x,underside", `size` | the purlin rings from the eave up, and the ridge purlin |
| `rafters` | `spacing`, `size`, `eave-out` | rafters on all four slopes and the hip rafters |
| `roof` | `thickness`, `ridge-cap` "width,height", `finial` | the covering, sheet to sheet, a cap along every hip and the ridge (`ridge-cap` sizes both), and the ridge's two end finials |
| `likeness` | `survey` "survey.json" | how alike the hall and the temple are, its frame included: `likeness.json`, `likeness.png` |
| `brief` | `brief` "brief.json", `photo` "photo.jpg" | in a design, how the hall answers its written brief, its frame included: `brief-check.json`, `brief.png` (the brief's photograph above, the hall below) |
| `faults` | — | what the checks found wrong, grouped by part: `faults.json` |
| `review` | (`profile`, `slot`) | an engineer's advice from the hall's numbers alone, by a model of another company: `review.json`. Advice, never a check; the operator's, after hand-over, and refused during a rebuild |

Each placing tool prints the heights it made (`column top`, `bracket top`, `lowest beam top`, ...)
and keeps them in `hall.json`. Use those printed heights for the next part, not a guess.

## How the heights chain

Work upward; each part stands on the one before.

1. **platform**: `top` and `size` from the survey's platform.
2. **columns**: `xs`, `ys`, `rings`, `diameter` from the survey; `foot` is the platform top;
   `height` is the survey's column top minus the foot.
3. **ties**: `top`, `depth`, `width` from the survey's tie beams. They end inside the columns.
4. **walls**: `foot`, `top` and `thickness` from the survey's walls (the foot is below the platform top: the
   walls start in the paving); `infill-top` is the underside of the lowest roof ring.
5. **brackets**: `seat` is the column top. The set's top is `seat + block + tiers × rise`
   (block is 0.35 and an arm is 0.315 deep unless you say otherwise; `rise` must be more than the
   arm's depth). Each tier of an outer set steps `reach` further out under the eave, so choose
   `reach` so that `tiers × reach` is how far the eave ring stands outside the outer columns.
   A roof ring that stands *outside* the outer columns (the survey says how far, as
   `out_from_outer_columns`) is carried by an outrigger: a long lever arm lying on the bracket top,
   given as "reach,top" where reach is how far out the ring stands and top is that ring's
   underside. The lowest outrigger's underside (its top minus the arm depth) must equal the
   bracket top, so choose `tiers` and `rise` to make it so. A second outrigger lies on the first.
6. **frames**: `seat` is the bracket top. The tool lays the lowest beams on it itself, their top at
   `seat + depth`; every `beam` you give stands on posts above them. Give one for each roof ring
   that stands *inside* the outer columns, lowest first: its top is that ring's underside, more than
   a `depth` above the top of the beam below it (the first more than `seat + 2 × depth`), and its
   halfspan is the ring's half_y plus 0.3. Posts are cut to fit between the beams. `king` is
   the ridge's underside. A cross line that stands under the sloping end of the roof cannot carry
   the whole stack (it is an x further out than the ridge's half_x, where the roof is already
   coming down): name those lines in `end-lines` and say in `end-beams` how many beams they
   carry, or posts will stand out through the roof. Name **every** such line in one call, both
   ends of the hall: placing the frames again replaces them, so a second call for the other end
   undoes the first. `end-beams` is one whole number for all of them, or one per end line.
7. **purlins**: the survey's roof rings, eave first, and its ridge, unchanged. Rings are counted
   from the eave: ring 1 is the eave ring, in the survey, in piece names and in the fault report.
   The ridge's half_x is how far it runs each way from the middle, along the hall: it reaches over
   the outermost king posts, and its underside is their top.
8. **rafters**: `size` and `spacing` from the survey's rafters; `eave-out` is the survey's eave
   edge `out_from_eave_ring`. Then **roof**: it prints its top; choose `finial` so it comes to the
   survey's top.

## Checking, and repairing

After placing, run model-anatomy `inventory`, then `bearing`, then load-path `weights` with
`anatomy` and `bearing` (no column may carry more than its timber can bear), then load-path
`settle` with `anatomy` and `bearing` and `seconds` 3, then load-path `shake` with `anatomy` and `bearing`
(nothing may come down when the ground shakes and the hall is pulled sideways), then `likeness`, then judge `likeness.png` with shot-judge
(args `image` "likeness.png" and `meant`: "two pictures of the same timber hall, the temple
above and the rebuilt hall below: the same roof shape, the same columns, and no post or beam
standing out through the roof").
Every check's answer comes back with the fault report's line under it; `faults.json` has the
whole of it: the part, how many pieces, the gap to what is under them however far down, and the
numbers that part was told. Do not read bearing.json or settle.json for this; they are lists of
every piece. A piece hanging g
metres above what is under it means that part's height is g too high, or the part under it is g
too low: change one part, the one the fault names, then run the check that failed first and,
when it passes, every other check again. Settle and shake take minutes; likeness takes seconds.

## Designing from a brief

A design has no standing building: `survey` and `likeness` are refused, and every number the chain
above takes "from the survey" is yours to choose, from the brief, its photograph and what the tools
print. The heights still chain the same way, each part on the one before. In the checks, `brief`
takes likeness's place and the eyes judge `brief.png`; the rest are the same, in the same order.

## An engineer's review

**Not part of a rebuild: the operator asks for it after the hall is handed over.** During a rebuild
the harness refuses it and no lap is lost. In its first two rounds, eight of its eleven notes misread
the sheet, and each named a part and a number: a builder told to act on them would have lost laps or
broken a hall that passes (`docs/measured/engineers-review-first-run.md`).

It puts the temple as measured, the hall as
told and as measured, both buildings' column heights given the same way, the columns' loads beside
the temple's (weighed by the same tools, when the run folder holds `temple-loads.json`), the let-go
test and the shake on one sheet of numbers, which opens with how to read it, and
asks NVIDIA's Nemotron, a model from a different company than the builder's and shown no picture, what
does not make structural sense. Its REVIEW line names a part, a number, the concern and a change to
try. It is advice: the hand-over gate never reads it, so it can neither pass a hall nor fail one,
and when the engineer cannot be reached or its answer cannot be read the line says so and nothing
stops. Check a note against the numbers before changing anything because of it.

## What it never does

It never measures the hall to make a piece fit, never edits the temple, and never says the hall
stands: that is load-path's settle. A hall that stands and looks alike is still a plain hall;
it has no carved brackets, doors, tiles or curved eaves.
