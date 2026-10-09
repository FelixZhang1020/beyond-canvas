"""Three true joints, cut into copies of the pieces and saved as a derived model:
- tenon: a square tenon grows on a column top and a matching mortise opens in the piece above;
- crosslap: two arms crossing at one level each lose a half-depth notch, the upper from below and
  the lower from above, the way a hua gong meets a nidao gong in the big block;
- dovetail: a beam end flares into a dovetail and the column it meets gets the matching slot,
  open at the top so the beam drops in.
The originals are hidden on the copy and kept; the source file is never saved.
Usage: blender -b model.blend --python-exit-code 1 --python joints.py -- out_dir
           [--tenon COLUMN INTO] [--crosslap A B] [--dovetail BEAM INTO min|max] [--stem NAME]
"""
import argparse
import json
import os
import sys

import bmesh
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from timber import add_box, add_plan_prism, box_of, cut, join_into, new_bm, own_mesh  # noqa: E402

COLLECTION = "10_Joints"
PLAY = 0.002


def derived(scene, name):
    """A visible copy named '<name> | JOINT' in the joints collection; the original hidden. A piece in
    two joints is one copy with both cut into it, as the column under a corner set carries its tenon
    and its dovetail slot: a second copy was made from the hidden original, and was hidden too."""
    made = scene.objects.get(f"{name} | JOINT")
    if made is not None:
        return made
    src = scene.objects[name]
    coll = bpy.data.collections.get(COLLECTION) or bpy.data.collections.new(COLLECTION)
    if coll.name not in scene.collection.children:
        scene.collection.children.link(coll)
    copy = src.copy()
    copy.data = src.data.copy()
    copy.name = f"{name} | JOINT"
    coll.objects.link(copy)
    src.hide_render = src.hide_viewport = True
    return own_mesh(copy)


def tenon(scene, column, into, size=0.16, depth=0.12):
    col, top = derived(scene, column), derived(scene, into)
    lo, hi = box_of(col)
    cx, cy, z = (lo.x + hi.x) / 2, (lo.y + hi.y) / 2, hi.z
    h = size / 2
    bm, uv = new_bm()
    add_box(bm, uv, cx - h, cx + h, cy - h, cy + h, z - 0.001, z + depth)
    join_into(col, bm)
    bm, uv = new_bm()
    add_box(bm, uv, cx - h - PLAY, cx + h + PLAY, cy - h - PLAY, cy + h + PLAY, z - 0.01, z + depth + PLAY)
    cut(top, bm)
    return {"kind": "tenon", "pieces": [col.name, top.name], "explode": {top.name: [0, 0, 0.5]}}


def first_hit(obj, x, y, z, up):
    """Where a vertical ray from (x, y, z), going up or down, first meets the piece; None if it misses."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.transform(obj.matrix_world)
    hit = BVHTree.FromBMesh(bm).ray_cast(Vector((x, y, z)), Vector((0, 0, 1 if up else -1)))
    bm.free()
    return hit[0].z if hit[0] is not None else None


def crosslap(scene, a_name, b_name):
    """Two arms crossing at one level: the lower loses its top half where they cross, the upper its
    bottom half, and the upper lifts off. A model may already have the lap cut, as the Foguang hall's
    front-left set does (its Nidao gong sits on its Hua gong); then the arms are read for which is upper
    and cutting again changes nothing. The first arm named used to be always lifted and cut from
    below, which went clean through that set's arms (operator: "they cross the wrong directions")."""
    a, b = derived(scene, a_name), derived(scene, b_name)
    la, ha = box_of(a)
    lb, hb = box_of(b)
    x0, x1 = max(la.x, lb.x) - PLAY, min(ha.x, hb.x) + PLAY
    y0, y1 = max(la.y, lb.y) - PLAY, min(ha.y, hb.y) + PLAY
    z0, z1 = max(la.z, lb.z), min(ha.z, hb.z)
    mid, cx, cy = (z0 + z1) / 2, (x0 + x1) / 2, (y0 + y1) / 2
    quarter = (z1 - z0) / 4

    def open_below(obj):
        hit = first_hit(obj, cx, cy, z0 - 1.0, up=True)
        return hit is not None and hit > z0 + quarter
    upper, lower = (a, b) if open_below(a) else (b, a)
    bm, uv = new_bm()
    add_box(bm, uv, x0, x1, y0, y1, mid, z1 + 0.01)
    cut(lower, bm)
    bm, uv = new_bm()
    add_box(bm, uv, x0, x1, y0, y1, z0 - 0.01, mid)
    cut(upper, bm)
    return {"kind": "crosslap", "pieces": [upper.name, lower.name], "explode": {upper.name: [0, 0, 0.35], lower.name: [0, 0, 0]}}


