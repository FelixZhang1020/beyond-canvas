from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Literal

from evalkit.rubric.assisted import (RULE_3, RULE_4, RULE_12_REPLY, rule_3_grounded_details,
                                    rule_4_non_presumptive, rule_12_followup)
from evalkit.rubric.lexical import (
    RULE_6,
    RULE_7,
    rule_1_process_not_person,
    rule_5_no_comparison,
    rule_6_no_correction,
    rule_7_no_realism_policing,
    rule_8_no_diminishing,
)
from evalkit.rubric.loop import (
    RULE_11,
    RULE_12,
    RULE_12_SKETCH,
    RULE_13,
    RULE_14,
    rule_11_serves_the_lesson,
    rule_12_question_enters_the_process,
    rule_12_question_enters_the_world,
    rule_13_reply_uses_the_childs_words,
    rule_14_machine_never_tells_the_story,
    rule_14_without_a_model,
)
from evalkit.rubric.report import RED_LINES, RubricReport, RuleResult
from evalkit.rubric.structural import (
    RULE_2,
    RULE_9,
    rule_2_observation_opener,
    rule_9_ends_with_open_question,
    rule_10_short_sentences,
)
from studio.core.errors import ModelError
from studio.core.metering import carried
from studio.providers.base import VisionChatClient

__all__ = [
    "BEATS",
    "ENTRANCES",
    "Beat",
    "Entrance",
    "RED_LINES",
    "RubricReport",
    "RuleResult",
    "run_rubric",
]

# The teacher picks one when the class starts. There is no automatic detection,
# because a coloured-pencil study would fool a colour test and the lesson
# already knows which kind of class it is; so there is no default either.
Entrance = Literal["sketch", "colour"]
ENTRANCES: tuple[Entrance, ...] = ("sketch", "colour")

# Which of the four things the machine says this text is. The rules that apply
# differ, and two of the four used to have their scoping hand-built
# elsewhere, which is how a rung came to be graded by a list that omitted the one
# rule the reference writes about rungs. There is one scoping table and it is here.
Beat = Literal["opening", "reply", "rung"]
BEATS: tuple[Beat, ...] = ("opening", "reply", "rung")


