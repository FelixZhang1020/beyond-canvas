# A storybook's pages redrawn in a picture-book style

The operator asked for a second way to make a storybook: every page redrawn by FLUX.2 Klein 4B on the Spark in
one style, "like a real published book", beside the book of the child's originals (a drawing or its clip on each
page). This is what was tried before anything was built, and what decided the design in
`studio/book_pictures.py` and `skills/drawings-to-storybook/assets/picture-styles.json`.

## Setup

- The six drawings of the test class 故事书测试 圣诞城堡3, from `Image Sample/Story Book`: AI-made pictures of a
  Christmas castle, soldiers, grey mice, a princess and a painted Christmas tree. **Not a real child's drawing**:
  none was available to measure with.
- FLUX.2 Klein 4B (`~/models/flux2-klein-4b`) in `beyond-canvas/spark-diffusers:1`, loaded once per run the way
  the retired still pose loaded it (no offload, no memory-mapping), 4 steps, guidance 1.0, seed 42.
- One-off scripts in `~/storybook-style-samples` on the node, holding the shared GPU lock. The kept-loaded 3D model
  was set aside for room (30.6 GiB available before, 56.5 after); nothing else was paused.

## Time and memory

| | |
|---|---|
| Loading FLUX | 13.6–23.8 s |
| One picture, 1024 on the long side | 4.3–6.9 s |
| One picture, 1536 (the drawing's own size) | 8.3–11.7 s |
| Lowest memory available during a run | 32.8–36.4 GiB (the node's floor is 24) |
| Qwen3.6's must-keep list, one drawing | 2.7–3.6 s |
| Qwen3.6's comparison of a redraw with its original | 0.6–3.6 s |

## Six rounds

| Round | What changed | What came back |
|---|---|---|
| 1 | "Keep every character where the child put it, same colours", 1024, watercolour / pencil / gouache | The princess on the tower gone in all three; the princess in a window turned into a lit window; grey mice brown or in coloured clothes (drawings 2, 3, 5); grey snowballs yellow |
| 2 | "However small, including anyone in a window…; grey stays grey", at 1024 and 1536 | Grey kept. The tower princess kept at 1536 only. **New faces painted into empty castle windows** (drawings 4, 5) and a small figure into the stocking (6): the words "in a window" put them there |
| 3 | No window words; "colours as strong as the child painted them, the background too", 1536 | Every character kept in watercolour, but **blue skies turned grey** (2) and the orange background grey (6); pencil browned the mice again |
| 4 | Qwen3.6 lists what each drawing must keep (characters with colours, the sky); the list goes into the instruction; 1536 | Everything kept, but one: drawing 3's mice came out green because **the list itself said green uniforms**. The look barely changed from the original |
| 5 | Six styles with the list, 1536 | Clay and gouache clearly changed; watercolour, storybook painting, cut paper and ink stayed close to the original |
| 6 | The same six styles with the list, **1024** (drawings 1, 2 and 6) | **Every character kept in all six.** Watercolour, gouache, cut paper and clay clearly changed; storybook painting and ink only a little |

Kept for the classroom (operator: "keep them all and let teacher choose"): watercolour, gouache, cut
paper and clay at first, then all seven tried (coloured pencil, storybook painting and ink and wash
added, knowing the last three change the look less), at 1024, with the must-keep list. The teacher sees page 1
in all seven first; seven pictures fit one job of the picture service's eight.

## The comparison check

The instruction in `skills/drawings-to-storybook/assets/prompts/picture-compare.txt`, asked of Qwen3.6 with the
original, the redraw and the must-keep list, on redraws whose answer was known:

- 5 of 5 that lost the princess or recoloured the mice were flagged, 12 of 12 good ones passed: **18 of 19 right**.
- The miss was round 4's drawing 3, the green mice, where the list had said green: told the list may be wrong, it
  still trusted it. A page still flagged after one more draw is only marked for the teacher, not held back.

## The first book through the class page

Built and sent straight after these rounds, then made in the test class from the page: page 1 in four styles came back in
53 s (list 3 s, FLUX 40 s for four pictures with its load, checks 11 s), and the other four pages in clay about a
minute later (list 5 s, FLUX 40 s, checks 11 s, one page drawn again 27 s). Every character stayed. But:

- **The purple-dressed princess of page 1 came out red in all four styles**, and one dancing mouse on page 5 red.
  The lists and the comparison were then asked of the class's writer (`vlm.creation`, temperature 0.6); the lists
  of the rounds above were asked at 0.2.
- **The comparison read the style as change.** Asked again of the same eight pictures through the writer, it listed
  faces drawn in, scarves and paper texture as changes and called five of eight not kept; three answers ran past
  300 tokens and could not be read at all. In the class run it had left three of eight unchecked.

So both moved to the class's checking model (`vlm.director`, temperature 0.1), the comparison was told that
faces, clothing details, textures and material come with the style and only a character lost, swapped, added or
recoloured counts, answers are read from their first words, and the list leaves out how the drawing was made
(pencil, strokes, flat colour), which it had begun to describe. Measured on the checking model with the new
comparison: **19 of 19 known cases right**, the green mice included, and on the eight class pictures it flagged
the red princess and the red mouse, which are real, beside two doubtful ones (red coats called maroon, soldiers
called lost that are there).

## The second book, on the checking model

The same test class after the change, its earlier redraws removed so every page was drawn again:

- Page 1 in four styles: list 4 s, FLUX 37 s, checks 7 s. Three of four were flagged and drawn again (36 s, checks
  5 s); two then passed and clay stayed flagged, which the teacher sees on its tile. About 1½ minutes in all.
- The other four pages in watercolour: list 4 s, FLUX 40 s, checks 6 s, all four kept. About 50 s.
- **The princess is purple in all four styles and on every page, and every mouse grey.** Looked at page by page in
  the reader.

## Kept warm between the jobs of a book

A teacher's book in the test class, read from the node's records: page 1 in the three styles not yet drawn took
~45 s (FLUX 36 s for three pictures), the other four pages in her style ~81 s (FLUX 40 s for four, then 27 s to
draw one flagged page again). About 22 s of every FLUX job was loading it, ~4.5 s a picture the drawing, so
~45 s of the 81 were two loads. The operator chose to keep FLUX loaded after a book's job: the first job starts
it, later ones are handed to it, and it leaves three minutes after the last, ~22 GiB held meanwhile. Expected:
the rest of a five-page book in ~35 s. Measured on the node after it was sent, two jobs straight to the
picture service with one of the test class's drawings: one picture with FLUX loading 22.1 s, then four pictures
on the loaded model 19.4 s (four took 40 s when each job loaded it).

## Not measured yet

- A real child's drawing, and a sketch: sketches have no storybook.
- A whole book through the class page (the next step, in the browser).
- How often a second draw fixes what the first lost; these rounds used one seed.

## Side effect found

After the first run the kept-loaded 3D model did not load again: with the chat voice and the safety reader loaded
there were 57 GiB available and its keeper asks for 62. Sketch-to-3D still worked, in about 3½ minutes instead of
about 1. A clip that sets it aside does the same. A storybook exists only in a colour class, where that 3D model is
not used, so this was left as it is.
