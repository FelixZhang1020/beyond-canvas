"""The hall carpenter: parts placed by the numbers they are told, on a hall small enough to check
in seconds. Told right it seats and stands; told wrong it hangs, and the fault report names the
part. The tools never fit a piece for the model, and these tests are what holds them to that."""
import json
import subprocess
import sys

import pytest
from showpiece.blend import RIGHT, SKILLS, TIGHT, place, run_in_blender

from studio.showpiece.blender_bin import run_tool

SCRIPTS = SKILLS / "hall-carpenter/scripts"
ANATOMY, LOAD = SKILLS / "model-anatomy/scripts", SKILLS / "load-path/scripts"
def checked(blender, folder):
    hall = folder / "hall.blend"
    run_in_blender(blender, hall, ANATOMY / "inventory.py", str(folder))
    run_in_blender(blender, hall, ANATOMY / "bearing.py", str(folder))
    return json.loads((folder / "bearing.json").read_text())


@pytest.fixture(scope="module")
def small_hall(blender, tmp_path_factory):
    folder = tmp_path_factory.mktemp("hall")
    place(blender, folder, RIGHT)
    return folder


def test_a_hall_told_the_right_heights_has_nothing_hanging_and_stands_when_let_go(blender, small_hall):
    bearing = checked(blender, small_hall)
    assert bearing["floating"] == {}
    run_in_blender(blender, small_hall / "hall.blend", LOAD / "settle.py", str(small_hall), "--anatomy",
                   str(small_hall / "anatomy.json"), "--bearing", str(small_hall / "bearing.json"), "--seconds", "3",
                   "--fps", "10", "--width", "160", "--height", "90")
    settle = json.loads((small_hall / "settle.json").read_text())
    assert (settle["summary"]["fell"], settle["summary"]["shifted"]) == (0, 0)
    groups = {p["group"] for p in settle["pieces"].values() if p["group"]}
    assert len(groups) > 10, "a hall that settles as one lump has passed nothing: only cut joints may lock"


def test_a_frame_told_a_seat_too_high_hangs_and_the_fault_report_names_the_frames(blender, tmp_path):
    # 0.4 above the bracket top, and so 0.085 clear of the outrigger that lies on it
    wrong = [step if step[0] != "frames" else ("frames", "--seat", "5.15", "--beam", "6.3,1.8", "--king", "6.6",
                                               "--lines", "0") for step in RIGHT]
    place(blender, tmp_path, wrong)
    bearing = checked(blender, tmp_path)
    assert any(name.startswith("Frame") for name in bearing["floating"]), "the tool must not fit the beam for the model"
    done = subprocess.run([sys.executable, str(SCRIPTS / "faults.py"), str(tmp_path)], capture_output=True, text=True)
    faults = json.loads((tmp_path / "faults.json").read_text())
    frames = [f for f in faults["hanging"] if f["part"] == "frames"]
    assert frames and abs(frames[0]["gap_m"] - 0.085) < 0.02, done.stdout
    assert "outrigger" in frames[0]["nearest_below"]
    assert faults["what_those_parts_were_told"]["frames"]["seat"] == 5.15


def test_a_part_that_cannot_be_placed_as_told_says_why_and_leaves_the_hall_alone(blender, tmp_path):
    place(blender, tmp_path, RIGHT[:2])
    before = (tmp_path / "hall.blend").stat().st_mtime_ns
    with pytest.raises(RuntimeError, match="REFUSED place the ties first"):
        place(blender, tmp_path, [("brackets", "--seat", "3.5")])
    with pytest.raises(RuntimeError, match="REFUSED rise"):
        place(blender, tmp_path, [("brackets", "--seat", "3.5", "--rise", "0.2", "--inter", "no")])
    place(blender, tmp_path, [("ties", "--top", "3.3"), ("brackets", "--seat", "3.5", "--tiers", "2", "--rise", "0.45")])
    with pytest.raises(RuntimeError, match="REFUSED lines: no columns stand on the cross line x = -3.0"):
        place(blender, tmp_path, [("frames", "--seat", "4.75", "--lines=-3,3")])     # the ys, given as lines
    before = (tmp_path / "hall.blend").stat().st_mtime_ns
    with pytest.raises(RuntimeError, match="REFUSED width 960.0 is not a timber's size"):
        place(blender, tmp_path, [("ties", "--top", "3.3", "--width", "960")])
    assert (tmp_path / "hall.blend").stat().st_mtime_ns == before


