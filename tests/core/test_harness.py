"""The stage loop, the ledger and the memory watchdog.

The properties worth holding are the ones a live run cannot easily show: that a
crash resumes, that a gate failure is not an exception, that the ledger never
carries a child's content, and that the watchdog refuses rather than tries.
"""

import pytest

from studio.core.errors import ModelUnavailable
from studio.core.harness import Harness, Stage
from studio.core.ledger import Entry, Ledger, hash_inputs
from studio.core.watchdog import Watchdog, WouldNotFit

PASSES = (True, "fine")


@pytest.fixture
def ledger(tmp_path):
    return Ledger(tmp_path / "ledger.jsonl")


def always(value):
    return lambda inputs: value


def test_stages_run_in_order_and_feed_the_next(ledger):
    seen = []
    stages = [
        Stage("one", "skill-a", lambda inputs: seen.append(sorted(inputs)) or "A"),
        Stage("two", "skill-b", lambda inputs: seen.append(sorted(inputs)) or "B"),
    ]
    outcomes = Harness(ledger).run(stages, {"drawing": "x"})
    assert [outcome.ok for outcome in outcomes] == [True, True]
    assert seen[1] == ["drawing", "one"], "stage two should see stage one's result"


def test_a_failing_gate_stops_the_run_without_raising(ledger):
    stages = [
        Stage("one", "a", always("A"), gate=lambda result: (False, "not good enough")),
        Stage("two", "b", always("B")),
    ]
    harness = Harness(ledger)
    outcomes = harness.run(stages, {})
    assert len(outcomes) == 1, "stage two must not run"
    assert not outcomes[0].ok
    assert harness.stopped_with == "not good enough"


def test_a_failing_gate_is_retried_exactly_once(ledger):
    calls = []

    def flaky(inputs):
        calls.append(1)
        return "good" if len(calls) > 1 else "bad"

    stage = Stage("one", "a", flaky, gate=lambda result: (result == "good", "check"))
    assert Harness(ledger).run([stage], {})[0].ok
    assert len(calls) == 2, "one retry, not more"


def test_repair_gets_the_last_word_after_a_retry_fails(ledger):
    attempts = []

    def run(inputs):
        attempts.append(inputs.get("size", "original"))
        return "good" if inputs.get("size") == "smaller" else "bad"

    stage = Stage(
        "one",
        "a",
        run,
        gate=lambda result: (result == "good", "too big"),
        repair=lambda inputs, reason: {**inputs, "size": "smaller"},
    )
    outcome = Harness(ledger).run([stage], {})[0]
    assert outcome.ok
    assert attempts == ["original", "original", "smaller"]


def test_an_unreachable_model_stops_the_stage(ledger):
    def dead(inputs):
        raise ModelUnavailable("nothing is listening")

    outcome = Harness(ledger).run([Stage("one", "a", dead)], {})[0]
    assert not outcome.ok
    assert "nothing is listening" in outcome.reason


def test_a_restart_skips_what_already_passed(ledger):
    """A crash costs at most one repeated stage, never a wrong answer."""
    ledger.append(Entry(session="s1", stage="one", skill="a", gate="pass", inputs_hash="h"))
    ran = []
    stages = [
        Stage("one", "a", lambda inputs: ran.append("one")),
        Stage("two", "b", lambda inputs: ran.append("two")),
    ]
    Harness(ledger, session="s1").run(stages, {})
    assert ran == ["two"], "stage one already has a pass recorded"


def test_a_stage_with_a_failed_record_runs_again(ledger):
    """Only a recorded pass counts. A failure is not progress."""
    ledger.append(Entry(session="s1", stage="one", skill="a", gate="fail", inputs_hash="h"))
    ran = []
    Harness(ledger, session="s1").run([Stage("one", "a", lambda i: ran.append("one"))], {})
    assert ran == ["one"]


def test_the_ledger_records_every_attempt_not_just_the_last(ledger):
    calls = []
    stage = Stage(
        "one", "a",
        lambda inputs: calls.append(1) or ("good" if len(calls) > 1 else "bad"),
        gate=lambda result: (result == "good", "check"),
    )
    Harness(ledger, session="s2").run([stage], {})
    gates = [entry.gate for entry in ledger.entries("s2")]
    assert gates == ["fail", "pass"]


def test_the_ledger_keeps_no_child_content(ledger):
    """Section 1a promises nothing is kept. A hash proves which drawing without storing it."""
    stage = Stage("one", "a", always("the child said the dragon was lonely"))
    Harness(ledger, session="s3").run([stage], {"drawing": "a photograph of a child's work"})
    written = ledger.path.read_text(encoding="utf-8")
    assert "dragon" not in written
    assert "photograph" not in written


