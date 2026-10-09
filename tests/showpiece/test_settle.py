"""load-path settle: every piece let go under gravity; a sound stack does not move."""
import json

from showpiece.blend import SKILLS, brightness, run_in_blender

ANATOMY = SKILLS / "model-anatomy/scripts/inventory.py"
SETTLE = SKILLS / "load-path/scripts/settle.py"


def test_the_stack_stands(blender, stack_model, tmp_path):
    run_in_blender(blender, stack_model, ANATOMY, str(tmp_path))
    printed = run_in_blender(blender, stack_model, SETTLE, str(tmp_path), "--anatomy", str(tmp_path / "anatomy.json"),
                             "--seconds", "1", "--fps", "12", "--width", "320", "--height", "180", timeout=900)
    assert "SETTLE 9 pieces fell 0 shifted 0" in printed, "seven timber pieces and two rafters are let go"
    result = json.loads((tmp_path / "settle.json").read_text())
    assert max(p["moved_m"] for p in result["pieces"].values()) < 0.05
    assert result["summary"]["groups"] >= 1, "the two rafters and the sheet move as one roof"
    assert (tmp_path / "settle-end.png").is_file() and (tmp_path / "settle" / "f0012.png").is_file()
    assert 20 < brightness(tmp_path / "settle-end.png") < 235, "the still is lit: neither black nor washed out"
