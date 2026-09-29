"""Which part each visible piece plays, read from the names of the collections it sits in.

Roles: ground never moves; wall is held in place and carries nothing; timber pieces each stand on
their own; rafters move with the roof; covering is weight only. A model whose collections are
named in plain words is sorted by keyword, so the Foguang hall's numbered collections and a
child's toy with a single collection go through the same list. Cameras, lights, empties, bare
curves and the hall's weathering fissures play no part.
"""
import bmesh
from mathutils import Vector

ROLE_KEYWORDS = (
    ("ground", ("platform", "stone", "ground", "courtyard", "terrace", "floor", "plinth", "slab")),
    ("wall", ("wall", "door", "window", "infill", "plaster")),
    ("rafter", ("rafter", "eave board", "eaves")),
    ("timber", ("column", "pillar", "bracket", "dougong", "beam", "purlin", "tier", "ceiling",
                "frame", "timber", "lintel", "post", "fang", "gong", "dou", "ang", "truss")),
    ("covering", ("tile", "roof", "ridge", "covering", "bedding", "clay", "thatch")),
)
IGNORED_NAMES = ("fissure", "crack", "camera", "light", "empty")


def role_of(obj, default="timber"):
    """The role, or None for what plays no part."""
    if obj.type not in {"MESH", "CURVE"} or any(w in obj.name.lower() for w in IGNORED_NAMES):
        return None
    if obj.type == "MESH" and not len(obj.data.vertices):
        return None
    if obj.type == "CURVE" and not (obj.data.bevel_depth or obj.data.bevel_object or obj.data.extrude):
        return None
    names = " ".join(c.name.lower().replace("_", " ") for c in obj.users_collection)
    for role, words in ROLE_KEYWORDS:
        if any(w in names for w in words):
            return role
    return default


def visible_pieces(scene):
    layer = scene.view_layers[0]
    out = {}
    for obj in scene.objects:
        if obj.hide_render or not obj.visible_get(view_layer=layer):
            continue
        role = role_of(obj)
        if role:
            out[obj.name] = role
    return out


def refuse_if_stale(scene, names, tool):
    """Stop a check in one sentence when anatomy.json and the model no longer hold the same pieces.

    anatomy.json is what the model held when inventory ran, and placing a part again replaces it:
    in design run 2 the roof went from three purlin rings to two, bearing looked the
    third up by name, and the builder was handed a Blender traceback it could not read; the same
    run's columns went from 36 to 45, and a check on the old file would have left nine out without
    a word. A new piece is one inventory would count now (`visible_pieces`), so a camera or a hidden
    original is none; a piece anatomy.json names that is only hidden is still in the model. The line
    opens REFUSED so the driver repeats it last, where the agent reads; the exit is not zero because
    the check did not run."""
    named = set(names)
    gone = [n for n in names if n not in scene.objects]
    added = [n for n in visible_pieces(scene) if n not in named]

    def count(found):
        return f"{len(found)} piece" + ("s" if len(found) > 1 else "")

    said = []
    if gone:
        said.append(f"anatomy.json names {count(gone)} the model no longer has (first: {gone[0]!r})")
    if added:
        said.append(f"the model has {count(added)} anatomy.json does not name (first: {added[0]!r})")
    if said:
        print(f"REFUSED {' and '.join(said)}: it was made before the model last changed. Run model-anatomy "
              f"inventory again, then {tool}.", flush=True)
        raise SystemExit(1)


def world_bmesh(obj, depsgraph=None):
    """Triangulated copy of the piece in world space; a closed piece built inside-out is turned
    the right way round on the copy. The model itself is never touched."""
    bm = bmesh.new()
    if obj.type == "MESH":
        bm.from_mesh(obj.data)
    else:
        ev = obj.evaluated_get(depsgraph)
        bm.from_mesh(ev.to_mesh())
        ev.to_mesh_clear()
    bm.transform(obj.matrix_world)
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    bm.normal_update()
    if all(e.is_manifold for e in bm.edges) and bm.calc_volume(signed=True) < 0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
        bm.normal_update()
    bm.verts.index_update()
    bm.faces.index_update()
    return bm


def long_axis(points):
    """Centre and unit long axis of a point cloud, by power iteration on its covariance."""
    n = len(points)
    c = sum(points, Vector()) / n
    cov = [[0.0] * 3 for _ in range(3)]
    for p in points:
        d = p - c
        for i in range(3):
            for j in range(3):
                cov[i][j] += d[i] * d[j]
    v = Vector((1.0, 0.7, 0.3))
    for _ in range(60):
        v = Vector([sum(cov[i][j] * v[j] for j in range(3)) for i in range(3)])
        if v.length < 1e-12:
            return c, Vector((0, 0, 1))
        v.normalize()
    return c, v
