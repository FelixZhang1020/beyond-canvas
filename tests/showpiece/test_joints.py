"""joint-reveal: real mortise-and-tenon joints on a copy, the model itself untouched."""
import json
import subprocess

from showpiece.blend import SKILLS, run_in_blender

TOOL = SKILLS / "joint-reveal/scripts/joints.py"
COUNT = ("import bpy; o = bpy.data.objects[{name!r}]; "
         "print('VERTS', len(o.data.vertices), 'FACES', len(o.data.polygons), 'MATS', [m.name for m in o.data.materials if m])")
CROSS = ("import bpy, bmesh; bpy.ops.wm.read_factory_settings(use_empty=True)\n"
         "def box(n, c, s):\n"
         "    m = bpy.data.meshes.new(n); bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)\n"
         "    bmesh.ops.scale(bm, vec=s, verts=bm.verts); bmesh.ops.translate(bm, vec=c, verts=bm.verts)\n"
         "    bm.to_mesh(m); o = bpy.data.objects.new(n, m); bpy.context.scene.collection.objects.link(o)\n"
         "box('A', (0, 0, 1), (2.0, 0.2, 0.3)); box('B', (0, 0, 1), (0.2, 2.0, 0.3))\n"
         "bpy.ops.wm.save_as_mainfile(filepath={path!r})")


def facts(blender, model, name):
    done = subprocess.run([str(blender), "-b", str(model), "--python-exit-code", "1", "--python-expr",
                           COUNT.format(name=name)], capture_output=True, text=True, timeout=120)
    assert done.returncode == 0, done.stderr
    line = [ln for ln in done.stdout.splitlines() if ln.startswith("VERTS")][0].split()
    return int(line[1]), int(line[3]), " ".join(line[5:])


def test_a_tenon_grows_on_the_column_and_a_mortise_opens_in_the_lintel(blender, stack_model, tmp_path):
    printed = run_in_blender(blender, stack_model, TOOL, str(tmp_path), "--tenon", "Column SW", "Lintel front")
    assert "JOINTS 1" in printed
    derived = tmp_path / "stack-joints.blend"
    assert derived.is_file()
    verts, faces, mats = facts(blender, derived, "Column SW | JOINT")
    assert verts == 16 and faces in (11, 12), "a box plus a tenon box on top"
    verts, faces, mats = facts(blender, derived, "Lintel front | JOINT")
    assert faces > 6 and "exposed end grain" in mats, "the mortise adds faces with the end-grain material"
    before, _, _ = facts(blender, stack_model, "Column SW")
    assert before == 8, "the source model is untouched"
    joints = json.loads((tmp_path / "joints.json").read_text())
    assert joints["joints"][0]["kind"] == "tenon"
    assert joints["joints"][0]["explode"]["Lintel front | JOINT"] == [0, 0, 0.5]


def test_a_dovetail_shapes_the_beam_end_and_slots_the_column(blender, stack_model, tmp_path):
    printed = run_in_blender(blender, stack_model, TOOL, str(tmp_path), "--dovetail", "Lintel front", "Column SE", "max")
    assert "JOINTS 1" in printed
    derived = tmp_path / "stack-joints.blend"
    _, faces, mats = facts(blender, derived, "Lintel front | JOINT")
    assert faces > 6 and "exposed end grain" in mats
    _, faces, _ = facts(blender, derived, "Column SE | JOINT")
    assert faces > 6, "the slot cuts faces into the column"


def test_a_crosslap_notches_two_crossing_beams(blender, tmp_path):
    scene = tmp_path / "cross.blend"
    subprocess.run([str(blender), "-b", "--python-exit-code", "1", "--python-expr", CROSS.format(path=str(scene))],
                   check=True, capture_output=True, text=True, timeout=120)
    printed = run_in_blender(blender, scene, TOOL, str(tmp_path), "--crosslap", "A", "B")
    assert "JOINTS 1" in printed
    derived = tmp_path / "cross-joints.blend"
    _, faces_a, _ = facts(blender, derived, "A | JOINT")
    _, faces_b, _ = facts(blender, derived, "B | JOINT")
    assert faces_a > 6 and faces_b > 6, "both beams lose a half-depth notch at the crossing"