def test_the_same_inputs_hash_the_same_and_different_ones_do_not():
    assert hash_inputs("a", 1) == hash_inputs("a", 1)
    assert hash_inputs("a", 1) != hash_inputs("a", 2)


def test_spend_is_totalled_per_session(ledger):
    for cost in (0.001, 0.002):
        ledger.append(
            Entry(session="s4", stage="x", skill="a", gate="pass", inputs_hash="h",
                  tokens=100, cost_usd=cost)
        )
    tokens, spent = ledger.spent("s4")
    assert tokens == 200
    assert spent == 0.003


# --- the watchdog ------------------------------------------------------------


def test_the_studio_resident_set_fits():
    """The resident set as it stands, and it must load.

    Was 57 GB against section 7's original roster. video.scene and rig.figure
    were deleted — the requirements exclude video generation
    outright, and the animation skill needs no model — which took 16 GB out of
    the always-loaded set. These are the Watchdog's numbers, not the profile's;
    `tests/ops/test_dayzero.py` is what checks the profile itself adds up.
    """
    dog = Watchdog()
    for name, size in (
        ("safety.image", 8.0), ("vlm.studio", 24.0), ("mesh.fast", 6.0),
        ("tts.studio", 5.0), ("depth", 1.0),
    ):
        dog.load(name, size)
    assert dog.used_gb == 44.0


def test_the_big_slot_fits_on_top_of_the_resident_set():
    """44 resident plus the largest rotating occupant peaks at 72, under 90."""
    dog = Watchdog(resident={"resident-set": 44.0})
    assert dog.would_fit(28.0)
    assert dog.peak_for(28.0) == 72.0


def test_a_load_that_would_cross_the_ceiling_is_refused():
    dog = Watchdog(resident={"resident-set": 57.0})
    with pytest.raises(WouldNotFit) as caught:
        dog.load("something-huge", 34.0)
    assert "limit" in str(caught.value)


def test_studio_mode_stays_well_under_what_the_box_makes_usable():
    """The gap between the 90 ceiling and the 108 GB floor is the transient
    allowance. How much of it a load actually needs is not modelled here: that is
    a measurement for day zero, and asserting a guess about it would be a test
    of my arithmetic rather than of the box."""
    dog = Watchdog(resident={"resident-set": 57.0})
    dog.load("image.edit", 28.0)
    assert dog.used_gb == 85.0
    assert dog.used_gb <= dog.ceiling_gb


def test_the_director_model_cannot_join_the_studio_set():
    """109 GB is why there are two modes rather than one."""
    dog = Watchdog(resident={"resident-set": 57.0})
    assert not dog.would_fit(109.0)


def test_the_director_model_does_not_fit_under_the_studio_ceiling_even_alone():
    """Emptying the studio is not enough. It needs the whole box, which is a mode."""
    assert not Watchdog().would_fit(109.0)


def test_director_mode_unloads_everything_and_takes_the_box():
    dog = Watchdog(resident={"resident-set": 57.0, "image.edit": 28.0})
    dog.enter_director_mode("vlm.director", 109.0)
    assert dog.resident == {"vlm.director": 109.0}
    assert dog.director_mode


def test_leaving_director_mode_empties_the_box_again():
    dog = Watchdog()
    dog.enter_director_mode("vlm.director", 109.0)
    dog.restore_studio_mode()
    assert dog.used_gb == 0.0
    assert not dog.director_mode
    assert dog.limit_gb == 90.0


def test_swapping_unloads_before_it_loads():
    """The order is the safety property: both resident at once is the freeze."""
    dog = Watchdog(resident={"resident-set": 57.0, "image.edit": 28.0})
    dog.swap("mesh.premium", 29.0, slot_holder="image.edit")
    assert "image.edit" not in dog.resident
    assert dog.resident["mesh.premium"] == 29.0


def test_swapping_without_unloading_would_have_been_refused():
    """Proof the swap is doing something: the same load without the unload fails."""
    dog = Watchdog(resident={"resident-set": 57.0, "image.edit": 28.0})
    with pytest.raises(WouldNotFit):
        dog.load("mesh.premium", 29.0)


def test_loading_the_same_model_twice_is_free():
    dog = Watchdog()
    dog.load("vlm.studio", 24.0)
    dog.load("vlm.studio", 24.0)
    assert dog.used_gb == 24.0


def test_a_stage_can_refuse_to_be_retried(ledger):
    """A safety verdict is a decision, not a flaky call. Re-rolling a refusal
    until it comes back "allow" is asking a different question until you like
    the answer."""
    calls = []
    stage = Stage(
        "screen", "studio-safety",
        lambda inputs: calls.append(1) or "blocked",
        gate=lambda result: (False, "block: a photograph"),
        retries=0,
    )
    outcome = Harness(ledger).run([stage], {})[0]
    assert not outcome.ok
    assert len(calls) == 1, "a refusal must be asked exactly once"


