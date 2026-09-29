# A picture book's speed, and which model checks its pages

Two measurements made on the Spark with the class page after the storybook's samples stopped being drawn twice
(`studio/making/book_pictures.py`): how long a teacher now waits, and whether NVIDIA's own vision model could
check the redrawn pages instead of Qwen3.6. The drawings are AI-made samples from the sample picker, **not a real
child's drawing**.

## How long the teacher waits

One test course of three drawings, driven by hand on the class page, timed from the press to the pictures on
screen, and read against the node's records.

| Step | Before | Now |
|---|---|---|
| Page 1 in seven styles | 234 s on screen (107 s in the studio, the rest one 2.2 MB download) | **46 s** on screen (34 s drawing, 11 s checking) |
| The rest of the book in the chosen style, until it is bound | not timed | **91 s** |

FLUX was already loaded when page 1 was asked for: it loads (24 s) while the story is on screen. Page 1's seven
samples came back once, three of them marked; the one chosen, a marked one, was drawn again with the rest of
the book and passed.

Of the rest of the book's 91 s, **about 46 s were spent waiting for NVIDIA's safety reader to load again**:

| | Seconds |
|---|---|
| Pages 1 (again), 2 and 3 drawn | 17 |
| Waiting for the safety reader | ~22 |
| Checked: page 1 kept, pages 2 and 3 flagged | 7 |
| Pages 2 and 3 drawn again | 13 |
| Waiting for the safety reader | ~24 |
| Checked: both still flagged, marked | 6 |
| Bound | 2 |

With FLUX loaded the node had about 27 GiB available. The picture service counts 4 GiB for a job on the loaded
FLUX (`FLUX_JOB_GIB`, `deploy/spark/media_spark.py`) above a 24 GiB floor, so each job paused the reader for room
and the check waited for it. The node's monitor shows a job on the loaded FLUX taking about 2 GiB, on its first
job only (29.5 GiB available before page 1, 27.6 GiB during and after it).

## Qwen3.6 or Nemotron Nano 12B v2 VL for the check

The same instruction the class sends (`skills/drawings-to-storybook/assets/prompts/picture-compare.txt`), the
same must-keep list for both (written by Qwen with `picture-keep.txt`, as in class), the original then the
redraw, temperature 0.1, thinking off. Qwen3.6-35B-A3B is the class's own (`vlm.director`, vLLM on the node);
`nv-community/NVIDIA-Nemotron-Nano-12B-v2-VL-NVFP4-QAD` was served beside it for the trial with vLLM, a 0.15
memory share and two pictures a question, and stopped after.

Cases, labelled by eye before either model answered: 21 real redraws from two test books, 13 in which every
character and animal is there in its colours and 8 borderline (a small cart become a wheelbarrow and moved,
a sky or a house recoloured); and 18 made from six of the kept ones that break the rule for certain: every
colour swapped, the middle painted out (which hid most of the main character), a figure from another picture
pasted in.

| | Qwen3.6 | Nemotron 12B VL |
|---|---|---|
| Kept pages passed | 6 of 13 | **13 of 13** |
| Changed pages caught | **18 of 18** | 15 of 18 |
| Borderline pages flagged | 8 of 8 | 2 of 8 |
| Seconds a page, median | **0.96** | 1.54 |

- **Qwen flags what the instruction says does not count.** Its seven wrong flags name objects and shades: "added
  a brown bone", "changed the bowl color from gold to yellow", "changed main colour of dog from brown to
  orange", soldiers' coats "red to maroon". Each wrong flag is a page drawn again for nothing.
- **Nemotron missed a main character painted out**, three times of the four such corgi pages ("kept": true),
  which is the loss the check exists to catch.
- **Nemotron does not fit beside a book.** It held about 18 GiB; with FLUX loaded the node has about 27 GiB
  available above a 24 GiB floor, so it could not stay loaded while a book is drawn without everything else
  stepping aside.

Qwen stayed (operator), and its instruction was made to say what it had been ignoring: only characters and
animals count, not objects, buildings, plants, the ground, the sky or the background; features drawn more
fully come with the style; a lighter, darker, warmer or cooler shade is the same colour. Written in general
words, none of the objects from the cases above. Checked on the same cases and on held-out ones, 10 real
redraws from three other books (7 kept by eye, 3 borderline) and 18 made from six of them the same ways:

| | Instruction before | Instruction now |
|---|---|---|
| Kept pages passed, the cases above | 6 of 13 | **13 of 13** |
| Kept pages passed, held out | 4 of 7 | **6 of 7** |
| Changed pages caught, both | 36 of 36 | **36 of 36** |

The same answers on a second run. The one kept page still flagged is a clay bear whose hat brim came out black.
And a job on the loaded FLUX is now counted at 2 GiB (operator), so the reader stays loaded for the check.

## After both changes

The same test course, the story written again (FLUX loaded meanwhile, 29 s), then watercolour chosen for the
two pages not yet drawn in it: **the book was bound 17.7 s after the press** (two pages drawn in 11 s, checked
in 3 s, both kept, none drawn again). The safety reader was not stopped, and the node never had less than
26.8 GiB available. Two pages, not three, and none needing a second try: a book whose chosen sample was flagged
adds one page to the same job, about 5 s.

## Not measured

- A real child's drawing: none is kept to measure with.
- More than one answer per case: each was asked once, at temperature 0.1.
- Nemotron 3 Nano Omni (30B-A3B, NVFP4 21 GB), NVIDIA's newer vision model: no copy was found on ModelScope,
  the only model site the node reaches.