def dovetail_plan(lo, hi, end, flare, reach):
    """The dovetail in plan and the box that clears the beam's old end, for a beam along x or y."""
    along_x = (hi.x - lo.x) >= (hi.y - lo.y)
    sign = 1 if end == "max" else -1
    if along_x:
        tip = hi.x if end == "max" else lo.x
        root = tip - sign * reach
        plan = [(root, lo.y), (root, hi.y), (tip, hi.y + flare), (tip, lo.y - flare)]
        clear = [(root, lo.y - 1), (root, hi.y + 1), (tip + sign, hi.y + 1), (tip + sign, lo.y - 1)]
    else:
        tip = hi.y if end == "max" else lo.y
        root = tip - sign * reach
        plan = [(hi.x, root), (lo.x, root), (lo.x - flare, tip), (hi.x + flare, tip)]
        clear = [(hi.x + 1, root), (lo.x - 1, root), (lo.x - 1, tip + sign), (hi.x + 1, tip + sign)]
    if sign < 0:
        plan, clear = plan[::-1], clear[::-1]
    return plan, clear


def dovetail(scene, beam_name, into, end="max", flare=0.06, reach=0.30):
    beam, col = derived(scene, beam_name), derived(scene, into)
    lo, hi = box_of(beam)
    plan, clear = dovetail_plan(lo, hi, end, flare, reach)
    bm, uv = new_bm()
    add_plan_prism(bm, uv, clear, lo.z - 0.01, hi.z + 0.01)
    cut(beam, bm)
    bm, uv = new_bm()
    add_plan_prism(bm, uv, plan, lo.z, hi.z)
    join_into(beam, bm)
    bm, uv = new_bm()
    add_plan_prism(bm, uv, plan, lo.z - PLAY, box_of(col)[1].z + 0.01)
    cut(col, bm)
    return {"kind": "dovetail", "pieces": [beam.name, col.name], "explode": {beam.name: [0, 0, (hi.z - lo.z) + 0.25]}}


def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("out_dir")
    parser.add_argument("--tenon", nargs=2, action="append", default=[], metavar=("COLUMN", "INTO"))
    parser.add_argument("--crosslap", nargs=2, action="append", default=[], metavar=("A", "B"))
    parser.add_argument("--dovetail", nargs=3, action="append", default=[], metavar=("BEAM", "INTO", "END"))
    parser.add_argument("--stem", default=None)
    args = parser.parse_args(argv)
    scene = bpy.context.scene
    made = [tenon(scene, c, i) for c, i in args.tenon]
    made += [crosslap(scene, a, b) for a, b in args.crosslap]
    made += [dovetail(scene, b, i, e) for b, i, e in args.dovetail]
    stem = args.stem or os.path.splitext(os.path.basename(bpy.data.filepath))[0]
    os.makedirs(args.out_dir, exist_ok=True)
    target = os.path.join(os.path.abspath(args.out_dir), f"{stem}-joints.blend")
    bpy.ops.wm.save_as_mainfile(filepath=target, copy=True)
    with open(os.path.join(args.out_dir, "joints.json"), "w") as f:
        json.dump({"model": target, "joints": made}, f, indent=1)
    print("JOINTS", len(made), target)


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1:])
