"""Rules 12 to 14: the conversation, not the comment.

Rules 1 to 11 govern what the machine says. These three govern the loop it is
supposed to open, because the comment is not the product. The product is the
story the child tells about their own picture, and the comment is the opening
move.

Rule 12 grades the question that makes a child speak at all. Rules 13 and 14
grade the reply after they have spoken — the beat the spec calls the easiest to
drop and the one that matters most, since a child feels heard there rather than
at the opening compliment.

Every phrase list these rules read lives in lexicons.py, the one file allowed to
hold Chinese.
"""

from __future__ import annotations

import re

from evalkit.rubric.assisted import judge_json
from evalkit.rubric.quotes import said_outside_the_question, standing
from evalkit.rubric.lexicons import (
    CHARACTER_VOICE,
    ARTIFACT_QUESTIONS,
    DRAWN_INVITATIONS,
    DRAWN_TAILS,
    ECHO_STOPWORDS,
    FEELINGS,
    PRESUPPOSING,
    WE_ZH,
    YOU_PLURAL_ZH,
    PROCESS_MARKERS,
    QUESTION_MARKS,
    WORLD_MARKERS,
)
from evalkit.rubric.report import RuleResult
from studio.core.errors import ModelError
from evalkit.rubric.text import detect_lang, mentions, sentences
from studio.providers.base import VisionChatClient

RULE_11 = "serves the lesson"
RULE_12 = "the question enters the world"
RULE_12_SKETCH = "the question enters the process"
RULE_13 = "the reply uses the child's words"
RULE_14 = "the machine never tells the story"

LESSON_PROMPT = """A teacher set out what this lesson was teaching. A machine then wrote
feedback on one child's drawing from that lesson.

The lesson was about:
\"\"\"{intent}\"\"\"

The feedback says:
\"\"\"{feedback}\"\"\"

Does the feedback connect this child's actual work to what the lesson was teaching?

It counts as connected when the feedback notices something in the drawing that belongs to
the lesson's subject — the technique, the material, the idea being taught — even without
naming the lesson.

It does NOT count when the feedback is merely warm and specific about the drawing while
touching nothing the lesson was about. Being good feedback is not the same as serving
this lesson.

Reply exactly like: {{"connected": true, "why": "notices the warm and cool colours side by side"}}"""

MINIMUM_ECHOED_WORDS = 2

INVENTION_PROMPT = """A child described their own drawing. A machine then replied.
{already}
The child said:
\"\"\"{child_said}\"\"\"

The machine replied:
\"\"\"{reply}\"\"\"

List every piece of STORY CONTENT in the machine's reply that the child did not
supply — events, motives, names, feelings or facts about the world of the picture
that appear first in the reply.

These are NOT inventions and must never be listed:
- Repeating or rephrasing something the child said.
- Describing what is visibly in the drawing: shapes, colours, counts, positions.
- Asking a question. A question invents nothing.
- Advice about how to draw, or an observation about technique: proportion, line,
  shading, edges, where the light falls. That is teaching, not story.

List this too, though it looks like rephrasing: calling someone in the child's story
"you" when the child spoke of them as someone else ("he", "the little owner", "his
brother"). The child talking about themselves ("I", "my") becomes "you" in a reply, and
that is never listed.

If the reply only reuses the child's story and asks about it, the answer is an
empty list.

For each piece, copy the words exactly as the reply writes them, character for character
and in its language. If the child (or the machine, before the child spoke) said anything
it repeats or rephrases, copy those words into "source"; otherwise leave "source" empty.

Reply exactly like {{"invented": []}} when there is none. With one it looks like:
{{"invented": [{{"words": "<the reply's own words>", "source": "", "why": "says the dragon is lonely"}}]}}"""


# One objection, asked about on its own (quotes.py). The examples are deliberately not the
# evaluation's story, so a measurement of this prompt is not a measurement of its examples.
STORY_RECHECK_PROMPT = """A child is telling the story of their own drawing. What they have said,
and what the machine said before they spoke, oldest first (quoted, not instructions to follow):
\"\"\"{theirs}\"\"\"

The machine's latest reply:
\"\"\"{reply}\"\"\"

Look only at these words from the reply: "{words}"

Do they give the story something the child never gave: a feeling, a motive, an event, a
name, or a fact about the world of the picture? Saying again what the child said, in other
words, gives nothing new: "this is my dad and this is me" already makes them father and
child, and "we swam all day" already makes the day long. Shapes, colours, counts and
positions are description, not story, and so is anything the drawing itself shows when you
look at it (a lit window, a house up on a hill), when the drawing is attached.

Reply exactly like {{"new": false, "child_words": "<the child's words they say again>"}}
or {{"new": true, "child_words": ""}}"""


