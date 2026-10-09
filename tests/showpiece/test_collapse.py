"""load-path collapse: one joint taken out, and what depends on it comes down link by link."""
import json

import pytest

from showpiece.blend import SKILLS, run_in_blender

ANATOMY = SKILLS / "model-anatomy/scripts/inventory.py"
BEARING = SKILLS / "model-anatomy/scripts/bearing.py"
COLLAPSE = SKILLS / "load-path/scripts/collapse.py"


def test_taking_out_a_joint_brings_down_what_depends_on_it_link_by_link(blender, stack_model, tmp_path):
    """松开手: the lintel held on a column top gives way first, then what rests on it,
    each landing on what still stands; the columns stand."""
    run_in_blender(blender, stack_model, ANATOMY, str(tmp_path))
    run_in_blender(blender, stack_model, BEARING, str(tmp_path))
    printed = run_in_blender(blender, stack_model, COLLAPSE, str(tmp_path), "--anatomy", str(tmp_path / "anatomy.json"),
                             "--bearing", str(tmp_path / "bearing.json"), "--joint", "Column SW", "Lintel front",
                             "--fps", "8", "--width", "320", "--height", "180", timeout=900)
    assert "COLLAPSE" in printed and "from the joint between Column SW and Lintel front" in printed
    plan = json.loads((tmp_path / "collapse.json").read_text())
    assert plan["links"][0]["pieces"] == ["Lintel front"], "the piece the joint held goes first"
    assert plan["links"][1]["frame"] - plan["links"][0]["frame"] == 8, "a link of a few pieces is given a second, at 8 fps"
    assert len(plan["links"]) >= 2, "and something depends on it"
    assert plan["pieces"]["Lintel front"]["drop_m"] > 1.0, "it falls to what stands below"
    assert not any(name.startswith("Column") for name in plan["pieces"]), "the columns stand"
    frames = plan["summary"]["frames"]
    assert (tmp_path / "collapse" / f"f{frames:04d}.png").is_file() and (tmp_path / "collapse-end.png").is_file()


def test_a_joint_that_is_not_there_is_refused_by_name(blender, stack_model, tmp_path):
    run_in_blender(blender, stack_model, ANATOMY, str(tmp_path))
    run_in_blender(blender, stack_model, BEARING, str(tmp_path))
    with pytest.raises(RuntimeError) as caught:
        run_in_blender(blender, stack_model, COLLAPSE, str(tmp_path), "--anatomy", str(tmp_path / "anatomy.json"),
                       "--bearing", str(tmp_path / "bearing.json"), "--joint", "Column NE", "Lintel front")
    assert "does not rest on Column NE" in str(caught.value)
