"""The hand-over gate: a model's "finished" is a claim, and the run folder is the evidence.
No Blender here; the gate reads events and JSON, so every refusal is proven on made-up ones."""
import json

import pytest

from conftest import FakeClient
from studio.showpiece import catalog
from studio.showpiece import driver as drv
from studio.showpiece.adoption import Adoption


def act(skill, tool, text="ok", **more):
    return {"kind": "act", "skill": skill, "tool": tool, "text": text, "command": f"{skill}/{tool}", "args": {}, **more}


PLACE = act("hall-carpenter", "roof")
CHECKS = [act("model-anatomy", "inventory"), act("model-anatomy", "bearing"), act("load-path", "weights"),
          act("load-path", "settle"), act("load-path", "shake"), act("hall-carpenter", "likeness")]
LOOK = act("shot-judge", "judge", args={"image": "likeness.png"}, verdict={"verdict": "pass", "change": ""})


def folder(tmp_path, floating=(), fell=0, shifted=0, frames=30, alike=True, short=(), overloaded=(), came_down=(), seconds=3.0):
    (tmp_path / "bearing.json").write_text(json.dumps({"floating": {n: None for n in floating}}))
    (tmp_path / "loads.json").write_text(json.dumps({"summary": {"allowed_MPa": 10.0, "overloaded": list(overloaded)}}))
    (tmp_path / "settle.json").write_text(json.dumps({"summary": {"fell": fell, "shifted": shifted, "frames": frames,
                                                                  "seconds": seconds}}))
    (tmp_path / "likeness.json").write_text(json.dumps({"alike": alike, "short_of_the_temple": list(short)}))
    (tmp_path / "shake.json").write_text(json.dumps({"summary": {"shake": {
        "peak_g": 0.2, "pull_g": 0.07, "came_down": len(came_down), "came_down_names": list(came_down)}}}))
    return tmp_path


def test_a_hall_with_every_check_fresh_and_passed_is_adopted(tmp_path):
    assert Adoption().outstanding(folder(tmp_path), [PLACE, *CHECKS, LOOK]) == []


def test_nothing_placed_is_nothing_to_hand_over(tmp_path):
    assert Adoption().outstanding(tmp_path, [CHECKS[0]]) == ["nothing has been placed yet"]


def test_a_check_older_than_the_last_change_does_not_count(tmp_path):
    owed = Adoption().outstanding(folder(tmp_path), [PLACE, *CHECKS, LOOK, PLACE])
    assert len(owed) == len(CHECKS) and all("changed after the last" in r for r in owed)


def test_a_tool_that_failed_or_was_refused_is_not_a_check(tmp_path):
    failed = act("load-path", "settle", text="exit 1: Traceback")
    refused = {k: v for k, v in act("hall-carpenter", "likeness").items() if k != "command"}
    owed = Adoption().outstanding(folder(tmp_path), [PLACE, *CHECKS[:2], failed, refused, LOOK])
    assert [r for r in owed if "load-path/settle" in r] and [r for r in owed if "hall-carpenter/likeness" in r]


def test_each_failed_check_is_a_reason_in_words_the_model_can_act_on(tmp_path):
    events = [PLACE, *CHECKS, LOOK]
    assert "2 pieces hang in mid-air" in Adoption().outstanding(folder(tmp_path, floating=("a", "b")), events)[0]
    assert "3 pieces fell and 1 shifted" in Adoption().outstanding(folder(tmp_path, fell=3, shifted=1), events)[0]
    assert "less than three seconds" in Adoption().outstanding(folder(tmp_path, frames=5, seconds=0.5), events)[0]
    assert Adoption().outstanding(folder(tmp_path, alike=False, short=("the front shadow shares 70%",)), events) == [
        "the front shadow shares 70%"]


