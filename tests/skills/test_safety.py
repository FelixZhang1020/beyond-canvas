"""The filter that runs before anything else.

The tests that matter here are the ones about failing safely: a filter that
fails open is worse than one that fails loudly, and a frightening drawing must
not be treated as an unsafe one.
"""

from pathlib import Path

import pytest
from conftest import load_script

from studio.core.errors import ModelRefused

SCRIPT = Path("skills/studio-safety/scripts/safety.py")
IMAGE = "data:image/png;base64,AAAA"


@pytest.fixture(scope="module")
def module():
    return load_script(SCRIPT, "safety_script")


def test_a_childs_drawing_is_allowed(module, fake_client):
    client = fake_client(['{"verdict": "allow", "reason": "a crayon house", "text_found": []}'])
    result = module.screen(IMAGE, client)
    assert result.verdict == "allow"
    assert result.may_proceed


def test_a_frightening_drawing_is_softened_not_blocked(module, fake_client):
    """Children draw monsters. Blocking one tells a child their subject was wrong."""
    client = fake_client(['{"verdict": "soften", "reason": "a monster with teeth", "text_found": []}'])
    result = module.screen(IMAGE, client)
    assert result.verdict == "soften"
    assert result.may_proceed, "a scary drawing is still a drawing and must reach the studio"


def test_a_photograph_is_blocked(module, fake_client):
    """Two looks, because a refusal stops a child and must not rest on one."""
    photo = '{"verdict": "block", "reason": "a photograph of a room", "text_found": []}'
    client = fake_client([photo, photo])
    result = module.screen(IMAGE, client)
    assert not result.may_proceed


def test_a_blank_page_stops_but_is_not_a_block(module, fake_client):
    """Nothing is wrong with the child; there is simply nothing to talk about yet."""
    blank = '{"verdict": "empty", "reason": "the page is blank", "text_found": []}'
    client = fake_client([blank, blank])
    result = module.screen(IMAGE, client)
    assert result.verdict == "empty"
    assert not result.may_proceed


def test_writing_on_the_page_is_reported_without_blocking(module, fake_client):
    client = fake_client(
        ['{"verdict": "allow", "reason": "a blue circle", '
         '"text_found": ["Mei Lin", "Sunshine Primary, Class 2B"]}']
    )
    result = module.screen(IMAGE, client)
    assert result.may_proceed
    assert result.carries_personal_text
    assert "Mei Lin" in result.text_found


def test_writing_given_as_one_string_or_as_nothing_is_still_read(module, fake_client):
    """Code review: writing returned as a lone string was split into letters, which redaction skips, so the name
    stayed in what was shown and spoken; returned as null, it crashed the screen into the hiccup line."""
    one = '{"verdict": "allow", "reason": "a name in the corner", "text_found": "Mei Lin"}'
    assert module.screen(IMAGE, fake_client([one])).text_found == ("Mei Lin",)
    none = '{"verdict": "allow", "reason": "a crayon house", "text_found": null}'
    assert module.screen(IMAGE, fake_client([none])).text_found == ()
    listed = '{"verdict": "allow", "reason": "", "text_found": ["Mei Lin", null]}'
    assert module.screen(IMAGE, fake_client([listed])).text_found == ("Mei Lin",)


def test_an_answer_that_is_not_an_object_is_refused_rather_than_crashing(module, fake_client):
    with pytest.raises(ModelRefused):
        module.screen(IMAGE, fake_client(['["allow"]', '"allow"']))


def test_an_unreadable_answer_is_refused_rather_than_allowed(module, fake_client):
    """A filter that fails open is worse than one that fails loudly."""
    client = fake_client(["not json", "still not json"])
    with pytest.raises(ModelRefused):
        module.screen(IMAGE, client)


def test_an_unknown_verdict_is_refused_rather_than_allowed(module, fake_client):
    """A model inventing a fifth verdict must not slip through as a pass."""
    client = fake_client(['{"verdict": "probably fine"}', '{"verdict": "Mei Lin drew her house"}'])
    with pytest.raises(ModelRefused) as refused:
        module.screen(IMAGE, client)
    # The refusal becomes a ledger note and reaches the page: a code, never the model's words about the child.
    said = str(refused.value).lower()
    assert "mei lin" not in said and "probably" not in said, said


def test_redaction_removes_a_name_that_reached_the_feedback(module):
    """The prompt forbids repeating a name; this is the half that guarantees it."""
    cleaned = module.redact(
        "I see Mei Lin wrote her name and drew a blue circle.",
        ("Mei Lin", "Sunshine Primary"),
    )
    assert "Mei Lin" not in cleaned
    assert "blue circle" in cleaned


def test_redaction_leaves_a_single_character_alone(module):
    """Removing every "a" from the feedback would destroy it."""
    cleaned = module.redact("I see a big red apple.", ("a",))
    assert "apple" in cleaned


def test_the_longest_written_piece_is_redacted_first(module):
    """Otherwise removing 'Sunshine' first leaves 'Primary' orphaned in the text."""
    cleaned = module.redact(
        "Sunshine Primary is written here.", ("Sunshine", "Sunshine Primary")
    )
    assert "Sunshine" not in cleaned
    assert "Primary" not in cleaned


def test_the_prompt_refuses_to_block_on_how_a_drawing_was_made(module):
    """Live run: the monster fixture was blocked as "a digital graphic",
    while an equally synthetic drawing passed. How a drawing was made is irrelevant,
    and a tidy reason can hide a block that was really about the subject."""
    prompt = " ".join(module.SAFETY_PROMPT.split())
    assert "HOW the drawing was made is irrelevant" in prompt
    # Widened after a child's scribble was refused as "a digital
    # graphic icon": the list now names every way a young child's drawing looks.
    assert "it looks like a digital graphic, an icon, clip art or a logo" in prompt


def test_the_prompt_says_a_frightening_subject_is_never_a_block(module):
    prompt = " ".join(module.SAFETY_PROMPT.split())
    assert "A frightening subject is never a reason to block" in prompt
    assert "the answer is \"soften\"" in prompt


def test_polished_pencil_studies_are_art_but_photographs_still_stop(module):
    """The supplied still life was refused before its geometry could be read.
    Medium is the criterion; perceived age or drawing skill must not exclude it.
    This checks the prompt boundary, not the live model's classification accuracy.
    """
    prompt = " ".join(module.SAFETY_PROMPT.split())
    assert "not the creator's age or level of skill" in prompt
    assert "A carefully shaded graphite still life is artwork too" in prompt
    assert 'Actual scene/person photographs still get "block"' in prompt
    assert 'blank pages still get "empty"' in prompt
    assert 'genuinely harmful images still get "unsafe"' in prompt
