"""The Skill-picking test: a model is shown only the Skills' names and descriptions and asked which
one should take each eval case. What it measures is the descriptions, so the test set has to be
sound first: every case must name a Skill that exists, and every Skill must be on the menu."""
from types import SimpleNamespace

import pytest

from evalkit import dispatch
from studio.core.errors import EmptyCompletion, ModelRefused
from studio.showpiece import catalog
from studio.core.slots import load_profile, resolve


def test_every_case_names_a_skill_that_exists():
    names = set(dispatch.every_skill())
    wrong = [f"{case['from']}/{case['id']} -> {case['expected']}" for case in dispatch.cases()
             if case["expected"] not in names]
    assert wrong == [], "a case whose right answer is not on the menu can only ever be counted a miss"


def test_every_skill_is_on_the_menu_under_its_own_name():
    names = dispatch.every_skill()
    skills = catalog.load_skills(dispatch.SKILLS, names)
    menu = dispatch.menu(skills)
    assert len(names) == len(list(dispatch.SKILLS.glob("*/SKILL.md")))
    assert all(f"\n{name}: {skills[name].description}" in "\n" + menu and skills[name].description for name in names)


def test_the_pick_is_read_from_the_json_and_prose_alone_is_no_pick():
    assert dispatch.chosen('{"skill": "art-feedback"}') == "art-feedback"
    assert dispatch.chosen('I would send this one on.\n{"skill": " load-path "}') == "load-path"
    assert dispatch.chosen("art-feedback, clearly") is None
    assert dispatch.chosen('{"skill": ""}') is None and dispatch.chosen("") is None


def test_braces_in_the_prose_before_the_answer_do_not_hide_it():
    assert dispatch.chosen('Two candidates {a, b}. {"skill": "load-path"}') == "load-path"
    assert dispatch.chosen('{"skill": null}') is None


def test_only_the_answer_itself_counts_not_a_skill_named_inside_it():
    assert dispatch.chosen('{"skill": "art-feedback", "why": {"skill": "load-path"}}') == "art-feedback"


def test_a_miss_is_counted_against_the_skill_the_case_was_meant_for():
    rows = [{"id": "a", "expected": "art-feedback", "picked": "art-feedback"},
            {"id": "b", "expected": "art-feedback", "picked": "studio-safety"},
            {"id": "c", "expected": "load-path", "picked": None}]
    text = dispatch.report(rows)
    assert text.startswith("chose right: 1 of 3")
    assert "art-feedback             1/2" in text and "load-path                0/1" in text
    assert "wanted art-feedback" in text and "chose studio-safety" in text and "chose (unreadable)" in text


class Model:
    def __init__(self, *answers):
        self.answers = list(answers)

    def chat(self, *args, **kwargs):
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return SimpleNamespace(text=answer, input_tokens=10, output_tokens=5)


def test_a_model_that_refuses_or_goes_quiet_costs_one_case_and_says_why():
    assert dispatch.ask(Model('{"skill": "art-feedback"}'), "menu", "q") == ("art-feedback", 15, '{"skill": "art-feedback"}')
    picked, _, said = dispatch.ask(Model(ModelRefused("stepfun 400: bad request")), "menu", "q")
    assert picked is None and said.startswith("error: stepfun 400")
    picked, _, said = dispatch.ask(Model(EmptyCompletion("empty"), EmptyCompletion("empty")), "menu", "q")
    assert picked is None and said == "empty twice"


def test_the_default_is_the_one_deployment_and_names_a_model():
    assert resolve(dispatch.SLOT, load_profile(dispatch.PROFILE)).model == "qwen3.6-35b-a3b"


CASES = [{"id": str(n), "question": "q", "expected": "art-feedback", "from": "art-feedback"} for n in range(10)]


def test_three_errors_in_a_row_stop_the_run_before_any_report_is_written():
    """A missing key, a rejected key or an empty account fails every case the same way; going on
    would spend six minutes of pauses and write "0 of 51" over the last good report."""
    model = Model(*[ModelRefused("StepFun rejected STEPFUN_API_KEY.")] * 10)
    with pytest.raises(SystemExit, match="3 errors in a row"):
        dispatch.run(model, "menu", CASES, pause=0)
    assert len(model.answers) == 7


def test_one_error_among_answers_is_a_miss_and_the_run_goes_on():
    model = Model(ModelRefused("stepfun 400: odd"), '{"skill": "art-feedback"}')
    rows, spent = dispatch.run(model, "menu", CASES[:2], pause=0)
    assert [row["picked"] for row in rows] == [None, "art-feedback"] and spent == 15
