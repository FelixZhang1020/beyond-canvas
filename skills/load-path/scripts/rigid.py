"""Geometry for the settle test, from the physics check's proven simulation: volume centroids,
recentring with a small easing so exact fits survive the solver's contact skin, shrunk convex
hulls, grouping of pieces drawn through one another, and the holders that make a group one
body. Nothing runs on import; nothing here saves the model.
"""
from collections import defaultdict

import bmesh
import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

TIMBER, CLAY, G = 500.0, 1900.0, 9.81
SHRINK = 0.002                   # hulls are pulled in 2 mm so touching is not counted as passing through
CLEAR_SIDE, CLEAR_END = 0.003, 0.0015   # moving pieces are eased this much per side on the copy
MARGIN = 0.001                   # the solver's contact skin
FRICTION = 0.4                   # timber on timber and on stone
MASS_POWER = 0.3                 # masses are compressed (heavier stays heavier) so the solver stays stable


def tris_world(obj):
    """Triangulated world-space copy; a curve (a bevelled ridge) is taken as its evaluated tube."""
    bm = bmesh.new()
    if obj.type == "MESH":
        bm.from_mesh(obj.data)
    else:
        ev = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
        bm.from_mesh(ev.to_mesh())
        ev.to_mesh_clear()
    bm.transform(obj.matrix_world)
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    return bm


def centre_and_volume(obj):
    """Volume centroid (world) and volume, from signed tetrahedra; vertex mean for open meshes.
    The tetrahedra are taken about the vertex mean, not the world origin: a 6 cm block ear 15 m
    from the origin came out 23 cm off in single precision, and the easing then slid it off its
    block."""
    bm = tris_world(obj)
    pts = [v.co.copy() for v in bm.verts]
    mean = sum(pts, Vector()) / len(pts)
    vol, acc = 0.0, Vector()
    for f in bm.faces:
        a, b, c = (v.co - mean for v in f.verts)
        v6 = a.dot(b.cross(c))
        vol += v6
        acc += (a + b + c) * v6
    bm.free()
    if abs(vol) < 1e-9:
        return mean, 0.0
    return mean + acc / (4 * vol), abs(vol) / 6


def recentre(obj, centre, ease=True):
    """Pivot to the piece's own centre; moving pieces are also eased (CLEAR_SIDE on each side,
    CLEAR_END top and bottom) so an arm drawn exactly into a block's slot still fits."""
    if obj.data.users > 1:
        obj.data = obj.data.copy()
    local = obj.matrix_world.inverted() @ centre
    obj.data.transform(Matrix.Translation(-local))
    obj.matrix_world = obj.matrix_world @ Matrix.Translation(local)
    if ease:
        co = [v.co for v in obj.data.vertices]
        size = [max(c[i] for c in co) - min(c[i] for c in co) for i in range(3)]
        cut = (CLEAR_SIDE, CLEAR_SIDE, CLEAR_END)
        obj.data.transform(Matrix.Diagonal([max(0.5, 1 - 2 * cut[i] / max(size[i], 1e-6)) for i in range(3)] + [1]))


def hull_tree(obj):
    bm = tris_world(obj)
    hull = bmesh.new()
    for v in bm.verts:
        hull.verts.new(v.co)
    bm.free()
    bmesh.ops.convex_hull(hull, input=hull.verts[:])
    for v in [v for v in hull.verts if not v.link_faces]:
        hull.verts.remove(v)
    mid = sum((v.co for v in hull.verts), Vector()) / len(hull.verts)
    for v in hull.verts:
        d = mid - v.co
        v.co += d.normalized() * min(SHRINK, d.length * 0.5)
    hull.verts.index_update()
    hull.normal_update()
    pts = [v.co.copy() for v in hull.verts]
    tree = BVHTree.FromPolygons(pts, [[v.index for v in f.verts] for f in hull.faces])
    lo = Vector([min(p[i] for p in pts) for i in range(3)])
    hi = Vector([max(p[i] for p in pts) for i in range(3)])
    inward = 1 if hull.calc_volume(signed=True) >= 0 else -1
    planes = [(f.normal * inward, f.verts[0].co.copy()) for f in hull.faces]
    hull.free()
    return tree, lo, hi, planes, mid


def inside(point, planes):
    return all((point - on).dot(n) <= 1e-6 for n, on in planes)


def block_stem(name):
    """The block a foot, seat or ear belongs to ("... | Ludou", "... | Man gong end dou"), or None."""
    head, _, part = name.rpartition(" ")
    part = part.split(".")[0]
    return head if part in {"foot", "seat", "ear"} and head.lower().endswith("dou") else None


def groups(scene, names, roof, block_of, pairs=()):
    """Union pieces whose hulls pass through each other or sit one inside the other, pieces of
    one block, all roof names as one group, and every pair given outright (a block's ear on its
    seat, from the bearing map)."""
    parent = {n: n for n in names}

    def find(n):
        while parent[n] != n:
            parent[n] = parent[parent[n]]
            n = parent[n]
        return n

    for n in roof[1:]:
        parent[find(n)] = find(roof[0])
    for a, b in pairs:
        if a in parent and b in parent:
            parent[find(a)] = find(b)
    trees, grid = {}, defaultdict(list)
    for n in names:
        trees[n] = hull_tree(scene.objects[n])
        lo, hi = trees[n][1], trees[n][2]
        for gx in range(int(lo.x // 1), int(hi.x // 1) + 1):
            for gy in range(int(lo.y // 1), int(hi.y // 1) + 1):
                grid[gx, gy].append(n)
    seen = set()
    for cell in grid.values():
        for i, a in enumerate(cell):
            for b in cell[i + 1:]:
                if (a, b) in seen or find(a) == find(b):
                    continue
                seen.add((a, b))
                (ta, la, ha, pa, ma), (tb, lb, hb, pb, mb) = trees[a], trees[b]
                if not all(la[k] <= hb[k] + 0.01 and lb[k] <= ha[k] + 0.01 for k in range(3)):
                    continue
                same_block = block_of(a) is not None and block_of(a) == block_of(b)
                if same_block or ta.overlap(tb) or inside(ma, pb) or inside(mb, pa):
                    parent[find(a)] = find(b)
    out = defaultdict(list)
    for n in names:
        out[find(n)].append(n)
    return list(out.values())


def is_box(obj, volume):
    d = obj.dimensions
    return len(obj.data.vertices) == 8 and abs(d.x * d.y * d.z - volume) < 0.02 * max(volume, 1e-9)


def solver_mass(kg):
    """Keeps order but narrows the range: 10 kg -> 50, 1 t -> 200, 1000 t -> 1600."""
    return 25.0 * max(kg, 1.0) ** MASS_POWER


def holder_for(scene, name, centre):
    me = bpy.data.meshes.new(name)
    me.from_pydata([(0, 0, 0), (0.001, 0, 0), (0, 0.001, 0)], [], [(0, 1, 2)])
    obj = bpy.data.objects.new(name, me)
    scene.collection.objects.link(obj)
    obj.matrix_world = Matrix.Translation(centre)
    return obj


def attach(child, holder):
    world = child.matrix_world.copy()
    child.parent = holder
    child.matrix_parent_inverse = holder.matrix_world.inverted()
    child.matrix_world = world
