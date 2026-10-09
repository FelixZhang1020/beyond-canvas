"""load-path flow: pieces coloured by what they carry, revealed from the roof down."""
import json
import subprocess
import sys

from showpiece.blend import SKILLS, run_in_blender

ANATOMY = SKILLS / "model-anatomy/scripts/inventory.py"
BEARING = SKILLS / "model-anatomy/scripts/bearing.py"
WEIGHTS = SKILLS / "load-path/scripts/weights.py"
FLOW = SKILLS / "load-path/scripts/flow.py"


def test_colours_come_down_from_the_roof(blender, stack_model, tmp_path):
    run_in_blender(blender, stack_model, ANATOMY, str(tmp_path))
    run_in_blender(blender, stack_model, BEARING, str(tmp_path))
    subprocess.run([sys.executable, str(WEIGHTS), str(tmp_path / "anatomy.json"), str(tmp_path / "bearing.json"),
                    str(tmp_path)], check=True, capture_output=True)
    printed = run_in_blender(blender, stack_model, FLOW, str(tmp_path), "--anatomy", str(tmp_path / "anatomy.json"),
                             "--loads", str(tmp_path / "loads.json"), "--seconds", "1.0", "--hold", "0.2", "--fps", "10",
                             "--width", "320", "--height", "180")
    assert "FLOW 9 pieces 12 frames" in printed, "seven timber pieces and two rafters; the sheet is hidden"
    plan = json.loads((tmp_path / "flow.json").read_text())
    reveal = {p["name"]: p["reveal_frame"] for p in plan["pieces"]}
    # The rafter and ridge tops are 5 cm apart in a 3 m drop: the same frame at this length.
    assert reveal["Rafter front"] <= reveal["Ridge beam"] < reveal["Column SW"]
    by_name = {p["name"]: p for p in plan["pieces"]}
    # The ridge carries both rafters and most of the sheet; a rafter carries three sevenths of the sheet.
    assert by_name["Ridge beam"]["carries_N"] > by_name["Rafter front"]["carries_N"]
    assert by_name["Ridge beam"]["colour"] != by_name["Rafter front"]["colour"], "more load, a different colour"
    assert (tmp_path / "flow-end.png").is_file() and (tmp_path / "flow" / "f0012.png").is_file()