def test_the_eyes_must_look_after_the_picture_was_made_and_must_pass(tmp_path):
    early = [PLACE, LOOK, *CHECKS]
    assert "eyes have not looked" in Adoption().outstanding(folder(tmp_path), early)[0]
    failed = act("shot-judge", "judge", args={"image": "likeness.png"}, verdict={"verdict": "fail", "change": "posts stick out"})
    assert "posts stick out" in Adoption().outstanding(folder(tmp_path), [PLACE, *CHECKS, failed])[0]


def test_bearing_before_inventory_is_refused_because_it_read_the_old_pieces(tmp_path):
    owed = Adoption().outstanding(folder(tmp_path), [PLACE, CHECKS[1], CHECKS[0], *CHECKS[2:], LOOK])
    assert owed == ["inventory, bearing and settle must run in that order, each reading the one before"]


def test_columns_too_thin_for_what_they_carry_keep_the_hall_from_being_handed_over(tmp_path):
    """A frame can stand in the settle test and still ask a column to carry more than timber can:
    the load numbers were always there, and until now nothing in the gate read them."""
    thin = {"name": "Column -4.00 -3.00", "carries_kN": 55.0, "diameter_m": 0.05, "stress_MPa": 28.0}
    owed = Adoption().outstanding(folder(tmp_path, overloaded=(thin,)), [PLACE, *CHECKS, LOOK])
    assert owed == ["1 column carries more than its timber can bear (over 10 MPa): Column -4.00 -3.00 at 28.0 MPa; "
                    "make the columns thicker"]


def test_a_hall_with_pieces_pulled_over_in_the_shake_is_not_handed_over(tmp_path):
    """Standing when let go is not enough: a post only stood on end is pulled over by a sideways pull
    a real hall shrugs off, and the reason names it and says what a carpenter would do."""
    owed = Adoption().outstanding(folder(tmp_path, came_down=("Frame 0.00 | king post", "Frame 4.41 | king post")),
                                  [PLACE, *CHECKS, LOOK])
    assert len(owed) == 1 and "2 pieces came down" in owed[0] and "Frame 0.00 | king post" in owed[0]
    assert "0.2 g" in owed[0] and "0.07 g" in owed[0] and "cut" in owed[0]


def test_a_shake_that_never_ran_or_ran_before_the_bearing_it_reads_does_not_count(tmp_path):
    unshaken = [e for e in CHECKS if e["tool"] != "shake"]
    assert any("load-path/shake" in r for r in Adoption().outstanding(folder(tmp_path), [PLACE, *unshaken, LOOK]))
    early = [PLACE, CHECKS[0], CHECKS[4], *CHECKS[1:4], CHECKS[5], LOOK]
    assert "shake must run after bearing" in " ".join(Adoption().outstanding(folder(tmp_path), early))


def test_eyes_that_looked_before_the_likeness_picture_was_made_did_not_see_it(tmp_path):
    """The picture the eyes judge is written by likeness, the last check; a look at the one before it is
    a look at the old hall."""
    stale = [PLACE, *CHECKS[:-1], LOOK, CHECKS[-1]]
    assert "eyes have not looked" in Adoption().outstanding(folder(tmp_path), stale)[0]


def test_the_engineers_review_can_neither_pass_nor_fail_a_hall(tmp_path):
    """Advice from a model is not a check: a hall with every check passed is handed over whatever the
    engineer wrote, and one that never asked is handed over too."""
    alarmed = act("hall-carpenter", "review", text="REVIEW 5 notes (advice, not a check): ties: far too thin")
    assert Adoption().outstanding(folder(tmp_path), [PLACE, *CHECKS, alarmed, LOOK]) == []
    assert Adoption().outstanding(folder(tmp_path), [PLACE, *CHECKS, LOOK]) == []
    failing = Adoption().outstanding(folder(tmp_path, fell=2), [PLACE, *CHECKS, act("hall-carpenter", "review", text="REVIEW 0 notes"), LOOK])
    assert failing and "fell" in failing[0], "and a kind review rescues nothing"
    assert Adoption().laps_used([PLACE, alarmed, PLACE]) == 0, "a review is not a check that opens a repair lap"