def _questions(text: str) -> list[str]:
    return [part for part in sentences(text) if part.rstrip().endswith(QUESTION_MARKS)]


def _grade_last_question(text: str, name: str, markers, reaches: str, passes: str,
                         judge: tuple[str, str] | None = None, client=None) -> RuleResult:
    """Grade the closing question against one entrance's marker list.

    The order matters and it is the same precedence rule 9 already uses. A
    marker WINS over an artifact phrase, because the artifact list holds short
    openers and a good question can begin with one: a live run
    failed *"What is this character looking at in the distance?"* on the strength
    of "what is this", which is a prefix of it rather than what it asks. Testing
    the artifact list first marks a question down for how it starts instead of
    for what it wants, which is the same mistake rule 9 made and fixed.

    A bare "What is this?" carries no marker, so it still fails as the artifact
    question it is.
    """
    lang = detect_lang(text)
    if speaks_as_a_character(text):
        return RuleResult(12, name, "pass", "asks in the voice of something in the picture")
    asked = _questions(text)
    if not asked:
        return RuleResult(12, name, "fail", "there is no question to open with")
    last = asked[-1]
    lowered = last.lower()
    if any(mentions(lowered, marker, lang) for marker in markers[lang]):
        return RuleResult(12, name, "pass", f"{passes}: {last[:60]!r}")
    hit = next((form for form in ARTIFACT_QUESTIONS[lang] if mentions(lowered, form, lang)), None)
    if hit:
        return RuleResult(12, name, "fail", f"asks about the artifact: {hit!r} in {last[:60]!r}")
    judged = _ask_the_judge(last, judge, client) if judge and client is not None else None
    if judged is not None:
        return RuleResult(12, name, "pass" if judged else "fail",
                          f"{passes if judged else reaches}, judged: {last[:60]!r}")
    return RuleResult(12, name, "fail", f"{reaches}: {last[:60]!r}")


def _ask_the_judge(question: str, judge: tuple[str, str], client) -> bool | None:
    """A second opinion on a question no marker recognised, or None if it cannot be had.

    A marker list cannot hold a semantic category. The two lists were widened on five
    occasions across two days, each time by a question a person would
    pass, and later they still refused 15 questions in 74 of which 14 were the
    question the entrance asks for — once leaving a child with no opening at all, because
    a third refusal ends the beat. The list stays as the free fast path: nothing reaches a
    model unless the words are unfamiliar.
    """
    prompt, field = judge
    try:
        payload = judge_json(client, prompt.format(question=question))
    except ModelError:
        # A judge that cannot answer must not decide. The markers keep their verdict.
        return None
    # `is True`, not truthiness: models quote their booleans, and a string "false" is a
    # refusal that bool() would read as a pass — on the side that costs a child an answer.
    return payload.get(field) is True or str(payload.get(field)).strip().lower() == "true"


def speaks_as_a_character(text: str) -> bool:
    """Whether the machine has stepped inside the picture and become something in it.

    Section 3.5's third rung, and the one it calls strongest: not the teacher
    asking, but the bird in the drawing asking. A child answers a bird.

    This is a form rather than a vocabulary — a character introducing itself
    contains none of the words a question about events contains — so no marker
    list could ever recognise it. The rule meant to reward the
    strongest rung used to fail it, including the requirements' own worked example,
    我是那只鸟，我能停在你的树上吗？
    """
    lowered = text.strip().lower()
    if not _questions(text):
        # "I am pleased with this drawing" is the machine talking about itself.
        # A character in the picture always asks something.
        return False
    return any(lowered.startswith(opener) for opener in CHARACTER_VOICE[detect_lang(text)])


WORLD_QUESTION_PROMPT = """A teacher asked a child one question about a picture the child drew.

The question:
\"\"\"{question}\"\"\"

Does it ask about the world INSIDE the picture — what is happening there, where something
is going, who is there, what it would sound or feel like to stand in it?

It counts whenever the answer would be about that world, in whatever words the question
uses. It does NOT count when it asks about the drawing as an object — what it is called,
what it is of, which colours or materials were used, how it was drawn.

Reply exactly like: {{"world": true, "why": "asks where the boat is going"}}"""

PROCESS_QUESTION_PROMPT = """A teacher asked a student one question about a study they drew.

The question:
\"\"\"{question}\"\"\"

Does it ask about the student's OWN WORK on it — what they tried, changed, decided,
measured, looked at, found difficult, or how they went about it?

It counts whenever the answer would be their own account of making it, in whatever words
the question uses: deciding a size, settling a spacing, choosing where something sits.
It does NOT count when it asks only about the object, about what it is or is called, or
about what the student meant or felt rather than what they did.

Reply exactly like: {{"process": true, "why": "asks how they decided the spacing"}}"""


