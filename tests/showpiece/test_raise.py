"""raise-the-hall: the building goes up in its true carrying order, scene by scene."""
import json
import subprocess
import sys

from showpiece.blend import SKILLS, run_in_blender

ANATOMY = SKILLS / "model-anatomy/scripts/inventory.py"
BEARING = SKILLS / "model-anatomy/scripts/bearing.py"
STAGES = SKILLS / "raise-the-hall/scripts/stages.py"
RAISE = SKILLS / "raise-the-hall/scripts/raise.py"


def measured(blender, stack_model, tmp_path):
    run_in_blender(blender, stack_model, ANATOMY, str(tmp_path))
    run_in_blender(blender, stack_model, BEARING, str(tmp_path))
    return subprocess.run([sys.executable, str(STAGES), str(tmp_path / "bearing.json"), str(tmp_path / "anatomy.json"),
                           str(tmp_path)], capture_output=True, text=True, check=True)


def test_stages_become_scenes_with_labels(blender, stack_model, tmp_path):
    done = measured(blender, stack_model, tmp_path)
    assert "SCENES 5 from 5 stages" in done.stdout
    scenes = json.loads((tmp_path / "scenes.json").read_text())["scenes"]
    # The lintels are all named "Lintel ...", so their scene is "tie beams"; the ridge is a plain beam.
    assert [s["label"] for s in scenes] == ["columns", "tie beams", "beams", "rafters", "roof covering"]
    assert scenes[0]["pieces"] == ["Column NE", "Column NW", "Column SE", "Column SW"]


def test_the_stack_rises_scene_by_scene(blender, stack_model, tmp_path):
    measured(blender, stack_model, tmp_path)
    printed = run_in_blender(blender, stack_model, RAISE, str(tmp_path), "--scenes", str(tmp_path / "scenes.json"),
                             "--anatomy", str(tmp_path / "anatomy.json"), "--scene-seconds", "0.2",
                             "--settle-seconds", "0.2", "--fps", "10", "--width", "320", "--height", "180")
    assert "RAISE 5 scenes 12 frames" in printed
    plan = json.loads((tmp_path / "raise.json").read_text())
    assert plan["scenes"][0]["frames"] == [1, 3] and plan["scenes"][4]["frames"] == [9, 11]
    assert (tmp_path / "raise-1.png").is_file() and (tmp_path / "raise" / "f0012.png").is_file()
