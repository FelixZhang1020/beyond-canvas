"""explode: a group of pieces pulls apart in stacking order, on a copy, rendered to frames."""
import json
import subprocess

from showpiece.blend import SKILLS, run_in_blender

ANATOMY = SKILLS / "model-anatomy/scripts/inventory.py"
TOOL = SKILLS / "joint-reveal/scripts/explode.py"
TAG = ("import bpy\nfor n in ('Block', 'Beam'): bpy.data.objects[n]['assembly'] = 'Set A'\n"
       "bpy.ops.wm.save_mainfile()")


def test_the_stack_explodes_in_tiers(blender, stack_model, tmp_path):
    run_in_blender(blender, stack_model, ANATOMY, str(tmp_path))
    printed = run_in_blender(blender, stack_model, TOOL, str(tmp_path), "--anatomy", str(tmp_path / "anatomy.json"),
                             "--pieces", "Column SW,Column SE,Lintel front,Ridge beam,Rafter front",
                             "--seconds", "0.2", "--fps", "10", "--width", "320", "--height", "180")
    assert "EXPLODE 5 pieces 4 tiers 2 frames" in printed
    assert (tmp_path / "explode" / "f0001.png").is_file() and (tmp_path / "explode-open.png").is_file()
    plan = json.loads((tmp_path / "explode.json").read_text())
    tiers = {p["name"]: p["tier"] for p in plan["pieces"]}
    assert tiers["Column SW"] == 0 and tiers["Lintel front"] == 1 and tiers["Ridge beam"] == 2 and tiers["Rafter front"] == 3
    assert plan["pieces"][-1]["offset"][2] > plan["pieces"][0]["offset"][2]


def test_the_closeups_film_each_joint_alone_one_after_another(blender, tmp_path):
    """The pull-apart among its neighbours hid the joints it was meant to show, and close-ups on
    black made no sense: the film opens on the set for three seconds, then shows each joint
    close, coming apart and locking again, and still plans the whole group for the live 3D view."""
    from showpiece.test_joints import TOOL as JOINTS, framed
    scene = framed(blender, tmp_path)
    run_in_blender(blender, scene, JOINTS, str(tmp_path), "--tenon", "Post", "Block", "--dovetail", "Beam", "Post", "max")
    derived = tmp_path / "framed-joints.blend"
    run_in_blender(blender, derived, ANATOMY, str(tmp_path / "jointed"))
    printed = run_in_blender(blender, derived, TOOL, str(tmp_path), "--anatomy", str(tmp_path / "jointed/anatomy.json"),
                             "--pieces", "Post | JOINT,Block | JOINT,Beam | JOINT", "--joints", str(tmp_path / "joints.json"),
                             "--closeups", "--seconds", "0.3", "--fps", "10", "--width", "320", "--height", "180")
    assert "EXPLODE 2 joints tenon dovetail 36 frames" in printed, "30 frames of the set, then 3 for each joint"
    plan = json.loads((tmp_path / "explode.json").read_text())
    assert [(c["kind"], c["frames"]) for c in plan["closeups"]] == [("tenon", [31, 33]), ("dovetail", [34, 36])]
    assert {p["name"] for p in plan["pieces"]} == {"Post | JOINT", "Block | JOINT", "Beam | JOINT"}
    assert (tmp_path / "joint-tenon.png").is_file() and (tmp_path / "joint-dovetail.png").is_file()
    assert (tmp_path / "explode" / "f0036.png").is_file()


def test_the_closeups_need_only_the_anatomy_read_before_the_joints_were_cut(blender, tmp_path):
    """A live run hands explode the hall's own anatomy.json, read before any joint was cut, and names the
    pieces as that file does: the cut copies are measured where they stand and take the
    originals' places, so the film is the one made with the copy's own anatomy."""
    from showpiece.test_joints import TOOL as JOINTS, framed
    scene = framed(blender, tmp_path)
    run_in_blender(blender, scene, ANATOMY, str(tmp_path))
    run_in_blender(blender, scene, JOINTS, str(tmp_path), "--tenon", "Post", "Block", "--dovetail", "Beam", "Post", "max")
    printed = run_in_blender(blender, tmp_path / "framed-joints.blend", TOOL, str(tmp_path),
                             "--anatomy", str(tmp_path / "anatomy.json"), "--pieces", "Post,Block,Beam",
                             "--joints", str(tmp_path / "joints.json"), "--closeups",
                             "--seconds", "0.3", "--fps", "10", "--width", "320", "--height", "180")
    assert "EXPLODE 2 joints tenon dovetail 36 frames" in printed
    plan = json.loads((tmp_path / "explode.json").read_text())
    assert {p["name"] for p in plan["pieces"]} == {"Post | JOINT", "Block | JOINT", "Beam | JOINT"}
    assert [set(c["pieces"]) for c in plan["closeups"]] == [{"Post | JOINT", "Block | JOINT"},
                                                              {"Beam | JOINT", "Post | JOINT"}]


def test_one_call_on_a_set_whose_joints_are_known_cuts_and_films_them(blender, tmp_path):
    """A live model never cut the joints, took stock of the copy and filmed it in turn: it
    pulled the set apart whole, or tried stills until its context ran out. Asked for a set whose joints
    are known, explode cuts them on its copy in memory and films them close, and saves nothing."""
    from showpiece.test_joints import framed
    scene = framed(blender, tmp_path)
    subprocess.run([str(blender), "-b", str(scene), "--python-exit-code", "1", "--python-expr", TAG],
                   check=True, capture_output=True, text=True, timeout=120)
    run_in_blender(blender, scene, ANATOMY, str(tmp_path))
    sets = tmp_path / "sets.json"
    sets.write_text(json.dumps({"Set A": {"tenon": [["Post", "Block"]], "dovetail": [["Beam", "Post", "max"]]}}))
    before = scene.read_bytes()
    printed = run_in_blender(blender, scene, TOOL, str(tmp_path), "--anatomy", str(tmp_path / "anatomy.json"),
                             "--assembly", "Set A", "--sets", str(sets),
                             "--seconds", "0.3", "--fps", "10", "--width", "320", "--height", "180")
    assert "EXPLODE 2 joints tenon dovetail 36 frames" in printed
    assert (tmp_path / "joint-tenon.png").is_file() and (tmp_path / "joint-dovetail.png").is_file()
    assert scene.read_bytes() == before, "the model file is never saved"
