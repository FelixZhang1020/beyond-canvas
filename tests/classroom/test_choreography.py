"""Choreography: what the gate refuses, and why each refusal matters.

The deterministic half of this gate is the whole reason section 5b prefers
choreography to a video model — the output is checkable. These tests are that
claim, made specific. Every case below is a plan that would look fine as JSON
and wrong on a child's screen.
"""

import json

import pytest

from tests.conftest import load_script

MOTION = load_script("skills/painting-to-animation/scripts/choreograph.py", "choreograph_skill")

GOOD = {
    "duration_s": 6,
    "layers": [
        {
            "name": "the large round shape on the left",
            "box": [0.1, 0.2, 0.3, 0.4],
            "move": "drift",
            "start_s": 0,
            "end_s": 4,
            "distance": [0.2, -0.05],
        }
    ],
}


def plan(**changes):
    document = json.loads(json.dumps(GOOD))
    layer = document["layers"][0]
    for key, value in changes.items():
        if key in layer:
            layer[key] = value
        else:
            document[key] = value
    return MOTION.parse(json.dumps(document))


def test_a_sound_plan_has_nothing_wrong_with_it():
    assert MOTION.problems(plan()) == []


def test_a_plan_where_nothing_moves_is_refused():
    assert "nothing moves" in MOTION.problems(MOTION.parse('{"duration_s": 6, "layers": []}'))[0]


def test_a_box_outside_the_picture_is_refused():
    """A rectangle off the edge of the paper is wrong whatever a model thinks."""
    problems = MOTION.problems(plan(box=[0.8, 0.2, 0.5, 0.4]))
    assert any("not inside the picture" in problem for problem in problems)


def test_an_empty_box_is_refused():
    assert any("empty box" in problem for problem in MOTION.problems(plan(box=[0.1, 0.2, 0, 0.4])))


def test_a_move_nobody_implemented_is_refused():
    """A closed vocabulary is what lets the page execute a plan without judgement."""
    problems = MOTION.problems(plan(move="explode"))
    assert any("not one of" in problem for problem in problems)


@pytest.mark.parametrize("seconds", [0.5, 1.9, 10.1, 60])
def test_a_clip_a_child_would_not_watch_is_refused(seconds):
    assert any("outside" in problem for problem in MOTION.problems(plan(duration_s=seconds)))


def test_a_layer_that_runs_past_the_end_of_the_clip_is_refused():
    problems = MOTION.problems(plan(end_s=99))
    assert any("does not fit the clip" in problem for problem in problems)


def test_a_layer_that_ends_before_it_starts_is_refused():
    problems = MOTION.problems(plan(start_s=3, end_s=1))
    assert any("does not fit the clip" in problem for problem in problems)


def test_a_drawing_that_flies_off_the_paper_is_refused():
    """Past the edge it is not the drawing any more."""
    problems = MOTION.problems(plan(distance=[2.5, 0]))
    assert any("further than the whole picture" in problem for problem in problems)


def test_more_layers_than_a_drawing_needs_is_refused():
    document = json.loads(json.dumps(GOOD))
    document["layers"] = document["layers"] * 4
    with pytest.raises(ValueError, match="more than the"):
        MOTION.parse(json.dumps(document))


@pytest.mark.parametrize("field,value", [
    ("distance", [float("nan"), 0]), ("distance", [0, float("inf")]),
    ("box", [0, 0, float("nan"), .5]), ("duration_s", float("nan")),
])
def test_non_finite_numbers_never_reach_the_renderer(field, value):
    assert MOTION.problems(plan(**{field: value}))


@pytest.mark.parametrize("payload", ["null", "[]", '{"layers":null}', '{"layers":[null]}'])
def test_wrong_json_shapes_are_gate_failures(payload):
    with pytest.raises(ValueError):
        MOTION.parse(payload)


@pytest.mark.parametrize("field,value", [("box", [0, 0, .5]), ("distance", [0]), ("box", "0000")])
def test_vectors_are_not_silently_padded_or_truncated(field, value):
    with pytest.raises(ValueError):
        plan(**{field: value})


def test_the_prompt_names_every_move_the_page_can_execute():
    """A prompt that offers a move the gate refuses wastes a call every time."""
    prompt = MOTION.build_prompt("en")
    for move in MOTION.MOVES:
        assert move in prompt


