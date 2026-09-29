"""The replay page's technical layer says what the harness did in the adopted run. These tests hold its
numbers to their sources: the run's own steps in the same record, the harness code that set the
limits, and the placing tool's own argument checks, so a claim on the page cannot drift from them."""
import inspect
import json
import re
from pathlib import Path

from evalkit import fromzero
from studio.showpiece import adoption, driver
from studio.showpiece.rebuild_facts import guards

RECORD = Path(__file__).resolve().parents[2] / "studio/showpiece/page/rebuild-record.json"


def record():
    return json.loads(RECORD.read_text(encoding="utf-8"))


def test_the_counts_the_page_shows_add_up_from_the_runs_own_steps():
    data = record()
    steps, facts = data["steps"], data["harness"]
    acts = [s for s in steps if s["kind"] == "act"]
    assert facts["turns"]["actions"] == len(acts) == 71
    assert facts["tokens"] == sum(s.get("tokens", 0) for s in steps) == 1_005_308
    assert abs(facts["tool_seconds"] - sum(s.get("seconds", 0) for s in acts)) < 1
    assert sum(facts["turns"]["by_tool"].values()) == len(acts)
    assert all(s["skill"] and s["command"] for s in acts), "every action names its skill and the command the harness ran"


def test_the_limits_the_page_quotes_are_the_ones_the_harness_code_sets():
    facts = record()["harness"]
    gate = adoption.Adoption()
    assert facts["limits"] == {"actions": 80, "laps": gate.laps, "hand_overs": gate.bounces, "let_go_seconds": gate.min_seconds}
    assert facts["limits"]["actions"] == inspect.signature(fromzero.carpenter).parameters["cap"].default
    assert facts["checks"] == [f"{s}/{t}" for s, t in adoption.CHECKS] + ["shot-judge/judge"]
    assert (facts["model"]["max_tokens"], facts["model"]["retry_tokens"]) == (driver.MAX_TOKENS, driver.RETRY_TOKENS)
    assert facts["guards"] == guards()


def test_what_the_tool_refused_in_the_run_is_what_its_limits_say():
    data = record()
    low, high = data["harness"]["guards"]["spacing_m"]
    refusal = next(s for s in data["steps"] if s["step"] == 26)
    assert f"between {low:g} and {high:g} metres" in refusal["evidence"]
    assert data["harness"]["survey"]["rafters"]["spacing"] < low, "the temple's own rafters are closer than the tool allows"


def test_no_command_on_the_page_carries_a_private_path():
    for step in record()["steps"]:
        command = step.get("command", "")
        assert ".studio/" not in command and "/Users/" not in command and "/home/" not in command, step["step"]
        assert not re.search(r"\b\d{8}-\d{6}-[0-9a-f]{6}\b", command), step["step"]


def test_every_spark_re_run_lasted_as_long_as_the_runs_own_call_asked():
    """The page says each round's gravity and shake tests were re-run on the Spark with the run's own
    settings; the re-run's frames and rate must be what that round's logged command asked for."""
    steps = record()["steps"]
    hall = json.loads(RECORD.with_name("rebuild-hall.json").read_text(encoding="utf-8"))
    for step in (s for s in steps if s.get("physics")):
        seconds = re.search(r"--seconds (\S+)", step["command"])
        fps = re.search(r"--fps (\S+)", step["command"])
        want_fps = int(fps.group(1)) if fps else 24
        want_frames = round((float(seconds.group(1)) if seconds else (6.0 if step["physics"] == "shake" else 4.0)) * want_fps)
        head = hall["rounds"][step["frame"]][step["physics"]]
        assert (head["frames"], head["fps"]) == (want_frames, want_fps), (step["step"], step["physics"])
