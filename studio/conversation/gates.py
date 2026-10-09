"""What makes a beat's text acceptable, once the model has answered.

Split out of conversation.py to bring that file back under the
size limit. The rules are the same rules and are moved unchanged; each one still
reads the conversation it is gating through `self`. They belong apart because
gating is a different job from holding a drawing open: one decides what may be
shown to a child, the other remembers what has already been said to them.

The rubric floor and the strict-attempt count live here because they are the
numbers the gates decide by, and `Unreadable` because it exists so that a gate
can refuse with a reason instead of the harness raising on a model's answer.
"""

from __future__ import annotations

import itertools
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from evalkit.rubric import run_rubric
from evalkit.rubric.assisted import judge_json
from evalkit.rubric.report import RubricReport
from evalkit.rubric.structural import rule_9_ends_with_open_question
from evalkit.rubric.text import detect_lang
from studio.conversation.words import asked_in, bare_question
from studio.core.errors import ModelError
from studio.core.harness import RETRY_ONCE
from studio.core.metering import carried

# He, she and it in the child's answer, by code point, and in English: the answer is then about whoever the
# question asked about, and the reply must say it about that one (_gives_it_away). Not the he of "other" or
# "guitar" (the two characters before it), and not "they" in either language, which may be anyone.
_HE_SHE_IT_ZH = ("(?<![" + chr(0x5176) + chr(0x5409) + "])[" + "".join(map(chr, (0x4ED6, 0x5979, 0x5B83)))
                 + "](?!" + chr(0x4EEC) + ")")
HE_SHE_IT = re.compile(_HE_SHE_IT_ZH + "|\\b(he|she|it)\\b", re.IGNORECASE)
WHO_SAID_IT = Path(__file__).parents[1] / "prompts" / "who-said-it.txt"
GIVEN_AWAY = ("it gives what the child said about he, she or it to a different character; keep it with the one the "
              "question asked about")
# The who-check runs beside the rubric's own judges, so it adds little to a reply's wait.
_BESIDE = ThreadPoolExecutor(max_workers=4, thread_name_prefix="who-said-it")

# What the quality rules must average, once no red line has been crossed. At
# twelve scored rules this tolerates two slips and refuses a third; the old 0.82
# claimed to allow two and allowed one, because 9/11 is 0.818.
RUBRIC_FLOOR = 0.80

# The follow-up judge's issues that put something into the child's story (FOLLOWUP_PROMPT's own words):
# an event or feeling never given, a reason of the machine's own, who did what turned round. These are
# refused on every attempt; the rest are a question to taste, and buy one rewrite (code review).
# When every attempt is refused the child hears their own words back instead.
INVENTED_PREMISE = ("never gave", "as if it happened", "motive", "purpose", "reverses", "who does what",
                    "as already done")

# How many opening attempts are graded strictly — every rule must pass — before
# the last one is allowed through on the average. One more than the harness's
# retry count, so the two ordinary attempts are strict and the repair attempt,
# which is the last chance to say anything at all, is not.
STRICT_ATTEMPTS = RETRY_ONCE + 1


@dataclass(frozen=True)
class Unreadable:
    """A model answered, and what it said could not be read.

    Carried through the gate rather than raised, so the attempt is recorded and
    the child is told a gate failed rather than that the machine is unreachable.
    """

    why: str


