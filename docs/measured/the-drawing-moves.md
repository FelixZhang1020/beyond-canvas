# Making the drawing move, measured

Measured with Step3-VL-10B running locally, on the generated test
drawings. This is scenario two's first working form and the first evidence for
or against section 5b's central bet: that a model writing choreography beats a
model generating video.

## The bet, restated

No pixel is generated. The model names rectangles of the child's own photograph
and says what each does; the page cuts those rectangles out and moves them. Every
moving pixel came off the child's paper.

## What the model produces

Asked to animate a drawing of a sun, two stick figures and a purple creature,
with no words from the child:

| Layer name | Move | Box |
|---|---|---|
| the yellow spiky sun in the top left | drift | 0.05, 0.10, 0.20, 0.20 |
| the two black stick figures in the middle | sway | 0.20, 0.35, 0.25, 0.30 |
| the purple shape with oval body and round head | sway | 0.50, 0.25, 0.40, 0.60 |

Names describe appearance rather than claiming identity, which is what the
prompt asks for. On a scribble nobody could identify it holds up completely:
*"the large orange spiral with concentric circles"*, *"the three green dots on
the bottom left"*. This is the case that used to produce "the snail".

## The child's words drive the motion

Given *"the purple creature walked away and the sun got bigger"*, the same model
returns the sun on `grow` and the creature on `exit`, with no invented third
event. That is section 5b's requirement met: the child says a thing and the
world changes because they said it.

## How accurate the boxes are

Drawn back onto the picture, boxes are close but not exact:

- The creature box holds the whole creature, legs included. **Good.**
- The sun box holds the disc and clips the rays. **The rays stay behind when the
  disc moves**, which a child sees at once.
- The stick-figure box holds the heads and misses the bodies.

The first prompt asked for a *tight* box, which was the wrong instruction and
produced worse tears; it now asks for the whole shape including whatever sticks
out, and to err larger. That fixed the creature and did not fix the sun.

**This is the honest ceiling of a 10B model doing spatial grounding, and it is
what the feature costs.** A rectangle is a coarse instrument. Real segmentation
would fix it and needs a model this pack does not carry. Until then the artifact
is visible, and it is a torn shape rather than a redrawn one — the difference
that section 5b says matters.

## Speed

| Step | Seconds |
|---|---|
| safety, on the same drawing | 8 to 11 |
| choreography, local model | 37 to 95 |
| gate, with no words from the child | 0, no judge runs |
| gate, with words from the child | one judge call |

The gate is deterministic unless the child has spoken, which is what keeps this
close to instant. Section 5b's requirement is a couple of seconds and the local
model is not there yet; the comparison it wins is against diffusion, which is
one to fifteen minutes.

## Two defects this found

**A passing animation reported itself as failed.** A beat's success was read
from its text, and an animation has no text — only a plan. The ledger recorded
the pass and the child saw "Splat needs a little rest". Fixed: a beat succeeds
if it produced the thing it was for.

**The wrong rule was on the gate.** Rule 4 forbids asserting what an ambiguous
shape is, and it protects what a child *hears*. Layer names are never heard or
shown, and fed to the judge as bare noun phrases they read as assertions: a
correct plan was refused for calling a clearly drawn tree a tree. The gate now
uses rule 14 instead — the machine never tells the story — and only when the
child has said something for it to contradict.
