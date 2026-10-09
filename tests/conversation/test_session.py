"""The hero scenario assembled: safety, then feedback, then the gate.

The order is what these tests hold. A blocked image must never reach a skill,
and nothing a child sees may skip the rubric.
"""

import json

import pytest

from studio.core.ledger import Ledger
from studio.conversation.session import RUBRIC_FLOOR, open_a_conversation

DRAWING = "skills/art-feedback/evals/files/dog-sun.png"

GOOD_OPENING = (
    "I see a yellow sun with pointy triangle rays. I notice two figures below it. "
    "What is happening between them?"
)


class Scripted:
    """Replays canned replies and remembers the order it was asked."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.prompts = []

    def chat(self, prompt, images=(), *, system=None, max_tokens=None):
        from studio.providers.base import ChatResult

        self.prompts.append(prompt[:40])
        return ChatResult(
            text=self.replies.pop(0), input_tokens=10, output_tokens=10,
            reasoning_tokens=0, cost_usd=0.0, latency_s=0.0, provider="fake", model="fake",
        )


@pytest.fixture
def wired(monkeypatch):
    """Point both slots at one scripted client."""
    def install(replies):
        client = Scripted(replies)
        monkeypatch.setattr("studio.conversation.session.build_client", lambda config: client)
        return client
    return install


def test_a_blocked_image_never_reaches_the_feedback_skill(wired, tmp_path):
    """The whole reason safety runs first."""
    photo = '{"verdict": "block", "reason": "a photograph", "text_found": []}'
    client = wired([photo, photo])
    session = open_a_conversation(DRAWING, tmp_path / "l.jsonl", entrance="colour")
    assert not session.ok
    assert "does not look like a drawing" in session.refused
    assert len(client.prompts) == 2, "the two safety looks, and nothing else"


def test_a_blank_page_gets_its_own_words_not_a_block(wired, tmp_path):
    blank = '{"verdict": "empty", "reason": "blank", "text_found": []}'
    wired([blank, blank])
    session = open_a_conversation(DRAWING, tmp_path / "l.jsonl", entrance="colour")
    assert "do not see a drawing" in session.refused


def test_a_frightening_drawing_proceeds_to_feedback(wired, tmp_path):
    """soften means proceed. This is the test that stops a well-meaning regression."""
    wired([
        '{"verdict": "soften", "reason": "a monster", "text_found": []}',
        GOOD_OPENING,
        '{"grounded": ["yellow sun", "two figures"]}',
        '{"presumptive": []}',
    ])
    session = open_a_conversation(DRAWING, tmp_path / "l.jsonl", entrance="colour")
    assert session.ok
    assert session.opening == GOOD_OPENING


def test_writing_found_on_the_page_is_stripped_from_what_is_shown(wired, tmp_path):
    wired([
        '{"verdict": "allow", "reason": "a circle", "text_found": ["Mei Lin"]}',
        "I see Mei Lin drew a blue circle. What is happening in it?",
        '{"grounded": ["blue circle", "a circle"]}',
        '{"presumptive": []}',
    ])
    session = open_a_conversation(DRAWING, tmp_path / "l.jsonl", entrance="colour")
    assert "Mei Lin" not in session.opening
    assert "blue circle" in session.opening


def test_feedback_failing_the_rubric_is_not_shown_to_a_child(wired, tmp_path):
    """The gate is the point: warm nonsense is still not shown."""
    flattery = "What a beautiful painting! You are so talented."
    judges = ['{"grounded": []}', '{"presumptive": []}']
    # Three attempts now: the first, the retry, and the repair — which section 6
    # always specified and nothing used to supply.
    wired(
        ['{"verdict": "allow", "reason": "a drawing", "text_found": []}']
        + [flattery, *judges] * 3
    )
    session = open_a_conversation(DRAWING, tmp_path / "l.jsonl", entrance="colour")
    assert "beautiful" not in session.opening and "talented" not in session.opening
    # The studio's own look-and-ask stands in, rather than a gate message.
    assert session.ok and not session.refused


def test_every_stage_is_written_to_the_ledger(wired, tmp_path):
    wired([
        '{"verdict": "allow", "reason": "a drawing", "text_found": []}',
        GOOD_OPENING,
        '{"grounded": ["yellow sun", "two figures"]}',
        '{"presumptive": []}',
    ])
    path = tmp_path / "l.jsonl"
    session = open_a_conversation(DRAWING, path, entrance="colour")
    entries = list(Ledger(path).entries(session.session_id))
    assert [entry.stage for entry in entries] == ["screen", "opening"]
    assert all(entry.gate == "pass" for entry in entries)


def test_the_ledger_holds_no_drawing_and_no_feedback_text(wired, tmp_path):
    wired([
        '{"verdict": "allow", "reason": "a drawing", "text_found": []}',
        GOOD_OPENING,
        '{"grounded": ["yellow sun", "two figures"]}',
        '{"presumptive": []}',
    ])
    path = tmp_path / "l.jsonl"
    open_a_conversation(DRAWING, path, entrance="colour")
    written = path.read_text(encoding="utf-8")
    assert "pointy triangle rays" not in written
    assert "base64" not in written
    for line in written.splitlines():
        assert json.loads(line)["inputs_hash"]


def test_the_rubric_floor_leaves_room_for_a_rule_or_two():
    """A floor of 1.0 would refuse every real reply; a floor of 0 would gate nothing."""
    assert 0.7 < RUBRIC_FLOOR < 1.0


def test_a_model_that_failed_to_answer_does_not_produce_the_block_message(monkeypatch, tmp_path):
    """Live run: a 147-second empty reply on the safety stage came back
    wearing "this does not look like a drawing". Nothing had been decided about
    the drawing. A child must not be refused on the strength of a hiccup."""
    from studio.core.errors import EmptyCompletion

    class Dead:
        def chat(self, *args, **kwargs):
            raise EmptyCompletion("returned no text")

    monkeypatch.setattr("studio.conversation.session.build_client", lambda config: Dead())
    session = open_a_conversation(DRAWING, tmp_path / "l.jsonl", entrance="colour")
    assert not session.ok
    assert "does not look like a drawing" not in session.refused
    assert "Try that photo again" in session.refused


def test_a_session_names_its_entrance_or_does_not_start(wired, tmp_path):
    """Section 5a: the teacher picks by hand, so nothing here guesses for them."""
    wired([])
    with pytest.raises(TypeError):
        open_a_conversation(DRAWING, tmp_path / "l.jsonl")


def test_the_sketch_entrance_reaches_the_skill_and_the_gate(wired, tmp_path):
    """On sketch the prompt reads light and form, and a correction is not a failure."""
    client = wired([
        '{"verdict": "allow", "reason": "a sphere", "text_found": []}',
        "I see the shadow turning under the sphere. It should sit closer to the base, so you could "
        "try measuring it. Which part did you change the most?",
        '{"grounded": ["shadow", "sphere"]}',
        '{"presumptive": []}',
    ])
    session = open_a_conversation(DRAWING, tmp_path / "l.jsonl", entrance="sketch")
    assert session.ok, session.refused
    # The scripted client keeps forty characters, enough to tell the two openings apart:
    # colour begins "You are a warm art teacher", sketch "You are an art teacher looking at a stud".
    assert client.prompts[1].startswith("You are an art teacher looking at a stud")
