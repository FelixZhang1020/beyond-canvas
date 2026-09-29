"""The two entrances, and which rules each one grades.

Section 5a of the spec settles that the teacher picks an entrance by hand when
the class starts. On the colour entrance correction is harm and rule 6 is
absolute. On the sketch entrance a plaster-cast study is an observational
exercise, so correction is expected and proportion is the subject: rules 6 and
7 do not apply there at all. Settled with the operator.
"""

import pytest

from evalkit.rubric import run_rubric

COLOUR_OPENING = (
    "I notice your dog is purple and your sun has pointy triangle rays. "
    "I also see two people holding hands. "
    "What just happened to them?"
)
SKETCH_OPENING = (
    "I see the shadow turning darker under the sphere and a soft edge where the light lands. "
    "The cast shadow is out of proportion to the ball, so you could try measuring it against the width. "
    "Which part did you change the most?"
)
SKETCH_OPENING_ZH = (
    "我看到球体下面的阴影一点点变深，亮的那一边边缘很柔和。"
    "比例不对的地方可以试着量一量。哪一块你改了最多次？"
)


def statuses(report):
    return {result.rule: result.status for result in report.results}


def test_the_entrance_is_required():
    """There is no automatic detection, so there is no default either."""
    with pytest.raises(TypeError):
        run_rubric(COLOUR_OPENING)


def test_an_unknown_entrance_is_refused():
    with pytest.raises(ValueError):
        run_rubric(COLOUR_OPENING, entrance="crayon")


def test_a_correction_fails_rule_6_on_the_colour_entrance():
    report = run_rubric("I see a purple dog. It should have four legs. What is it doing?", entrance="colour")
    assert statuses(report)[6] == "fail"


def test_a_correction_is_not_graded_on_the_sketch_entrance():
    """Critique is the whole exercise on a plaster cast. Withholding it fails the child."""
    report = run_rubric("I see a purple dog. It should have four legs. What is it doing?", entrance="sketch")
    result = next(result for result in report.results if result.rule == 6)
    assert result.status == "skip"
    assert "sketch" in result.evidence


def test_proportion_critique_fails_rule_7_on_colour_and_is_skipped_on_sketch():
    """Rule 7 forbids the very words a sketch critique is made of."""
    assert statuses(run_rubric(SKETCH_OPENING, entrance="colour"))[7] == "fail"
    assert statuses(run_rubric(SKETCH_OPENING, entrance="sketch"))[7] == "skip"


@pytest.mark.parametrize("text", [SKETCH_OPENING, SKETCH_OPENING_ZH])
def test_a_process_question_passes_rule_12_on_the_sketch_entrance(text):
    """The spec's own sketch question: which part did you change the most?"""
    report = run_rubric(text, entrance="sketch")
    result = next(result for result in report.results if result.rule == 12)
    assert result.status == "pass", result.evidence


def test_a_process_question_does_not_pass_rule_12_on_the_colour_entrance():
    """On colour the question has to enter the world of the picture, not the process."""
    assert statuses(run_rubric(SKETCH_OPENING, entrance="colour"))[12] == "fail"


def test_a_story_question_does_not_pass_rule_12_on_the_sketch_entrance():
    """A plaster cast has no story, so asking what is happening there is absurd."""
    report = run_rubric(
        "I see the shadow turning darker under the sphere. What is happening here?",
        entrance="sketch",
    )
    result = next(result for result in report.results if result.rule == 12)
    assert result.status == "fail"
    assert "process" in result.evidence


def test_asking_what_the_object_is_still_fails_rule_12_on_sketch():
    report = run_rubric("I see a round shape with a shadow. What is this?", entrance="sketch")
    assert statuses(report)[12] == "fail"


@pytest.mark.parametrize("entrance", ["sketch", "colour"])
def test_every_rule_is_returned_in_order_on_both_entrances(entrance):
    report = run_rubric(COLOUR_OPENING, entrance=entrance)
    assert [result.rule for result in report.results] == list(range(1, 15))


def test_the_sketch_entrance_scores_two_rules_fewer_without_an_image():
    """Skips are excluded from the score, so scoping must not inflate a sketch result."""
    colour = run_rubric(COLOUR_OPENING, entrance="colour")
    sketch = run_rubric(SKETCH_OPENING, entrance="sketch")
    assert len(sketch.scored) == len(colour.scored) - 2
