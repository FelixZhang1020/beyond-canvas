# The fourteen rules, and why each one exists

Read this when a rule looks arbitrary, or when the grader returns a result that seems
wrong. Each section says what the rule forbids, what it allows instead, where it comes
from, and which function checks it.

Every rule works in both Chinese and English. The phrase lists live in
`evalkit/rubric/lexicons.py`, the only file in the codebase holding Chinese.

---

## Red lines and quality rules

Added after a live class showed four responses in twenty reaching a child
having failed a rule. The gate averaged every rule together, so a reply that failed the
one rule requiring it to use the child's words was shown anyway at 89%.

Section 3.6 of the requirements calls its list 红线 — **red lines**. A red line cannot
be averaged against a rule about sentence length.

| Red lines, any one refuses | Quality rules, these average |
|---|---|
| 1 praises the child rather than the choice | 2 opens with an observation |
| 4 asserts what an ambiguous shape is | 3 names two real details |
| 5 compares or ranks | 9 ends with an open question |
| 6 corrects, on the colour entrance | 10 keeps sentences short |
| 7 polices whether it looks real | 11 serves the lesson |
| 8 uses a diminishing word | 12 the question reaches inside the picture |
| 13 a reply that did not use the child's words | |
| 14 tells or corrects the child's story | |

The split is not severity, it is kind. A red line is **harm to the child**: it says
something that damages the thing the studio exists to protect. A quality rule is how
good the response is. One is refused outright; two of the others may slip before the
response is refused, and the teacher is told either way.

The list lives in `evalkit/rubric/report.py` as `RED_LINES`, and the gate reads it.

---

## Rule 1 — praise the process, not the person

**Forbidden:** "you are talented", "you're so creative", "you're a real artist".
**Allowed:** "you chose purple", "you pressed hard here", "you worked at this part".

