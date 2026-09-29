"""Some rules are red lines. A red line cannot be averaged away.

Found live: four responses in twenty were shown to a child having
failed a rule, including a reply that failed the one rule requiring it to use the
child's words. The requirements call section 3.6 红线 — red lines — and a rule
whose violation is harm cannot be traded against a rule about sentence length.
"""

import pytest

from evalkit.rubric import BEATS, run_rubric
from evalkit.rubric.report import RED_LINES, RubricReport, RuleResult


def report(*rules):
    """A report where the named rules fail and a few others pass."""
    failing = {rule for rule in rules}
    results = [
        RuleResult(rule, f"rule {rule}", "fail" if rule in failing else "pass", "")
        for rule in range(1, 15)
    ]
    return RubricReport(tuple(results))


@pytest.mark.parametrize("rule", sorted(RED_LINES))
def test_each_red_line_refuses_on_its_own(rule):
    assert not report(rule).fit_to_show, f"rule {rule} is a red line and must refuse alone"


@pytest.mark.parametrize("rule", [2, 3, 9, 10, 11, 12])
def test_a_quality_rule_does_not_refuse_on_its_own(rule):
    """These describe how good the response is, not whether it harms."""
    assert report(rule).fit_to_show


def test_the_red_lines_are_the_ones_the_requirements_name():
    """1 talent, 4 guessing, 5 comparison, 6 correction, 7 realism, 8 belittling,
    13 not using the child's words, 14 telling their story for them."""
    assert RED_LINES == {1, 4, 5, 6, 7, 8, 13, 14}


def test_a_clean_report_is_fit_to_show():
    assert report().fit_to_show
    assert report().pass_rate == 1.0


# The gate, which is where it matters ------------------------------------------


class Judge:
    """Answers every judged rule with a pass."""

    def chat(self, prompt, images=(), *, system=None, max_tokens=None):
        from studio.providers.base import ChatResult

        return ChatResult(
            text='{"grounded": ["a", "b"], "presumptive": [], "invented": []}',
            input_tokens=1, output_tokens=1, reasoning_tokens=0,
            cost_usd=0.0, latency_s=0.0, provider="fake", model="fake",
        )


def conversation(tmp_path, **extra):
    from studio.conversation.conversation import Conversation
    from studio.core.ledger import Ledger

    return Conversation(
        "skills/art-feedback/evals/files/dog-sun.png",
        Ledger(tmp_path / "l.jsonl"),
        entrance=extra.pop("entrance", "colour"),
        studio=Judge(),
        director=Judge(),
        **extra,
    )


def test_a_correction_on_the_colour_line_is_refused_however_good_the_rest_is(tmp_path):
    """Section 3.1: correcting on this entrance is harm, with no switch and no
    exception. It used to be one failure among eleven and could be averaged out."""
    talk = conversation(tmp_path)
    ok, reason = talk._gate(
        "I see a red house with a blue door. You should make the roof straighter. "
        "What is happening inside?"
    )
    assert not ok
    assert "red line" in reason
    assert "rule 6" in reason


def test_a_reply_that_did_not_hear_the_child_is_refused(tmp_path):
    """Seen live: shown to the child at 89%."""
    talk = conversation(tmp_path)
    ok, reason = talk._gate("What a lovely picture. Tell me more.", child_said="the dog ran away")
    assert not ok
    assert "red line" in reason


def test_a_long_sentence_is_a_slip_rather_than_a_refusal(tmp_path):
    """Sentence length is quality. One slip must not refuse a warm, specific reply."""
    talk = conversation(tmp_path)
    long_one = (
        "I see a yellow sun with pointy triangle rays and two small figures standing "
        "together on a green line near the bottom of the page holding what looks like "
        "a long stick between them. What is happening between them?"
    )
    ok, reason = talk._gate(long_one)
    assert ok, reason
    assert "rule 10" in reason, "the slip is still recorded, it just does not refuse"


