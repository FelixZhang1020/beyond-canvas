"""A design from a written brief (operator's option C): the builder is given the Foguang hall's
public facts and a photograph, never our model of it, and the hall is judged against the brief. These
hold the design to what was promised: the temple cannot be measured, the photograph is seen, the brief's
checked numbers are the ones the builder was told, and a hall is judged by the brief and not a temple."""
import json

from conftest import FakeClient
from evalkit import fromzero
from showpiece.blend import RIGHT, SEAMS, SKILLS, TIGHT, place, run_in_blender
from studio.showpiece import adoption, catalog

FOGUANG = catalog.ROOT / "evalkit/briefs/foguang-east-hall"
SCRIPTS = SKILLS / "hall-carpenter/scripts"
SMALL = {"bays": [2, 1], "span_m": [8.0, 6.0], "span_within": 0.06, "column_rings": 1, "brackets_of_column": [0.3, 0.7]}


def test_a_design_cannot_measure_or_compare_with_the_temple_and_is_told_so(tmp_path):
    client = FakeClient(['{"think": "measure first", "skill": "hall-carpenter", "tool": "survey", "args": {}}',
                         '{"think": "compare", "skill": "hall-carpenter", "tool": "likeness", "args": {}}',
                         '{"think": "stop", "final": "nothing"}'])
    driver = fromzero.designer(client, tmp_path / "runs", cap=4)
    driver.gate = None
    request, seed = fromzero.brief_of(FOGUANG)
    run = driver.run_sync(request, from_nothing=True, seed=seed, show="photo.jpg")
    refused = [e for e in run.events if e.get("tool") in ("survey", "likeness")]
    assert len(refused) == 2 and all("command" not in e and "no standing temple" in e["text"] for e in refused)
    assert driver.model_path is None and not (run.dir / "survey.json").exists()


def test_the_builder_sees_the_photograph_on_its_first_turn_and_the_brief_in_every_turn(tmp_path):
    client = FakeClient(['{"think": "done", "final": "nothing"}'])
    driver = fromzero.designer(client, tmp_path / "runs", cap=2)
    driver.gate = None
    request, seed = fromzero.brief_of(FOGUANG)
    run = driver.run_sync(request, from_nothing=True, seed=seed, show="photo.jpg")
    assert len(client.calls[0]["images"]) == 1, "the photograph goes with the first question"
    assert "seven bays across the front" in client.calls[0]["prompt"]
    assert (run.dir / "photo.jpg").is_file() and (run.dir / "brief.json").is_file()
    assert "no survey" in client.calls[0]["system"] and "hall-carpenter brief" in client.calls[0]["system"]


def test_what_the_brief_check_measures_is_what_the_builder_was_told():
    """The check may only hold the hall to numbers the brief gave it in words."""
    told, checked = (FOGUANG / "brief.md").read_text(), json.loads((FOGUANG / "brief.json").read_text())
    assert "seven bays across the front and four bays" in told and checked["bays"] == [7, 4]
    assert "34 m from the first column to the last" in told and "17.7 m deep" in told and checked["span_m"] == [34.0, 17.7]
    assert "two rings of columns" in told and checked["column_rings"] == 2
    assert "about half as high as the column" in told and checked["brackets_of_column"][0] < .5 < checked["brackets_of_column"][1]
    assert (FOGUANG / "CREDITS.md").read_text().count("CC BY-SA 4.0") == 1


def test_a_design_is_judged_by_its_brief_and_the_eyes_on_the_brief_picture(tmp_path):
    gate = adoption.Adoption(look=adoption.BRIEF)
    act = lambda skill, tool, **more: {"kind": "act", "skill": skill, "tool": tool, "text": "ok", "command": tool,  # noqa: E731
                                       "args": {}, **more}
    events = [act("hall-carpenter", "roof"), act("model-anatomy", "inventory"), act("model-anatomy", "bearing"),
              act("load-path", "weights"), act("load-path", "settle"), act("load-path", "shake"),
              act("hall-carpenter", "brief"),
              act("shot-judge", "judge", args={"image": "brief.png"}, verdict={"verdict": "pass", "change": ""})]
    (tmp_path / "bearing.json").write_text(json.dumps({"floating": {}}))
    (tmp_path / "loads.json").write_text(json.dumps({"summary": {"overloaded": []}}))
    (tmp_path / "settle.json").write_text(json.dumps({"summary": {"fell": 0, "shifted": 0, "seconds": 3.0}}))
    (tmp_path / "shake.json").write_text(json.dumps({"summary": {"shake": {"came_down": 0}}}))
    (tmp_path / "brief-check.json").write_text(json.dumps({"meets": False, "short_of_the_brief": ["5 bays across"]}))
    assert gate.outstanding(tmp_path, events) == ["5 bays across"]
    (tmp_path / "brief-check.json").write_text(json.dumps({"meets": True, "short_of_the_brief": []}))
    assert gate.outstanding(tmp_path, events) == []
    temple_eyes = events[:-1] + [act("shot-judge", "judge", args={"image": "likeness.png"}, verdict={"verdict": "pass"})]
    assert "eyes have not looked at brief.png" in gate.outstanding(tmp_path, temple_eyes)[0]
    assert any("hall-carpenter/likeness" in r for r in adoption.Adoption().outstanding(tmp_path, events)), \
        "and a rebuild still asks for the temple's likeness"


