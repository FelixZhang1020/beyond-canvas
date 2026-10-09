"""Every hall designed from a written brief that the replay page plays (rebuild.html?design=N) is held to
its own run: its counts add up from its own steps, it carries no private path, it is judged by the brief
and never by the temple, and every step shows a stage its hall holds. A made-up run folder with a brief
check, pictures, a refused tool and a broken one shows the builder reading each the way the page needs,
and a made-up adopted design shows what happens when a check added since fails its final hall."""
import json
import re
from pathlib import Path

import pytest

from studio.showpiece import adoption
from studio.showpiece.rebuild_designs import listed, numbered, real_hall, record_of, words

PAGE = Path(__file__).resolve().parents[2] / "studio/showpiece/page"
RUN_ID = re.compile(r"\b\d{8}-\d{6}-[0-9a-f]{6}\b")


def load(name):
    return json.loads((PAGE / name).read_text(encoding="utf-8"))


DESIGNS = load("rebuild-designs.json")["designs"]


@pytest.fixture(params=[d["n"] for d in DESIGNS], ids=lambda n: f"design {n}")
def design(request):
    return load(f"rebuild-design{request.param}-record.json")


def test_the_page_lists_each_design_it_can_play_once_in_order():
    assert [d["n"] for d in DESIGNS] == list(range(1, len(DESIGNS) + 1))
    assert len({d["run"] for d in DESIGNS}) == len(DESIGNS)
    for d in DESIGNS:
        assert load(f"rebuild-design{d['n']}-record.json")["source_run"] == d["run"]
        for suffix in ("glb", "json"):
            assert (PAGE / f"rebuild-design{d['n']}-hall.{suffix}").is_file(), (d["n"], suffix)


def test_the_counts_a_design_shows_add_up_from_its_own_steps(design):
    steps, facts = design["steps"], design["harness"]
    acts = [s for s in steps if s["kind"] == "act"]
    assert [s["step"] for s in steps] == list(range(1, len(steps) + 1))
    assert facts["turns"]["actions"] == len(acts) == design["measured"]["actions"]
    assert facts["tokens"] == sum(s.get("tokens", 0) for s in steps) == design["measured"]["tokens"]
    assert abs(facts["tool_seconds"] - sum(s.get("seconds", 0) for s in acts)) < 1
    assert sum(facts["turns"]["by_tool"].values()) == len(acts)


def test_no_design_on_the_page_carries_a_private_path(design):
    text = json.dumps({k: v for k, v in design.items() if k != "source_run"}, ensure_ascii=False)
    for private in ("/home/", "/Users/", ".studio/", "beyond-canvas-design"):
        assert private not in text, private
    assert not RUN_ID.search(text), RUN_ID.search(text)


def test_a_design_is_judged_by_its_brief_and_never_by_the_temple(design):
    checks = design["harness"]["checks"]
    assert checks == [f"{s}/{t}" for s, t in adoption.Adoption(look=adoption.BRIEF).checks] + ["shot-judge/judge"]
    assert "hall-carpenter/brief" in checks and "hall-carpenter/likeness" not in checks
    for step in (s for s in design["steps"] if s.get("tool") in ("survey", "likeness")):
        assert step["evidence"].startswith("REFUSED"), step["step"]


def test_every_step_of_a_design_shows_a_stage_its_hall_holds(design):
    hall = load(f"rebuild-design{design['run']}-hall.json")
    placed = [s for s in design["steps"] if s["kind"] == "act" and s["frame"] == f"step-{s['step']}"]
    assert len(placed) == design["harness"]["turns"]["placing"]
    if design["stages_kept"]:
        assert hall["kept_stages"] and {s["frame"] for s in design["steps"]} - {"temple"} == set(hall["stages"])
    names = {name for name, _ in hall["pieces"]}
    faults = design["faults"]
    for name in [*faults["fell"], *faults["hanging"], *faults["through_the_roof"], *faults.get("beyond_the_eaves", [])]:
        assert name in names, name


def test_every_picture_a_design_shows_is_on_the_page(design):
    shown = [design["opening"], *(name for s in design["steps"] for name in (s.get("media") or {}).values())]
    for name in shown:
        assert name and (PAGE / name).is_file(), name


def test_a_design_keeps_its_number_and_a_new_run_takes_the_next():
    manifest = {"designs": [{"n": 1, "run": "a"}, {"n": 2, "run": "b"}]}
    assert numbered(["b", "c", "d"], manifest) == {"a": 1, "b": 2, "c": 3, "d": 4}