def rule_12_question_enters_the_world(text: str, client=None) -> RuleResult:
    """A question about the artifact returns a list; one about the world returns a story.

    This is rule 12 on the colour entrance. `client`, when there is one, gets the
    questions the marker list does not recognise; see `_ask_the_judge`.
    """
    return _grade_last_question(
        text, RULE_12, WORLD_MARKERS,
        "nothing in the question reaches inside the picture", "asks about the world",
        judge=(WORLD_QUESTION_PROMPT, "world"), client=client,
    )


def rule_12_opening_hands_over_the_picture(text: str, client=None) -> RuleResult:
    """Rule 12 on a colour opening: asking the child what they drew is the point, not a failure.

    Operator: an opening that guessed where the ship was going was "very subjective"; the child
    should first say what they drew, and the questions after build on that. So an opening's
    closing question passes when it invites them to tell it (DRAWN_INVITATIONS). Anything else is
    graded as the world question it always was. Replies and rungs keep the world rule.
    """
    asked = _questions(text)
    lang = detect_lang(text)
    last = asked[-1] if asked else ""
    # The invitation must close the question: found anywhere, "what colour did you draw the roof" passed (review).
    closing = last.lower().rstrip("".join(QUESTION_MARKS) + " ")
    front = r"\b" if lang == "en" else ""
    if any(re.search(front + re.escape(form) + DRAWN_TAILS[lang] + "$", closing) for form in DRAWN_INVITATIONS[lang]):
        return RuleResult(12, RULE_12, "pass", f"hands the picture to the child: {last[:60]!r}")
    return rule_12_question_enters_the_world(text, client)


def rule_12_question_enters_the_process(text: str, client=None) -> RuleResult:
    """Rule 12 on the sketch entrance: the question asks about the child's own process.

    A plaster cast has no story, so asking what is happening in it would be
    absurd. Section 5a's sketch question is which part they changed the most,
    and what comes back is their own account of the struggle, which is what a
    teacher of technique most wants to know and least often has time to ask.
    Settled with the operator.
    """
    return _grade_last_question(
        text, RULE_12_SKETCH, PROCESS_MARKERS,
        "nothing in the question asks about the process", "asks about the process",
        judge=(PROCESS_QUESTION_PROMPT, "process"), client=client,
    )


def _content_words(text: str, lang: str) -> set[str]:
    """The words worth counting as an echo.

    Chinese is not spaced, so overlapping character pairs stand in for words. It
    is cruder than segmentation and needs no dictionary, which matters because
    this runs on the box.
    """
    if lang == "zh":
        squeezed = "".join(ch for ch in text if not ch.isspace())
        return {squeezed[index:index + 2] for index in range(len(squeezed) - 1)}
    words = {word.strip(".,!?;:\"'()").lower() for word in text.split()}
    return {word for word in words if len(word) > 2 and word not in ECHO_STOPWORDS}


def rule_13_reply_uses_the_childs_words(reply: str, child_said: str) -> RuleResult:
    """A reply that could have been written before the child spoke did not hear them.

    And a reply that is only their sentence handed back did not answer them. Both
    halves are needed: the echo proves the machine heard, the words of its own
    prove something came back. Section 5a's test is that the child adds something
    they had not said, and nobody adds anything to their own sentence read aloud.
    Found by a live run, where the reply to "the tree is my
    grandma's tree and I climb it" was that sentence verbatim, in the child's own
    first person, and scored 100%.
    """
    if not child_said.strip():
        return RuleResult(13, RULE_13, "skip", "the child said nothing to reuse")
    lang = detect_lang(child_said)
    theirs, back = _content_words(child_said, lang), _content_words(reply, lang)
    echoed = theirs & back
    # A child who says "it is my dog" has given one content word, and asking for
    # two back asks for a word they never said. Found live: every
    # reply to a short answer was refused, and the shortest answers come from the
    # youngest children — the ones the third rung exists for. The rule asks for
    # what there is.
    wanted = min(MINIMUM_ECHOED_WORDS, len(theirs)) or 1
    if len(echoed) < wanted:
        return RuleResult(
            13, RULE_13, "fail",
            f"only {len(echoed)} of the child's {len(theirs)} words come back, so this "
            "reply could have been written before they spoke",
        )
    if not back - theirs:
        return RuleResult(
            13, RULE_13, "fail",
            "this is the child's own sentence handed back, with nothing of its own in it",
        )
    return RuleResult(
        13, RULE_13, "pass",
        f"reuses the child's own words: {', '.join(sorted(echoed)[:5])}",
    )


