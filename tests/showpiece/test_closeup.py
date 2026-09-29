"""closeup: one still of a place in the model, far pieces hidden, studio or daylight look."""
from pathlib import Path

from showpiece.blend import SKILLS, run_in_blender

TOOL = SKILLS / "joint-reveal/scripts/closeup.py"


def test_a_closeup_renders_and_hides_the_far_pieces(blender, stack_model, tmp_path):
    out = tmp_path / "corner.png"
    printed = run_in_blender(blender, stack_model, TOOL, str(out), "--at", "1,-4,4.5", "--look", "2,-1.2,2.8",
                             "--hide-beyond", "2.0", "--width", "320", "--height", "180")
    assert out.is_file() and out.stat().st_size > 2000
    kept = int(printed.split("kept")[1].split()[0])
    assert kept < 11, "the far corner of the stack must be hidden"


def test_daylight_keeps_every_piece(blender, stack_model, tmp_path):
    out = tmp_path / "all.png"
    printed = run_in_blender(blender, stack_model, TOOL, str(out), "--at", "9,-9,5", "--look", "0,0,1.7",
                             "--style", "daylight", "--width", "320", "--height", "180")
    assert "kept 11 pieces" in printed and Path(out).is_file()