def test_weights_read_before_bearing_read_the_old_carrying_order_and_do_not_count(tmp_path):
    events = [PLACE, CHECKS[0], CHECKS[2], CHECKS[1], *CHECKS[3:], LOOK]
    assert Adoption().outstanding(folder(tmp_path), events) == ["weights must run after bearing, reading its bearing.json"]


def test_the_fault_report_names_the_columns_too_weak_for_their_load(tmp_path):
    import subprocess
    import sys
    thin = {"name": "Column -4.00 -3.00", "carries_kN": 55.0, "diameter_m": 0.05, "stress_MPa": 28.0}
    (tmp_path / "loads.json").write_text(json.dumps({"summary": {"allowed_MPa": 10.0, "overloaded": [thin]}}))
    script = catalog.SKILLS / "hall-carpenter/scripts/faults.py"
    out = subprocess.run([sys.executable, str(script), str(tmp_path)], capture_output=True, text=True).stdout
    faults = json.loads((tmp_path / "faults.json").read_text())
    assert faults["too_weak"] == [thin] and "too weak 1: Column -4.00 -3.00 at 28.0 MPa" in out


def test_the_fault_report_names_what_came_down_in_the_shake_and_judges_a_slender_column_on_its_design_stress(tmp_path):
    import subprocess
    import sys
    bowed = {"name": "Column 4.00 3.00", "carries_kN": 49.0, "diameter_m": 0.15, "stress_MPa": 2.8, "design_MPa": 33.4}
    (tmp_path / "loads.json").write_text(json.dumps({"summary": {"allowed_MPa": 10.0, "overloaded": [bowed]}}))
    (tmp_path / "shake.json").write_text(json.dumps({"summary": {"shake": {
        "peak_g": 0.2, "pull_g": 0.07, "came_down": 2, "came_down_names": ["Frame 0.00 | king post", "Frame 4.41 | king post"]}}}))
    script = catalog.SKILLS / "hall-carpenter/scripts/faults.py"
    out = subprocess.run([sys.executable, str(script), str(tmp_path)], capture_output=True, text=True).stdout
    faults = json.loads((tmp_path / "faults.json").read_text())
    assert faults["came_down_in_the_shake"] == ["Frame 0.00 | king post", "Frame 4.41 | king post"]
    assert "came down in the shake 2: Frame 0.00 | king post; Frame 4.41 | king post" in out
    assert "Column 4.00 3.00 at 33.4 MPa" in out, "the number beside the limit is the one the column was judged on"


def test_the_harness_counts_the_repair_laps_and_stops_the_one_too_many():
    gate = Adoption(laps=2)
    lap = [PLACE, CHECKS[1]]
    assert gate.laps_used([PLACE, PLACE, *lap]) == 0, "placing the hall the first time is not a repair"
    assert gate.laps_used([*lap, *lap, PLACE]) == 2
    again = {"skill": "hall-carpenter", "tool": "frames"}
    assert gate.refuses([*lap, PLACE, CHECKS[1]], again) is None
    assert "all 2 repair laps are used" in gate.refuses([*lap, *lap, *lap], again)
    assert gate.refuses([*lap, *lap, *lap], {"skill": "hall-carpenter", "tool": "faults"}) is None, "looking is free"


class Owing:
    bounces = 2

    def outstanding(self, run_dir, events):
        return ["3 pieces hang in mid-air"]

    def refuses(self, events, action):
        return None


def test_a_final_the_gate_refuses_goes_back_to_the_model_with_the_reason_then_stops_the_run(tmp_path):
    client = FakeClient([json.dumps({"think": "done", "final": "the hall is finished"})] * 3)
    run = drv.Driver(client, None, tmp_path, cap=5, gate=Owing()).run_sync("rebuild", from_nothing=True)
    kinds = [e["kind"] for e in run.events]
    assert kinds == ["think", "bounce", "think", "bounce", "think", "stop"]
    assert "harness: not handed over yet: 3 pieces hang in mid-air" in client.calls[1]["prompt"]
    assert run.events[-1]["text"].startswith("not adopted after 2 refusals")
    assert run.model.endswith("hall.blend") and str(run.dir) in run.model