PROBE = ("import bpy, bmesh; from mathutils import Vector; from mathutils.bvhtree import BVHTree\n"
         "o = bpy.data.objects[{name!r}]; bm = bmesh.new(); bm.from_mesh(o.data); bm.transform(o.matrix_world)\n"
         "hit = BVHTree.FromBMesh(bm).ray_cast(Vector({origin!r}), Vector({direction!r}))\n"
         "print('HIT', 'none' if hit[0] is None else round(hit[0].z, 4), 'HIDDEN', o.hide_render)")
FRAMED = ("import bpy, bmesh; bpy.ops.wm.read_factory_settings(use_empty=True)\n"
          "def box(n, c, s):\n"
          "    m = bpy.data.meshes.new(n); bm = bmesh.new(); bmesh.ops.create_cube(bm, size=1.0)\n"
          "    bmesh.ops.scale(bm, vec=s, verts=bm.verts); bmesh.ops.translate(bm, vec=c, verts=bm.verts)\n"
          "    bm.to_mesh(m); o = bpy.data.objects.new(n, m); bpy.context.scene.collection.objects.link(o)\n"
          "box('Post', (0, 0, 1.5), (0.4, 0.4, 3.0)); box('Block', (0, 0, 3.05), (0.6, 0.6, 0.1))\n"
          "box('Beam', (-1.1, 0, 2.5), (2.2, 0.3, 0.4))\n"
          "bpy.ops.wm.save_as_mainfile(filepath={path!r})")


def probe(blender, model, name, origin, direction):
    """Where a ray first meets one piece, and whether the piece is hidden from the render."""
    done = subprocess.run([str(blender), "-b", str(model), "--python-exit-code", "1", "--python-expr",
                           PROBE.format(name=name, origin=origin, direction=direction)], capture_output=True, text=True, timeout=120)
    assert done.returncode == 0, done.stderr
    words = [ln for ln in done.stdout.splitlines() if ln.startswith("HIT")][0].split()
    return (None if words[1] == "none" else float(words[1])), words[3] == "True"


def framed(blender, tmp_path):
    """A post with a block on top and a beam framing into its side below the top, the way a tie beam
    meets a column under its bracket set."""
    scene = tmp_path / "framed.blend"
    subprocess.run([str(blender), "-b", "--python-exit-code", "1", "--python-expr", FRAMED.format(path=str(scene))],
                   check=True, capture_output=True, text=True, timeout=120)
    return scene


def test_the_mortise_is_a_real_hole_the_tenon_fits(blender, stack_model, tmp_path):
    """Every cut used to be made with its faces inside out and removed nothing, while the
    face counts above still passed: the lintel over a tenon had no hole. A ray up into it tells."""
    run_in_blender(blender, stack_model, TOOL, str(tmp_path), "--tenon", "Column SW", "Lintel front")
    bottom, _ = probe(blender, stack_model, "Lintel front", (-2.0, -1.2, 2.0), (0, 0, 1))
    assert abs(bottom - 2.7) < 1e-3, "the untouched lintel is met at its underside"
    into, _ = probe(blender, tmp_path / "stack-joints.blend", "Lintel front | JOINT", (-2.0, -1.2, 2.0), (0, 0, 1))
    assert into > 2.8, f"the ray runs 12 cm up into the mortise, not stopped at the underside ({into})"


