"""The opening is sent back for any failed rule, and still always delivers.

The opening used to be gated on an average: an 80% floor, plus red
lines. So an opening that failed exactly one rule and passed the rest was shown
to the child unchanged, and that is how a closed question survived — rule 9
caught 「它看起来像在笑，还是在吓人？」 and the floor forgave it.

Two properties are protected here and they pull in opposite directions. Any
failed rule must buy a rewrite. And a rule that is not a red line must never end
in the child seeing a gate message instead of a reply, because requirement 06
says 每一段都可以掉，但它永远交得出东西.
"""

import pytest

from studio.conversation.conversation import STRICT_ATTEMPTS, Conversation


class _Report:
    """A rubric verdict, without the rubric."""

    def __init__(self, failures, crossed=(), pass_rate=1.0):
        self.failures = failures
        self.crossed = crossed
        self.pass_rate = pass_rate
        self.fit_to_show = not crossed


class _Rule:
    def __init__(self, rule):
        self.rule = rule


def gate_over(reports):
    """An opening gate whose underlying rubric returns these reports in order."""
    conversation = Conversation.__new__(Conversation)
    remaining = list(reports)

    def scored(text, child_said=""):
        conversation._report = remaining.pop(0)
        report = conversation._report
        if not report.fit_to_show:
            return False, "red line"
        return report.pass_rate >= 0.80, "scored"

    conversation._gate = scored
    return conversation._opening_gate()


def test_a_single_failed_rule_sends_the_opening_back():
    """The whole point. One rule, well above the floor, still buys a rewrite."""
    gate = gate_over([_Report(failures=[_Rule(9)], pass_rate=0.95)])
    ok, reason = gate("一个封闭问题吗？")
    assert not ok
    assert "rule 9" in reason


def test_a_clean_opening_passes_on_the_first_attempt():
    gate = gate_over([_Report(failures=[], pass_rate=1.0)])
    ok, _ = gate("干净的开场。")
    assert ok


def test_the_last_attempt_is_shown_even_with_a_rule_still_failing():
    """A closed question is worse than a gate message only until it is the last
    thing on offer. Then the child gets the reply."""
    reports = [_Report(failures=[_Rule(9)], pass_rate=0.95) for _ in range(STRICT_ATTEMPTS + 1)]
    gate = gate_over(reports)
    for attempt in range(STRICT_ATTEMPTS):
        ok, _ = gate("还是封闭的吗？")
        assert not ok, f"attempt {attempt + 1} should have been sent back"
    ok, _ = gate("还是封闭的吗？")
    assert ok, "the last attempt must be delivered rather than refused"


def test_a_red_line_is_refused_on_every_attempt_including_the_last():
    """Leniency is for quality rules. A red line is not a quality rule."""
    reports = [_Report(failures=[_Rule(4)], crossed=[_Rule(4)]) for _ in range(STRICT_ATTEMPTS + 2)]
    gate = gate_over(reports)
    for _ in range(STRICT_ATTEMPTS + 2):
        ok, reason = gate("凭空编出来的细节。")
        assert not ok
        assert "red line" in reason


def test_each_beat_counts_its_own_attempts():
    """A second drawing starts strict again, rather than inheriting leniency."""
    first = gate_over([_Report(failures=[_Rule(9)], pass_rate=0.95)])
    assert not first("一")[0]
    second = gate_over([_Report(failures=[_Rule(9)], pass_rate=0.95)])
    assert not second("二")[0], "the counter leaked between beats"


@pytest.mark.parametrize("rate", [0.5, 0.79])
def test_a_low_average_still_fails_before_the_rule_check(rate):
    gate = gate_over([_Report(failures=[_Rule(2), _Rule(9)], pass_rate=rate)])
    assert not gate("勉强及格。")[0]


def test_a_last_attempt_below_the_floor_is_still_refused_so_the_studios_own_line_stands_in():
    """Showing it put "you are so talented" in front of a child (test_session); the
    conversation gives the studio's own look-and-ask instead (test_classroom)."""
    reports = [_Report(failures=[_Rule(2), _Rule(9)], pass_rate=0.64) for _ in range(STRICT_ATTEMPTS + 1)]
    gate = gate_over(reports)
    for _ in range(STRICT_ATTEMPTS + 1):
        assert not gate("你真有天赋！")[0]


def test_every_attempt_counts_so_the_last_is_lenient_whatever_came_before():
    """Two attempts under the floor, then one above it with a rule failing: the third is shown."""
    reports = [_Report(failures=[_Rule(2), _Rule(9)], pass_rate=0.6)] * STRICT_ATTEMPTS
    reports += [_Report(failures=[_Rule(9)], pass_rate=0.92)]
    gate = gate_over(reports)
    for _ in range(STRICT_ATTEMPTS):
        assert not gate("差一点的开场。")[0]
    assert gate("好一些的开场吗？")[0]


def test_missing_the_lesson_alone_does_not_send_the_opening_back():
    """A zoo drawing in a class on solids and shading: no honest comment connects them."""
    gate = gate_over([_Report(failures=[_Rule(11)], pass_rate=0.92)])
    assert gate("我看到一只长颈鹿在向日葵旁边。它要去哪里？")[0]


def test_an_opening_in_the_wrong_language_is_refused_even_on_the_last_attempt():
    conversation = Conversation.__new__(Conversation)
    conversation._gate = lambda text, child_said="": (False, "answered in en, but this class is in zh")
    gate = conversation._opening_gate()
    for _ in range(STRICT_ATTEMPTS + 2):
        ok, reason = gate("An opening in English.")
        assert not ok and "answered in en" in reason