def test_the_child_s_own_sentence_reaches_the_prompt():
    prompt = MOTION.build_prompt("en", "the dragon flew away")
    assert "the dragon flew away" in prompt
    assert "because they said it" in prompt


def test_a_fenced_reply_is_still_read():
    fenced = "```json\n" + json.dumps(GOOD) + "\n```"
    assert MOTION.parse(fenced).duration_s == 6


def test_the_plan_round_trips_to_what_the_page_receives():
    document = MOTION.parse(json.dumps(GOOD)).as_dict()
    assert document["layers"][0]["box"] == [0.1, 0.2, 0.3, 0.4]
    assert document["layers"][0]["move"] == "drift"


def test_the_gate_asks_no_judge_when_the_child_said_nothing(tmp_path, monkeypatch):
    """Section 5b wants this instant. With nothing to contradict, nothing is judged."""
    from studio.conversation.conversation import Conversation
    from studio.core.ledger import Ledger

    class NeverCalled:
        def chat(self, *args, **kwargs):
            raise AssertionError("no judge should run without the child's words")

    talk = Conversation(
        "skills/art-feedback/evals/files/dog-sun.png",
        Ledger(tmp_path / "l.jsonl"),
        entrance="colour",
        studio=NeverCalled(),
        director=NeverCalled(),
    )
    ok, reason = talk._motion_gate(plan(), "")
    assert ok
    assert "1 layers" in reason


def test_the_gate_asks_no_judge_even_when_the_child_has_spoken(tmp_path):
    """Two borrowed rules were tried here and both were the wrong rule.

    Rule 4 refused a correct plan for calling a tree a tree; rule 14 then refused
    a plan whose motion was exactly what the child asked for, because "the
    figures drift" is not a phrase a child says. Until a rule is written for
    movement, the deterministic checks stand alone — which is also what keeps
    this instant, as section 5b requires.
    """
    from studio.conversation.conversation import Conversation
    from studio.core.ledger import Ledger

    class NeverCalled:
        def chat(self, *args, **kwargs):
            raise AssertionError("no judge belongs on the motion gate")

    talk = Conversation(
        "skills/art-feedback/evals/files/dog-sun.png",
        Ledger(tmp_path / "l.jsonl"),
        entrance="colour",
        studio=NeverCalled(),
        director=NeverCalled(),
    )
    ok, reason = talk._motion_gate(plan(), "the creature walked away")
    assert ok
    assert "1 layers" in reason


def test_the_gate_still_refuses_a_plan_that_leaves_the_paper(tmp_path):
    """The deterministic half is the half that has always worked."""
    from studio.conversation.conversation import Conversation
    from studio.core.ledger import Ledger

    talk = Conversation(
        "skills/art-feedback/evals/files/dog-sun.png",
        Ledger(tmp_path / "l.jsonl"),
        entrance="colour",
        studio=None,
        director=None,
    )
    ok, reason = talk._motion_gate(plan(box=[0.9, 0.9, 0.5, 0.5]), "")
    assert not ok
    assert "not inside the picture" in reason


def test_animation_work_is_bounded_across_tablets_and_slot_is_released(tmp_path):
    from studio.classroom.classroom import Classroom
    from tests.classroom.test_classroom import Scripted, ALLOW, CLASS, DRAWING
    from tests.making.test_animation import CLEAN, Editor
    client = Scripted([ALLOW] * 6 + [CLEAN])
    classroom = Classroom(tmp_path / 'ledger.jsonl', clients={'vlm.studio':client,'vlm.director':client}, editor=Editor().slot())
    session = classroom.begin(CLASS)
    drawing = classroom.add_drawing(session, open(DRAWING, 'rb').read())
    classroom.animation_slot.acquire()
    blocked = classroom.request(session, 'painting-to-animation', [drawing], {})['request_id']
    classroom.run_request(blocked)
    events = list(classroom.follow(blocked))
    assert any(data.get('reason_code') == 'busy' for _, data in events)
    assert not client.prompts
    classroom.animation_slot.release()
    request = classroom.request(session, 'painting-to-animation', [drawing], {})['request_id']
    classroom.run_request(request)
    assert any(data.get('outputs', {}).get('video_url') for _, data in classroom.follow(request))
    assert classroom.animation_slot.acquire(blocking=False)
    classroom.animation_slot.release()
    classroom.end(session)
