"""load-path's rigid geometry: a piece's centre must not drift with its distance from the origin."""
from showpiece.blend import SKILLS, run_in_blender

PROBE = '''
import sys
sys.path.insert(0, {scripts!r})
import bpy
from rigid import centre_and_volume
bpy.ops.mesh.primitive_cube_add(size=1.0, location=(-8.0925, -10.6075, 8.06))
ear = bpy.context.object
ear.scale = (0.065, 0.065, 0.1)
bpy.context.view_layer.update()
centre, volume = centre_and_volume(ear)
print("PROBE", round(centre.x, 5), round(centre.y, 5), round(centre.z, 5), round(volume, 9))
'''


def test_a_block_ear_fifteen_metres_out_is_centred_to_a_millimetre(blender, stack_model, tmp_path):
    probe = tmp_path / "probe.py"
    probe.write_text(PROBE.format(scripts=str(SKILLS / "load-path/scripts")))
    printed = run_in_blender(blender, stack_model, probe, str(tmp_path))
    line = next(l for l in printed.splitlines() if l.startswith("PROBE"))
    x, y, z, volume = (float(v) for v in line.split()[1:])
    assert abs(x + 8.0925) < 0.001 and abs(y + 10.6075) < 0.001 and abs(z - 8.06) < 0.001
    assert abs(volume - 0.065 * 0.065 * 0.1) < 1e-6
