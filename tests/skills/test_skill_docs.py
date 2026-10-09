"""The documents a reader trusts must say what the code does.

A SKILL.md that documents a flag the script no longer takes, or a contract
that names a setting the page no longer sends, is the most expensive kind of
wrong: it is the last thing a reader sees before they stop looking.
"""

from pathlib import Path

import pytest

DOCUMENTS = {
    "skill": Path("skills/art-feedback/SKILL.md"),
    "rubric": Path("skills/art-feedback/references/rubric.md"),
    "contract": Path("docs/specs/studio-page-contract.md"),
    "card": Path("skills/art-feedback/skill-card.md"),
}
SKILL = DOCUMENTS["skill"].read_text(encoding="utf-8")
RUBRIC = DOCUMENTS["rubric"].read_text(encoding="utf-8")
CONTRACT = DOCUMENTS["contract"].read_text(encoding="utf-8")


def test_the_skill_documents_the_entrance_it_requires():
    assert "--entrance sketch" in SKILL
    assert "--entrance colour" in SKILL


@pytest.mark.parametrize("name", sorted(DOCUMENTS))
def test_no_document_still_offers_a_suggestion_switch_or_an_age(name):
    lowered = DOCUMENTS[name].read_text(encoding="utf-8").lower()
    assert "suggestion switch" not in lowered
    assert "suggestions on" not in lowered
    assert "age band" not in lowered or "were removed" in lowered


def test_the_skill_counts_fourteen_rules_not_ten():
    assert "ten pedagogy rules" not in SKILL
    assert "## The ten rules" not in SKILL
    assert "fourteen" in SKILL.lower()


def test_the_rubric_says_which_rules_the_sketch_entrance_skips():
    for rule in ("Rule 6", "Rule 7"):
        assert rule in RUBRIC
    lowered = RUBRIC.lower()
    assert "sketch entrance" in lowered
    assert "process" in lowered


def test_the_page_contract_carries_the_entrance():
    assert 'entrance: "sketch"|"colour"' in CONTRACT
    assert "suggestion?" not in CONTRACT