def test_a_small_hall_meets_a_brief_for_itself_and_falls_short_of_the_foguang_brief(blender, tmp_path):
    place(blender, tmp_path, RIGHT)
    (tmp_path / "small.json").write_text(json.dumps(SMALL))
    hall = tmp_path / "hall.blend"
    run_in_blender(blender, hall, SCRIPTS / "brief.py", str(tmp_path), "--brief", str(tmp_path / "small.json"),
                   "--photo", str(FOGUANG / "photo.jpg"))
    own = json.loads((tmp_path / "brief-check.json").read_text())
    assert own["meets"], own["short_of_the_brief"]
    assert own["bays"] == [2, 1] and own["column_rings"] == 1 and 0.3 <= own["brackets"]["of_column"] <= 0.7
    run_in_blender(blender, hall, SCRIPTS / "brief.py", str(tmp_path), "--brief", str(FOGUANG / "brief.json"),
                   "--photo", str(FOGUANG / "photo.jpg"))
    short = " | ".join(json.loads((tmp_path / "brief-check.json").read_text())["short_of_the_brief"])
    assert "2 bays across the front and 1 deep; the brief's hall is 7 by 4" in short
    assert "8.0 m apart across the front" in short and "1 ring of columns" in short
    head = (tmp_path / "brief.png").read_bytes()[:24]      # a PNG's width and height sit in its header
    assert head[:8] == b"\x89PNG\r\n\x1a\n" and (int.from_bytes(head[16:20]), int.from_bytes(head[20:24])) == (960, 1092), \
        "the photograph above the hall, both 960 by 540, with the 12-pixel gap"


def test_bracket_arms_and_outriggers_past_the_edge_of_the_roof_fail_the_brief_in_numbers(blender, tmp_path):
    """Design run 4 was adopted with its bracket arms and outriggers in the open air past the eaves at both short
    ends: its eave ring stood at the outer columns, no check measured it, and the eyes passed it. The small hall
    meets a brief for itself; with its eave ring pulled in to its outer columns, it does not."""
    place(blender, tmp_path, TIGHT)
    (tmp_path / "small.json").write_text(json.dumps(SMALL))
    run_in_blender(blender, tmp_path / "hall.blend", SCRIPTS / "brief.py", str(tmp_path), "--brief",
                   str(tmp_path / "small.json"), "--photo", str(FOGUANG / "photo.jpg"))
    check = json.loads((tmp_path / "brief-check.json").read_text())
    said = next((s for s in check["short_of_the_brief"] if "past the edge of the roof" in s), "")
    assert not check["meets"] and "outriggers" in said and "bracket arms" in said, check["short_of_the_brief"]
    assert "along the hall they reach 5.4 m from the middle and the covering ends at 4.55" in said
    assert said.endswith("the eave ring must stand further out than the bracket sets reach, or the eave-out be longer")


def brief_check(blender, folder, steps):
    place(blender, folder, steps)
    (folder / "small.json").write_text(json.dumps(SMALL))
    run_in_blender(blender, folder / "hall.blend", SCRIPTS / "brief.py", str(folder), "--brief",
                   str(folder / "small.json"), "--photo", str(FOGUANG / "photo.jpg"))
    return json.loads((folder / "brief-check.json").read_text())


def test_a_roof_on_rings_that_step_unevenly_under_a_long_eave_is_closed_at_its_hips(blender, tmp_path):
    """Design run 6 was adopted with its roof open at the hips. Its rings stepped in 3.8 m along the hall where
    they stepped in 6.2 m across it, under a 1.8 m eave, and the end sheets, stretched flat past the hips to
    hide the end purlins' tips, stood up to 1.01 m over the long slopes: dark wedges from the front corner,
    which the eyes passed. The small hall with rings that step the same way and a long eave is closed."""
    check = brief_check(blender, tmp_path, SEAMS)
    assert check["open_roof"] is None, check["short_of_the_brief"]
    assert check["meets"] and check["through_the_roof"] == [], check["short_of_the_brief"]


def test_a_roof_with_no_ridge_is_open_along_its_top_and_fails_the_brief_in_numbers(blender, tmp_path):
    """The check must be able to say no: with no ridge the slopes stop at the top ring, 8.6 m by 3 m apart."""
    open_top = [s if s[0] != "purlins" else ("purlins", "--ring", "5.2,4.2,5.065", "--ring", "4.3,1.5,5.9")
                for s in SEAMS]
    check = brief_check(blender, tmp_path, open_top)
    said = next((s for s in check["short_of_the_brief"] if s.startswith("the roof is open")), "")
    assert not check["meets"] and "m2 inside its outline with no covering at all" in said, check["short_of_the_brief"]
    assert 25.0 < check["open_roof"]["holes_m2"] < 26.5 and said.endswith("and its top at the ridge")