def test_every_beat_the_rubric_knows_about_is_gradeable(tmp_path):
    """The scoping lives in one place now, so every beat must resolve there."""
    for beat in BEATS:
        report = run_rubric(
            "I see red lines. What is happening here?",
            entrance="colour",
            beat=beat,
            image_data_uri="data:,x",
            client=Judge(),
            child_said="the red lines are running" if beat == "reply" else "",
        )
        assert report.scored, f"{beat} scored nothing at all"


def test_the_second_attempt_is_told_what_the_first_one_broke(tmp_path, monkeypatch):
    """Section 6: retry once, then repair, then stop. The repair step existed from
    the first day and no caller ever supplied one, so a refused response was
    rewritten by a model that had not been told what was wrong with it."""
    prompts = []

    class Watching:
        def chat(self, prompt, images=(), *, system=None, max_tokens=None):
            from studio.providers.base import ChatResult

            prompts.append(prompt)
            text = (
                '{"grounded": ["a", "b"], "presumptive": [], "invented": []}'
                if "annotator" in (system or "") or "Here is a child" in prompt
                else "You are so talented. What a beautiful painting."
            )
            return ChatResult(
                text=text, input_tokens=1, output_tokens=1, reasoning_tokens=0,
                cost_usd=0.0, latency_s=0.0, provider="fake", model="fake",
            )

    talk = conversation(tmp_path)
    talk.studio.inner = Watching()
    talk.director.inner = Watching()
    talk.verdict = type("V", (), {"may_proceed": True, "verdict": "allow", "text_found": ()})()
    beat = talk.open()
    assert "talented" not in beat.text and "beautiful" not in beat.text, "flattery must never reach a child"
    # The studio's own look-and-ask stands in, rather than a gate message.
    assert beat.text == "I can see your picture. What is happening in it?"
    told = [p for p in prompts if "Your last attempt was refused" in p]
    assert told, "the repair attempt was written with no idea what was wrong"
    assert "rule 1" in told[0]


def test_an_opening_whose_repair_attempt_meets_a_dead_model_says_so(tmp_path):
    """Two refused openings and then no answer at all is an outage, not a third
    refusal. The teacher was shown the quality-check line for it, which tells
    them to expect a different result from trying again later rather than now."""
    from studio.core.errors import ModelUnavailable

    class DiesOnRepair:
        def chat(self, prompt, images=(), *, system=None, max_tokens=None):
            from studio.providers.base import ChatResult

            if "Your last attempt was refused" in prompt:
                raise ModelUnavailable("nothing is listening")
            # English in a Chinese class: refused by the language check, no judge needed.
            return ChatResult(
                text="I see a red kite over the square. What is holding it up?",
                input_tokens=1, output_tokens=1, reasoning_tokens=0,
                cost_usd=0.0, latency_s=0.0, provider="fake", model="fake",
            )

    talk = conversation(tmp_path, language="zh")
    talk.studio.inner = DiesOnRepair()
    talk.verdict = type("V", (), {"may_proceed": True, "verdict": "allow", "text_found": ()})()
    beat = talk.open()
    assert not beat.ok
    assert beat.reason_code == "model_unavailable"


def test_a_response_in_the_wrong_language_is_refused(tmp_path):
    """Seen live: a Chinese class got an English response and every rule
    passed it, because the grader picks its phrase lists from the text rather
    than from the class."""
    talk = conversation(tmp_path)
    talk.language = "zh"
    ok, reason = talk._gate("I see a pink sky and a green tree. What is the bird doing?")
    assert not ok
    assert "zh" in reason and "en" in reason


def test_the_right_language_passes(tmp_path):
    talk = conversation(tmp_path)
    talk.language = "zh"
    assert talk._wrong_language("我看到粉色的天空和一棵绿色的树。") == ""
    talk.language = "en"
    assert talk._wrong_language("I see a pink sky and a green tree.") == ""