def test_without_a_gate_the_exhibit_behaves_as_it_always_did(tmp_path):
    client = FakeClient([json.dumps({"think": "done", "final": "one shot"})])
    run = drv.Driver(client, None, tmp_path, cap=5).run_sync("show me")
    assert [e["kind"] for e in run.events] == ["think", "final"] and run.events[-1]["adopted"] is False
    assert set(catalog.load_skills()) == set(catalog.SIX), "the exhibit's menu does not grow a carpenter by accident"


def test_a_placing_tool_is_told_its_part_and_where_the_hall_is_and_the_survey_reads_the_temple(tmp_path):
    spec = catalog.TOOLS[("hall-carpenter", "columns")]
    argv = catalog.argv_for(spec, {"xs": "-4,4", "ys": [-3, 3], "foot": 0.5, "height": 3}, None, tmp_path,
                            hall=tmp_path / "hall.blend")
    tail = argv[argv.index("--") + 1:]
    assert tail[:2] == ["columns", str(tmp_path / ".")] or tail[:2] == ["columns", str(tmp_path)]
    assert "--xs=-4,4" in tail and "--ys=-3,3" in tail and tail[-2:] == ["--hall", str(tmp_path / "hall.blend")]
    assert catalog.TOOLS[("hall-carpenter", "survey")].reference and not catalog.TOOLS[("load-path", "settle")].reference


def test_the_stage_render_defaults_never_reach_a_placing_tool():
    """The rehearsal's frames came out 960 m wide: `width` is a render flag and a beam's flag."""
    frames = catalog.TOOLS[("hall-carpenter", "frames")]
    assert "width" in frames.flags and catalog.quick_args(frames, {"seat": 9.0}, catalog.QUICK) == {"seat": 9.0}
    settle = catalog.TOOLS[("load-path", "settle")]
    assert catalog.quick_args(settle, {}, catalog.QUICK)["width"] == "960"


def test_a_tools_verdict_line_is_the_last_thing_the_agent_reads(tmp_path):
    """Blender's progress lines flush after the tool's print, so SETTLE's answer sat out of sight."""
    import sys

    from studio.showpiece.blender_bin import run_tool
    noisy = "print('SETTLE 9 pieces fell 0 shifted 0'); print('\\n'.join(f'bake: frame {i} :: 900' for i in range(900)))"
    code, text = run_tool([sys.executable, "-c", noisy], 30)
    assert code == 0 and text.rstrip().endswith("SETTLE 9 pieces fell 0 shifted 0")
    assert run_tool([sys.executable, "-c", "print('quiet')"], 30) == (0, "quiet\n")


def test_an_input_the_folder_already_holds_is_filled_in_and_one_the_model_gave_is_kept(tmp_path):
    settle = catalog.TOOLS[("load-path", "settle")]
    assert catalog.known_inputs(settle, {"seconds": 3}, tmp_path) == {"seconds": 3}, "nothing is invented"
    (tmp_path / "anatomy.json").write_text("{}")
    assert catalog.known_inputs(settle, {"seconds": 3}, tmp_path) == {"anatomy": "anatomy.json", "seconds": 3}
    assert catalog.known_inputs(settle, {"anatomy": "other.json"}, tmp_path)["anatomy"] == "other.json"


def test_a_file_read_long_ago_is_a_stub_in_the_transcript_and_a_fresh_one_is_whole():
    read = {"step": 2, "kind": "act", "skill": "showpiece", "tool": "read", "args": {}, "text": "x" * 5000}
    later = [{"step": i, "kind": "think", "text": "t"} for i in range(3, 3 + drv.RECENT)]
    assert "x" * 5000 in drv.transcript([read, *later[:2]])
    old = drv.transcript([read, *later])
    assert "x" * 300 not in old and "read it again if you need it" in old