def test_a_scripted_design_runs_every_tool_for_real_and_only_the_eyes_are_left(blender, tmp_path):
    """The rehearsal before a live run: a builder that says exactly the right things, through the real driver,
    the real tools and the real gate. Everything a program checks must pass, so the one thing still owed at the
    hand-over is the eyes, which need a model this test does not have."""
    import shutil
    brief = tmp_path / "brief"
    brief.mkdir()
    (brief / "brief.md").write_text("Design a small hall: two bays by one, 8 m by 6 m, one ring of columns.")
    (brief / "brief.json").write_text(json.dumps(SMALL))
    shutil.copyfile(FOGUANG / "photo.jpg", brief / "photo.jpg")
    small_picture = {"width": "160", "height": "90"}
    parts = [("platform", {"size": "12,9", "top": "0.5", "thickness": "0.5"}),
             ("columns", {"xs": "-4,0,4", "ys": "-3,3", "foot": "0.5", "height": "3.0", "diameter": "0.4"}),
             ("ties", {"top": "3.3", "depth": "0.3", "width": "0.2"}), ("walls", {"foot": "0.5", "top": "3.0"}),
             ("brackets", {"seat": "3.5", "tiers": "2", "rise": "0.45", "outrigger": ["1.2,5.065"]}),
             ("frames", {"seat": "4.75", "beam": ["5.9,1.8"], "king": "6.6", "lines": "0"}),
             ("purlins", {"ring": ["5.2,4.2,5.065", "3.5,1.5,5.9"], "ridge": "2.0,6.6"}),
             ("rafters", {"spacing": "0.8"}), ("roof", {"finial": "0.5"})]
    checks = [("model-anatomy", "inventory", {}), ("model-anatomy", "bearing", {}), ("load-path", "weights", {}),
              ("load-path", "settle", {"seconds": "3", "fps": "10", **small_picture}),
              ("load-path", "shake", small_picture), ("hall-carpenter", "brief", {})]
    said = [json.dumps({"think": f"place the {tool}", "skill": "hall-carpenter", "tool": tool, "args": args}) for tool, args in parts]
    said += [json.dumps({"think": f"check {tool}", "skill": skill, "tool": tool, "args": args}) for skill, tool, args in checks]
    said.append(json.dumps({"think": "all checked", "final": "a small hall"}))
    request, seed = fromzero.brief_of(brief)
    run = fromzero.designer(FakeClient(said), tmp_path / "runs", cap=40).run_sync(request, from_nothing=True, seed=seed,
                                                                                    show="photo.jpg")
    acts = [e for e in run.events if e["kind"] == "act"]
    failed = [(e["tool"], e["text"][-300:]) for e in acts if "command" not in e or e["text"].startswith("exit ")]
    assert len(acts) == len(parts) + len(checks) and not failed, failed
    assert json.loads((run.dir / "brief-check.json").read_text())["meets"]
    handed = next(e for e in run.events if e["kind"] == "bounce")
    assert handed["text"] == "not handed over yet: the eyes have not looked at brief.png since it was made: judge it"
    assert "unlike: nothing" in next(e for e in acts if e["tool"] == "brief")["text"], "the fault line reads the brief"
    placed = [e["step"] for e in acts if e["tool"] in {tool for tool, _ in parts}]
    assert sorted(p.name for p in (run.dir / "stages").iterdir()) == sorted(f"step-{n}.blend" for n in placed), \
        "the hall after every placing call is kept, so the replay can show each stage"
    brief_step = next(e["step"] for e in acts if e["tool"] == "brief")
    assert (run.dir / "media" / f"step-{brief_step}-brief.png").is_file() and any(
        p.name.endswith("settle.mp4") for p in (run.dir / "media").iterdir()), "and every picture and video, by step"


def test_a_designs_eyes_are_step_on_the_subscription_and_never_the_class_model():
    """vlm.studio went to Qwen on the Spark with the class chat. A design's eyes must not load
    the class's own model, and must be the model the rebuilds were judged by."""
    from studio.core.slots import load_profile, resolve
    driver = fromzero.designer(FakeClient([]), catalog.ROOT / "unused")
    judge = catalog.TOOLS[("shot-judge", "judge")]
    assert catalog.quick_args(judge, {}, driver.quick)["slot"] == fromzero.STEP
    step = resolve(fromzero.STEP, load_profile("stepfun"))
    assert (step.provider, step.model) == ("stepfun", "step-3.7-flash")


def test_a_design_may_think_longer_than_a_rebuild_before_it_answers():
    """Design run 1 spent 6,000 and then 12,000 tokens thinking out the column grid, the rebuild's whole
    budget, and the run stopped with nothing placed but the platform."""
    from studio.showpiece import driver as drv
    designing = fromzero.designer(FakeClient([]), catalog.ROOT / "unused").think
    assert designing[0] > drv.MAX_TOKENS and designing[1] > drv.RETRY_TOKENS
    assert fromzero.carpenter(FakeClient([]), fromzero.TEMPLE, catalog.ROOT / "unused").think == (drv.MAX_TOKENS, drv.RETRY_TOKENS)