def test_the_dovetail_slot_is_open_at_the_top_so_the_beam_drops_in(blender, tmp_path):
    scene = framed(blender, tmp_path)
    run_in_blender(blender, scene, TOOL, str(tmp_path), "--dovetail", "Beam", "Post", "max")
    top, _ = probe(blender, scene, "Post", (-0.1, 0, 5.0), (0, 0, -1))
    assert abs(top - 3.0) < 1e-3
    floor, _ = probe(blender, tmp_path / "framed-joints.blend", "Post | JOINT", (-0.1, 0, 5.0), (0, 0, -1))
    assert floor < 2.4, f"the slot runs from the top down to the beam's underside ({floor})"


def test_a_piece_in_two_joints_is_one_visible_copy_with_both_cut_into_it(blender, tmp_path):
    """The corner set's column takes a tenon on top and a dovetail slot in its side. A second copy used to be
    made from the hidden original, hidden too, so the slot's close-up showed a beam over nothing."""
    scene = framed(blender, tmp_path)
    run_in_blender(blender, scene, TOOL, str(tmp_path), "--tenon", "Post", "Block", "--dovetail", "Beam", "Post", "max")
    derived = tmp_path / "framed-joints.blend"
    joints = json.loads((tmp_path / "joints.json").read_text())["joints"]
    assert {n for j in joints for n in j["pieces"]} == {"Post | JOINT", "Block | JOINT", "Beam | JOINT"}
    tenon, hidden = probe(blender, derived, "Post | JOINT", (0.04, 0, 5.0), (0, 0, -1))
    assert tenon > 3.05 and not hidden, "the tenon stands on the post's top"
    slot, _ = probe(blender, derived, "Post | JOINT", (-0.15, 0, 5.0), (0, 0, -1))
    assert slot < 2.4, "and the same post has the slot"


def test_the_upper_crossing_arm_lifts_off_and_arms_already_lapped_are_never_cut_through(blender, tmp_path):
    """Fresh arms: the lower keeps its bottom half where they cross, the upper its top half, and the upper
    lifts. The Foguang hall's set comes already lapped, its lower arm named first; the first arm
    used to be lifted and cut from below every time, which went clean through both (operator: "they cross the wrong
    directions"). Named either way round, lapped arms keep their halves and the upper one lifts."""
    scene = tmp_path / "cross.blend"
    subprocess.run([str(blender), "-b", "--python-exit-code", "1", "--python-expr", CROSS.format(path=str(scene))],
                   check=True, capture_output=True, text=True, timeout=120)
    run_in_blender(blender, scene, TOOL, str(tmp_path), "--crosslap", "A", "B")
    lapped = tmp_path / "cross-joints.blend"
    joint = json.loads((tmp_path / "joints.json").read_text())["joints"][0]
    assert joint["explode"]["B | JOINT"] == [0, 0, 0.35] and joint["explode"]["A | JOINT"] == [0, 0, 0]
    assert abs(probe(blender, lapped, "A | JOINT", (0.0, 0.0, 2.0), (0, 0, -1))[0] - 1.0) < 0.02, "A, lower, cut from above"
    assert abs(probe(blender, lapped, "B | JOINT", (0.0, 0.0, 0.0), (0, 0, 1))[0] - 1.0) < 0.02, "B, upper, cut from below"
    again = tmp_path / "again"
    run_in_blender(blender, lapped, TOOL, str(again), "--crosslap", "B | JOINT", "A | JOINT", "--stem", "twice")
    joint = json.loads((again / "joints.json").read_text())["joints"][0]
    assert joint["explode"]["B | JOINT | JOINT"] == [0, 0, 0.35], "the upper arm is found, whichever is named first"
    twice = again / "twice-joints.blend"
    assert abs(probe(blender, twice, "A | JOINT | JOINT", (0.0, 0.0, 0.0), (0, 0, 1))[0] - 0.85) < 0.02, "A keeps its bottom"
    assert abs(probe(blender, twice, "B | JOINT | JOINT", (0.0, 0.0, 2.0), (0, 0, -1))[0] - 1.15) < 0.02, "B keeps its top"
