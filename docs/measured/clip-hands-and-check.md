# Hands in Wan clips, the clip wording, and the clip check

Measured on the hosted DGX Spark (Wan 2.2 I2V A14B, the class setting: 49 frames, 15 steps,
guidance 3.5, seed 42, 480p by area, 16 fps) and, for the check, from the Mac against StepFun
First's `safety.image` slot (Step 3.7 Flash, reasoning high, subscription). Inputs were six of
the art centre's colour drawings in `Image Sample/Color Artwork/` with a child's request each.

## Why

A clip of the corgi drawing made with the class wording then in use showed two human hands
holding paintbrushes reaching into the picture, as if someone were still painting it. The
operator asked for a stronger instruction and then for a check before the teacher sees a clip.

## The wording: 18 clips, three wordings, same drawings, requests and seed

- **A, the old one**: the wording classes used until this test, which lists "human hands" among
  things not to add.
- **B, stronger**: says the painting is finished and nobody is painting it, that only the painted
  figures move, and that nothing enters the frame: no hands, fingers, arms, brushes, pencils,
  crayons or people. Now `VIDEO_PROMPT` in `studio/animation.py`.
- **C, clean + ban list**: never mentions hands, plus Wan's negative prompt listing them.

| Drawing (request) | A | B | C |
|---|---|---|---|
| Corgi (wag tail, tilt head, smile) | **two human hands with brushes** | no hands; barely moves | no hands; barely moves |
| Dog (raise a paw to say hello) | a dog's paw | a dog's paw, late | **a white hand with fingers** |
| Lions (open mouth and yawn) | yawn | yawn | both lions yawn, gazelle moves |
| Flamingos (spread wings) | barely moves | barely moves | flies, repainted as smooth cartoon |
| Rabbit (dance in the burrow) | dances, body odd at the end | dances | **an extra figure appears** |
| Giraffe (lower head to eat leaves) | head lowers | head lowers, a leaf sprig appears | head lowers, leopard smears |

Human hands: A 1 of 6, B 0 of 6, C 1 of 6. B moved about as much as A and kept the drawing;
C moved most and was least faithful. The operator watched the side-by-side clips and chose B.
Each clip took 454–472 s with the model already loaded.

## The check: three versions, each on all 18 clips

The check shows one comparison sheet — the original drawing, then the five frames the safety
screen already decodes — to the screening model, and reads a JSON answer of closed codes
(`skills/painting-to-animation/scripts/clip_check.py`). Expected to hold back: corgi A (hands,
brushes); for versions 1 and 2 also dog C (finger hand) and rabbit C (extra figure).

| Version | Asked about | Bad clips held back | Good clips held back | No answer |
|---|---|---|---|---|
| 1 | hands, tools, people, new figures; answer JSON only | corgi A (1 of 3) | giraffe B, a leaf sprig as a "new figure" | rabbit C (the model found the figure in prose; the reader expected JSON alone) |
| 2 | as 1, plus "a paw with fingers is a hand", plus list-then-compare steps | corgi A, rabbit C (2 of 3) | dog A, dog B, flamingo B, rabbit B, giraffe B (5) | lion C |
| 3 | only a real hand or arm, a person, an art tool; paws are not hands | corgi A, both passes | rabbit A, first pass only (1 in 34) | none |

Version 3 ran twice: 17 of 18 answers were the same both times, 3–25 s a call, one 83 s. The
reader now takes the last answer object in the reply, since the model often reasons first.

## What this means

- The failure seen with the class wording — a person's hands and brushes coming in — is caught.
- A paw that grows fingers and a figure the child did not paint are **not** checked. Asking about
  them produced the false alarms (toes read as fingers, falling leaves as new figures) and still
  missed the finger hand. Both appeared only with wording C, which classes do not use.
- A held-back clip costs the teacher a re-make, about 12 minutes; the new try asks the video
  worker for a different start (`seed` 43, 44, …), because the same start paints the same clip.
- Six drawings is a small sample. The rates above are these clips, not a general accuracy.
