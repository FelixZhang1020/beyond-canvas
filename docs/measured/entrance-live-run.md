# Both entrances against the real model: what fourteen drawings found

Measured on the cloud profile, `stepfun/step-3.7-flash` through OpenRouter, provider
pinned to StepFun, `reasoning.effort=low`. Writer on `vlm.studio` (6000 tokens), judge on
`vlm.director` (8000). English only; Chinese is still unmeasured.

## What was run

Every one of the seven eval fixtures through both entrances, seven of the fourteen
off-distribution on purpose: a child's scribble graded as a sketch study, a plaster
sphere graded as a painting. Off-distribution is where the prompts were expected to
break, and it is where four of the six defects showed up.

Reproduce it with the runner in this session's scratchpad, or by calling
`skills/art-feedback/scripts/feedback.py` once per fixture per entrance and passing each
reply to `evalkit.rubric.run_rubric` with the matching `entrance=`.

## Six defects, and none of them was found by a unit test

| # | Where | What happened | Fix |
|---|---|---|---|
| 1 | fixture | `sphere-study.png` was a smooth mathematical gradient, and the model refused it on both entrances: *"a photograph of a round, gray ball"*, *"a digital image rather than a hand-drawn sketch"* | redrawn in graphite hatching; `test_the_sphere_study_is_drawn_in_strokes_rather_than_rendered` |
| 2 | prompt | rule 2 failed on **six of seven** sketch drawings: the sketch prompt asked for "a plain observation" but never for the words *"I see"* or *"I notice"*, which is what the rule checks | prompt now asks for the opener, as the colour prompt already did |
| 3 | prompt | rule 4 failed twice on sketch: the prompt never carried the hedging instruction at all, though the rule grades both entrances | prompt now forbids asserting what an ambiguous shape is |
| 4 | prompt | rule 10 failed twice on sketch at 31 and 33 words against a 25 limit: the prompt said "keep every sentence short" and gave no number | prompt now says under twenty words, one idea per sentence |
| 5 | grader | rule 8 failed **three correct replies** on the word **"through"**, which contains "rough" | word-boundary matching in `evalkit.rubric.text.mentions` |
| 6 | grader | rule 12 failed three questions that are exactly what it asks for, including section 5a's own sketch question in the model's words | `WORLD_MARKERS` and `PROCESS_MARKERS` widened to stems |

## Three more, found only because the sweep was run again

Re-running the same fourteen after fixing the first six found three that the first sweep
could not have shown, because the first sweep's own failures were hiding them.

| # | Where | What happened | Fix |
|---|---|---|---|
| 8 | grader | rule 12 failed *"What is this character looking at in the distance?"* because "what is this" is a **prefix** of it. The question was marked down for how it starts rather than for what it asks | a marker now wins over an artifact phrase, the same precedence rule 9 already uses; "looking" and "watching" added, since a character's gaze is inner state |
| 9 | grader | rule 12 failed three sketch questions opening *"How did you decide…"*, *"How did you approach…"*, which is the construction the model reaches for most | `PROCESS_MARKERS` now carries "how did you" |
| 10 | runner | `run_suite` called the writer unguarded, so one empty completion aborted a benchmark and discarded every case already paid for | one retry, then the case is dropped with a line saying so |

**Defect 10 came from a failure that the token ceiling does not explain.** Two writer
calls returned empty at 6000 tokens; raising both writer slots to 12000 left one still
returning empty on the next sweep. Three empty completions in forty-two calls, roughly
seven per cent. Headroom makes it rarer and does not make it go away, so the eval runner
has to survive it rather than assume it away. A dropped case is recorded as dropped: a
model that said nothing has earned neither a pass nor a fail, and averaging silence in as
a zero would publish an outage as a quality.

## One sweep is not a measurement

Runs two and three put the same prompts against the same drawings and disagreed. The
colour entrance landed on 0.922 both times; the sketch entrance moved from 0.978 to
0.852, and the drawings that failed were not the same drawings. Nothing in the code
changed between them except a token ceiling, which decides whether a call finishes rather
than how good it is.

So **every number in this file is one sample.** They are worth reading for the failures
they name and the defects they exposed, and they are not worth quoting to three decimal
places or comparing across a change of a point or two. A benchmark that wants to detect
a small regression needs repeats, and this one has none.

## A seventh, created by the fix for the fourth

Defect 4's fix told the sketch prompt to keep sentences under twenty words and to start
a new sentence rather than join two observations. It worked: rule 10 stopped failing.
It also produced a **ten-sentence reply** on one drawing and a six-sentence one on
another, against a prompt that asks for two to four sentences and a question. Nothing
caught it, because **rule 10 measures sentence length and no rule measures sentence
count**, though the skill contract in section 5 of the spec specifies "2 to 4 sentences
plus one question".

