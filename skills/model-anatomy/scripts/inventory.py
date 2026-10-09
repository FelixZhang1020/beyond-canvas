"""What is in this model: every piece with its role, kind and size, the tags its author left on
it, the building's box, its cameras, and named places a camera can stand.
Reads the model, writes <out_dir>/anatomy.json, changes nothing.
Usage: blender -b model.blend --python-exit-code 1 --python inventory.py -- out_dir
"""
import json
import os
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pieces import long_axis, visible_pieces, world_bmesh  # noqa: E402

TAG_TYPES = (str, int, float, bool)


def kind_of(extents, axis):
    length, b, h = extents
    if min(extents) < 0.08 * sorted(extents)[1]:
        return "sheet"
    if length < 2.5 * max(b, h):
        return "block"
    return "column" if abs(axis.z) > 0.8 else "beam"


def tags_of(obj):
    """The author's own labels on a piece (assembly, component, construction phase, ...)."""
    return {k: obj[k] for k in obj.keys() if not k.startswith("_") and isinstance(obj[k], TAG_TYPES)}


def describe(obj, role, depsgraph):
    bm = world_bmesh(obj, depsgraph)
    pts = [v.co.copy() for v in bm.verts]
    volume = abs(bm.calc_volume())
    bm.free()
    centre, axis = long_axis(pts)
    side = axis.cross(Vector((0, 0, 1)))
    side = side.normalized() if side.length > 1e-6 else Vector((1, 0, 0))
    third = axis.cross(side).normalized()
    extents = [max(q.dot(d) for q in pts) - min(q.dot(d) for q in pts) for d in (axis, side, third)]
    lo = [min(q[i] for q in pts) for i in range(3)]
    hi = [max(q[i] for q in pts) for i in range(3)]
    return {
        "role": role, "collections": [c.name for c in obj.users_collection], "kind": kind_of(extents, axis),
        "centre": list(centre), "axis": list(axis), "extents": extents, "box": [lo, hi],
        "volume": volume, "zmin": lo[2], "zmax": hi[2], "tags": tags_of(obj),
    }


def box_of(pieces):
    lo = [min(p["box"][0][i] for p in pieces) for i in range(3)]
    hi = [max(p["box"][1][i] for p in pieces) for i in range(3)]
    return [lo, hi]


def landmarks(lo, hi):
    """Camera positions around the building, each with the point it looks at."""
    cx, cy = (lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2
    size = max(hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2])
    eye_z = lo[2] + 0.5 * (hi[2] - lo[2])
    look = [cx, cy, eye_z]
    return {
        "centre": {"at": look, "look": look},
        "front": {"at": [cx, lo[1] - 1.2 * size, eye_z], "look": look},
        "back": {"at": [cx, hi[1] + 1.2 * size, eye_z], "look": look},
        "left": {"at": [lo[0] - 1.2 * size, cy, eye_z], "look": look},
        "right": {"at": [hi[0] + 1.2 * size, cy, eye_z], "look": look},
        "above": {"at": [cx, cy, hi[2] + 1.5 * size], "look": [cx, cy, lo[2]]},
        "inside": {"at": [cx, cy, lo[2] + 0.4 * (hi[2] - lo[2])],
                   "look": [cx, cy + 1.0, lo[2] + 0.6 * (hi[2] - lo[2])]},
    }


def cameras(scene):
    """The cameras the model's author left in it, as positions with the point each looks at."""
    out = {}
    for obj in scene.objects:
        if obj.type != "CAMERA":
            continue
        ahead = obj.matrix_world @ Vector((0, 0, -10)) if obj.matrix_world else obj.location
        out[obj.name] = {"at": list(obj.matrix_world.translation), "look": list(ahead), "lens_mm": obj.data.lens}
    return out


def main(out_dir):
    scene = bpy.context.scene
    depsgraph = bpy.context.evaluated_depsgraph_get()
    roles = visible_pieces(scene)
    pieces = {name: describe(scene.objects[name], role, depsgraph) for name, role in roles.items()}
    building = [p for p in pieces.values() if p["role"] != "ground"] or list(pieces.values())
    ground = [p for p in pieces.values() if p["role"] == "ground"]
    lo, hi = box_of(building)
    by_role, assemblies = {}, {}
    for p in pieces.values():
        by_role[p["role"]] = by_role.get(p["role"], 0) + 1
        if "assembly" in p["tags"]:
            assemblies[p["tags"]["assembly"]] = assemblies.get(p["tags"]["assembly"], 0) + 1
    model = {"scene": scene.name, "box": [lo, hi], "size": [hi[i] - lo[i] for i in range(3)],
             "height": hi[2] - lo[2], "ground_box": box_of(ground) if ground else None, "by_role": by_role,
             "collections": sorted(c.name for c in bpy.data.collections), "assemblies": assemblies}
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "anatomy.json"), "w") as f:
        json.dump({"model": model, "pieces": pieces, "landmarks": landmarks(lo, hi), "cameras": cameras(scene)},
                  f, indent=1)
    print("ANATOMY", len(pieces), "pieces", by_role, len(assemblies), "assemblies")


main(sys.argv[sys.argv.index("--") + 1])