Kamins and Dweck gave five and six year olds either person praise ("you are a good
drawer") or process praise ("you found a good way to do that"), then a setback. The
person-praised children blamed themselves and gave up more often, even though person
praise is positive. Praise that names a fixed trait makes the next failure evidence
against the child.

**Checked by:** `rule_1_process_not_person`, regular expressions in `lexicons.PERSON_PRAISE`.
**Known false positive:** none yet. Add any found here, with the sentence that triggered it.

---

## Rule 2 — open with a plain observation

**Forbidden:** any opening sentence that judges — "what a beautiful painting", "I see a
lovely dog". The judgement word is forbidden even when it sits inside an otherwise
neutral opener.
**Allowed:** "I see", "I notice", "我看到", "我注意到", followed by what is actually there.

Harvard Project Zero's See-Think-Wonder routine puts seeing before interpreting, and the
Kennedy Center's arts-education guidance makes the same point as "describe, don't judge".
A child who hears a verdict first learns that the verdict is the point. A child who hears
a description first learns that being looked at closely is the point.

**Checked by:** `rule_2_observation_opener`. Two ways to fail: the first sentence does not
start with an observation opener, or it carries a word from `EVALUATIVE_WORDS`.
**Known false positive:** a legitimate opener in a form not on the list. Add the form to
`OBSERVATION_OPENERS` rather than loosening the check.

---

## Rule 3 — name at least two real details

**Forbidden:** feedback that could apply to any drawing. "I love your picture, it's full
of energy" names nothing.
**Allowed:** colours, shapes, counts, positions — "the dog is purple", "eight triangle
rays", "two people side by side".

The ArtInsight study of model-written descriptions of children's art found missed detail
to be one of the recurring failure modes. Specificity is what separates warmth from
flattery: it is the evidence that someone actually looked.

**Checked by:** `rule_3_grounded_details`. This rule needs the drawing, so a vision model
is asked which mentioned details are genuinely visible, and at least two must survive.
Without an image the rule is marked **skip**, never pass.
**Applies to the opening only, as corrected.** On a reply it is skipped: the judge
ignores questions, and a reply is mostly one. See the settled section at the end.
**Known false positive:** a judge that fails to see a faint detail. Inspect the returned
`grounded` list before trusting a failure.

---

## Rule 4 — never assert what an ambiguous shape is

**Forbidden:** "the mushroom in the corner", when the child drew something they have not
named.
**Allowed:** hedging — "it looks like", "is that…", or simply asking.

The same ArtInsight work found over-assumption among the recurring failure modes, and it
is the most common failure in this skill's own runs: in one early run the model called a
purple blob a mushroom. Naming a shape wrongly tells a child their meaning did not come
across, which is the opposite of what the feedback is for.

**Checked by:** `rule_4_non_presumptive`, also a vision call. Hedged phrases and questions
are explicitly excluded by the judge prompt, and so is anything the child said themselves:
when `child_said` is supplied the prompt carries it, because repeating a name the child
gave a shape is the opposite of presuming.
**The escalation prompts needed this rule too.** A live run on the
orange-scribble drawing had rung two ask *"is the snail hiding in its shell?"* and rung
three speak as *"the tree with rings"*. Both guessed what the lines were, which is the
exact failure the spec's own worked example avoids — it ends *"two rungs, and the
machine never once guessed what the lines were"*. The rung prompts now say to offer
choices about what a shape is DOING rather than what it might BE, and to speak as the
marks themselves when nothing is clearly a creature. Rule 4 was never in those prompts
because they were written after it.

**Known false positive, mitigated.** The judge was flagging geometry as
presumption — *"calls the purple shape an oval; calls the red shapes circles; calls the
white shapes triangles"*. Describing a shape's geometry is description; claiming it is a
dinosaur is presumption. The judge prompt now says so with examples on both sides. Read the
quoted claim before acting on any remaining failure.

---

## Rule 5 — never compare or rank

**Forbidden:** "better than last time", "the best in the class", "比其他小朋友画得好".
**Allowed:** nothing comparative at all. Talk about this drawing only.

This is the social form of the Kamins and Dweck problem. A child told they are ahead
learns that the ranking is what matters, and the same ranking will eventually place them
behind. It also breaks the product promise: every child gets a response about their own
work.

**Checked by:** `rule_5_no_comparison`, phrase list `lexicons.COMPARISON`.

---

## Rule 6 — correct nothing

**Forbidden:** "it should have four legs", "you forgot the tail", "next time try".
**Allowed:** describing what is there, and asking about it.

Standard art-educator guidance against correcting children's work. A drawing is not an
attempt at a right answer, so there is nothing to be wrong. Correction converts a piece of
self-expression into a test the child failed.

**Applies on the colour entrance only, and there it is absolute.** Settled in section 5a
of the spec. No switch, no age condition, no exceptions. On the sketch
entrance the rule is skipped, not passed: a student drawing a plaster cast wants to know
where the proportion slipped, and withholding that fails them. There the correction arrives
as something to try rather than as something got wrong, and rule 8 still forbids
diminishing the work while it does.

**Checked by:** `rule_6_no_correction`, phrase list `lexicons.CORRECTION`, run only when
`run_rubric` is told `entrance="colour"`.
**Known false positive:** "应该" appears in ordinary Chinese phrasing that is not a
correction. Check the surrounding sentence.

---

## Rule 7 — never judge realism

**Forbidden:** "so realistic", "doesn't look like a real dog", "the proportions are off".
**Allowed:** treating what is on the page as correct.

Lowenfeld's stages of artistic development describe non-realistic drawing as the normal
work of a developmental stage, not an error on the way to photographs. A purple dog with
three legs is a complete and correct drawing. Praising realism also quietly ranks children
by how close they are to a stage they have not reached yet.

**Skipped on the sketch entrance, settled with the operator.** The phrase
list is made of the very words a sketch critique is made of: "out of proportion", 比例不对,
"doesn't look like". A plaster-cast study is an observational exercise, so likeness and
proportion are its subject rather than a judgement, and a correct critique would fail the
rule as written. The spec table scoped only rule 6; rule 7 was scoped the same way for the
same reason, because a benchmark that punishes correct behaviour teaches the wrong thing to
whoever tunes against it.

**Checked by:** `rule_7_no_realism_policing`, phrase list `lexicons.REALISM`, run only when
`run_rubric` is told `entrance="colour"`.

---

## Rule 8 — never diminish the technique

**Forbidden:** "just a simple sketch", "a bit messy", "scribbles", "随便画".
**Allowed:** naming what the marks do — "big looping lines", "you filled the whole page".

The Kennedy Center's "describe, don't judge" guidance again, applied to the downward
direction. A diminishing word does its damage even when wrapped in praise, because the
child hears the qualifier.

**Checked by:** `rule_8_no_diminishing`, phrase list `lexicons.DIMINISHING`.
**Known false positive:** "simple" used about a shape rather than the work — "a simple
circle". The list is deliberately strict; rephrase rather than loosening it.

**Known false positive, fixed. The words were never there.** A live run over
fourteen drawings failed this rule three times on the word **"through"**, which carries
"rough" inside it. The replies said *"what would happen if I stepped through that space"*
and *"the sphere reads as round throughout"*. Nothing diminishing was said in either.

The cause was not this list but how every English list was read: a bare substring test,
so any forbidden word buried inside an innocent one fired. Two more were latent and are
now covered by tests: **"cute" inside "acute"**, which a sketch critique says often, and
**"how" inside "show"**, which let a closed question pass rule 9 rather than fail it.

`evalkit.rubric.text.mentions` now anchors English phrases to a word boundary at the
front, which keeps the endings the rules mean to catch — "scribble" still catches
"scribbles", "rough" still catches "roughly". Rule 9's question words additionally
anchor at the back, because "who" is always "who" and otherwise it matched "whole".
Chinese keeps the plain substring test, having no boundary to anchor to.

**The lesson is about the shape of the check, not the words.** A substring test over a
list of short words fails silently in the direction that punishes correct writing, and
no unit test written from the list itself would ever catch it.

---

## Rule 9 — end with one open question

**Forbidden:** ending with no question, or with a yes-or-no question — "is that your pet?",
"这是你的宠物吗？".
**Allowed:** what, how, why, who, where, which, "tell me about" — and their Chinese
equivalents.

The Wonder in See-Think-Wonder. A closed question ends the exchange with a single word; an
open one hands the drawing back to the child as its author. In a class of twenty this
question is what the teacher asks next, so it has to be worth asking.

**Checked by:** `rule_9_ends_with_open_question`. Three ways to fail: no question at all, a
closed question, or a question with no open marker.

**Known false positive, fixed.** The check tested the grammatical opener before
looking for an open marker, so it failed *"Can you tell me what you were making?"* — a
question that opens yes-or-no on paper and that no child answers with "yes". An open marker
now wins over the opener. A closed request with no open marker, such as *"Could you send me
a photo of it?"*, still fails, and a test holds both halves.

---

## Rule 10 — keep sentences short

**Forbidden:** any sentence over 25 English words or 45 Chinese characters.
**Allowed:** anything shorter. Nothing is gained by filling the limit.

Feedback a child cannot follow is feedback that did not happen, however kind it is.

**The age bands were removed.** Section 5a declines an age-graded rule
engine: the operator's split at third grade was an illustration, not a specification.
The entrance fork, sketch or colour, replaced both the age split and the teacher's
switch for a gentle suggestion: whether to critique is decided by the kind of work, not
by who drew it. One limit now applies to everyone, and it sits where the middle band
was.

**Checked by:** `rule_10_short_sentences`, arithmetic on `SENTENCE_LIMIT_WORDS` and
`SENTENCE_LIMIT_CHARS`. English counts words, Chinese counts characters, and the
language is detected per piece of feedback.
**Known false positive:** none. The limits are a judgement call and can be tuned in one
place if the human panel disagrees with them.

---

## A limitation the rules cannot fix: a refusal is not feedback

Found in the first benchmark. The blank-page case produced exactly the right
reply — *"I see the page is blank. Could you share a photo of your drawing with me?"* — and
scored 80%, failing rules 3 and 9.

Both failures are correct readings of the rules and both are wrong about the reply. Rule 3
wants two visible details, and a blank page has none. Rule 9 wants an open question, and the
right move is a closed request for a photo. **The ten rules grade feedback on a drawing, and
a refusal is not feedback on a drawing.**

Do not loosen rules 3 or 9 to accommodate this. Doing so would weaken them for the case they
exist to serve, in exchange for a number on a case that should not be scored by them at all.
The honest fix is for the runner to score refusal cases against their own expectations —
the `expected_behavior` list already in `evals/evals.json` — rather than against a rubric
built for something else. Until that exists, read a blank-page or not-a-drawing score as
measuring the wrong thing, and judge those cases by reading the reply.

The same caution applies to any future case whose correct answer is a refusal.

---

# Rules 12 to 14: the loop, not the comment

Rules 1 to 11 govern what the machine says. These three govern the conversation it is
supposed to open, and they exist because **the comment is not the product.** The product
is the story the child tells about their own picture. The comment is the opening move.

---

## Rule 11 — serves the lesson

**Forbidden:** nothing. This rule has no phrase list and cannot fail a response for
what it says. It asks one thing: when the teacher told the studio what today's class
was teaching, does this response touch it at all?

**Skipped whenever it cannot honestly apply:** no lesson intent was typed in, or there
is no judge to ask. Most classes will leave the field empty and that is not a failure.

**Applies to the opening only, as corrected.** A live run in Chinese marked a
correct reply down for not connecting to warm and cool colours — a reply that had used
the child's own words, which is the entire job of beat four. Section 5a asks the reply
to answer the child and get out of the way, not to steer back to the lesson plan. A
rung is skipped for the same reason: it is a question, not feedback.

**Checked by:** `rule_11_serves_the_lesson`, a text-only judge call.
**Known false positive:** a lesson intent so broad that nothing could fail it, which
makes the rule free rather than wrong.

*This section once said the rule was "not yet built", when it was already
built, wired, prompted, collected by the page and forwarded by the session. A reference
that describes thirteen of fourteen rules is worse than one that admits a gap.*

---

## Rule 12 — the question enters the world

**Forbidden:** questions about the artifact. "What did you draw", "what is this", 这是什么.
**Allowed:** questions about events, characters, the unseen, the senses, inner state, or
before and after. "What is happening here", "where is he going", "what would I hear if I
stood here".

The whole design turns on the difference. Asking a child to describe their picture returns
a list of nouns: this is a dragon, this is a house. Asking what is happening inside it
returns a story: the dragon just flew home because his house was on fire. Only the second
produces 创作思路 and 故事情节, two of the six dimensions, and neither is visible in any
photograph.

The strongest form asks from inside the fiction, in a character's voice: *I am the bird in
your tree, may I sit on your branch?* A child is no longer answering an adult, and the
guard drops. That is the oldest technique in drama education, and it is the third rung when
a child says nothing.

**Checked by:** `rule_12_question_enters_the_world`. Three ways to fail: no question at
all, a question naming the artifact, or a question with nothing reaching inside the
picture.
**Known false positive:** a world question phrased in a form the marker list does not
carry. Add the form to `WORLD_MARKERS` rather than loosening the check.

**Both lists were widened from a live run rather than from taste.** Three
questions were marked down that are precisely what this rule asks for:

| Question the model wrote | Why it failed | What was missing |
|---|---|---|
| *What would happen if I stepped through that space?* | colour | the list carried "happening" and "happened" but not the stem `happen` |
| *What is hiding under the fuzzy skin?* | colour | the unseen had no words at all, though section 5a names it the class that forces invention hardest |
| *What part of the cast did you redraw the most?* | sketch | the list carried "which part" but not "what part", "redo" but not "redraw" |

The third is section 5a's own sketch question in the model's words, which is the clearest
possible sign that a marker list is too narrow rather than a reply too weak. Adding stems
rather than inflections is the general fix: `happen` covers happening, happened and
happens at once.

**Then it happened twice more, on the next two sweeps.** *"What is this character looking
at in the distance?"*, *"How did you decide on the placement of the green dots?"*, *"What
adventure are they having together?"* — three more questions that deserved to pass. The
first also exposed a precedence bug: it was failed as an artifact question because "what
is this" is a **prefix** of it. A marker now wins over an artifact phrase, exactly as an
open marker already wins over a yes-or-no opener in rule 9, so a question is graded on
what it asks rather than on how it starts. A bare *"What is this?"* carries no marker and
still fails.

**Read that pattern before adding a fourth round of words.** Three widenings in one day,
each from a question a person would pass, is evidence about the method rather than the
vocabulary: a keyword list cannot decide whether a question enters a world, and every
sweep will keep finding new words. The two real options — a judge call when no marker
matches, or accepting the false-negative rate and publishing it — are laid out in
`docs/measured/entrance-live-run.md` and are the operator's to choose. Neither
was taken, so this check is known to mark down some questions it should not.

**On the sketch entrance the question enters the process instead.** Settled with the
operator. A plaster cast has no story, so 画里发生了什么 would be absurd
there; section 5a's sketch question is 哪一块你改了最多次, and what comes back is the
child's own account of the struggle, which is what a teacher of technique most wants to
know and least often has time to ask. Checked by `rule_12_question_enters_the_process`
against `PROCESS_MARKERS`: which part, hardest, changed, tried, how many times. A story
question fails on sketch and a process question fails on colour, so the two forms cannot
be confused for one another in a benchmark.

**Applies to the opening only, as corrected.** A live run scored a good reply
down because it asked nothing, and section 5a tells beat four to do exactly that: one
question at most, none at all is fine once the child has said something whole, and when
the child is talking, stop talking. Rule 12 is now skipped whenever `child_said` is
supplied, because that marks the text as a reply rather than an opening. The failure was
the same shape as the blank-page problem: a rule judging text it was not written for.

---

## Rule 13 — the reply uses the child's words

**Forbidden:** a reply that could have been written before the child spoke. Warmth is not
enough: "what a lovely story, would you like to draw another?" hears nothing.
**Allowed:** saying their words back. If the child said the dragon's house was on fire,
"house" and "fire" appear in the reply.

This is the fourth beat, and the spec calls it the easiest to drop and the one that matters
most. **A child feels heard here, not at the opening compliment.** When it lands, children
usually add something they had not said yet, and that addition is the evidence it worked.

**Two halves, the second one added later.** The reply must carry the child's words AND at
least one word of its own. A live run replied to *"the tree is my grandma's tree and I
climb it"* with that sentence verbatim, in the child's own first person, and scored 100%:
every rule passed, because a total echo maximises the overlap this rule measures. Section
5a's proof that the beat worked is that the child adds something they had not said, and
nobody adds anything to their own sentence read back to them.

**Checked by:** `rule_13_reply_uses_the_childs_words`, set intersection of content words,
needing at least two. English strips stopwords; Chinese has no spaces, so overlapping
character pairs stand in for words — cruder than segmentation, and it needs no dictionary,
which matters because this runs on the box.
**Skipped, not failed, when the child said nothing.** In a class of twenty not every child
speaks, and silence is not a failure of the machine.

---

## Rule 14 — the machine never tells the story

**Forbidden:** story content the child did not supply — events, motives, names, feelings.
Also forbidden: correcting their story. If the child says the sun is angry, the sun is
angry.
**Allowed:** repeating them, describing what is visibly drawn, and asking.

The moment the machine offers a better version, the child's version dies. This is the
failure that makes the whole loop pointless, because a polished story that goes home is the
machine's story, and the thing worth keeping was the child's own language: the long road,
the wind that cannot stop, the teeth for biting stones.

**Checked by:** `rule_14_machine_never_tells_the_story`, a judge call that needs no image
because it compares the reply against what was said rather than against the drawing.
**Skipped when the child said nothing**, like rule 13.

---

## Settled: which rules apply to which beat

The machine says four kinds of thing and they are not graded alike.
The whole table lives in `run_rubric`, which takes a `beat`, rather than being partly
there and partly hand-assembled in the harness — where a rung came to be graded by a
list that omitted the one rule written about rungs.

| Rule | Opening | Reply | Rung |
|---|---|---|---|
| 1, 5, 8, 10 what it says | yes | yes | yes |
| 6, 7 correction and realism | colour only | colour only | colour only |
| 2 opens with an observation | yes | no | no |
| 3 two real details | yes | no | no |
| 4 presumes nothing | yes | yes | yes |
| 9 ends with an open question | yes | no | **no** |
| 11 serves the lesson | yes | no | no |
| 12 the question reaches inside | yes | no | **yes** |
| 13, 14 heard the child | when they spoke | yes | no |

**Rule 9 must not apply to a rung**, and this is the one that looks wrong until you
read section 3.5. The second rung is deliberately a choice between two things — *is he
just arriving, or about to leave?* — which is a closed question by rule 9's definition
and precisely why it works on a child who cannot invent an answer.

**Rule 12 must apply to a rung**, because section 3.5's strongest rung IS rule 12's
strongest form: a character inside the picture asking the child directly.

### Rules 2, 9 and 12 grade an opening, and a reply is not one

Found in a live run, and **decided the same day.**

Grading beat four's reply against the full set fails two more rules:

- **Rule 2** wants the text to open with "I see" or "I notice". A reply that begins
  *"The two stick figures are his brother and him"* fails, because it is answering rather
  than opening.
- **Rule 9** wants an open question at the end. The reply asks nothing, which is exactly
  what section 5a instructs: one question at most, and none at all is fine once the child
  has said something whole.

Rule 12 was scoped to openings because the spec forbids its behaviour in a reply in so many
words. Rules 2 and 9 are not that clear-cut: the spec says rules 1 to 11 govern what the
machine says, without separating the opening from the reply, and an argument exists that a
reply should still be grounded and still invite.

**Decision: all three are opening rules and skip on a reply.** They describe one shape
— begin with a plain observation, end with one open question, make that question reach
inside the picture — and that shape is beat two's. Section 5a asks beat four for the
opposite. Keeping them universal would have meant publishing a number that marks the
machine down for obeying the spec, and a benchmark that punishes correct behaviour teaches
the wrong thing to whoever tunes against it.

A reply is now graded on the rules written for a reply: 1, 4, 5, 6, 7, 8 and 10 for what
it says, 13 and 14 for whether it heard. Supplying `child_said` is what marks the text as
a reply.

**Rule 3 joined them, from a second live run.** The first reply the studio
page ever produced was refused twice, on rule 3 and rule 4 together:

> The tree is your grandma's tree and you climb it. Is that the tree with the brown trunk
> and green leaves?

That reply is what beat four is supposed to look like. It repeats the child, invents
nothing, hedges, and asks. Rules 13 and 14 passed it. Rule 3 returned **zero grounded
details** — because the grounding judge is instructed to ignore questions, and almost all
of that reply is one. A reply written as section 5a asks can therefore never satisfy rule
3, whatever it names. Rule 13 already does rule 3's job for a reply, using the child's own
words instead of the drawing's, so rule 3 is now skipped on a reply.

**Rule 4 stays, but it is now told what the child said.** In the same run it flagged
*"calls the ambiguous purple shape grandma's tree"* — a presumption the child had made
themselves, a sentence earlier. Section 5a settles this outright: *with the child's words,
naming the shape is repeating the child, not presuming.* The judge prompt now carries the
transcript and the instruction that anything the child named is theirs. Without a
transcript the prompt is unchanged, so an opening is graded exactly as before.

The blank-page case is deliberately NOT fixed the same way, because a refusal is not a
different beat — it is the machine declining to start. That one stays recorded as a
limitation above.