def test_adding_a_design_keeps_the_success_path_the_page_draws():
    path = [{"runs": [1, 2], "end": "path.6.end"}]
    after = listed({"designs": [{"n": 1, "run": "a"}, {"n": 2, "run": "b"}], "path": path}, {"a": 1, "b": 2, "c": 3})
    assert after == {"designs": [{"n": 1, "run": "a"}, {"n": 2, "run": "b"}, {"n": 3, "run": "c"}], "path": path}


RUN = "20260930-120000-abcdef"
BRIEF_SHORT = ("BRIEF 7 by 4 bays | corner columns [34.0, 17.7] m apart | 2 rings of columns | bracket sets 48% of the column"
               " | does NOT meet the brief: 1 timber pieces stand out through the roof: Frame 3 | king post; a frame line"
               " under the sloping end of the roof is named in frames' end-lines | brief.png: the photograph above, the hall below")


def made_up_run(root: Path) -> Path:
    """A design run folder as the driver leaves one, small: a platform, a refused survey, a bearing check
    that broke, a settle with its video, a brief check that found timber through the roof, the eyes on
    its picture, a hand-over sent back and the cap."""
    folder, home = root / RUN, f"/home/someone/beyond-canvas-design/.studio/showpiece/designs/{RUN}"
    for sub in ("stages", "media"):
        (folder / sub).mkdir(parents=True)
    act = lambda step, skill, tool, text, **more: {"step": step, "kind": "act", "skill": skill, "tool": tool, "args": more.pop("args", {}),
                                                   "seconds": 1.0, "command": f"blender -b {home}/hall.blend -- .studio/showpiece/designs/{RUN}",
                                                   "text": text, "at": f"2026-09-30T12:00:{step:02d}+00:00", **more}
    events = [
        {"step": 1, "kind": "think", "text": "the platform first", "tokens": 100, "at": "2026-09-30T12:00:01+00:00"},
        act(2, "hall-carpenter", "platform", "PLACED platform: 1 pieces | top 0.500"),
        {k: v for k, v in act(3, "hall-carpenter", "survey", "REFUSED there is no standing temple in a design: nothing to measure").items()
         if k != "command"},                                   # refused before it ran: no command
        act(4, "model-anatomy", "bearing", f'exit 1: 00:00.1 blend | Read blend: "{home}/hall.blend"\nTraceback (most recent call last):\n'
            '  File "/home/someone/beyond-canvas-design/skills/model-anatomy/scripts/bearing.py", line 52, in __init__\n'
            "KeyError: 'key \"Purlin ring 3\" not found'\nError: script failed, file: '/home/someone/beyond-canvas-design/x.py'"),
        act(5, "load-path", "settle", "SETTLE 2 pieces fell 0 shifted 0 | wrote settle.json"),
        act(6, "hall-carpenter", "brief", BRIEF_SHORT),
        act(7, "shot-judge", "judge", "{}", args={"image": "brief.png"}, verdict={"verdict": "fail", "change": "lower the roof"}),
        {"step": 8, "kind": "bounce", "text": "not handed over yet: the hall changed after the last hall-carpenter/brief, or it never ran: run it",
         "at": "2026-09-30T12:00:08+00:00"},
        {"step": 9, "kind": "stop", "text": "the cap of 80 actions was reached", "at": "2026-09-30T12:00:09+00:00"},
    ]
    (folder / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")
    for name in ("stages/step-2.blend", "media/step-5-settle.mp4", "media/step-5-settle-end.png", "media/step-6-brief.png", "photo.jpg"):
        (folder / name).write_bytes(b"x")
    (folder / "scorecard.json").write_text(json.dumps({
        "agent": "step-3.7-flash", "adopted": False, "tokens": 100, "tool_seconds": 5.0, "wall_seconds": 9.0, "still_owed": [],
        "turns": {"actions": 6, "placing": 1, "tools_that_failed": 1, "reads": 0, "repair_laps": 0, "hand_overs_refused": 1,
                  "by_tool": {}}}), encoding="utf-8")
    (folder / "brief-check.json").write_text(json.dumps({
        "bays": [7, 4], "span": [34.0, 17.7], "column_rings": 2, "brackets": {"height": 3.0, "column": 6.25, "of_column": 0.48},
        "meets": False, "short_of_the_brief": ["1 timber pieces stand out through the roof: Frame 3 | king post"],
        "through_the_roof": ["Frame 3 | king post"]}), encoding="utf-8")
    (folder / "bearing.json").write_text(json.dumps({"floating": {"Purlin ridge": {}}}), encoding="utf-8")
    return folder


def test_a_design_run_folder_becomes_a_record_the_page_plays(tmp_path):
    record, plan = record_of(7, made_up_run(tmp_path), {"fps": 24})
    at = {s["step"]: s for s in record["steps"]}
    assert record["faults"]["through_the_roof"] == ["Frame 3 | king post"], "the brief check's own roof list"
    assert record["faults"]["hanging"] == [], "the bearing check broke, so its file says nothing of this hall"
    assert record["harness"]["brief"] == {"bays": [7, 4], "span": [34.0, 17.7], "column_rings": 2, "meets": False,
                                          "brackets": {"height": 3.0, "column": 6.25, "of_column": 0.48},
                                          "short_of_the_brief": ["1 timber pieces stand out through the roof: Frame 3 | king post"],
                                          "current": True}
    assert at[3]["detail"] == words("design.detail.withheld")
    assert at[4]["evidence"] == "exit 1: KeyError: 'key \"Purlin ring 3\" not found'", "a broken tool shows the error it stopped on"
    assert [at[n]["frame"] for n in range(1, 10)] == ["temple"] + ["step-2"] * 8
    assert at[5]["media"] == {"video": "rebuild-design7-step5-settle.mp4", "image": "rebuild-design7-step5-settle-end.jpg"}
    assert at[6]["media"] == at[7]["media"] == {"image": "rebuild-design7-step6-brief.jpg"}, "the eyes' step shows what they judged"
    assert (at[6]["title"], at[8]["title"], at[9]["title"]) == (words("design.tool.brief"), words("design.bounce.title"),
                                                               words("design.stop.cap.title"))
    assert "80" in at[9]["detail"] and record["opening"] == "rebuild-design7-photo.jpg"
    assert sorted(name for _, name in plan) == sorted(["rebuild-design7-step5-settle.mp4", "rebuild-design7-step5-settle-end.jpg",
                                                       "rebuild-design7-step6-brief.jpg", "rebuild-design7-photo.jpg"])
    text = json.dumps({k: v for k, v in record.items() if k != "source_run"})
    assert "/home/" not in text and ".studio/" not in text and RUN not in text
    assert at[2]["command"].endswith("-- run")


EAVES = ("2 timber pieces stand past the edge of the roof, with no covering over them: 1 bracket arms, 1 outriggers; along the"
         " hall they reach 19.8 m from the middle and the covering ends at 19.2: the eave ring must stand further out")
LATER = {"bays": [7, 4], "span": [34.0, 17.7], "column_rings": 2, "brackets": {"height": 3.0, "column": 5.0, "of_column": 0.6},
         "size": [38.28, 21.92, 13.63], "top": 13.63, "frame": {"roof_rings": 2, "ridge": {"half_x": 12.0, "underside": 12.5}},
         "meets": False, "short_of_the_brief": [EAVES], "through_the_roof": [],
         "beyond_the_eaves": ["Bracket 3 | tier 1 arm", "Bracket 3 | outrigger"], "on": "step-2", "checked": "2026-09-30"}


def adopted_run(root: Path) -> Path:
    """A design handed over under the checks of its day: its roof placed, a brief check it met (a file with no
    eaves list, as before that check existed), and the hand-over."""
    folder = root / "20260930-130000-fedcba"
    (folder / "stages").mkdir(parents=True)
    at = lambda step: f"2026-09-30T13:00:{step:02d}+00:00"
    events = [{"step": 1, "kind": "think", "text": "build it", "tokens": 50, "at": at(1)},
              {"step": 2, "kind": "act", "skill": "hall-carpenter", "tool": "roof", "args": {}, "seconds": 1.0, "command": "blender",
               "text": "PLACED roof: 15 pieces | top 13.630", "at": at(2)},
              {"step": 3, "kind": "act", "skill": "hall-carpenter", "tool": "brief", "args": {}, "seconds": 1.0, "command": "blender",
               "text": "BRIEF 7 by 4 bays | corner columns [34.0, 17.7] m apart | 2 rings of columns | bracket sets 60% of the column"
                       " | meets the brief | brief.png: the photograph above, the hall below", "at": at(3)},
              {"step": 4, "kind": "final", "text": "The hall is designed.", "adopted": True, "at": at(4)}]
    (folder / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events), encoding="utf-8")
    for name in ("stages/step-2.blend", "photo.jpg"):
        (folder / name).write_bytes(b"x")
    (folder / "scorecard.json").write_text(json.dumps({
        "agent": "step-3.7-flash", "adopted": True, "tokens": 50, "tool_seconds": 2.0, "wall_seconds": 4.0, "still_owed": [],
        "turns": {"actions": 2, "placing": 1, "tools_that_failed": 0, "reads": 0, "repair_laps": 0, "hand_overs_refused": 0,
                  "by_tool": {}}}), encoding="utf-8")
    (folder / "brief-check.json").write_text(json.dumps({key: LATER[key] for key in ("bays", "span", "column_rings", "brackets", "size", "top", "frame")}
                                                        | {"meets": True, "short_of_the_brief": [], "through_the_roof": []}), encoding="utf-8")
    return folder