@pytest.mark.parametrize("beat", ["opening", "reply", "rung"])
def test_every_beat_gets_the_repair_step(beat, tmp_path):
    """The reply needs it most: rule 13 is a red line there, so a reply that
    missed the child's words is refused, and a blind second attempt misses them
    again. A live sketch class failed twice and stopped, because
    only the opening had been given the hook."""
    prompts = []

    class Watching:
        def chat(self, prompt, images=(), *, system=None, max_tokens=None):
            from studio.providers.base import ChatResult

            prompts.append(prompt)
            judged = "Here is a child" in prompt or "A child described" in prompt
            return ChatResult(
                text=('{"grounded": [], "presumptive": [], "invented": []}' if judged
                      else "You are so talented."),
                input_tokens=1, output_tokens=1, reasoning_tokens=0,
                cost_usd=0.0, latency_s=0.0, provider="fake", model="fake",
            )

    talk = conversation(tmp_path)
    talk.studio.inner = Watching()
    talk.director.inner = Watching()
    talk.verdict = type("V", (), {"may_proceed": True, "verdict": "allow", "text_found": ()})()
    talk.opening = "I see a yellow sun. What is happening?"
    if beat == "opening":
        talk.open()
    elif beat == "reply":
        talk.reply("the dog ran away")
    else:
        talk.climb(2)
    assert any("Your last attempt was refused" in p for p in prompts), (
        f"the {beat} was rewritten with no idea what was wrong with it"
    )


@pytest.mark.parametrize("beat", ["opening", "reply", "rung"])
def test_every_beat_shows_the_naming_judge_the_teachers_line(beat, tmp_path):
    """The rung gate used to call the rubric without the lesson at all. A smaller
    question about a kite in a kite class is no more a guess than an opening is."""
    naming = []

    class Watching:
        def chat(self, prompt, images=(), *, system=None, max_tokens=None):
            from studio.providers.base import ChatResult

            if "real-world IDENTITY" in prompt:
                naming.append(prompt)
            judged = "Here is a child" in prompt or "A child described" in prompt or "A teacher set" in prompt
            # A line that crosses no red line on its own: one that did (it was "You are so talented.") is now
            # refused before any judge is asked, and this test is about what the judges are told.
            return ChatResult(
                text=('{"grounded": [], "presumptive": [], "invented": [], "connected": true}' if judged
                      else "The kite is going to the moon over the square. What is holding it up?"),
                input_tokens=1, output_tokens=1, reasoning_tokens=0,
                cost_usd=0.0, latency_s=0.0, provider="fake", model="fake",
            )

    talk = conversation(tmp_path, lesson_intent="flying kites in the square")
    talk.studio.inner = Watching()
    talk.director.inner = Watching()
    talk.verdict = type("V", (), {"may_proceed": True, "verdict": "allow", "text_found": ()})()
    talk.opening = "I see a red kite. What is happening?"
    if beat == "opening":
        talk.open()
    elif beat == "reply":
        talk.reply("the kite is going to the moon")
    else:
        talk.climb(2)
    assert naming, f"the {beat} was never shown to the naming judge"
    assert all("flying kites in the square" in prompt for prompt in naming), (
        f"the {beat}'s naming judge was not told what the class was drawing"
    )


def test_a_refusal_hands_back_the_evidence_and_not_only_a_number(conversation_gate):
    """The retry is written by a model that can only read what the reason says.

    `RuleResult.evidence` exists so a failure tells the author what to change, and
    the gate reduced it to "red line: rule 14". The writer is looking at a reply
    prompt whose own numbered rules stop at 7, and rubric rule 4 is "presumes
    nothing" while prompt rule 4 is "give something back" — so the number named a
    different rule than the one it was reading, and pointed the second attempt the
    wrong way. Three live attempts crossed the same red line and the
    child was shown the hiccup line instead of an answer.
    """
    ok, reason = conversation_gate(report_with_evidence())
    assert not ok
    assert "rule 14" in reason
    assert "invented: a lantern nobody mentioned" in reason


def report_with_evidence():
    results = [RuleResult(rule, f"rule {rule}", "pass", "") for rule in range(1, 14)]
    results.append(RuleResult(14, "the machine never tells the story", "fail",
                              "invented: a lantern nobody mentioned"))
    return RubricReport(tuple(results))


@pytest.fixture
def conversation_gate():
    from studio.conversation.conversation import Conversation
    return lambda report: Conversation._score(SimpleGate(), report)


class SimpleGate:
    """Only _score is under test; it reads nothing else off the conversation."""
    _report = None