The prompt now caps the count as well as the length, and says which to sacrifice: drop
the weaker observation rather than add a fifth sentence. The unenforced contract line is
left unenforced, because a fifteenth rule is a change to a settled spec rather than a
defect fix. It is recorded here so that the next person to widen a prompt knows that
this particular constraint has no grader behind it.

## The two that generalise

**A substring test over short words fails in the direction that punishes correct
writing.** Defect 5 is not about the word "rough". Every English phrase list in the
grader was read with `phrase in text`, so any forbidden word buried inside an innocent
one fired. "rough" inside "through" and "throughout" was the one the live run caught;
two more were latent and now have tests, **"cute" inside "acute"** and **"how" inside
"show"**. The last of those failed in the opposite and worse direction: it would have
let a closed question pass rule 9 rather than fail an open one. No unit test written
from the phrase list would ever have found any of them, because the list is where the
mistake is not.

**A prompt and the rule that grades it are two copies of one intention.** Defects 2, 3
and 4 are all the same shape: the sketch prompt was written fresh for the sketch
entrance and quietly dropped three instructions the colour prompt carries, while the
grader went on checking all three. The rules were right and the writing was reasonable;
they simply disagreed. The colour prompt never failed rule 2 in fourteen runs, which is
what a stated instruction is worth. **When an entrance is added, every rule not
explicitly scoped off it has to appear in its prompt.**

## The open question this leaves: rule 12's marker list

`WORLD_MARKERS` was widened **three times in one day**, once per sweep, and every
widening was prompted by a question that deserved to pass: *what would happen if I
stepped through that space*, *what is hiding under the fuzzy skin*, *what is this
character looking at in the distance*, *what adventure are they having together*. The
sketch list took the same treatment for *how did you decide* and *what part did you
redraw*.

That is a signal about the approach rather than about the words. A keyword list cannot
decide whether a question enters a world, so the false-negative rate is real, unbounded,
and rediscovered by every sweep. **Two honest ways out, and this is the operator's call
rather than a defect to fix:**

1. **Fall back to a judge** when no marker matches, as rules 3, 4, 11 and 14 already do.
   It would end the whack-a-mole and costs one model call per grade, on the one rule
   that currently costs nothing.
2. **Accept the rate and measure it.** Keep the list, and publish how often it marks
   down a question a person would pass, so the benchmark's own error bar is stated.

Neither is taken here. The list carries the words that four sweeps actually produced,
and the limitation is written down rather than hidden in a number.

## Numbers

Four sweeps of the same fourteen. Every number is one sample; see the section above on
why they should not be read to three decimal places.

| Sweep | What changed | colour | sketch | Empty completions |
|---|---|---|---|---|
| 1 | as committed | 0.883 | 0.762 | 0 of 14 |
| 2 | fixture, prompt and grader fixes 1 to 6 | 0.922 | 0.978 | 2 of 14 |
| 3 | writer ceilings raised to 12000 | 0.922 | 0.852 | 1 of 14 |
| 4 | fixes 7 to 10 | 0.909 | 0.952 | **0 of 14** |

Sweep 2's sketch figure is measured over five drawings rather than seven, because two
did not answer; sweep 3's over six. Sweep 4 is the only one where all fourteen completed.

**What survives in sweep 4, and why none of it is a defect.** Rule 4 fails twice on the
colour entrance for naming a yellow shape a sun and a brown shape an animal, which is the
known most-common failure and is already documented under rule 4. Rules 3, 9 and 12 fail
on the blank page on both entrances, which is the documented refusal limitation: a
refusal is not feedback on a drawing and these rules were not written for it. Rule 3
fails on the monster through the **sketch** entrance, where the model correctly declines
a flat vector shape as not an observational drawing.

Every reply in sweep 4 came in at three to five sentences, against the ten and six that
defect 7 produced.

## What this did not measure

Chinese. Every prompt interpolates its language and every rule has a Chinese phrase
list, and none of that was exercised here. The studio page defaults to Chinese and the
customer is a Chinese art centre, so this is the largest remaining gap in the hero
layer, not a footnote.

Also unmeasured: the reply (beat four) and the two rungs, which need a child's words to
run against, and the lesson intent, which needs a teacher to type one.

**One gap is worth naming precisely, because it is the same shape as defects 2 to 4.**
Rules 3 and 4 are graded on a reply whenever an image and a judge are supplied, and
neither reply prompt mentions hedging. That is exactly the disagreement between prompt
and rule that cost six of seven sketch runs their rule 2, and it is sitting in the reply
path untested. It is left alone here rather than fixed on a hunch: beat four was not run,
so there is no evidence, and a prompt that reaches children should not be edited on a
guess. Run the replies before touching them.