def test_the_digest_of_a_gravity_result_leads_with_what_moved(tmp_path):
    from studio.showpiece.files import read_file
    pieces = {f"Still {i:04d}": {"moved_m": 0.001, "drop_m": 0.0, "pad": "p" * 80} for i in range(200)}
    pieces["Fallen beam"] = {"moved_m": 1.2, "drop_m": 1.18, "pad": ""}
    (tmp_path / "settle.json").write_text(json.dumps({"pieces": pieces, "summary": {"fell": 1}}))
    text = read_file(tmp_path, "settle.json")
    assert text.index("Fallen beam") < text.index("Still 0000")


def test_the_fault_report_looks_to_the_ground_and_calls_an_old_check_old(tmp_path):
    import os
    import subprocess
    import sys
    box = lambda x, z0, z1: [[x, 0, z0], [x + 1, 1, z1]]   # noqa: E731
    pieces = {"Platform": {"role": "ground", "box": box(0, 0, 1)}, "Frame 0.00 | post 1 +": {"role": "timber", "box": box(0, 5, 6)},
              "Frame 9.00 | post 1 +": {"role": "timber", "box": box(9, 5, 6)}}
    (tmp_path / "anatomy.json").write_text(json.dumps({"pieces": pieces}))
    (tmp_path / "settle.json").write_text(json.dumps({"pieces": {}, "summary": {}}))
    (tmp_path / "hall.blend").write_text("")
    os.utime(tmp_path / "settle.json", (1, 1))
    (tmp_path / "bearing.json").write_text(json.dumps({"floating": {n: None for n in pieces if n != "Platform"}}))
    script = catalog.SKILLS / "hall-carpenter/scripts/faults.py"
    out = subprocess.run([sys.executable, str(script), str(tmp_path)], capture_output=True, text=True).stdout
    faults = json.loads((tmp_path / "faults.json").read_text())
    post = faults["hanging"][0]
    assert post["pieces"] == 2 and post["gap_m"] == 4.0 and post["nearest_below"] == "Platform"
    assert faults["moved_under_gravity"] == "settle: not run since the hall last changed" and "settle: not run" in out


def test_the_check_that_failed_may_be_run_first_after_a_repair_and_still_counts(tmp_path):
    """The fourth live run spent 18 of its 37 minutes proving the physics again before reaching the
    six-second likeness check that was failing. The gate never needed that order: likeness and the eyes
    only have to be newer than the last change, so the builder is told to run the failed check first."""
    likeness, rest = CHECKS[-1], CHECKS[:-1]
    assert Adoption().outstanding(folder(tmp_path), [PLACE, likeness, LOOK, *rest]) == []
    told = (catalog.ROOT / "studio/showpiece/prompts/carpenter.txt").read_text()
    assert "run the check that failed first" in told


def test_a_frame_post_too_thin_for_its_load_is_called_a_post_with_a_remedy_the_builder_has(tmp_path):
    """A frame post's section is set by the frames tool, so "make it thicker" is a remedy nobody can use."""
    post = {"name": "Frame 0.00 | king post", "what": "post", "carries_kN": 49.0, "diameter_m": 0.05, "design_MPa": 32.5}
    owed = Adoption().outstanding(folder(tmp_path, overloaded=(post,)), [PLACE, *CHECKS, LOOK])
    assert owed == ["1 frame post carries more than its timber can bear (over 10 MPa): Frame 0.00 | king post at 32.5 MPa; "
                    "a frame post's size is fixed, so lighten what stands on it"]


# Found by an independent review of the staged commit. Each is a way the gate could pass a
# hall on a check that did not look at it, or not count what it should.

def test_a_placing_tool_written_as_skill_slash_tool_still_counts_against_the_laps():
    """Models write "hall-carpenter/frames" in the tool field and the driver has always accepted it; the lap
    limit read the field as written, so that spelling went on placing after every lap was spent."""
    lap = [PLACE, CHECKS[1]]
    spent = Adoption(laps=2).refuses([*lap, *lap, *lap], {"tool": "hall-carpenter/frames"})
    assert spent and "all 2 repair laps are used" in spent