def test_an_adopted_design_whose_final_hall_fails_todays_brief_check_is_marked_found_later(tmp_path):
    record, _ = record_of(8, adopted_run(tmp_path), {}, LATER)
    faults = record["faults"]
    assert faults["found_later"] is True
    assert faults["beyond_the_eaves"] == ["Bracket 3 | tier 1 arm", "Bracket 3 | outrigger"], "the pieces the last step paints red"
    assert faults["later"] == {"on": "step-2", "checked": "2026-09-30", "meets": False, "short_of_the_brief": [EAVES],
                               "new_checks": ["beyond_the_eaves"]}, "the check its own day's file did not have"
    assert record["measured"]["adopted"] is True and record["harness"]["brief"]["meets"] is True, "its own day's check reads as it did"


def test_an_adopted_design_that_still_meets_todays_brief_stays_adopted(tmp_path):
    record, _ = record_of(8, adopted_run(tmp_path), {}, {**LATER, "meets": True, "short_of_the_brief": [], "beyond_the_eaves": []})
    faults = record["faults"]
    assert faults["found_later"] is False and faults["beyond_the_eaves"] == [] and faults["later"]["meets"] is True


def test_a_design_that_was_never_adopted_is_not_judged_again(tmp_path):
    record, _ = record_of(7, made_up_run(tmp_path), {}, LATER)
    assert record["faults"]["found_later"] is False and "later" not in record["faults"]