def test_a_beam_too_close_above_the_frames_own_lowest_beam_is_refused_with_the_least_top_it_may_have(blender, tmp_path):
    """The frames lay their lowest beam on the seat themselves. Design run 2 gave its first beam the seat's
    own height, was told of "the beam below it", and spent about 30 of its 80 actions on six beam tops from
    9.35 to 10.0, never learning that beam was the tool's own. Its numbers are used here: the refusal is
    arithmetic, made before anything is placed."""
    place(blender, tmp_path, RIGHT[:5])
    before = (tmp_path / "hall.blend").stat().st_mtime_ns
    frames = ("frames", "--seat", "9.35", "--depth", "0.4", "--lines", "0")
    told = r"lay their lowest beam on the seat themselves.*9\.35 \+ 0\.4 = 9\.75.*more than 9\.75 \+ 0\.4 = 10\.15\n"
    for top in ("9.35", "9.75", "10", "10.15"):
        with pytest.raises(RuntimeError, match=rf"REFUSED beam 1 \(top {top}\).*" + told):
            place(blender, tmp_path, [frames + ("--beam", f"{top},1.8")])
    with pytest.raises(RuntimeError, match=r"REFUSED beam 2 \(top 10\.7\) leaves no room for a post above beam 1 "
                                           r"\(top 10\.5\).*more than 10\.5 \+ 0\.4 = 10\.9\n"):
        place(blender, tmp_path, [frames + ("--beam", "10.5,1.8", "--beam", "10.7,1.2")])
    assert (tmp_path / "hall.blend").stat().st_mtime_ns == before
    out = place(blender, tmp_path, [frames + ("--beam", "10.16,1.8")])[0]
    assert "lowest beam top 9.750 top beam top 10.160" in out, "the least top the refusal names is the tool's own rule"


def test_a_ridge_that_misses_the_king_posts_is_refused_with_where_they_stand_and_the_least_half_x(blender, small_hall,
                                                                                                  tmp_path):
    """Design run 2 gave the ridge half_x 0, a ridge of no length at the middle, between king posts at ±2.429
    and ±7.286. The fault report said it hung 12 m above the platform, and the builder added a ninth column
    line under it, breaking the brief's seven bays. Here the king posts stand on x = ±4 and the top ring is
    wide enough for a ridge to reach them; under the small hall's own top ring no ridge can."""
    place(blender, tmp_path, RIGHT[:5] + [("frames", "--seat", "4.75", "--beam", "5.9,1.8", "--king", "6.6",
                                           "--lines=-4,4")])
    before = (tmp_path / "hall.blend").stat().st_mtime_ns
    rings = ("purlins", "--ring", "5.2,4.2,5.065", "--ring", "4.5,1.5,5.9")
    told = (r"rests on no king post: half_x is how far the ridge runs each way from the middle, along the hall.*"
            r"king posts stand at x = ±4, their tops at 6\.6, so give half_x of at least 4\n")
    for half_x in ("0", "2"):
        with pytest.raises(RuntimeError, match=rf"REFUSED the ridge \(half_x {half_x}\) " + told):
            place(blender, tmp_path, [rings + ("--ridge", f"{half_x},6.6")])
    with pytest.raises(RuntimeError, match=r"REFUSED the ridge \(half_x 2\).*x = ±4.*no ridge shorter than the top "
                                           r"ring \(half_x 3\.5\) reaches them.*end-lines"):
        place(blender, tmp_path, [("purlins", "--ring", "5.2,4.2,5.065", "--ring", "3.5,1.5,5.9", "--ridge", "2,6.6")])
    with pytest.raises(RuntimeError, match=r"REFUSED the ridge \(half_x 5, underside 6\.6\) must be shorter than the "
                                           r"top ring and higher than it.*give half_x less than 4\.5 and an underside "
                                           r"above 5\.9"):
        place(blender, tmp_path, [rings + ("--ridge", "5,6.6")])
    assert (tmp_path / "hall.blend").stat().st_mtime_ns == before
    assert "ridge underside 6.600" in place(blender, tmp_path, [rings + ("--ridge", "4.2,6.6")])[0]
    assert json.loads((small_hall / "hall.json").read_text())["parts"]["purlins"]["ridge"]["half_x"] == 2.0, \
        "the small hall's ridge reaches its one king post, at x = 0"