def test_a_let_go_test_shorter_than_three_seconds_is_refused_however_many_frames_it_drew(tmp_path):
    """The rule said three seconds and the check counted thirty frames: at 24 a second, 1.25 s passed."""
    owed = Adoption().outstanding(folder(tmp_path, frames=30, seconds=1.25), [PLACE, *CHECKS, LOOK])
    assert owed == ["the gravity test ran for 1.25 s, less than three seconds"]
    (tmp_path / "settle.json").write_text(json.dumps({"summary": {"fell": 0, "shifted": 0, "frames": 30}}))
    assert Adoption().outstanding(tmp_path, [PLACE, *CHECKS, LOOK]) == ["the gravity test does not say how long it ran: run it again"]


@pytest.mark.parametrize("name", ["bearing.json", "loads.json"])
def test_a_check_whose_file_is_missing_is_never_read_as_a_pass(tmp_path, name):
    """A missing bearing.json read as nothing hanging, and a missing loads.json as nothing overloaded."""
    (folder(tmp_path) / name).unlink()
    owed = Adoption().outstanding(tmp_path, [PLACE, *CHECKS, LOOK])
    assert owed and any(name in reason for reason in owed)


def test_a_check_that_wrote_somewhere_else_did_not_check_this_hall(tmp_path):
    """The gate reads the run folder's own files. A check told another out_dir left them as they were."""
    elsewhere = act("load-path", "settle", args={"out_dir": "older"})
    owed = Adoption().outstanding(folder(tmp_path), [PLACE, *CHECKS[:3], elsewhere, *CHECKS[4:], LOOK])
    assert any("load-path/settle" in reason for reason in owed)
    here = act("load-path", "settle", args={"out_dir": str(tmp_path)})
    assert Adoption().outstanding(tmp_path, [PLACE, *CHECKS[:3], here, *CHECKS[4:], LOOK]) == [], "its own folder, spelled out"


def test_the_eyes_must_have_looked_at_this_runs_likeness_picture(tmp_path):
    stray = act("shot-judge", "judge", args={"image": "/somewhere/else/likeness.png"}, verdict={"verdict": "pass", "change": ""})
    owed = Adoption().outstanding(folder(tmp_path), [PLACE, *CHECKS, stray])
    assert owed == ["the eyes have not looked at likeness.png since it was made: judge it"]


def test_a_part_placed_after_a_check_is_told_at_once_that_it_opened_a_repair_lap():
    """Design run 3 checked a half-built hall after nearly every part, each check passing, and ran out of laps
    before its roof was on; the rule that each part placed after a check opens a lap was never said."""
    gate = Adoption()
    assert gate.lap_opened([PLACE, PLACE]) == "", "building before any check opens nothing"
    said = gate.lap_opened([PLACE, CHECKS[1], PLACE])
    assert "opens repair lap 1 of 6" in said and "even after a check that passed" in said
    assert gate.lap_opened([PLACE, CHECKS[1], PLACE, PLACE]) == "", "a second part in the same lap opens no new one"


def test_the_driver_says_so_with_the_placing_call_that_opened_the_lap(tmp_path, monkeypatch):
    moves = [{"think": "roof", "skill": "hall-carpenter", "tool": "roof", "args": {}},
             {"think": "look", "skill": "model-anatomy", "tool": "bearing", "args": {}},
             {"think": "roof again", "skill": "hall-carpenter", "tool": "roof", "args": {}}]
    monkeypatch.setattr(drv.Driver, "_act", lambda self, run, action: act(action["skill"], action["tool"]))
    driver = drv.Driver(FakeClient([json.dumps(m) for m in moves]), None, tmp_path / "runs", cap=3, gate=Adoption())
    run = driver.run_sync("build", from_nothing=True)
    placed = [e for e in run.events if e.get("tool") == "roof"]
    assert "repair lap" not in placed[0]["text"] and "opens repair lap 1 of 6" in placed[1]["text"]