class Gates:
    """The gates a Conversation applies to what it has just written.

    A mixin rather than a collaborator on purpose: every gate reads the
    conversation's own entrance, language and rubric report, and nothing outside
    a conversation has ever needed to run one.
    """

    # The gates ---------------------------------------------------------------

    def _opening_gate(self):
        """Send the opening back for ANY failed rule, until the last attempt.

        The average used to decide this, so an opening that failed one rule and
        passed the rest was shown to the child unchanged. In a measured run,
        that is how 「它看起来像在笑，还是在吓人？」 reached a child — a closed
        question, which rule 9 caught and the 80% floor then forgave. On the beat
        whose entire purpose is to make a child talk, a question they can answer
        in one word is the feature failing, not a blemish on it.

        Strict for the first attempts, lenient for the last. Requirement 06 says
        每一段都可以掉，但它永远交得出东西 — the line always delivers something —
        so a rule that is not a red line must not end in a child being shown a
        gate message. It buys a rewrite, and if the rewrite is no better the
        first-class answer is still shown. Red lines are unaffected: `_score`
        refuses those on every attempt, including the last.

        The counter lives in a closure rather than on the conversation because it
        belongs to one beat: a second opening on a second drawing starts again.

        Two changes, after a teacher got the gate message for a first comment. Every
        attempt counts, so the last is lenient however the earlier ones failed; it still has to meet
        the floor, and when it does not the studio's own look-and-ask stands in (chat_beats.py), so
        requirement 06 holds without showing a weak attempt (showing one below the floor put
        "you are so talented" in front of a child in test_session, found soon after). And
        rule 11 (serves the lesson) buys no rewrite: the class's lesson was solids and shading, the
        drawing a zoo, and no honest comment could connect them, so three attempts were spent forcing
        a link. It is still scored.
        """
        attempts = itertools.count(1)

        def gate(text: str) -> tuple[bool, str]:
            last = next(attempts) > STRICT_ATTEMPTS
            self._report = None
            ok, reason = self._gate(text)
            if not ok:
                return ok, reason
            report = self._report
            failures = [failure for failure in (report.failures if report is not None else ()) if failure.rule != 11]
            if failures and not last:
                broken = ", ".join(f"rule {failure.rule}" for failure in failures)
                return False, broken
            return True, reason

        return gate

    def _reply_gate(self, child_said: str, dialogue: str, earlier_child_words: str, asked: tuple[str, ...] = (),
                    answering: str = ""):
        """A reply is read against the drawing and against everything the child has said.

        Its question, when it asks one, is judged against the conversation so far: rule 12
        in its follow-up form, whose failures are a question that quizzes the child on their
        own story, repeats one, or walks past what they just revealed. That judge can send
        back ONE attempt, which costs one more round of writing and judging; the next attempt
        is shown even if it still dislikes its question, because a child who has just spoken
        must hear something back. The rounds that felt broken were the ones
        where the gate, re-judging a question to taste, refused every attempt and the child
        got the hiccup line instead of an answer. Red lines still refuse on every attempt.

        The counter lives in a closure because it belongs to one reply, as the opening's does.

        Only a problem the judge can point at buys that attempt: a question already answered, a
        repeat, an invented reason. "It skips the most meaningful new thing" is scored and buys
        nothing, because Qwen, the judge, says it of nearly every reply: in a probe
        of section 5a's conversation it sent back eight turns in eight, good questions
        among them, and each cost a round of writing and judging without a better question after.

        A question the companion already asked about this drawing, word for word (`asked`), is refused
        on every attempt and before any judge reads it, in both entrances: the follow-up judge reads
        colour conversations only, and once a sketch class heard the same question two rounds
        running, twice. When every attempt asks it again, the child hears their own words back instead.

        When a colour child answers the companion's last question (`answering`, the whole turn that asked it) with
        he, she or it, a judge is also asked, beside the rubric, whether the reply said it about the one the question
        named (studio/prompts/who-said-it.txt). The castle class: "he runs down to shut the gate", about
        the soldier the question named, came back as the mouse soldiers. It cannot see a wrong subject when the child
        named no one, which the reply prompt's own rule 8 keeps right instead. A judge that fails, or cannot tell,
        refuses nothing (docs/measured/who-said-it.md).
        """
        pushed_back: list[str] = []
        before = {bare_question(question) for question in asked}

        def gate(text: str) -> tuple[bool, str]:
            self._report = None   # this reply's report, or none: never the last reply's
            again = asked_in(text)
            if again and bare_question(again) in before:
                # A fixed sentence: the reason reaches the ledger, which never carries the conversation's words, and
                # the writer already sees its earlier questions in the conversation it is given.
                return False, "its question repeats one already asked about this drawing; ask something new, or nothing"
            who = self._who_check(answering, child_said, text)
            ok, reason = self._gate(text, child_said, dialogue_context=dialogue,
                                    earlier_child_words=earlier_child_words)
            if who is not None and not ok:
                who.cancel()
            elif who is not None and who.result():
                return False, GIVEN_AWAY
            if not ok or self._report is None:
                return ok, reason
            followup = next((result for result in self._report.results
                             if result.rule == 12 and result.status == "fail"), None)
            pointed = [issue for issue in (followup.evidence.split("; ") if followup else ())
                       if "meaningful new" not in issue.lower()]
            invented = [issue for issue in pointed if any(mark in issue.lower() for mark in INVENTED_PREMISE)]
            if invented:
                return False, f"its question puts something into the child's story: {'; '.join(invented)}"
            if pointed and not pushed_back:
                pushed_back.append(followup.evidence)
                return False, f"its question does not take the child's story further: {'; '.join(pointed)}"
            return True, reason

        return gate

    def _who_check(self, answering: str, child_said: str, reply: str):
        """The who-said-it judge, started beside the rubric; none when there is nothing for it to decide."""
        if self.entrance != "colour" or not answering or not HE_SHE_IT.search(child_said):
            return None
        return _BESIDE.submit(carried(lambda: self._gives_it_away(answering, child_said, reply)))

    def _gives_it_away(self, asked: str, child_said: str, reply: str) -> bool:
        """Whether the reply gives what the child said about he, she or it to a different character."""
        try:
            answer = judge_json(self.director, WHO_SAID_IT.read_text(encoding="utf-8").format(
                asked=asked, child_said=child_said, reply=reply))
        except ModelError:
            return False
        return isinstance(answer, dict) and answer.get("same") is False

    def _gate(self, text: str, child_said: str = "", *, dialogue_context: str = "",
              earlier_child_words: str = "") -> tuple[bool, str]:
        wrong = self._wrong_language(text)
        if wrong:
            return False, wrong
        if child_said and self.entrance == "colour" and text.rstrip().endswith(("?", "？")):
            # A reply may end without a question, but one that asks must leave the answer to the child:
            # open, not yes-or-no and not a choice of two. Driving the Spark, five replies
            # in five ended in 是不是 or 吗, three of them guessing at a reason the child never gave, and
            # the question's judge passed them; this rule is exact where that judge was lenient.
            question = rule_9_ends_with_open_question(text)
            if question.status != "pass":
                return False, f"its question must be open, never answered yes or no: {question.evidence}"
        report = run_rubric(
            text,
            entrance=self.entrance,
            image_data_uri=self.image,
            dialogue_context=dialogue_context,
            earlier_child_words=earlier_child_words,
            client=self.director,
            child_said=child_said,
            lesson_intent=self.lesson_intent,
            # Rule 14's judge must know what the studio itself said before the
            # child spoke, or it refuses the reply for repeating it.
            opening=self.opening,
            stop_at_local_red_line=True,   # a child is waiting: rewrite now, not after the judges
        )
        return self._score(report)

    def _wrong_language(self, text: str) -> str:
        """Whether this is even in the language the class is being taught in.

        Found by running real drawings: the third painting in a
        Chinese class came back entirely in English, and every rule passed it,
        because the grader picks its phrase lists by looking at the text rather
        than by comparing it to the class. A teacher reading English to a child
        who cannot read it is not a slip on a quality rule; it is a response
        that cannot be delivered. The repair step is told, so the second attempt
        knows what to change.
        """
        if not text.strip():
            return ""
        if detect_lang(text) == self.language:
            return ""
        return f"answered in {detect_lang(text)}, but this class is in {self.language}"

    def _rung_gate(self, text: str, earlier_child_words: str = "") -> tuple[bool, str]:
        """A rung is graded by the rubric, told that it is a rung.

        It used to be graded by a list assembled here by hand, which omitted
        rule 12 — the one rule the reference actually writes about rungs, whose
        strongest form IS the third rung — and applied a floor computed over four
        rules, so a single failure refused the child a smaller question. The
        scoping now lives in the rubric with every other beat's.
        """
        wrong = self._wrong_language(text)
        if wrong:
            return False, wrong
        return self._score(
            run_rubric(
                text,
                entrance=self.entrance,
                beat="rung",
                image_data_uri=self.image,
                # A character the child has named is theirs to speak as, whatever the drawing shows.
                earlier_child_words=earlier_child_words,
                client=self.director,
                # Rule 11 stays skipped on a rung; the naming judge still needs the lesson, and the
                # opening, whose names for the shapes it already checked.
                lesson_intent=self.lesson_intent,
                opening=self.opening,
                stop_at_local_red_line=True,
            )
        )

    def _motion_gate(self, plan, child_said: str) -> tuple[bool, str]:
        """Deterministic, and nothing else, until a rule is written for motion.

        Two judged rules were tried here and both were the wrong rule. Rule 4
        protects what a child HEARS, and a layer name is never heard: fed bare
        noun phrases it refused a correct plan for calling a tree a tree. Rule 14
        forbids the machine telling the story, and a movement is not story
        content: it then refused a plan whose motion was exactly what the child
        had asked for, because "the figures drift" is not a phrase the child
        said. Both failures were live.

        Borrowing a rule written for sentences to judge a movement has failed
        twice, so it stops. The deterministic checks work, they are what section
        5b claims as choreography's advantage over video, and they cost nothing —
        which is the other thing section 5b asks for.
        """
        if isinstance(plan, Unreadable):
            return False, f"the plan could not be read: {plan.why}"
        broken = self.motion.problems(plan)
        if broken:
            return False, "; ".join(broken[:3])
        return True, f"{len(plan.layers)} layers over {plan.duration_s}s"

    def _score(self, report: RubricReport) -> tuple[bool, str]:
        """A red line refuses on its own; everything else averages.

        Every rule used to be averaged, so a reply that failed the one
        rule requiring it to use the child's words was still shown to the child.
        The requirements call those rules red lines, and a red line that can be
        averaged away is not one.

        The reason carries the evidence as well as the number, because the reason
        is the whole of what the retry gets to read. A bare "red line: rule 14"
        was worse than saying nothing: the reply prompt's own numbered rules stop
        at 7, so 14 named nothing the writer could see, and rubric rule 4
        ("presumes nothing") is prompt rule 4 ("give something back") — so being
        told it broke rule 4 sent the second attempt further in the direction that
        had just failed. In one live run the attempt, the retry and the repair
        all crossed the same red line, and the child was shown the hiccup line.
        """
        self._report = report
        broken = ", ".join(f"rule {failure.rule}" for failure in report.failures)
        if not report.fit_to_show:
            crossed = ", ".join(
                f"rule {line.rule} ({line.name}){f': {line.evidence}' if line.evidence else ''}"
                for line in report.crossed
            )
            return False, f"red line: {crossed}"
        return report.pass_rate >= RUBRIC_FLOOR, f"{report.pass_rate:.0%} ({broken or 'clean'})"
