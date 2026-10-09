"""The classroom benchmark measures the skill against the same model without it.

These tests spend nothing: a fake client replays what a model would have said, so
what is checked here is the harness around the model — that both runs happen, that
the judge's yes and no reach the table, that a case whose picture is missing is
reported rather than counted, and that the report names the model that produced it.
"""
from __future__ import annotations

import json

from evalkit import classbench


def judge_reply(*met: bool) -> str:
    return json.dumps({"results": [{"n": i + 1, "met": m, "why": "checked"} for i, m in enumerate(met)]})


def test_every_case_is_run_twice_once_with_the_skill_and_once_without(fake_client, monkeypatch):
    cases = [{"id": "one", "question": "Screen this. File: ../art-feedback/evals/files/dog-sun.png",
              "ground_truth": "allow", "expected_behavior": ["Returns the verdict allow"]}]
    monkeypatch.setattr(classbench, "cases_for", lambda skill: cases)
    client = fake_client([
        json.dumps({"verdict": "allow", "reason": "a drawing", "text_found": []}),   # the skill's call
        judge_reply(True),                                                            # judged
        "It looks like a child's drawing, so yes.",                                   # the bare call
        judge_reply(False),                                                           # judged
    ])
    outcomes = classbench.run("studio-safety", client, client, "vlm.studio", pause=0.0)
    assert [o.slot for o in outcomes] == ["vlm.studio", "vlm.studio+no-skill"]
    assert [o.passed_all for o in outcomes] == [True, False]


def test_a_case_whose_picture_is_missing_is_reported_and_never_counted(fake_client, monkeypatch):
    cases = [{"id": "gone", "question": "Screen this. File: files/local/nowhere.jpg",
              "ground_truth": "block", "expected_behavior": ["Returns the verdict block"]}]
    monkeypatch.setattr(classbench, "cases_for", lambda skill: cases)
    skipped: list[str] = []
    outcomes = classbench.run("studio-safety", fake_client([]), fake_client([]), "vlm.studio", 0.0, skipped)
    assert outcomes == [] and skipped == ["gone"]
    assert "gone" in classbench.render("studio-safety", [], "Provenance: fake", tuple(skipped))


def test_the_report_carries_the_numbers_and_the_judges_reasons(fake_client, monkeypatch):
    cases = [{"id": "one", "question": "Screen this. File: ../art-feedback/evals/files/dog-sun.png",
              "ground_truth": "allow", "expected_behavior": ["Returns the verdict allow", "Says why"]}]
    monkeypatch.setattr(classbench, "cases_for", lambda skill: cases)
    client = fake_client([json.dumps({"verdict": "allow", "reason": "a drawing", "text_found": []}),
                          judge_reply(True, True), "Yes, fine.", judge_reply(False, False)])
    body = classbench.render("studio-safety",
                             classbench.run("studio-safety", client, client, "vlm.studio", 0.0),
                             "Provenance: step-3.7-flash via stepfun")
    assert "# BENCHMARK: studio-safety" in body
    assert "step-3.7-flash" in body                      # a number must name its model
    assert "`vlm.studio` | 1 | 100%" in body
    assert "`vlm.studio+no-skill` | 1 | 0%" in body
    assert "✓ Returns the verdict allow" in body and "✗ Returns the verdict allow" in body


def test_a_judge_that_answers_nothing_is_counted_as_a_failure_not_a_pass(fake_client):
    case = {"id": "one", "question": "q", "ground_truth": "g", "expected_behavior": ["a", "b"]}
    met, why = classbench.judge(fake_client(["not JSON at all"]), case, classbench.Answer("x"))
    assert met == (False, False) and "did not answer" in why[0]


def test_only_skills_with_a_script_of_their_own_can_be_measured_this_way():
    assert sorted(classbench.ADAPTERS) == ["painting-to-animation", "studio-safety"]


def test_a_judge_call_that_raises_loses_that_case_and_not_the_whole_run():
    """The defect `evalkit.runner` already had once: every case before the last had
    been paid for, and one failure at the end threw all of it away."""
    class Refuses:
        def chat(self, *args, **kwargs):
            raise RuntimeError("step-3.7-flash returned a truncated completion; raise max_tokens")

    case = {"id": "one", "question": "q", "ground_truth": "g", "expected_behavior": ["a", "b"]}
    met, why = classbench.judge(Refuses(), case, classbench.Answer("x"))
    assert met == (False, False) and "the judge failed" in why[0]


def test_the_judge_is_given_room_for_the_hidden_reasoning_it_is_billed_for():
    assert classbench.JUDGE_MAX_TOKENS >= 1000


def test_the_bare_model_gets_the_same_token_budget_the_skill_gets():
    """A comparison that starves one side measures the harness, not the skill. The
    first run gave the skill 12,000 tokens and the bare model 1,000;
    three of seven bare runs then died of a truncated completion, which flattered us."""
    safety = classbench.load_script(
        classbench.SKILLS / "studio-safety/scripts/safety.py", "budget_check_safety")
    choreo = classbench.load_script(
        classbench.SKILLS / "painting-to-animation/scripts/choreograph.py", "budget_check_choreo")
    assert classbench.SAFETY_MAX_TOKENS == 12000            # safety.py asks for this
    assert classbench.ANIMATION_MAX_TOKENS == choreo.CHOREOGRAPHY_MAX_TOKENS
    assert "max_tokens=12000" in (
        classbench.SKILLS / "studio-safety/scripts/safety.py").read_text(encoding="utf-8")
    assert safety.SAFETY_PROMPT                              # the skill's instructions exist to be withheld


def test_the_table_counts_judge_failures_so_a_biased_column_cannot_hide(fake_client, monkeypatch):
    """Measured: three judge calls ran out of budget and all three were in the
    bare column, because a bare answer is long prose where the skill returns compact JSON.
    That reads as the bare model doing worse than it did."""
    cases = [{"id": "one", "question": "Screen this. File: ../art-feedback/evals/files/dog-sun.png",
              "ground_truth": "allow", "expected_behavior": ["Returns the verdict allow"]}]
    monkeypatch.setattr(classbench, "cases_for", lambda skill: cases)
    client = fake_client([json.dumps({"verdict": "allow", "reason": "a drawing", "text_found": []}),
                          judge_reply(True), "Yes, fine.", "the judge ran out of room"])
    body = classbench.render("studio-safety",
                             classbench.run("studio-safety", client, client, "vlm.studio", 0.0),
                             "Provenance: fake")
    assert "Judge could not answer" in body
    assert "`vlm.studio` | 1 | 100% | 100% | 1/1 | 0 |" in body      # the skill: none failed
    assert "`vlm.studio+no-skill` | 1 | 0% | 0% | n/a | 1 |" in body  # the bare column: one did


def test_every_report_carries_its_own_limits():
    """A number published without its limits invites a reader to believe more than it says.
    The judge grades its own work, and the same code scored 86% and 100% on consecutive runs."""
    body = classbench.render("studio-safety", [], "Provenance: fake")
    assert "What this does not promise" in body
    assert "does not answer the same way twice" in body
    assert "judge is the model that wrote the answers" in body
    assert "No real child's drawing" in body