def run_rubric(
    text: str,
    *,
    entrance: Entrance,
    beat: Beat | None = None,
    image_data_uri: str | None = None,
    client: VisionChatClient | None = None,
    child_said: str = "",
    lesson_intent: str = "",
    opening: str = "",
    dialogue_context: str = "",
    earlier_child_words: str = "",
    stop_at_local_red_line: bool = False,
) -> RubricReport:
    """Score what the machine said, and the loop it opened.

    `text` is the machine's line. `entrance` is which kind of class the teacher
    chose, sketch or colour, and decides which rules apply. `child_said` is
    what the child answered, when they answered at all — supply it to grade the
    fourth beat, where the reply has to use their words.

    `lesson_intent` is what the teacher said this class was teaching, entered
    once at the start rather than per child.

    Rules skip rather than fail whenever they cannot honestly apply, and a skip
    is excluded from the score rather than counted: rules 3 and 4 without an
    image or a client, rules 13 and 14 when the child said nothing, rule 11
    without a lesson intent, rules 6 and 7 on the sketch entrance, and rules 2,
    9 and 12 when this text is a reply rather than an opening. In a class of
    twenty not every child speaks, most lessons will not have an intent typed
    in, and neither is a failure of the machine.

    A reply in a class carries the conversation so far. `dialogue_context` is the
    recent turns, and with it rule 12 judges the reply's question, if it asks one,
    against them: a reply with no question is a child hearing their story back,
    and is not asked about. `earlier_child_words` is what the child said before
    this answer; rules 4 and 14 read it with the answer, because a name or an
    event the child gave three turns ago is theirs, not the machine's invention.

    `stop_at_local_red_line` is for a class, where a child is waiting: when a rule checked here without
    a model has already crossed a red line, the judges are not asked, and their rules come back as
    skips. The line is refused either way, and each judge takes 20-60 s (measured on Step 3.7
    Flash at high effort), so the rewrite starts that much sooner. A benchmark leaves it off and every
    rule is judged.
    """
    if entrance not in ENTRANCES:
        raise ValueError(
            f"entrance must be one of {ENTRANCES}, not {entrance!r}; the teacher picks it by hand"
        )
    if beat is None:
        beat = "reply" if child_said.strip() else "opening"
    if beat not in BEATS:
        raise ValueError(f"beat must be one of {BEATS}, not {beat!r}")
    is_reply = beat == "reply"
    is_rung = beat == "rung"
    # Rules that cost a model call. Collected, then run together at the end.
    judged: list = []

    # Rules that hold whatever the machine is saying, on either entrance.
    results = [
        rule_1_process_not_person(text),
        rule_5_no_comparison(text),
        rule_8_no_diminishing(text),
        rule_10_short_sentences(text),
    ]
    results += _entrance_rules(text, entrance)
    heard = rule_13_reply_uses_the_childs_words(text, child_said)
    # Everything the child has said about this drawing, oldest first: theirs to name and to tell.
    child_words = "\n".join(part for part in (earlier_child_words.strip(), child_said.strip()) if part)
    # Only on an answer: a rung may speak as a character, and a character may say how it feels.
    feeling = rule_14_without_a_model(text, child_words if child_said.strip() else "", opening)
    # Every rule that crosses a red line without a model is known by now. In a class, once one has, no
    # model is asked at all: not the pooled judges, and not rule 12's, which runs in line below and
    # without a client decides by its marker list alone (code review).
    stopped = stop_at_local_red_line and any(r.status == "fail" and r.rule in RED_LINES
                                             for r in (*results, heard, feeling))
    results += _opening_rules(text, entrance, beat, None if stopped else client)
    if is_reply and dialogue_context.strip():
        results = [result for result in results if result.rule != 12]
        if not text.rstrip().endswith(("?", "？")):
            results.append(RuleResult(12, RULE_12_REPLY, "skip", "no question: the reply gives the child's story back"))
        elif client is None:
            results.append(RuleResult(12, RULE_12_REPLY, "skip", "no client to judge the question"))
        else:
            judged.append((12, RULE_12_REPLY,
                           lambda: _or_skip_followup(text, dialogue_context, child_said, client)))
    if not (image_data_uri and client is not None):
        reason = "no image or client supplied"
        results.append(RuleResult(3, RULE_3, "skip", reason))
        results.append(RuleResult(4, RULE_4, "skip", reason))
    else:
        # Rule 3 asks for two details the drawing actually shows, so that warmth
        # cannot be generic. A reply is not generic — rule 13 checks it against
        # the child's own words — and section 5a wants it short and mostly a
        # question. The judge is told to ignore questions, so a reply that is one
        # scores zero details however specific it is. A live run
        # refused "Is that the tree with the brown trunk and green leaves?" on
        # that basis, twice.
        if is_reply:
            results.append(
                RuleResult(3, RULE_3, "skip", "a reply is grounded in the child's words, by rule 13")
            )
        elif is_rung:
            # A rung is one short question and the grounding judge is told to
            # ignore questions, so it can only ever score zero details.
            results.append(RuleResult(3, RULE_3, "skip", "a rung is a question, not a description"))
        else:
            judged.append((3, RULE_3,
                lambda: _or_skip(3, RULE_3, rule_3_grounded_details, text, image_data_uri, client)
            ))
        judged.append((4, RULE_4,
            lambda: _or_skip(
                4, RULE_4, rule_4_non_presumptive, text, image_data_uri, client,
                child_said=child_words, lesson_intent=lesson_intent, opening=opening,
            )
        ))

    if is_reply or is_rung:
        # A live run in Chinese: a correct reply that used the child's
        # own words was marked down for not connecting to warm and cool colours.
        # Section 5a asks beat four to use the child's words and get out of the
        # way, not to steer back to the lesson plan. Rule 11 reads the FEEDBACK.
        results.append(
            RuleResult(11, RULE_11, "skip", f"a {beat} answers the child, not the lesson")
        )
    elif not lesson_intent.strip():
        results.append(RuleResult(11, RULE_11, "skip", "no lesson intent was supplied"))
    elif client is None:
        results.append(RuleResult(11, RULE_11, "skip", "no client to judge the connection"))
    else:
        judged.append((11, RULE_11, lambda: _or_skip_lesson(text, lesson_intent, client)))

    results.append(heard)
    if not child_said.strip():
        results.append(RuleResult(14, RULE_14, "skip", "the child said nothing to depart from"))
    elif feeling.status == "fail":
        results.append(feeling)   # a stated feeling needs no judge to refuse it
    elif client is None:
        results.append(RuleResult(14, RULE_14, "skip", "no client to judge invention with"))
    else:
        judged.append((14, RULE_14,
            # The drawing goes to the recheck only: once "the cabin with its light on" was refused as
            # invented about a drawing whose cabin plainly has a lit window, by a judge that could not see it.
            lambda: _or_skip_pair(rule_14_machine_never_tells_the_story, text, child_words, client, opening,
                                  image_data_uri)
        ))

    # Every judged rule is one model call, they do not depend on each other, and
    # they were run one after another. Once a single opening took five
    # minutes fifty-six seconds, most of it waiting in that queue. Running them
    # together costs the slowest instead of the sum.
    if judged and stopped:
        results.extend(RuleResult(rule, name, "skip", "not asked: a red line had already failed without a model")
                       for rule, name, _ in judged)
    elif judged:
        with ThreadPoolExecutor(max_workers=len(judged)) as pool:
            # Each judge's spending is counted for the request that asked (studio/core/metering.py).
            results.extend(pool.map(lambda call: call(), [carried(entry[2]) for entry in judged]))
    return RubricReport(tuple(sorted(results, key=lambda result: result.rule)))


