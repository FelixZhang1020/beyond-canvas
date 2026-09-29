"""load-path shake: the settle test with the ground moving like the design earthquake at the temple's
own site, then a steady sideways pull as hard as that site's frequent earthquake.

A slender piece only stood on end stands for ever when it is let go in still air, and stands through
the shaking too, because the ground moves only millimetres; the pull is what finds it. The two
pushes are plain arithmetic and are tested without Blender; the hall tests need it.
"""
import json
import math

from conftest import load_script
from showpiece.blend import SKILLS, run_in_blender

ANATOMY = SKILLS / "model-anatomy/scripts/inventory.py"
SETTLE = SKILLS / "load-path/scripts/settle.py"
SHAKE = SKILLS / "load-path/scripts/shake.py"
QUAKE = SKILLS / "load-path/scripts/quake.py"
SMALL = ("--width", "320", "--height", "180")

# A post a thirtieth as wide as it is tall, stood on the slab beside the stack and held by nothing.
LOOSE_POST = '''
import bpy
mesh = bpy.data.meshes.new("Loose post")
verts = [(2.7 + sx * 0.04, sy * 0.04, 1.5 + sz * 1.2) for sz in (-1, 1) for sy in (-1, 1) for sx in (-1, 1)]
mesh.from_pydata(verts, [], [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)])
bpy.data.collections["05_Beams"].objects.link(bpy.data.objects.new("Loose post", mesh))
bpy.ops.wm.save_as_mainfile(filepath=r"{out}")
'''

# The same stack with its joints cut: each piece let a few centimetres into the one below, which is
# what makes the tools hold them as one, and a plank left lying loose on the slab.
JOINTED = '''
import bpy
for name, down in (("Lintel front", 0.05), ("Lintel back", 0.05), ("Ridge beam", 0.10),
                   ("Rafter front", 0.12), ("Rafter back", 0.12), ("Tile sheet", 0.12)):
    bpy.data.objects[name].location.z -= down
mesh = bpy.data.meshes.new("Loose plank")
verts = [(sx * 0.5, sy * 0.15, 0.33 + sz * 0.03) for sz in (-1, 1) for sy in (-1, 1) for sx in (-1, 1)]
mesh.from_pydata(verts, [], [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)])
bpy.data.collections["05_Beams"].objects.link(bpy.data.objects.new("Loose plank", mesh))
bpy.ops.wm.save_as_mainfile(filepath=r"{out}")
'''


def pushes(fps=240):
    quake = load_script(QUAKE, "quake_script")
    frames = int(fps * quake.SECONDS)
    return (quake, fps, quake.ground_path(frames, fps, quake.SITE["peak_g"], quake.SITE["hz"]),
            quake.sideways_pull(frames, fps, quake.SITE["pull_g"]))


def test_the_ground_shakes_as_hard_as_it_says_and_comes_back_to_rest():
    quake, fps, path, _ = pushes()
    shaking = quake.shaking_seconds(len(path), fps)
    assert shaking == 2.0, "five waves at 2.5 Hz"
    assert all(x == 0.0 for x in path[:int(fps * quake.LEAD)]), "nothing moves before the shaking"
    assert all(abs(x) < 1e-9 for x in path[int(fps * (quake.LEAD + shaking)):]), \
        "the ground is back where it began, so what moved is measured against where it started"
    push = [abs(path[i - 1] - 2 * path[i] + path[i + 1]) * fps * fps / 9.81 for i in range(1, len(path) - 1)]
    steady = push[int(fps * (quake.LEAD + quake.SWELL + 0.1)):int(fps * (quake.LEAD + shaking - quake.SWELL - 0.1))]
    assert math.isclose(max(steady), 0.20, rel_tol=0.02), f"the steady waves push at {max(steady):.3f} g, not 0.20 g"
    assert max(push) < 0.22, "swelling and fading add a little, on the hard side, and never a tenth more"
    assert math.isclose(max(path), 0.20 * 9.81 / (2 * math.pi * 2.5) ** 2, rel_tol=0.02), "about 8 mm each way at 2.5 Hz"


