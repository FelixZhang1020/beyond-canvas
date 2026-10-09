---
name: art-feedback
description: Writes warm, specific feedback on a photograph of a child's drawing, in Chinese or English, on one of two entrances the teacher picks by hand. On the colour entrance the child tells the story inside their picture and nothing is corrected; on the sketch entrance light, proportion and structure get a professional read with a correction given as something to try. Fourteen pedagogy rules protect the child's motivation. Use when a teacher shares a drawing and wants a response, or when grading how kind and specific a piece of feedback is.
allowed-tools: art-feedback/feedback, art-feedback/story
license: Apache-2.0
compatibility: Requires a vision-capable model on the vlm.studio slot and Python 3.13 with uv.
metadata:
  author: beyond-canvas
  version: "0.2"
---

# Art feedback

Turn a photograph of a child's drawing into a few sentences of specific feedback and one
open question, on the entrance the teacher chose. On the colour entrance the opening is one
or two plain sentences about what is visible and then asks the child what they drew
(operator): nothing is read into the picture before the child has said what it is.

## Capabilities this skill uses

- Network: the model endpoint named by the `vlm.studio` slot in the active profile. No other host.
- Files: reads the drawing passed on the command line and its own prompts under
  `assets/prompts/`. Writes nothing.
- Shell: none beyond running its own script.

## The two entrances

The teacher picks one when the class starts. There is no automatic detection: a
coloured-pencil study would fool a colour test, and the lesson already knows which
kind of class it is. So there is no default either; every run names its entrance.

| | `--entrance colour` | `--entrance sketch` |
|---|---|---|
| What it reads | The picture's content, the idea, the story, the colours, the composition | Light, proportion, structure, technique |
| Correction | Never. Correction here is harm. | Expected, and given as something to try, never as something got wrong |
| The question | First asks what the child drew; after that, enters the world inside the picture | Enters the child's own process: which part they changed the most |
| What the child says | The story inside their picture | Where the difficulty was |

This fork replaced the age split and the teacher's switch for a gentle suggestion,
and both are deleted. Whether to critique is decided by the kind of work, not by the
child's age and not by a toggle. A plaster-cast study is a technical exercise at any
age; an imaginative painting is not a technical exercise at any age.

## How to run it

```bash
uv run python skills/art-feedback/scripts/feedback.py DRAWING --entrance colour --lang zh
uv run python skills/art-feedback/scripts/feedback.py DRAWING --entrance sketch
```

`--lang` is `en` or `zh`. Add `--slot vlm.director` to use the large model.

To run the fourth beat, pass what the child answered:

```bash
uv run python .../feedback.py DRAWING --entrance colour --said "they walked a long way"
```

On the colour entrance the reply's question asks for the next part of the child's story,
in order (who and what is happening, why, what happens next, how it ends), and never for
a small fact such as what colour, how long or how one action is done (operator; measured in
`docs/measured/story-questions.md`). On the sketch entrance the reply builds the technical
read around the part the child said was hard, and the correction it carries is still
something to try.

When the child says nothing, climb a rung rather than repeating yourself:

```bash
uv run python .../feedback.py DRAWING --entrance colour --opening "<what you asked>" --rung 2
```

Rung 1 is the opening question, already asked. Rung 2 offers two choices, because a
child who cannot invent can still choose, and choosing usually starts them talking.
Rung 3 lets a character in the drawing speak in the first person; almost no child
refuses that, because they are answering something they made themselves rather than
completing a task. On the sketch entrance the two choices are about the process and the
character is the object drawn, since a plaster cast has nowhere to be going. Never
repeat a question; make the door smaller.

To connect the feedback to what the class was working on, pass the lesson intent. The
teacher sets this once at the start of class, not per child:

```bash
uv run python .../feedback.py DRAWING --entrance colour --lesson "warm and cool colours"
```

## The fourteen rules

Feedback is graded against these. `references/rubric.md` carries the research behind each
one; read it when a rule seems arbitrary or when a grader result looks wrong.

1. Praise the action or the choice, never the child.
2. Open with a plain observation and no judgement word.
3. Name at least two details that are really in the drawing.
4. Never assert what an ambiguous shape is.
5. Never compare or rank.
6. Correct nothing. **Colour entrance only, and there it is absolute.**
7. Never judge realism. **Colour entrance only**: on a sketch, proportion is the subject.
8. Never diminish the technique.
9. End with one open question.
10. Keep every sentence short. One limit for everyone.
11. When the teacher gave a lesson intent, the feedback connects the child's work to it.
12. Ask about the world inside the picture, never about the artifact. On the sketch
    entrance, ask about the child's own process instead. A colour opening may ask what the
    child drew (operator).
13. After the child speaks, the reply uses their own words.
14. The machine never tells the story, and never corrects it.

**Eight of the fourteen are red lines and refuse on their own: 1, 4, 5, 6, 7, 8, 13 and
14.** Their violation is harm to the child rather than a flaw in the response, so they
are not averaged against the others. The remaining six are the quality of the response
and two of them may slip before it is refused. `RED_LINES` in `evalkit/rubric/report.py`
holds the list; `references/rubric.md` explains the split.

Which rules apply depends on the entrance and on which of the four things the machine
is saying. Rules 6 and 7 are skipped on the sketch entrance, where a correction is the
point. Rules 2, 3, 9 and 11 apply to an opening only. A rung keeps rule 12 — section
3.5's strongest rung is a character in the picture asking, which is rule 12's strongest
form — and drops rule 9, because the second rung is deliberately a choice between two
things. Rules 13 and 14 need the child to have spoken. The whole table is in
`references/rubric.md`, and `run_rubric` takes a `beat` so there is one copy of it.

## Grading a piece of feedback

```python
from evalkit.rubric import run_rubric

report = run_rubric(text, entrance="colour", image_data_uri=uri, client=client, child_said=transcript)
print(report.pass_rate, [f.evidence for f in report.failures])
```

The entrance is required; the grader refuses to guess it. Without an image, rules 3 and
4 are marked skipped rather than passed. Without `child_said`, so are rules 13 and 14:
in a class of twenty not every child speaks, and silence is not a failure of the machine.

## Gotchas

- Step 3.7 Flash returns empty content when `max_tokens` is small, because hidden reasoning
  consumes the whole budget. The slot profile sets at least 1000. If feedback comes back
  blank, that is the cause.
- The model will confidently name an ambiguous shape. In one early run it called a purple
  blob a mushroom. That is rule 4, and it is the most common failure.
- A drawing may carry the child's name or school. Never repeat either. The prompt forbids it
  and the eval suite tests it.
- A frightening subject is not a problem to solve. Describe it warmly and ask about it. Do
  not suggest drawing something happier.
- A sketch critique that passes on the sketch entrance fails on colour, by design. If a
  colour run is full of rule 6 and 7 failures, check which entrance the teacher chose
  before touching the prompt.
- **The wrong entrance does not just change the tone, it invents the subject.** Measured:
  a child's orange scribble sent through the sketch entrance came back
  describing "the outer edge of the cast" and "the spacing between each contour line",
  because the prompt tells the model it is looking at a plaster cast. A painting graded
  as a sketch will be described as a thing it is not. The entrance is a class-wide
  setting for exactly this reason, so it is set once and rarely wrong; when a whole
  class of feedback reads oddly, check it first.
- The comment is not the product. It is the opening move. The product is the story the
  child tells, and the fourth beat is where they find out whether anyone was listening.
  It is the easiest beat to drop and the one that matters most.
