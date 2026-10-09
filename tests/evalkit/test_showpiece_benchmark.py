"""The showpiece benchmark: the same requests with the skills and without, scored the same way."""
from pathlib import Path

from conftest import FakeClient
from evalkit import showpiece as bench


def test_cases_come_from_the_six_eval_files_with_placeholders_filled(tmp_path):
    found = bench.cases(Path("skills"), model=Path("/m/hall.blend"), out_dir=tmp_path)
    assert {c.skill for c in found} == set(bench.SIX)
    assert all("<" not in c.question for c in found)
    assert any("stack.blend" in c.question for c in found)


def test_a_bare_driver_has_no_skill_text_but_every_tool(tmp_path):
    driver = bench.bare_driver(FakeClient([]), None, tmp_path, cap=3)
    text = driver.system_prompt(tmp_path, set())
    assert "model-anatomy/inventory" in text and "joint-reveal/explode" in text
    assert "Looks at one rendered picture" not in text and "## Tool" not in text


def test_scoring_reads_completion_actions_and_judged_shots():
    events = [
        {"step": 1, "kind": "think", "text": "", "tokens": 100},
        {"step": 2, "kind": "act", "skill": "model-anatomy", "tool": "inventory", "args": {}, "text": "", "tokens": 0, "seconds": 2.0},
        {"step": 3, "kind": "act", "skill": "shot-judge", "tool": "judge", "args": {}, "text": "", "tokens": 0,
         "verdict": {"verdict": "pass"}, "seconds": 3.0},
        {"step": 4, "kind": "final", "text": "done", "tokens": 0},
    ]
    outcome = bench.score("x", "skills", events, expected_tools=[("model-anatomy", "inventory")])
    assert outcome.completed and outcome.actions == 2 and outcome.judged == 1 and outcome.passed == 1
    assert outcome.tokens == 100 and outcome.seconds == 5.0
    table = bench.render([outcome], "fake")
    assert "| x | skills | yes | 2 | 1/1 |" in table


def test_a_case_that_names_a_picture_gets_that_picture_in_its_run_folder():
    """At first it did not, and both modes answered "the file is not in the run
    folder". That is why `shot-judge` carried a BENCHMARK.md saying "Not yet measured":
    the run had never once worked, and nothing said so."""
    from pathlib import Path

    from evalkit.showpiece import cases

    found = cases(Path("skills"), None, Path(".studio/showpiece/runs"), only="shot-judge")
    assert found, "shot-judge has eval cases"
    for case in found:
        assert case.seed, f"{case.id} names a picture and must carry it"
        for name, source in case.seed:
            assert source.is_file() and name in case.question
            assert "/" not in name, "the driver copies a seed flat"


def test_a_named_file_that_does_not_exist_is_left_alone_and_never_invented():
    from pathlib import Path

    from evalkit.showpiece import _seeded

    question, seed = _seeded("Judge it. File: evals/files/nowhere.jpg", Path("skills/shot-judge"))
    assert seed == () and "evals/files/nowhere.jpg" in question


def test_the_report_says_that_a_zero_on_a_fail_case_is_the_right_answer():
    """`judge-cropped-ridge-fail` is built around a picture that should be refused, so
    0 passes is correct. A table of bare numbers reads that as a failure."""
    from evalkit.showpiece import Outcome, render

    body = render([Outcome("judge-cropped-ridge-fail", "skills", True, 1, 1, 0, 5124, 7.5, "")],
                  "step-3.7-flash via stepfun")
    assert "How to read this" in body
    assert "`0/1` there is the" in body and "correct answer" in body
