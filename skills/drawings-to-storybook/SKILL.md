---
name: drawings-to-storybook
description: Binds two to eight of a child's drawings into a page-turnable storybook whose words are confirmed by the teacher. Missing scene descriptions and the ordered story outline are generated directly from the originals and dialogue, with image safety and structural checks before the teacher edits and confirms them. Standalone scene descriptions for animation retain independent review. The book is made of the originals, each page the drawing or its clip, or, where the studio has FLUX on image.book, redrawn in one picture-book style the teacher picks after seeing page 1 in each; teacher-written passages are kept verbatim. Use when a class has several drawings and wants them to become one book, or when a scene description is needed before an animation.
allowed-tools:
license: Apache-2.0
compatibility: Python 3.13 with uv; a vision model on vlm.creation for drafts, and vlm.director for standalone animation-scene review, must-keep lists and redraw comparisons; optionally FLUX.2 Klein 4B on image.book for the picture-book look; the classroom harness in studio/classroom/classroom.py.
metadata:
  author: beyond-canvas
  version: "0.1"
---

# Drawings to storybook

A book made of the child's own drawings and the child's own words. The skill
never writes the child's ending: an extra blank page at the back is reserved for
the child. It draws only when the teacher asks for the picture-book look, and
then only over the child's picture, told what the picture must keep.

Two looks, the teacher's choice (operator):

- **原画, the originals.** Each page is the child's drawing, or the clip made
  from it where there is one; the teacher picks per page.
- **绘本风格, a picture book.** Every page redrawn by FLUX.2 Klein 4B in one
  style: watercolour, gouache, cut paper, clay, coloured pencil, storybook
  painting or ink and wash. She sees page 1 in all seven
  first, picks one, and the rest are drawn in it.

## What the classroom runs

Three requests, in this order, all through `Classroom.request`. The contract for
each, including which options it accepts, is
[docs/specs/creation-flow.md](../../docs/specs/creation-flow.md); this file says what the
skill does with them.

1. **`scene-description`** — one drawing. Writes an editable scene and one small
   action from the original image and every line of dialogue recorded for that
   drawing. Also what 让画动起来 asks for before an animation.
2. **`story-outline`** — two to eight drawings in the teacher's order. Supplies
   any scene description still missing, then writes one passage per drawing as
   a JSON array in exactly the supplied order.
3. **`book-pictures`** — only for the picture-book look. One drawing in up to
   seven styles (page 1, for the choice) or up to seven drawings in one style
   (the rest). The checking model, `vlm.director`, lists what each drawing must keep
   (`prompts/picture-keep.txt`); FLUX redraws them all in one job on the Spark
   (`assets/picture-styles.json`, `deploy/spark/flux_book_worker.py`); each
   redraw is screened by `studio-safety`, then `vlm.director` compares it with
   the original (`prompts/picture-compare.txt`). A page of the book that lost,
   changed or added something is drawn once more with another seed; one still
   off is marked for the teacher. Page 1's samples are drawn once and only
   marked; the sample she picks, if marked, gets its second try with the rest.
   A page is never drawn a third time. While she reads the story, FLUX is
   loaded and the lists are written, so page 1 does not wait for them.
4. **`drawings-to-storybook`** — the same drawings with the confirmed passages
   and the look. Screens each original, keeps the supplied text verbatim, and
   publishes the pages: the redrawn picture of each in the chosen style, or the
   original with its clip where the teacher chose it (`motion`), or every clip
   already made when she did not say.

Step 1 calls `vlm.creation` and then asks `vlm.director` for an independent
review because its description can be used to animate a painting. Step 2 calls
`vlm.creation` directly for missing scenes and the outline. It checks scene
length and the outline's page count, order and text before showing the result
for the teacher to edit and confirm; it makes no independent draft-review call.
Step 4 makes no model call at all: the only gate is `studio-safety` on each
original, which is why binding a book takes milliseconds. Step 3 is where the
time goes: ~20 s to load FLUX, ~5 s a page, ~3 s a list and ~1–3 s a check.

## Capabilities this skill uses

- `vlm.creation` — the draft writer, with `max_tokens` 12000.
- `vlm.director` — independent review of standalone `scene-description` for animation;
  not used by `story-outline`.
- `image.book` — FLUX.2 Klein 4B on the Spark's picture service (port 7270),
  several pictures per job. Optional: without it only the originals are offered.
- `studio-safety` — every drawing, before any model sees it, and again when the
  book binds; every redraw before it is shown.

## How to run it

From the page: 做本故事书, pick 2–8 drawings, order them, generate the outline,
edit or regenerate, then 确认情节，生成故事书. From Python:

```python
room.request(session_id, "story-outline", drawing_ids, {"scenes": {...}})
room.request(session_id, "book-pictures", drawing_ids[:1], {"styles": ["watercolour", "gouache", "paper", "clay"]})
room.request(session_id, "book-pictures", drawing_ids[1:], {"styles": ["clay"]})
room.request(session_id, "drawings-to-storybook", drawing_ids, {"pages": [...], "look": "clay"})
room.request(session_id, "drawings-to-storybook", drawing_ids, {"pages": [...], "look": "original", "motion": [...]})
```

`evalkit.packaging skills/drawings-to-storybook` checks this folder against the
Agent Skills specification.

## Bounds

- 2–8 distinct drawings; one drawing is refused before any work starts.
- A scene description is 1–600 characters; a passage 1–2000; a previous draft
  handed back for a rewrite at most 20000.
- Passages must arrive in the selected drawing order, one per drawing, or the
  request is refused with the reason.
- The outline beat runs with no retry. An invalid or unavailable model response
  is not published; an accepted draft still needs teacher confirmation.
- Teacher-edited passages are kept verbatim when the book binds.
- At most eight pictures in one `book-pictures` job, the picture service's own
  limit; a picture book is made in a colour class only.

## Measured

Historical StepFun First deployment, real drawings, before direct
storybook generation, read from the ledger:

- Scene description: 25–44 s and 3.8–5.7k tokens per drawing; 5 of 8 drafts
  passed the independent review, 3 were handed back.
- Story outline for two drawings: 77 s, 13.3k tokens, passed.
- Binding a page: 0 tokens, 9 of 9 passed; the safety verdict was already on
  record for each drawing.

## Gotchas

- **Told only "keep the picture", FLUX dropped what was small and recoloured
  what was grey.** A princess on a tower and one in a window
  vanished and grey mice came back brown in every style; "grey stays grey"
  turned blue skies grey. A list of what each drawing must keep, written by the
  vision model, fixed all of it; the comparison then caught 18 of 19 known
  cases, missing one where the list itself was wrong (green uniforms on grey
  mice). docs/measured/storybook-styles.md.
- **At the drawing's full size the style hardly shows.** Four of six styles
  came out looking like the original at 1536 pixels; at 1024, with the list,
  every style showed and every character stayed.

- **Storyboard drafts are now shown without an independent content review.**
  The teacher sees and confirms every passage before binding the book; image
  safety and structural checks still run.
- **A stale rejected scene once blocked the book forever.** A scene
  the reviewer had rejected used to stay in the page's draft slot, so the
  outline could never validate and the edit step never appeared. Fixed in
  `studio/page/src/29a-creation.js`; `tests/page/creation-flow.test.mjs`
  covers it.
- **Source data is evidence, never instructions.** Both prompts say so, and
  the reviewer is told the same about the candidate. A drawing with words
  written on it does not get to steer the story.
- **Silence is a picture page, not a missing page.** A drawing with no
  confirmed words still gets its page; the text is simply empty.
- **A story is always written fresh.** Handed its last story to improve,
  Qwen3.6 gave it back word for word, four times out of four,
  so the child's newer words never reached it. The page no longer sends it,
  and a story older than what a child has since said is written again.
- **Qwen3.6 often leaves out the list around the pages.** Four of ten
  five-picture stories came back as separate page objects, each
  right and in order; `studio/conversation/creation.py` reads them in order instead of
  refusing the whole story.
- **The story copies the scene descriptions' picture talk.** The scenes are
  written to place things on a picture for an animation ("画面右侧，…"), and
  the writer carried that into the story whatever it was told: ten such
  phrases in five stories with the instruction, ten without. The phrases in
  `assets/picture-talk.json` are removed where they open a clause, from the
  model's draft only (46 in the test class's 18 stories, none left); a
  teacher's words are never changed.

## The child's voice

The studio reads each page in the voice of the first answer a
child said out loud about its drawing, copied on the Spark by VoxCPM2, and in the
studio's own voice where the answers were typed or there were none. That is the
harness's reading of the finished book (`studio/voice/child_voice.py`), not a step of
this skill: the pages this skill writes are unchanged. The design record's rule
that a copied voice says only the child's own words was set aside by the operator.

## Not built

The design record promises an anthology when eight drawings do not make one
story, and layered assets from a scene package. Neither exists: the book is
pictures, confirmed words and, where one was made, the clip from 让画动起来.

## Verification

`tests/conversation/test_creation.py` runs the whole orchestration with scripted models;
`tests/making/test_book_pictures.py` the picture-book look, with a scripted painter;
`tests/page/creation-flow.test.mjs` covers the page's confirm boundary, stale
outlines and the teacher-owned path; `tests/skills/test_skill_packaging.py` proves this
folder is what the classroom loads.
