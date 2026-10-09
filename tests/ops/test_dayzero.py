"""The day-zero kit, checked here so the box does not have to debug it.

A measurement script that is written on the day is written badly. These tests
hold the two things that would waste that hour: a check that cannot fail is
worth nothing, and a check that crashes reports nothing.
"""

import pytest

from studio.ops.dayzero import (
    check_mode_switching,
    check_nothing_leaves_the_box,
    check_the_box,
    check_the_ceiling,
    check_the_studio_fits,
    run,
)
from studio.core.slots import SlotConfig, load_profile


def slot(name, provider="llamacpp", **options):
    return SlotConfig(name, provider, "a-model", options)


def test_the_spark_profile_reports_its_hosted_video_fallback():
    """The Replicate Wan fallback must never be labelled fully offline."""
    profile = load_profile("spark")
    finding = check_nothing_leaves_the_box(profile)
    assert not finding.ok
    assert "video.animation" in finding.detail
    assert "mesh.portrait" not in finding.detail
    assert profile["mesh.portrait"].provider == "localmesh"


@pytest.mark.parametrize("provider, offline", [("llamacpp", True), ("localmesh", True), ("openrouter", False)])
def test_the_offline_check_distinguishes_local_and_hosted_slots(provider, offline):
    finding = check_nothing_leaves_the_box({"vlm.studio": slot("vlm.studio", provider)})
    assert finding.ok is offline
    if not offline:
        assert "vlm.studio" in finding.detail


def test_the_cloud_profile_is_correctly_reported_as_leaving_the_box():
    finding = check_nothing_leaves_the_box(load_profile("cloud"))
    assert not finding.ok, "the cloud profile sends drawings to OpenRouter, and should say so"


def test_the_studio_set_fits_under_the_ceiling():
    """Section 7's arithmetic. The figures are held by the test below; they were 57, 30 and 87 when this was written."""
    finding = check_the_studio_fits(load_profile("spark"))
    assert finding.ok, finding.detail
    assert finding.numbers["peak_gb"] <= 90


def test_nvidias_safety_model_takes_the_place_of_the_one_it_replaces_and_the_class_still_fits():
    """ShieldGemma 2 was planned at 8 GB and never built; Nemotron 3.5 Content Safety measured about 11.
    The four verdicts are written by the resident studio model, which costs no second copy of it."""
    profile = load_profile("spark")
    assert profile["safety.reader"].options["size_gb"] == 11
    assert profile["safety.image"].model == profile["vlm.studio"].model and "size_gb" not in profile["safety.image"].options
    finding = check_the_studio_fits(profile)
    assert finding.ok and finding.numbers["resident_gb"] == 71 and finding.numbers["peak_gb"] == 90, finding.detail


def test_a_model_never_loaded_during_a_class_is_kept_out_of_the_class_arithmetic_and_said_so():
    """The engineer's review runs for the showpiece, started for a review and stopped after it."""
    profile = load_profile("spark")
    assert profile["llm.engineer"].options.get("outside_class") is True
    finding = check_the_studio_fits(profile)
    assert "outside class: llm.engineer 21" in finding.detail
    counted = dict(profile)
    counted["llm.engineer"] = slot("llm.engineer", size_gb=21, rotating_slot=True)
    assert not check_the_studio_fits(counted).ok, "counted as a class-time model it would not fit, which is why it is marked"


def test_a_model_kept_out_of_class_must_still_fit_the_box_by_itself():
    finding = check_the_studio_fits({"huge": slot("huge", size_gb=95, rotating_slot=True, outside_class=True)})
    assert not finding.ok and "huge" in finding.detail


def test_a_profile_too_big_for_the_box_is_refused_rather_than_loaded():
    finding = check_the_studio_fits(
        {f"slot-{index}": slot(f"slot-{index}", size_gb=40) for index in range(3)}
    )
    assert not finding.ok
    assert "REFUSED" in finding.detail


def test_the_state_machine_never_traps_the_studio_in_director_mode():
    assert check_mode_switching().ok


def test_the_box_reports_its_own_memory():
    finding = check_the_box()
    assert finding.ok, "every host this runs on should report its memory"
    assert finding.numbers["total_gb"] > 1


def test_the_ceiling_check_fails_honestly_on_a_machine_that_is_too_small(monkeypatch):
    """On this Mac it should fail: 64 GB cannot hold a 109 GB director model."""
    monkeypatch.setattr("studio.ops.dayzero.usable_memory_gb", lambda: (64.0, "test"))
    assert not check_the_ceiling().ok
    monkeypatch.setattr("studio.ops.dayzero.usable_memory_gb", lambda: (128.0, "test"))
    assert check_the_ceiling().ok


def test_the_whole_kit_runs_and_reports_rather_than_raising():
    findings = run("spark", full=False)
    assert len(findings) >= 7
    assert all(isinstance(finding.detail, str) and finding.detail for finding in findings)


@pytest.mark.parametrize("profile", ["cloud", "spark"])
def test_every_profile_loads(profile):
    assert load_profile(profile), f"{profile}.yaml should resolve at least one slot"


def test_a_full_box_refuses_a_request_rather_than_freezing(tmp_path, monkeypatch):
    """Section 7: out of memory freezes the machine, and a freeze during a class
    is the end of the class. The ceiling used to be arithmetic with a unit test and no
    caller."""
    from studio.classroom.classroom import Classroom

    classroom = Classroom(tmp_path / "l.jsonl", clients={"vlm.studio": None, "vlm.director": None})
    monkeypatch.setattr("studio.classroom.classroom.used_memory_gb", lambda: 4.0)
    assert not classroom._too_full()
    # The resident chat voice and TRELLIS.2 hold 93.6 GB, and a class must still run on them.
    monkeypatch.setattr("studio.classroom.classroom.used_memory_gb", lambda: 93.6)
    assert not classroom._too_full()
    monkeypatch.setattr("studio.classroom.classroom.used_memory_gb", lambda: 116.0)
    assert classroom._too_full(), "past the ceiling, one more model load freezes the box"
