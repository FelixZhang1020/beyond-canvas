---
name: painting-to-figure
description: Makes a small 3D toy figure inspired by a child's colour painting, which the child can turn on the class page. The model lists simple parts instead of writing code; the studio settles them, draws a preview and holds the figure back unless its checks pass.
allowed-tools:
license: Apache-2.0
compatibility: Python 3.13, Pillow and the configured vlm.figure chat model (Step 3.7 Flash under StepFun First; vlm.creation where a profile has no vlm.figure). The page draws the figure with the vendored three.js; no graphics card is needed.
metadata:
  author: beyond-canvas
  version: "0.1"
---

# Painting to figure

## What it makes

On the colour entrance only, one toy figure per painting: the painting's main subject (at most three, and a
prop or two that matter; a busy scene of more than three characters makes its one main thing alone, the castle
without its crowd, operator) built from spheres, boxes, cylinders, cones, capsules and rings on a
round base. The page shows it beside the original painting and labels it **a 3D figure inspired by the
painting**. It is not the child's painting in 3D and never presented as a correction of it; the colour
entrance corrects nothing.

## How

1. The drawing passes `studio-safety` first, like every other skill.
2. The model receives [assets/prompts/figure.txt](assets/prompts/figure.txt) and the painting, and answers
   with a JSON list of parts. It does not write code, so no model-written code runs in the class page.
3. [studio/making/figure.py](../../studio/making/figure.py) keeps only numbers and colours, then **settles** the parts under
   gravity: things that touch stay together, small loose bits join the nearest group, and each group drops
   onto the base or onto what is under it. The model places heights loosely; settling fixed a corgi's
   floating head and a dog hovering above its base on the first samples.
4. [studio/making/figure_render.py](../../studio/making/figure_render.py) draws a front and a side preview on the CPU.
5. Two checks look before the child does: the `studio-safety` screen on the preview, and a look check
   ([assets/prompts/look.txt](assets/prompts/look.txt)) in which the model compares the preview with the
   painting. It passes only on a clear yes: the same subject, each main character's face with its eyes,
   nothing broken, nothing upsetting. Writing in the painting is never asked for, and small background
   figures need no eyes (operator), nor do the characters a busy scene's toy left out.
   The look is taken twice and both must pass, because the same toy got different answers on
   repeat; a first fail is not asked again (operator).
6. A failure is written again with the check's reason, three writings in all; a third failure is held back,
   and the class gets no figure that time (`figure_held_back`); the page says so in one plain line. The third
   writing showed about six more toys a class than two did, with about as many poor ones among them
   ([measured](../../docs/measured/figure-three-writings.md)).

## Output

`{figure: {version: 1, parts: [{shape, at, size, turn, colour}]}, language, deployment}`. No model prose reaches the
page, the ledger or the Portfolio: the model's words about the painting are dropped when the parts are read.

## Bounds

- 3 to 140 parts; every number finite and bounded; colours `#rrggbb` or a common colour word from a fixed
  list; six shapes only. Text after the answer is ignored; one size number means the same every way.
- At most three writings and six looks per figure, one active figure across tablets.
- A model outage — the writer, the look check or the safety screen down — is reported as one, not hidden as
  a held-back figure. The writer's empty or unreadable answer counts as a failed writing.
- The teacher's stop is read before every call, so a stopped figure spends nothing more.

## Measured

`docs/measured/painting-to-figure.md`: the four colour samples, before and after settling, with
the look check's verdicts.
