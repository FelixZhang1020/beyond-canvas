"""structure-tour: a camera tour outside and in, the roof peeled for the overhead."""
import json

from showpiece.blend import SKILLS, brightness, run_in_blender

ANATOMY = SKILLS / "model-anatomy/scripts/inventory.py"
TOOL = SKILLS / "structure-tour/scripts/tour.py"


def test_the_tour_visits_four_places_and_peels_the_roof(blender, stack_model, tmp_path):
    run_in_blender(blender, stack_model, ANATOMY, str(tmp_path))
    printed = run_in_blender(blender, stack_model, TOOL, str(tmp_path), "--anatomy", str(tmp_path / "anatomy.json"),
                             "--seconds-per", "0.2", "--fps", "10", "--width", "320", "--height", "180")
    assert "TOUR 4 segments 8 frames" in printed
    plan = json.loads((tmp_path / "tour.json").read_text())
    names = [s["name"] for s in plan["segments"]]
    assert names == ["outside", "door", "inside", "overhead"]
    assert plan["segments"][3]["hidden_roles"] == ["covering", "rafter"]
    assert plan["segments"][2]["hidden_roles"] == ["wall"]
    for name in names:
        assert (tmp_path / f"tour-{name}.png").is_file()
        assert 20 < brightness(tmp_path / f"tour-{name}.png") < 235, f"{name} is lit: neither black nor washed out"
    assert (tmp_path / "tour" / "f0008.png").is_file()