def test_both_ends_of_the_roof_are_mended_in_one_call_however_the_model_writes_the_beam_count(blender, tmp_path):
    """The fourth live run lost five of its six repair laps here. It wrote end-beams as "3,3" to match its
    two end lines, was answered with the tool's usage text twice, then mended one end per call, and each
    call put the other end's post back, because placing a part again replaces it."""
    place(blender, tmp_path, RIGHT[:5])
    frames = ("frames", "--seat", "4.75", "--beam", "5.9,1.8", "--king", "6.6", "--lines=-4,0,4", "--end-lines=-4,4")
    for count in ("1,1", "1"):
        out = place(blender, tmp_path, [frames + ("--end-beams", count)])[0]
        assert "end lines [-4.0, 4.0]" in out, "the answer says which lines were treated as ends"
        run_in_blender(blender, tmp_path / "hall.blend", ANATOMY / "inventory.py", str(tmp_path))
        kings = sorted(n for n in json.loads((tmp_path / "anatomy.json").read_text())["pieces"] if "king post" in n)
        assert kings == ["Frame 0.00 | king post"], count
    with pytest.raises(RuntimeError, match="REFUSED end-beams takes one whole number.*name every end line in one call"):
        place(blender, tmp_path, [frames + ("--end-beams", "1,1,1")])
    with pytest.raises(RuntimeError, match="REFUSED end-beams"):
        place(blender, tmp_path, [frames + ("--end-beams", "1.5")])


def test_a_flag_the_tool_cannot_read_is_answered_in_a_sentence_and_never_with_usage_text(blender, tmp_path):
    place(blender, tmp_path, RIGHT[:2])
    with pytest.raises(RuntimeError) as refused:
        place(blender, tmp_path, [("ties", "--top", "high")])
    assert "REFUSED" in str(refused.value) and "--top" in str(refused.value) and "usage:" not in str(refused.value)


def test_placing_a_part_again_replaces_it(blender, tmp_path):
    place(blender, tmp_path, RIGHT[:2])
    place(blender, tmp_path, [("columns", "--xs=-4,4", "--ys=-3,3", "--foot", "0.5", "--height", "2.0")])
    out = run_in_blender(blender, tmp_path / "hall.blend", ANATOMY / "inventory.py", str(tmp_path))
    assert "ANATOMY 5 pieces" in out
    assert json.loads((tmp_path / "hall.json").read_text())["parts"]["columns"]["top"] == 2.5