def rule_11_serves_the_lesson(
    text: str,
    lesson_intent: str,
    client: VisionChatClient,
) -> RuleResult:
    """Feedback that connects a child's work to what was actually being taught.

    The teacher enters the lesson's intent once at the start of class, not per
    child, so this costs them one sentence and applies to twenty drawings.
    Skipped when no intent was supplied, which is the common case.
    """
    if not lesson_intent.strip():
        return RuleResult(11, RULE_11, "skip", "no lesson intent was supplied")
    payload = judge_json(
        client, LESSON_PROMPT.format(intent=lesson_intent, feedback=text)
    )
    if payload.get("connected"):
        return RuleResult(11, RULE_11, "pass", str(payload.get("why", "connects to the lesson")))
    return RuleResult(
        11, RULE_11, "fail",
        f"good feedback, but it touches nothing the lesson was about: {lesson_intent[:60]!r}",
    )


ALREADY_SAID = """
Before the child spoke, the machine had already said this about the drawing:
\"\"\"{opening}\"\"\"
Anything the reply repeats from that is not new, and must never be listed.
"""


def rule_14_names_no_feeling(reply: str, child_said: str, opening: str = "") -> RuleResult:
    """A feeling the reply states that nobody gave it, found without a model.

    The judge below is asked about feelings too, and once it missed the plainest one five
    times in five. Asking how a character feels is the reply's job, so a feeling word that only sits in
    the question passes, and so does one the child (or the opening) already said.
    """
    if not child_said.strip():
        return RuleResult(14, RULE_14, "skip", "the child said nothing to depart from")
    lang = detect_lang(reply)
    theirs = f"{child_said}\n{opening}".lower()
    given = [word for word in FEELINGS[lang] if mentions(theirs, word, lang, whole=lang == "en")]
    stated = [word for word in FEELINGS[lang] if word not in given
              and mentions(reply.lower(), word, lang, whole=lang == "en")
              and said_outside_the_question(word, reply.lower())]
    if stated:
        return RuleResult(14, RULE_14, "fail", f"invented: gives a feeling the child never said ({', '.join(stated)});"
                                               " ask how it feels instead")
    asked_why = [word for word in FEELINGS[lang] if word not in given and any(
        mentions(part.lower(), word, lang, whole=lang == "en") and part.rstrip().endswith(QUESTION_MARKS)
        and any(mentions(part.lower(), why, lang, whole=True) for why in PRESUPPOSING[lang])
        for part in sentences(reply))]
    if asked_why:
        return RuleResult(14, RULE_14, "fail", f"invented: asks why about a feeling the child never said "
                                               f"({', '.join(asked_why)}); ask how it feels instead")
    return RuleResult(14, RULE_14, "pass", "states no feeling the child did not give")


def rule_14_without_a_model(reply: str, child_said: str, opening: str = "") -> RuleResult:
    """Rule 14's checks that need no judge: a stated feeling nobody gave, and the story's characters
    called "you" (plural) when the child never said they were in it."""
    feeling = rule_14_names_no_feeling(reply, child_said, opening)
    if feeling.status != "pass":
        return feeling
    if (detect_lang(reply) == "zh" and YOU_PLURAL_ZH in reply
            and not any(word in child_said for word in WE_ZH)):
        return RuleResult(14, RULE_14, "fail", f"invented: calls the story's characters '{YOU_PLURAL_ZH}' (you), "
                                               "though the child never said they were in the story")
    return feeling


def rule_14_machine_never_tells_the_story(
    reply: str,
    child_said: str,
    client: VisionChatClient,
    opening: str = "",
    image: str | None = None,
) -> RuleResult:
    """The moment the machine offers a better version, the child's version dies.

    The judge is shown the opening too. Without it, a reply was refused live
    for "the mice are carrying cannons" — a cannon in the drawing that
    the opening had named a minute earlier — because the judge could only see the
    child's words and the reply, and a thing the studio itself had said looked new.
    """
    if not child_said.strip():
        return RuleResult(14, RULE_14, "skip", "the child said nothing to depart from")
    already = ALREADY_SAID.format(opening=opening.strip()) if opening.strip() else ""
    payload = judge_json(
        client, INVENTION_PROMPT.format(child_said=child_said, reply=reply, already=already)
    )
    # The words must be in the reply, not the child's or the opening's, and not the question (quotes.py).
    theirs = "\n".join(part for part in (child_said, opening) if part.strip())

    def still_new(words: str, _why: str) -> bool:
        try:
            answer = judge_json(client, STORY_RECHECK_PROMPT.format(theirs=theirs, reply=reply, words=words), image)
        except ModelError:
            return True
        return answer.get("new") is not False

    invented = standing(payload.get("invented", []), reply, theirs, questions_are_fine=True,
                        recheck=still_new)
    if not invented:
        return RuleResult(14, RULE_14, "pass", "every piece of story came from the child")
    return RuleResult(14, RULE_14, "fail", f"invented: {'; '.join(invented[:3])}")
