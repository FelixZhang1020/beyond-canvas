"""What goes home is the child's words, not the machine's.

Section 5a: "A parent at pickup receives what their child said, not what a model
wrote." These tests hold that line, because it is the one most easily lost to a
well-meaning tidy-up.
"""

import json
from pathlib import Path

import pytest
from conftest import load_script

SCRIPT = Path("skills/art-feedback/scripts/story.py")
STRINGS = Path("skills/art-feedback/assets/story-strings.json")
DRAWING = "data:image/png;base64,AAAA"
CHILD = "The dragon flew home because his house was on fire.\nHe is not scary really."


@pytest.fixture(scope="module")
def module():
    return load_script(SCRIPT, "story_script")


def test_the_page_carries_the_childs_words_verbatim(module):
    page = module.build_page(DRAWING, CHILD, "en")
    assert "The dragon flew home because his house was on fire." in page
    assert "He is not scary really." in page


def test_each_line_the_child_said_becomes_its_own_paragraph(module):
    assert module.build_page(DRAWING, CHILD, "en").count("<p>") == 2


def test_the_drawing_is_embedded_so_the_page_survives_being_sent(module):
    """No network: the box is not supposed to be talking to one."""
    page = module.build_page(DRAWING, CHILD, "en")
    assert DRAWING in page
    assert "http://" not in page
    assert "https://" not in page


def test_no_story_at_all_is_refused_rather_than_written_blank(module):
    with pytest.raises(ValueError):
        module.build_page(DRAWING, "   ", "en")


def test_a_childs_angle_brackets_do_not_break_the_page(module):
    page = module.build_page(DRAWING, "he said <hello> & waved", "en")
    assert "&lt;hello&gt;" in page
    assert "&amp;" in page


def test_the_page_says_no_machine_wrote_it(module):
    """The claim is the point of the artifact, so it appears on the page itself."""
    for language in ("en", "zh"):
        page = module.build_page(DRAWING, CHILD, language)
        assert json.loads(STRINGS.read_text(encoding="utf-8"))[language]["footer"][:8] in page


def test_the_parent_facing_text_lives_in_assets_not_in_code(module):
    """Chinese belongs in content files. The guard enforces this; so does this test."""
    source = SCRIPT.read_text(encoding="utf-8")
    assert not any("一" <= ch <= "鿿" for ch in source)
    strings = json.loads(STRINGS.read_text(encoding="utf-8"))
    assert any("一" <= ch <= "鿿" for ch in strings["zh"]["title"])
