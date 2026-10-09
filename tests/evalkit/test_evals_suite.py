"""The eval suite is part of the shipped skill, so it is checked like code.

The Agent Skills specification accepts evals at evals/evals.json, evals/*.json,
eval/*.json or benchmark/evals.json. Those are four accepted paths for one
format, not competing schemas, so there is exactly one suite and no converter.
"""

import json
import re
from pathlib import Path

import pytest

SUITE = Path("skills/art-feedback/evals/evals.json")
SKILL_ROOT = SUITE.parent.parent
ENTRANCE_IN_QUESTION = re.compile(r"\b(sketch|colour) entrance\b")
REQUIRED_KEYS = {
    "id",
    "question",
    "expected_skill",
    "expected_script",
    "ground_truth",
    "expected_behavior",
}


@pytest.fixture(scope="module")
def cases():
    return json.loads(SUITE.read_text(encoding="utf-8"))


def test_the_suite_is_a_non_empty_list_of_cases(cases):
    assert isinstance(cases, list)
    assert len(cases) >= 6


def test_every_case_carries_every_required_key(cases):
    for case in cases:
        missing = REQUIRED_KEYS - set(case)
        assert not missing, f"{case.get('id')} is missing {sorted(missing)}"


def test_case_ids_are_unique(cases):
    ids = [case["id"] for case in cases]
    assert len(ids) == len(set(ids))


def test_every_case_names_the_script_that_answers_it(cases):
    for case in cases:
        assert case["expected_skill"] == "art-feedback"
        assert (SKILL_ROOT / case["expected_script"]).is_file()


def test_every_expected_behavior_list_is_populated(cases):
    for case in cases:
        assert len(case["expected_behavior"]) >= 3, case["id"]


def test_every_case_names_its_entrance(cases):
    """The teacher picks by hand, so a case has to say which door it walks through."""
    for case in cases:
        assert ENTRANCE_IN_QUESTION.search(case["question"]), case["id"]


def test_the_suite_covers_both_entrances(cases):
    found = {
        match.group(1)
        for case in cases
        if (match := ENTRANCE_IN_QUESTION.search(case["question"]))
    }
    assert found == {"sketch", "colour"}


def test_no_case_mentions_an_age(cases):
    """Age modelling was dropped, and the suite must not keep it alive."""
    for case in cases:
        assert "year old" not in json.dumps(case), case["id"]


def test_at_least_three_cases_are_negative(cases):
    """A suite of happy paths measures nothing about refusal."""
    negatives = [case for case in cases if case["id"].startswith("negative-")]
    assert len(negatives) >= 3


def test_every_referenced_drawing_exists_or_is_a_documented_local_file(cases):
    """An eval pointing at a missing file passes by never running.

    The one case allowed to reference an absent file is the adult photograph:
    it lives under the gitignored local/ directory because a synthetic stand-in
    would not test what it claims to test. Its ground truth has to say so.
    """
    for case in cases:
        referenced = case["question"].split("File: ", 1)[1].strip()
        path = SKILL_ROOT / referenced
        if path.is_file():
            continue
        assert "/local/" in referenced, f"{case['id']} points at a missing file"
        assert "Skipped when the local file is absent" in case["ground_truth"], case["id"]