def test_design_4_was_adopted_by_its_day_and_todays_brief_check_finds_its_brackets_past_the_eaves():
    four = load("rebuild-design4-record.json")
    faults = four["faults"]
    assert four["measured"]["adopted"] is True and four["harness"]["brief"]["meets"] is True
    assert faults["found_later"] is True and "beyond_the_eaves" in faults["later"]["new_checks"]
    said = next(s for s in faults["later"]["short_of_the_brief"] if "past the edge of the roof" in s)
    assert said.startswith(f"{len(faults['beyond_the_eaves'])} timber pieces stand past the edge of the roof")


def test_the_real_hall_beside_the_designs_is_the_survey_the_adopted_rebuild_carries():
    survey = load("rebuild-record.json")["harness"]["survey"]
    real = load("rebuild-real-hall.json")
    assert real == real_hall(survey)
    assert real["roof_rings"] == survey["roof_rings"] and real["ridge_m"] == 2 * survey["ridge"]["half_x"]
    assert real["outline_m"] == survey["size"][:2] and real["top_m"] == survey["top"]
    ys = survey["columns"]["ys"]
    assert real["eaves_m"][0] == round((survey["size"][1] - (ys[-1] - ys[0])) / 2, 2), "the outline past the corner columns, in front"
    assert "/home/" not in json.dumps(real) and "/Users/" not in json.dumps(real)


def test_every_design_whose_hall_has_a_roof_is_measured_the_way_the_real_hall_is(design):
    roofed = any(s["kind"] == "act" and s.get("tool") == "roof" and s["frame"] == f"step-{s['step']}" for s in design["steps"])
    versus = design["versus_real"]
    assert (versus is not None) == roofed, f"design {design['run']}: a roof {roofed}, numbers {versus}"
    if versus:
        assert set(versus) == {"roof_rings", "ridge_m", "eaves_m", "outline_m", "top_m"}
        assert versus["top_m"] > 0 and len(versus["outline_m"]) == len(versus["eaves_m"]) == 2


def test_a_design_is_set_beside_the_real_hall_by_what_was_measured_on_the_hall_it_ended_with(tmp_path):
    record, _ = record_of(8, adopted_run(tmp_path), {}, {**LATER, "meets": True, "short_of_the_brief": [], "beyond_the_eaves": []})
    assert record["versus_real"] == {"roof_rings": 2, "ridge_m": 24.0, "eaves_m": [2.11, 2.14], "outline_m": [38.28, 21.92], "top_m": 13.63}
    assert record_of(7, made_up_run(tmp_path), {}, LATER)[0]["versus_real"] is None, "a hall with no roof is not set beside the real one"
