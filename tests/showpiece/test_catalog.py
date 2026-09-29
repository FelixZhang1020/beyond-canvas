"""The six skills are read from their folders, and every tool call becomes a plain argv list."""
from pathlib import Path

import pytest

from studio.showpiece import catalog


def test_the_six_skills_load_with_their_descriptions():
    skills = catalog.load_skills()
    assert set(skills) == set(catalog.SIX)
    assert skills["shot-judge"].description.startswith("Looks at one rendered picture")
    assert "## Tool" in skills["shot-judge"].body


def test_a_blender_tool_becomes_argv_with_the_model_and_run_folder(tmp_path):
    spec = catalog.TOOLS[("joint-reveal", "closeup")]
    argv = catalog.argv_for(spec, {"at": "-9.6,-11.9,8.6", "look": "0,0,1", "hide-above": 7.0,
                                   "move": ["A=0,0,0.3", "B=0,0,0.3"], "out": "tenon.png"},
                            Path("/m/hall.blend"), tmp_path)
    assert argv[1:4] == ["-b", "/m/hall.blend", "--python-exit-code"]
    assert argv[argv.index("--") + 1] == str(tmp_path / "tenon.png")
    assert "--at=-9.6,-11.9,8.6" in argv and argv.count("--move") == 2 and "--hide-above" in argv


def test_a_switch_is_said_or_left_out_never_given_a_value(tmp_path):
    spec = catalog.TOOLS[("joint-reveal", "explode")]
    args = {"anatomy": "a.json", "assembly": "Column A", "joints": "joints.json"}
    on = catalog.argv_for(spec, {**args, "closeups": True}, Path("/m/hall.blend"), tmp_path)
    off = catalog.argv_for(spec, {**args, "closeups": False}, Path("/m/hall.blend"), tmp_path)
    assert "--closeups" in on and "True" not in on, "argparse would refuse '--closeups True'"
    assert "--closeups" not in off and "False" not in off


def test_a_joint_is_named_the_ways_a_model_writes_it_and_never_letter_by_letter(tmp_path):
    """A live run wrote the joints as a string and as a flat list: the string went in a
    letter at a time ("o n r - 7 - . 3") and the list a name per --tenon, so no joint could be named."""
    spec, hall = catalog.TOOLS[("joint-reveal", "joints")], Path("/m/hall.blend")

    def tail(args):
        argv = catalog.argv_for(spec, {"out_dir": ".", **args}, hall, tmp_path)
        return argv[argv.index("--") + 2:]

    one = ["--tenon", "Post", "Column A | Ludou foot"]
    assert tail({"tenon": ["Post", "Column A | Ludou foot"]}) == one, "a flat list is one use"
    assert tail({"tenon": [["Post", "Column A | Ludou foot"]]}) == one, "a list per use"
    assert tail({"dovetail": [["Beam", "Post", "max"], ["Beam 2", "Post 2", "min"]]}).count("--dovetail") == 2
    with pytest.raises(ValueError, match=r'tenon takes 2 values each time, one list per use: \{"tenon": \[\["COLUMN"'):
        tail({"tenon": "Post Column A | Ludou foot"})
    collapse = catalog.argv_for(catalog.TOOLS[("load-path", "collapse")],
                                {"out_dir": ".", "joint": ["Post", "Block"]}, hall, tmp_path)
    assert collapse[-3:] == ["--joint", "Post", "Block"]
    closeup = catalog.argv_for(catalog.TOOLS[("joint-reveal", "closeup")], {"out": "a.png", "hide": "Roof"},
                               hall, tmp_path)
    assert closeup[-2:] == ["--hide", "Roof"], "a one-word flag given a string is that word"


def test_a_yes_where_a_file_belongs_is_left_out(tmp_path):
    """A live run wrote "joints": true and was told the folder held no file called True."""
    (tmp_path / "anatomy.json").write_text("{}")
    spec = catalog.TOOLS[("joint-reveal", "explode")]
    args = catalog.known_inputs(spec, {"assembly": "Column A", "joints": True, "closeups": True}, tmp_path)
    assert args == {"anatomy": "anatomy.json", "assembly": "Column A", "closeups": True}


def test_a_path_the_model_writes_stays_inside_the_run_folder(tmp_path):
    """Code review: an absolute or climbing path let a steered model write anywhere the studio can, or send any
    picture on the node to its provider. The call is refused instead, and the refusal is what the model reads."""
    run_dir = tmp_path / "runs" / "r1"
    spec = catalog.TOOLS[("shot-judge", "judge")]
    for elsewhere in ("/etc/passwd", "../../elsewhere.png", "sub/../../escape.png", f"{tmp_path}/other.png"):
        with pytest.raises(ValueError, match="outside the run folder"):
            catalog.argv_for(spec, {"image": elsewhere, "meant": "x"}, None, run_dir)
    assert catalog.input_path(run_dir, f"{run_dir}/renders/a.png") == run_dir / "renders" / "a.png"
    assert catalog.input_path(run_dir, "a.png") == run_dir / "a.png"


def test_unknown_keys_and_odd_values_are_refused(tmp_path):
    spec = catalog.TOOLS[("shot-judge", "judge")]
    with pytest.raises(ValueError, match="hidden"):
        catalog.argv_for(spec, {"image": "a.png", "meant": "x", "hidden": 1}, None, tmp_path)
    with pytest.raises(ValueError, match="newline"):
        catalog.argv_for(spec, {"image": "a.png", "meant": "x\ny"}, None, tmp_path)


def test_the_models_habits_are_forgiven(tmp_path):
    """The run folder's own path is stripped, dashed names lose their dashes, a list joins with commas."""
    spec = catalog.TOOLS[("structure-tour", "tour")]
    run_dir = tmp_path / "runs" / "r1"
    argv = catalog.argv_for(spec, {"--out_dir": str(run_dir), "anatomy": f"{run_dir}/anatomy.json",
                                   "segments": ["outside", "inside"]}, Path("/m/stack.blend"), run_dir)
    tail = argv[argv.index("--") + 1:]
    assert tail[0] == str(run_dir) and str(run_dir / "anatomy.json") in tail
    assert "outside,inside" in tail and "[" not in " ".join(tail)
    assert catalog.inside_run(run_dir, f"./{run_dir}/x/y.png") == "x/y.png"
    assert catalog.inside_run(run_dir, "plain.png") == "plain.png"


def test_quick_defaults_fill_only_the_render_flags_a_tool_has_and_never_the_models_own():
    tour = catalog.TOOLS[("structure-tour", "tour")]
    args = catalog.quick_args(tour, {"anatomy": "anatomy.json", "fps": "24"})
    assert args["fps"] == "24", "the model's own value stands"
    assert args["width"] == "960" and args["height"] == "540" and args["seconds-per"] == "3"
    assert "seconds" not in args, "the tour has no --seconds flag"
    stages = catalog.TOOLS[("raise-the-hall", "stages")]
    assert catalog.quick_args(stages, {"out_dir": "."}) == {"out_dir": "."}, "a tool without render flags is untouched"
    assert catalog.quick_args(tour, {"anatomy": "anatomy.json"}, None) == {"anatomy": "anatomy.json"}, "no quick, no change"