def test_a_part_placed_again_names_what_still_stands_on_the_old_one_until_that_is_placed_again(blender, tmp_path):
    """Placing a part again moves nothing that stands on it. Design run 7 lengthened the rafters'
    eave-out twice and never laid the roof again, so the covering stayed where the first rafters had put it and
    the brief check kept saying so; run 8 placed the frames again, then the purlins and the roof, but not the
    rafters, which stood on purlins that had moved, and it spent its six laps on what hung. Each placing now says
    what stands on an old part, in the order to place it again, on the line the driver shows the builder last;
    hall.json keeps it and the fault report leads with it. A part placed again with the same numbers is no change."""
    place(blender, tmp_path, RIGHT)
    argv = [str(blender), "-b", "--python-exit-code", "1", "--python", str(SCRIPTS / "place.py"), "--"]

    def again(part, *flags):
        code, tail = run_tool(argv + [part, str(tmp_path), "--hall", str(tmp_path / "hall.blend"), *flags], 600)
        assert code == 0, tail
        last = tail.strip().splitlines()[-1]
        assert last.startswith(f"PLACED {part}:") and last in tail[-600:], "the line the builder reads"
        return last, json.loads((tmp_path / "hall.json").read_text()).get("stale")

    roof = ("roof", "--finial", "0.5")
    last, stale = again("rafters", "--spacing", "0.8", "--eave-out", "1.2")                  # run 7
    assert last.endswith("| the roof stands on the old rafters: place it again before checking")
    assert stale == {"roof": "rafters"}
    faults = subprocess.run([sys.executable, str(SCRIPTS / "faults.py"), str(tmp_path)], capture_output=True, text=True)
    assert faults.stdout.startswith("FAULTS stale: roof (on the old rafters) | "), faults.stdout + faults.stderr
    last, stale = again(*roof)
    assert "old" not in last and stale == {}
    old_purlins = "| the rafters and roof stand on the old purlins: place them again, in that order, before checking"
    last, _ = again("frames", "--seat", "4.75", "--beam", "5.9,1.8", "--king", "6.6", "--lines", "0", "--width", "0.38")
    assert last.endswith("| the purlins, rafters and roof stand on the old frames: place them again, in that order, "
                         "before checking")                                                       # run 8
    assert again("purlins", "--ring", "5.2,4.2,5.065", "--ring", "3.5,1.5,5.9", "--ridge", "2.0,6.6",
                 "--overhang", "0.1")[0].endswith(old_purlins)
    last, stale = again(*roof)
    assert last.endswith(old_purlins) and stale == {"rafters": "purlins", "roof": "purlins"}, "laid on old rafters"
    assert again("rafters", "--spacing", "0.8")[0].endswith("| the roof stands on the old rafters: place it again "
                                                             "before checking")
    last, stale = again(*roof)
    assert "old" not in last and stale == {}
    last, stale = again("rafters", "--spacing", "0.8")
    assert "old" not in last and stale == {}, "the same numbers again move nothing"


def test_a_part_placed_before_what_it_stands_on_is_named_when_that_is_placed_again(blender, tmp_path):
    """The frames need only the columns, so a builder may place them before the brackets their beams sit on.
    The brackets' first placing is not a change to anything; placing them again is."""
    said = place(blender, tmp_path, RIGHT[:4] + [RIGHT[5], RIGHT[4], RIGHT[4] + ("--reach", "0.45")])
    lines = [next(line for line in out.splitlines() if line.startswith("PLACED")) for out in said]
    assert not any("old" in line for line in lines[:-1])
    assert lines[-1].endswith("| the frames stand on the old brackets: place them again before checking")
    assert json.loads((tmp_path / "hall.json").read_text())["stale"] == {"frames": "brackets"}