def test_the_pull_waits_for_the_shaking_to_end_holds_at_the_peak_and_lets_go():
    quake, fps, path, pull = pushes()
    shaking_ends = int(fps * (quake.LEAD + quake.shaking_seconds(len(path), fps)))
    assert all(g == 0.0 for g in pull[:shaking_ends + int(fps * quake.PAUSE)]), "one push at a time"
    assert max(pull) == 0.07 and math.isclose(sum(1 for g in pull if g == 0.07) / fps, quake.PULL_HOLD, abs_tol=0.02)
    assert all(g == 0.0 for g in pull[-int(fps * quake.REST) + 1:]), "what was pulled over is given time to fall"


def test_the_site_is_the_temples_own_and_says_where_its_numbers_come_from():
    quake = load_script(QUAKE, "quake_script")
    assert quake.SITE["peak_g"] == 0.20 and quake.SITE["hz"] == 2.5 and quake.SITE["pull_g"] == 0.07
    assert all(said in quake.SITE["source"] for said in ("GB 50011", "Wutai", "appendix A", "5.1.4-2", "5.1.2-2"))


def test_a_post_only_stood_on_end_stands_when_let_go_and_through_the_shaking_and_is_pulled_over(blender, stack_model, tmp_path):
    """The mistake the settle test cannot see: a slender post nobody cut into anything. The stack
    beside it, whose columns are an eighth as wide as they are tall, stands through both pushes."""
    script, model = tmp_path / "loose_post.py", tmp_path / "loose.blend"
    script.write_text(LOOSE_POST.format(out=model))
    run_in_blender(blender, stack_model, script)
    run_in_blender(blender, model, ANATOMY, str(tmp_path))
    anatomy = ("--anatomy", str(tmp_path / "anatomy.json"))
    assert "SETTLE 10 pieces fell 0 shifted 0" in run_in_blender(blender, model, SETTLE, str(tmp_path), *anatomy,
                                                                 "--seconds", "1", "--fps", "12", *SMALL, timeout=900)
    printed = run_in_blender(blender, model, SHAKE, str(tmp_path), *anatomy, *SMALL, timeout=900)
    result = json.loads((tmp_path / "shake.json").read_text())
    found = result["summary"]["shake"]
    assert found["moved_in_the_shaking"] == 0, "the ground moved 8 mm each way; nothing fell for that"
    assert found["came_down"] == 1 and found["came_down_names"] == ["Loose post"], printed[-400:]
    assert result["pieces"]["Loose post"]["turned_deg"] > 45 and result["pieces"]["Loose post"]["moved_in_the_shaking_m"] < 0.05
    assert "| 1 came down: Loose post |" in printed and "steady sideways pull of 0.07 g" in printed


def test_the_same_frame_with_its_joints_cut_stands_through_both(blender, stack_model, tmp_path):
    script, model = tmp_path / "jointed.py", tmp_path / "jointed.blend"
    script.write_text(JOINTED.format(out=model))
    run_in_blender(blender, stack_model, script)
    run_in_blender(blender, model, ANATOMY, str(tmp_path))
    printed = run_in_blender(blender, model, SHAKE, str(tmp_path), "--anatomy", str(tmp_path / "anatomy.json"), *SMALL,
                             timeout=900)
    assert "SHAKE 10 pieces fell 0 shifted 0" in printed and "| 0 came down |" in printed
    result = json.loads((tmp_path / "shake.json").read_text())
    assert result["pieces"]["Loose plank"]["moved_m"] < 0.05, "a plank lying loose does not slide for a pull of 0.07 g"
    assert result["summary"]["shake"]["came_down"] == 0 and result["summary"]["shake"]["drift_m"] < 0.05
    assert result["summary"]["shake"]["peak_g"] == 0.20 and result["summary"]["shake"]["shaking_seconds"] == 2.0
    assert (tmp_path / "shake-end.png").is_file() and not (tmp_path / "shake.mp4").exists(), "stills, no video unless asked"
    assert not (tmp_path / "settle.json").exists(), "the shake keeps its own record and leaves the settle test's alone"