def _entrance_rules(text: str, entrance: Entrance) -> list[RuleResult]:
    """Rules 6 and 7 hold on the colour entrance only.

    On the colour entrance correction is harm and rule 6 is absolute: no
    switch, no age condition, no exceptions. A plaster-cast study is an
    observational exercise, so on the sketch entrance a correction is expected
    and proportion and likeness are the subject rather than a judgement. Rule
    6's scope is settled in section 5a; rule 7 was scoped the same way with the
    operator, because its phrase list is made of the very words a
    sketch critique is made of.
    """
    if entrance == "colour":
        return [rule_6_no_correction(text), rule_7_no_realism_policing(text)]
    return [
        RuleResult(6, RULE_6, "skip", "the sketch entrance expects correction, given as something to try"),
        RuleResult(7, RULE_7, "skip", "a sketch is an observational study; proportion is its subject"),
    ]


def _opening_rules(text: str, entrance: Entrance, beat: Beat, client=None) -> list[RuleResult]:
    """Rules 2, 9 and 12 describe the shape of an OPENING.

    Begin with a plain observation, end with one open question, and make that
    question reach inside the picture — or, on the sketch entrance, into the
    child's own process, since a plaster cast has no story to enter.

    A REPLY is a different artifact and section 5a asks the opposite of it: one
    question at most, none at all once the child has said something whole, and
    stop talking once they start. Grading a reply against opening rules marks
    the machine down for obeying the spec, which a live run showed
    it doing.

    A RUNG keeps rule 12 and loses the other two. It is not an opening, so rule 2
    does not apply; and rule 9 must not apply, because the second rung is
    deliberately a choice between two things — "is he just arriving, or about to
    leave?" — which is a closed question by rule 9's definition and the whole
    reason the ladder works on a child who cannot invent. Rule 12 stays because
    section 5a's strongest rung IS rule 12's strongest form: a character in the
    picture asking the child directly.
    """
    if entrance == "colour":
        name_12, rule_12 = RULE_12, rule_12_question_enters_the_world
    else:
        name_12, rule_12 = RULE_12_SKETCH, rule_12_question_enters_the_process

    # Rule 12's judge reads the question only, so it needs no image — but without a
    # client it never runs, and the marker list decides alone as it always did.
    #
    # It runs HERE, in line, rather than in the pool below with the other judged rules,
    # and that is a deliberate cost: the markers answer 4 questions in 5 for nothing
    # (measured: 15 misses in 74), so the fifth adds one round trip to that
    # attempt rather than to every one. Moving it into the pool would hide the latency
    # behind the other judges; it would also make the order of a beat's model calls
    # depend on thread scheduling, which the scripted tests read as a sequence.
    def check_12(question: str) -> RuleResult:
        return rule_12(question, client=client)
    checks = (
        (2, RULE_2, rule_2_observation_opener),
        (9, RULE_9, rule_9_ends_with_open_question),
        (12, name_12, check_12),
    )
    if beat == "opening":
        return [check(text) for _, _, check in checks]
    if beat == "rung":
        return [
            RuleResult(2, RULE_2, "skip", "a rung answers nothing; it asks"),
            RuleResult(9, RULE_9, "skip", "the second rung is deliberately a choice of two"),
            check_12(text),
        ]
    return [
        RuleResult(number, name, "skip", "this is a reply, not an opening")
        for number, name, _ in checks
    ]


def _or_skip_lesson(text: str, lesson_intent: str, client) -> RuleResult:
    """Rule 11's judge gets the same tolerance as every other judge."""
    try:
        return rule_11_serves_the_lesson(text, lesson_intent, client)
    except ModelError as error:
        return RuleResult(11, RULE_11, "skip", f"judge unavailable: {error}")


def _or_skip_pair(check, reply: str, child_said: str, client, opening: str = "",
                  image: str | None = None) -> RuleResult:
    """Rule 14's judge gets the same tolerance as rules 3 and 4."""
    try:
        return check(reply, child_said, client, opening=opening, image=image)
    except ModelError as error:
        return RuleResult(14, RULE_14, "skip", f"judge unavailable: {error}")


def _or_skip_followup(text: str, dialogue_context: str, child_said: str, client) -> RuleResult:
    """Rule 12's follow-up judge gets the same tolerance as every other judge."""
    try:
        return rule_12_followup(text, dialogue_context, child_said, client)
    except ModelError as error:
        return RuleResult(12, RULE_12_REPLY, "skip", f"judge unavailable: {error}")


def _or_skip(number, name, check, text, image, client, **extra) -> RuleResult:
    """Run an assisted rule, recording a skip rather than dying if the judge fails.

    A judge's token cost has a long tail, so one unlucky call must not abort a
    whole benchmark. Skipping is honest in a way that passing would not be:
    RubricReport.scored excludes skips, so an unmeasured rule lowers the number
    of rules scored instead of inflating the score.
    """
    try:
        return check(text, image, client, **extra)
    except ModelError as error:
        return RuleResult(number, name, "skip", f"judge unavailable: {error}")
