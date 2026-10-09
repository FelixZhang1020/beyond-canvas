"""A refusal stops a child, so it may not rest on one unstable answer.

Found live: a child's scribble came back as "a digital graphic
icon, not a child's drawing", and the same image had passed the same filter an
hour earlier. These hold the shape of the fix.
"""

import pytest

from studio.core.errors import ModelRefused
from tests.conftest import load_script

SAFETY = load_script("skills/studio-safety/scripts/safety.py", "safety_skill")

ALLOW = '{"verdict": "allow", "reason": "a crayon drawing", "text_found": []}'
SOFTEN = '{"verdict": "soften", "reason": "a monster", "text_found": []}'
BLOCK = '{"verdict": "block", "reason": "a photograph of a room", "text_found": []}'
EMPTY = '{"verdict": "empty", "reason": "a blank page", "text_found": []}'


def test_a_drawing_is_allowed_on_one_look(fake_client):
    """The common case costs one call, because the common case is a drawing."""
    client = fake_client([ALLOW])
    assert SAFETY.screen("data:,x", client).verdict == "allow"
    assert len(client.calls) == 1


def test_a_frightening_drawing_also_costs_one_look(fake_client):
    client = fake_client([SOFTEN])
    assert SAFETY.screen("data:,x", client).may_proceed
    assert len(client.calls) == 1


def test_a_refusal_is_asked_a_second_time(fake_client):
    client = fake_client([BLOCK, BLOCK])
    assert SAFETY.screen("data:,x", client).verdict == "block"
    assert len(client.calls) == 2, "a refusal must not rest on one answer"


def test_a_second_look_that_sees_a_drawing_wins(fake_client):
    """The scribble case: one call said clip art, the next said drawing."""
    client = fake_client([BLOCK, ALLOW])
    verdict = SAFETY.screen("data:,x", client)
    assert verdict.may_proceed, "a child must not be refused on a disagreement"
    assert verdict.verdict == "allow"


def test_a_blank_page_gets_the_same_second_chance(fake_client):
    """A faint pencil drawing read as blank stops the child just as hard."""
    client = fake_client([EMPTY, ALLOW])
    assert SAFETY.screen("data:,x", client).may_proceed


def test_two_looks_that_both_refuse_still_refuse(fake_client):
    client = fake_client([EMPTY, EMPTY])
    assert not SAFETY.screen("data:,x", client).may_proceed


def test_an_unreadable_answer_still_raises_rather_than_allowing(fake_client):
    """A filter that fails open is worse than one that fails loudly."""
    client = fake_client(["not json", "still not json"])
    with pytest.raises(ModelRefused):
        SAFETY.screen("data:,x", client)


@pytest.mark.parametrize(
    "phrase",
    [
        "digital graphic",
        "clip art",
        "simple, flat",
        "scribble nobody can identify",
        "faint, small",
    ],
)
def test_the_prompt_names_what_is_never_a_block(phrase):
    """Every one of these is what a five-year-old's drawing looks like."""
    assert phrase in SAFETY.SAFETY_PROMPT


def test_the_prompt_says_which_mistake_is_worse():
    assert 'the answer is "allow"' in SAFETY.SAFETY_PROMPT
    assert "never gets said" in SAFETY.SAFETY_PROMPT


@pytest.mark.parametrize(
    "text, found, gone",
    [
        ("I see Mei Lin's blue circle.", ("Mei Lin",), "'s"),
        ('我看到标着“美琳”的橙色房子。', ("美琳",), "“"),
        ('画面上方有蓝色的“阳光小学”字样。', ("阳光小学",), "”"),
    ],
)
def test_removing_a_name_does_not_leave_a_hole(text, found, gone):
    """Real drawings: the writing was removed and its punctuation was
    not, so a child was read "the orange house marked with" and an empty pair of
    quotes. Deleting the words is the safety property; closing the gap is what
    stops the sentence reading as broken."""
    cleaned = SAFETY.redact(text, found)
    for name in found:
        assert name not in cleaned
    assert gone not in cleaned
    assert cleaned.strip()
