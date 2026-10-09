import pytest

from evalkit.rubric.report import RubricReport, RuleResult
from evalkit.runner import (
    CaseOutcome,
    red_line_failures,
    render_benchmark,
    summarise,
)


def outcome(case_id, slot, passed, cost=0.001, latency=1.0, tokens=200):
    results = tuple(
        RuleResult(number, f"rule {number}", "pass" if passed else "fail", "because")
        for number in range(1, 11)
    )
    return CaseOutcome(case_id, slot, "some feedback", RubricReport(results), latency, cost, tokens)


def test_summarise_reports_a_pass_rate_per_slot():
    summary = summarise([
        outcome("a", "vlm.studio", True),
        outcome("b", "vlm.studio", False),
        outcome("c", "vlm.director", True),
    ])
    assert summary["slots"]["vlm.studio"]["cases"] == 2
    assert summary["slots"]["vlm.studio"]["case_pass_rate"] == 0.5
    assert summary["slots"]["vlm.director"]["case_pass_rate"] == 1.0


def test_summarise_totals_cost_and_mean_latency():
    summary = summarise([
        outcome("a", "vlm.studio", True, cost=0.002, latency=2.0),
        outcome("b", "vlm.studio", True, cost=0.004, latency=4.0),
    ])
    assert summary["slots"]["vlm.studio"]["total_cost_usd"] == 0.006
    assert summary["slots"]["vlm.studio"]["mean_latency_s"] == 3.0


def test_summarise_counts_failures_per_rule():
    summary = summarise([outcome("a", "vlm.studio", False)])
    assert summary["slots"]["vlm.studio"]["failures_by_rule"]["1"] == 1


def test_render_benchmark_names_every_slot_and_the_verdict():
    summary = summarise([outcome("a", "vlm.studio", True), outcome("b", "vlm.director", True)])
    text = render_benchmark(summary)
    assert "vlm.studio" in text
    assert "vlm.director" in text
    assert "PASS" in text


def test_the_runner_no_longer_reads_an_age_out_of_a_case():
    """Age modelling was dropped, so the reader went with it."""
    import evalkit.runner as runner

    assert not hasattr(runner, "age_band_for")


def test_a_bare_skill_run_is_summarised_beside_the_skill_run():
    """The comparison NVIDIA scores is with-skill against without-skill."""
    summary = summarise([
        outcome("a", "vlm.director", True),
        outcome("a", "vlm.director+no-skill", False),
    ])
    assert summary["slots"]["vlm.director"]["case_pass_rate"] == 1.0
    assert summary["slots"]["vlm.director+no-skill"]["case_pass_rate"] == 0.0


def test_the_runner_reads_the_entrance_out_of_a_case():
    """The teacher picks by hand, so the case says which door it walks through."""
    from evalkit.runner import entrance_for

    assert entrance_for("Give feedback at the sketch entrance. File: evals/files/sphere-study.png") == "sketch"
    assert entrance_for("Give feedback at the colour entrance. File: evals/files/dog-sun.png") == "colour"


def test_a_case_naming_no_entrance_is_refused_rather_than_defaulted():
    from evalkit.runner import entrance_for

    with pytest.raises(ValueError):
        entrance_for("Give feedback on this drawing. File: evals/files/dog-sun.png")


class _Flaky:
    """Returns nothing the first time it is asked, then answers."""

    def __init__(self, failures):
        self.failures = failures
        self.calls = 0

    def chat(self, prompt, images=(), *, system=None, max_tokens=None):
        from studio.core.errors import EmptyCompletion
        from studio.providers.base import ChatResult

        self.calls += 1
        if self.calls <= self.failures:
            raise EmptyCompletion("returned no text")
        return ChatResult(
            text="I see a purple dog. What is happening?", input_tokens=10, output_tokens=10,
            reasoning_tokens=0, cost_usd=0.0, latency_s=0.0, provider="fake", model="fake",
        )


def test_one_empty_completion_does_not_end_the_benchmark():
    """Measured: Step 3.7 Flash returned nothing three times in
    forty-two calls. Unguarded, the first one threw away every case paid for
    before it."""
    from evalkit.runner import _write_or_skip

    client = _Flaky(failures=1)
    result = _write_or_skip(client, "prompt", "data:image/png;base64,AA", "a-case")
    assert result is not None
    assert client.calls == 2


def test_a_case_that_never_answers_is_dropped_rather_than_scored_zero():
    """Silence has earned neither a pass nor a fail, and scoring it as zero
    would publish an outage as a quality."""
    from evalkit.runner import _write_or_skip

    client = _Flaky(failures=99)
    assert _write_or_skip(client, "prompt", "data:image/png;base64,AA", "a-case") is None


def crossing(case_id, slot, rule):
    """One case that failed a single rule, so red-line handling can be exercised."""
    results = (RuleResult(rule, f"rule {rule}", "fail", "because"),)
    return CaseOutcome(case_id, slot, "some feedback", RubricReport(results), 1.0, 0.001, 200)


def test_a_crossed_red_line_is_counted_rather_than_crashing():
    """It read a field that does not exist, behind the one condition that means
    the benchmark has something serious to say. Found by the type checker,
    never by a test, because no invented fixture ever crossed one."""
    counts = red_line_failures([
        crossing("a", "vlm.director", 1),
        crossing("b", "vlm.director", 8),
        crossing("c", "vlm.director+no-skill", 14),
    ])
    assert counts == {"vlm.director": 2, "vlm.director+no-skill": 1}


def test_a_quality_failure_is_not_a_red_line():
    assert red_line_failures([crossing("a", "vlm.studio", 3)]) == {}


def test_the_skill_script_actually_loads():
    """The benchmark could not reach its first case: the loader never registered
    the module, so the dataclass in feedback.py raised at import. Nothing caught
    it because nothing ever ran the runner's loader outside a live run."""
    from pathlib import Path

    from evalkit.runner import _load_script

    script = _load_script(Path("skills/art-feedback"))
    settings = script.ClassSettings("colour", "zh")
    assert settings.language_name == "Chinese"
    assert script.build_prompt(settings)