def test_a_hall_measured_and_compared_with_itself_is_alike_and_a_lower_roof_is_not(blender, small_hall, tmp_path):
    hall = small_hall / "hall.blend"
    out = run_in_blender(blender, hall, SCRIPTS / "survey.py", str(tmp_path))
    sheet = json.loads((tmp_path / "survey.json").read_text())
    assert "SURVEY 6 columns" in out and sheet["columns"]["xs"] == [-4.0, 0.0, 4.0] and sheet["columns"]["top"] == 3.5
    assert [r["underside"] for r in sheet["roof_rings"]] == [5.07, 5.9] and sheet["ridge"]["underside"] == 6.6
    assert sheet["roof_rings"][0]["out_from_outer_columns"] == 1.2
    run_in_blender(blender, hall, SCRIPTS / "likeness.py", str(tmp_path), "--survey", str(tmp_path / "survey.json"))
    same = json.loads((tmp_path / "likeness.json").read_text())
    assert same["alike"] and min(same["shared_outline"].values()) > 0.99 and same["columns"]["matched"] == 6
    assert same["beyond_the_eaves"] == [], "the small hall's eaves cover every bracket set"
    assert same["open_roof"] is None, "and its roof is closed, hips and ridge"
    assert sheet["tie_spans"] == {"spans": 6, "tied": 6} and sheet["bracket_sets"] == {"columns": 6, "with_a_set": 6}
    assert same["frame"]["short"] == [] and same["frame"]["hall"]["roof_rings"] == 2
    assert (tmp_path / "likeness.png").is_file() and (tmp_path / "temple.png").is_file()
    low = tmp_path / "low"
    low.mkdir()
    flat = [s if s[0] != "purlins" else ("purlins", "--ring", "5.2,4.2,5.065", "--ring", "3.5,1.5,5.2", "--ridge",
                                         "2.0,5.4") for s in RIGHT]
    place(blender, low, [s for s in flat if s[0] != "frames"])
    for name in ("survey.json", "temple.png"):
        (low / name).write_bytes((tmp_path / name).read_bytes())
    (low / "masks").mkdir()
    for mask in (tmp_path / "masks").glob("temple-*.png"):
        (low / "masks" / mask.name).write_bytes(mask.read_bytes())
    run_in_blender(blender, low / "hall.blend", SCRIPTS / "likeness.py", str(low), "--survey", str(low / "survey.json"))
    other = json.loads((low / "likeness.json").read_text())
    assert not other["alike"] and other["shared_outline"]["front"] < 0.90, "the comparison must be able to say no"


def test_a_post_standing_out_through_the_roof_is_found_and_the_hall_is_not_alike(blender, small_hall, tmp_path):
    """The second live run was adopted with two king posts through its roof, and the eyes wrote
    "nothing protruding": six pixels. Frames on the end lines put a king post where the roof comes down.
    They are placed after the purlins here: placed before, the purlins refuse a ridge that misses those king
    posts, and this check is for what gets through anyway."""
    run_in_blender(blender, small_hall / "hall.blend", SCRIPTS / "survey.py", str(tmp_path))
    tall = [s for s in RIGHT if s[0] != "frames"]
    tall.insert(6, ("frames", "--seat", "4.75", "--beam", "5.9,1.8", "--king", "6.6", "--lines=-4,0,4"))
    assert [s[0] for s in tall[5:7]] == ["purlins", "frames"]
    place(blender, tmp_path, tall)
    run_in_blender(blender, tmp_path / "hall.blend", SCRIPTS / "likeness.py", str(tmp_path), "--survey",
                   str(tmp_path / "survey.json"))
    found = json.loads((tmp_path / "likeness.json").read_text())
    assert sorted(found["through_the_roof"]) == ["Frame -4.00 | king post", "Frame 4.00 | king post"]
    assert not found["alike"] and "stand out through the roof" in found["short_of_the_temple"][-1]
    assert "end-lines" in found["short_of_the_temple"][-1] and "in one call" in found["short_of_the_temple"][-1], \
        "the fault names its remedy: the fourth live run mended one end per call and each call undid the other"


