"""A child's sketch scene becomes a little building the skills can read and take apart."""
import json
from pathlib import Path

from showpiece.blend import ROOT, run_in_blender

TOY = ROOT / "studio/showpiece/toy.py"
ANATOMY = ROOT / "skills/model-anatomy/scripts/inventory.py"
BEARING = ROOT / "skills/model-anatomy/scripts/bearing.py"

SCENE = {"version": 1, "method": "geometric-approximation", "source_aspect": 1.5, "light": [-3, 6, 5],
         "camera": {"target": [0, 1, 0], "distance": 10, "elevation": 25, "azimuth": 0, "fov": 40},
         "objects": [{"kind": "box", "position": [0, 0.5, 0], "size": [2, 1, 1.4], "yaw": 0},
                     {"kind": "cylinder", "position": [-0.5, 1.6, 0], "size": [0.6, 1.2, 0.6], "yaw": 0},
                     {"kind": "sphere", "position": [0.6, 1.4, 0.2], "size": [0.8, 0.8, 0.8], "yaw": 0}]}


def test_the_scene_becomes_a_model_with_ground_and_three_pieces_that_rest_on_each_other(blender, tmp_path):
    scene_path = tmp_path / "scene.json"
    scene_path.write_text(json.dumps(SCENE))
    printed = run_in_blender(blender, None, TOY, str(scene_path), str(tmp_path / "toy.blend"))
    assert "TOY" in printed and "3 solids" in printed
    model = tmp_path / "toy.blend"
    run_in_blender(blender, model, ANATOMY, str(tmp_path))
    run_in_blender(blender, model, BEARING, str(tmp_path))
    anatomy = json.loads((tmp_path / "anatomy.json").read_text())
    assert anatomy["model"]["by_role"] == {"ground": 1, "timber": 3}
    bearing = json.loads((tmp_path / "bearing.json").read_text())
    on = {n: {c["on"] for c in cs} for n, cs in bearing["rests_on"].items()}
    assert on["Box 1"] == {"Slab"} and on["Cylinder 1"] == {"Box 1"} and on["Sphere 1"] == {"Box 1"}
    assert [sorted(s) for s in bearing["stages"]] == [["Box 1"], ["Cylinder 1", "Sphere 1"]]
