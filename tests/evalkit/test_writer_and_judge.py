"""Keep writer and reviewer requests separate.

The approved deployment plan permits Step 3.7 Flash in both
roles, using independent requests with distinct reasoning configurations.
Historical benchmark profiles retain their cross-model requirement.
"""

import pytest

from evalkit.runner import JUDGE_SLOT, WRITER_SLOT, argument_parser
from studio.core.slots import PROFILE_DIR, load_profile

PROFILES = sorted(path.stem for path in PROFILE_DIR.glob("*.yaml"))


def test_the_benchmark_does_not_default_to_marking_its_own_work():
    arguments = argument_parser().parse_args([])
    assert arguments.slot == WRITER_SLOT
    assert arguments.judge == JUDGE_SLOT
    assert arguments.slot != arguments.judge


def test_the_two_slots_are_not_the_same_name():
    """A guard against someone 'simplifying' the two constants into one."""
    assert WRITER_SLOT != JUDGE_SLOT


@pytest.mark.parametrize("profile", PROFILES)
def test_profiles_keep_their_approved_writer_and_review_roles(profile):
    """New deployment roles share weights; historical benchmarks stay distinct."""
    slots = load_profile(profile)
    writer, judge = slots.get(WRITER_SLOT), slots.get(JUDGE_SLOT)
    if writer is None or judge is None:
        pytest.skip(f"{profile} does not resolve both slots")
    if profile == "stepfun":
        # Operator: no Step 3.7 Flash in anything a person waits for, so the class's writer
        # and its judges are the same Qwen on the Spark, thinking off, judging in a second or two.
        assert writer.provider == judge.provider == "llamacpp"
        assert writer.model == judge.model == "qwen3.6-35b-a3b"
        return
    assert writer.model != judge.model, (
        f"{profile} gives {WRITER_SLOT} and {JUDGE_SLOT} the same model "
        f"({writer.model}), so the writer would grade itself"
    )


@pytest.mark.parametrize("profile", PROFILES)
def test_a_profile_that_judges_locally_does_not_share_the_writers_server(profile):
    """Same model, two ports is still the same model — and so is one port.

    On the Spark both slots are local, so "different model" has to mean a
    different server too: a profile that pointed them at one base_url would put
    the same loaded weights on both sides of the mark.
    """
    slots = load_profile(profile)
    writer, judge = slots.get(WRITER_SLOT), slots.get(JUDGE_SLOT)
    if writer is None or judge is None:
        pytest.skip(f"{profile} does not resolve both slots")
    writer_url = writer.options.get("base_url")
    judge_url = judge.options.get("base_url")
    if writer.provider == judge.provider == "stepfun":
        return  # Stateless API requests can share the official endpoint.
    if profile == "stepfun":
        return  # One Qwen writes and judges by the operator's choice (test above).
    if writer_url and judge_url:
        assert writer_url != judge_url, (
            f"{profile} serves both {WRITER_SLOT} and {JUDGE_SLOT} from {writer_url}"
        )


def test_a_published_number_names_the_model_that_produced_it():
    """BENCHMARK.md carried figures from a hosted stand-in and said so nowhere.

    The shipping model had never been measured, and no line on the page would
    have told anyone. A benchmark that does not name its model is the same
    defect as a writer grading itself: the number looks like evidence and is
    evidence about something else.
    """
    from evalkit.runner import _provenance, render_benchmark

    development = _provenance(argument_parser().parse_args([]))
    target = _provenance(argument_parser().parse_args(["--profile", "spark"]))

    assert "`qwen/qwen3-vl-8b-instruct` via `openrouter`" in development
    assert "differs from configured Spark target `step3-vl-10b`" in development
    assert "Graded by `step-3.7-flash` via `stepfun`" in development
    assert "`step3-vl-10b` via `llamacpp`" in target
    assert "matches configured Spark target `step3-vl-10b`" in target
    assert "hardware not verified" in development and "hardware not verified" in target

    one = {"cases": 1, "case_pass_rate": 1.0, "mean_rule_pass_rate": 1.0,
           "total_cost_usd": 0.0, "mean_latency_s": 1.0, "failures_by_rule": {}}
    page = render_benchmark({"slots": {"vlm.studio": one}}, development)
    assert development in page, "the provenance line must reach the published page"


def test_the_benchmark_keeps_the_development_profile_as_its_default():
    from evalkit.runner import DEFAULT_PROFILE

    assert argument_parser().parse_args([]).profile == DEFAULT_PROFILE == "local"


@pytest.mark.parametrize("profile,slot,relation", [
    ("cloud", "vlm.studio", "differs from"),
    (str(PROFILE_DIR / "spark.yaml"), "vlm.studio", "matches"),
    ("spark", "vlm.director", "differs from"),
])
def test_provenance_compares_the_resolved_writer_instead_of_the_profile_name(profile, slot, relation):
    from evalkit.runner import _provenance

    line = _provenance(argument_parser().parse_args(["--profile", profile, "--slot", slot]))
    assert f"{relation} configured Spark target `step3-vl-10b`" in line
    assert "hardware not verified" in line


def test_a_missing_spark_plan_does_not_erase_the_models_actually_measured(monkeypatch):
    from evalkit import runner

    monkeypatch.setattr(runner, "SPARK_PROFILE", "missing-profile")
    line = runner._provenance(argument_parser().parse_args([]))
    assert "`qwen/qwen3-vl-8b-instruct` via `openrouter`" in line
    assert "configured Spark target unavailable" in line


def test_a_run_where_everything_skipped_reports_it_rather_than_crashing():
    """The last step used to raise on an empty summary, after the run was paid for."""
    from evalkit.runner import render_benchmark

    page = render_benchmark({"slots": {}}, "")
    assert "every case was skipped" in page