def test_bracket_sets_reaching_past_the_eaves_are_found_in_numbers_and_the_hall_is_not_alike(blender, small_hall,
                                                                                               tmp_path):
    """Design run 4 was adopted with its bracket arms and outriggers standing past the eaves at both short ends,
    in the open air, and the eyes passed it: its eave ring stood at the outer columns. On the real hall the deep
    eaves cover every bracket set, as the small hall's do; pulled in to its outer columns, they do not."""
    run_in_blender(blender, small_hall / "hall.blend", SCRIPTS / "survey.py", str(tmp_path))
    place(blender, tmp_path, TIGHT)
    run_in_blender(blender, tmp_path / "hall.blend", SCRIPTS / "likeness.py", str(tmp_path), "--survey",
                   str(tmp_path / "survey.json"))
    found = json.loads((tmp_path / "likeness.json").read_text())
    said = next((s for s in found["short_of_the_temple"] if "past the edge of the roof" in s), "")
    assert not found["alike"] and "outriggers" in said and "bracket arms" in said, found["short_of_the_temple"]
    assert found["beyond_the_eaves"] and all(name.startswith("Bracket") for name in found["beyond_the_eaves"])
    assert "along the hall they reach 5.4 m from the middle and the covering ends at 4.55" in said
    assert "across it they reach 4.4 m from the middle and the covering ends at 3.55" in said
    assert said.endswith("the eave ring must stand further out than the bracket sets reach, or the eave-out be longer")


def test_rafters_as_thin_as_the_temples_do_not_leave_purlin_ends_showing_at_the_hips(blender, small_hall, tmp_path):
    """The purlins across the ends of the roof lie on top of the long ones, a purlin's depth higher, so at
    the hips the end slope's covering is that much higher than the long slope's. Rafters 0.36 m thick hid it
    in every live run. At the temple's true 0.13 m the purlin tips showed through: twelve pieces, no remedy."""
    run_in_blender(blender, small_hall / "hall.blend", SCRIPTS / "survey.py", str(tmp_path))
    thin = [s if s[0] != "rafters" else ("rafters", "--spacing", "0.8", "--size", "0.08") for s in RIGHT]
    place(blender, tmp_path, thin)
    run_in_blender(blender, tmp_path / "hall.blend", SCRIPTS / "likeness.py", str(tmp_path), "--survey",
                   str(tmp_path / "survey.json"))
    found = json.loads((tmp_path / "likeness.json").read_text())
    assert found["through_the_roof"] == [] and found["open_roof"] is None, "the hip caps hold the tips, and close"
    assert checked(blender, tmp_path)["floating"] == {}, "the covering still lies on its rafters"
    boxes = json.loads((tmp_path / "anatomy.json").read_text())["pieces"]
    across = {name: max(abs(piece["box"][0][1]), abs(piece["box"][1][1])) for name, piece in boxes.items()
              if name.startswith("Roof sheet")}
    assert max(across.values()) <= max(across["Roof sheet front eave"], across["Roof sheet back eave"]) + 0.02, \
        "the first fix lapped the eave corners too, and the real hall came out 0.8 m deeper; NVIDIA's reviewer found it"


def test_columns_and_walls_with_no_frame_on_them_are_not_built_like_the_temple(blender, small_hall, tmp_path):
    """The rebuild notes: a box with the temple's outline and its columns inside would pass likeness
    and gravity. Measured with the temple's own ruler, a hall with no frame is missing every member."""
    run_in_blender(blender, small_hall / "hall.blend", SCRIPTS / "survey.py", str(tmp_path))
    bare = tmp_path / "bare"
    bare.mkdir()
    place(blender, bare, [s for s in RIGHT if s[0] in ("platform", "columns", "walls")])
    (bare / "temple.png").write_bytes((tmp_path / "temple.png").read_bytes())
    (bare / "masks").mkdir()
    for mask in (tmp_path / "masks").glob("temple-*.png"):
        (bare / "masks" / mask.name).write_bytes(mask.read_bytes())
    run_in_blender(blender, bare / "hall.blend", SCRIPTS / "likeness.py", str(bare), "--survey",
                   str(tmp_path / "survey.json"))
    found = json.loads((bare / "likeness.json").read_text())
    missing = " ".join(found["frame"]["short"])
    assert not found["alike"] and set(found["frame"]["short"]) <= set(found["short_of_the_temple"])
    for member in ("tie beams", "roof rings", "ridge", "rafters", "bracket sets"):
        assert member in missing, member