def test_a_model_error_is_retried_once_even_when_the_stage_refuses_gate_retries(ledger):
    """retries=0 stops a verdict being re-rolled. It must not stop a model that
    returned nothing from being asked once more — that is not a verdict, it is
    an empty reply. Found by a live run."""
    calls = []

    def flaky(inputs):
        calls.append(1)
        if len(calls) == 1:
            raise ModelUnavailable("returned no text")
        return "a verdict"

    stage = Stage("screen", "studio-safety", flaky, retries=0)
    outcome = Harness(ledger).run([stage], {})[0]
    assert outcome.ok
    assert len(calls) == 2


def test_a_refusal_is_never_retried_even_where_model_errors_are(ledger):
    """An outage is asked once more; a refusal is not. The endpoint that rejected
    a request, or the teacher who stopped it, gives the same answer to the same
    call — at twice the wait and twice the bill. Found by review,
    when a stopped teacher report was re-submitted in full."""
    from studio.core.errors import ModelCancelled, ModelRefused
    for refusal in (ModelRefused("no key"), ModelCancelled("stopped")):
        calls = []

        def refuse(inputs, error=refusal):
            calls.append(1)
            raise error

        stage = Stage("report", "teacher-review", refuse, retries=1, retry_model_errors=True)
        outcome = Harness(ledger).run([stage], {})[0]
        assert not outcome.ok and outcome.errored
        assert len(calls) == 1, f"{type(refusal).__name__} must be asked exactly once"


def test_a_model_error_that_persists_is_marked_as_an_error_not_a_decision(ledger):
    def dead(inputs):
        raise ModelUnavailable("nothing is listening")

    outcome = Harness(ledger).run([Stage("screen", "studio-safety", dead, retries=0)], {})[0]
    assert not outcome.ok
    assert outcome.errored, "the caller needs to know this was not a verdict"
    gates = [entry.gate for entry in ledger.entries(Harness(ledger).session)] or ["error"]
    assert "error" in gates


def repaired_run(calls, *, fails_on_repair):
    """Refused as written; the repaired inputs meet a model that fails `fails_on_repair` times."""

    def run(inputs):
        calls.append("repaired" if inputs.get("repaired") else "original")
        if not inputs.get("repaired"):
            return "bad"
        if calls.count("repaired") <= fails_on_repair:
            raise ModelUnavailable("nothing is listening")
        return "good"

    return run


def a_stage_that_repairs(run):
    return Stage(
        "opening", "art-feedback", run,
        gate=lambda result: (result == "good", "rule 9"),
        repair=lambda inputs, reason: {**inputs, "repaired": True},
    )


def test_a_model_error_on_the_repair_attempt_is_an_error_not_a_decision(ledger):
    """The repair attempt is the third ask, and a model can fail on it as easily
    as on the first. Its failure used to come back unmarked, so a teacher was told
    the response had failed a quality check when the model had simply not answered."""
    calls = []
    stage = a_stage_that_repairs(repaired_run(calls, fails_on_repair=2))
    outcome = Harness(ledger).run([stage], {})[0]
    assert not outcome.ok
    assert outcome.errored, "the caller needs to know the repair attempt was not a verdict"
    assert "nothing is listening" in outcome.reason


def test_the_repair_attempt_is_asked_once_more_after_a_model_error_like_any_other(ledger):
    """A model that returned nothing is asked once more on every attempt, and the
    repair attempt is an attempt. It called the skill directly and missed the one
    cheap retry the first two attempts get."""
    calls = []
    stage = a_stage_that_repairs(repaired_run(calls, fails_on_repair=1))
    outcome = Harness(ledger).run([stage], {})[0]
    assert outcome.ok
    assert calls == ["original", "original", "repaired", "repaired"]


def test_what_was_written_is_offered_before_its_gate_rules(ledger):
    """The rule judges take 12-37 s on the Spark against 5 s for the writing.

    The watcher hears the draft between the two, so the page can show it as
    under review; the outcome is still decided by the gate alone.
    """
    heard = []
    stage = Stage("one", "art-feedback", always("draft words"),
                  gate=lambda result: (heard.append("gate") or False, "rule 9"))
    outcome = Harness(ledger, observe=lambda t: heard.append((t.status, t.draft))).run([stage], {})[0]
    assert not outcome.ok
    assert heard[:3] == [("running", ""), ("checking", "draft words"), "gate"]


def test_only_text_is_offered_as_a_draft(ledger):
    heard = []
    stages = [Stage("screen", "studio-safety", always({"verdict": "allow"})), Stage("blank", "b", always("  "))]
    Harness(ledger, observe=lambda t: heard.append(t.status)).run(stages, {})
    assert "checking" not in heard
