"""What rests on what, measured from the model. Reads <out_dir>/anatomy.json for the roles,
writes <out_dir>/bearing.json, changes nothing.

Every downward face of a timber or rafter piece is sampled; from each sample a ray goes straight
down. A hit within TOUCH is a seat. A sample already inside another piece asks that piece's own
tree, so a neighbour's level face cannot fool the answer; a piece reached that way and reaching
below the sample is the seat, one drawn crossing at the same level is a joint and is passed.
Walls hold nothing up. Pieces with no seat at all are floating, with the nearest thing below.
Usage: blender -b model.blend --python-exit-code 1 --python bearing.py -- out_dir
"""
import heapq
import json
import math
import os
import sys
from collections import defaultdict

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pieces import refuse_if_stale, world_bmesh  # noqa: E402

TOUCH, LOOK, SEATED, LAP, NUDGE = 0.010, 0.30, 0.030, 0.002, 0.001
SETTLE = LOOK        # a near miss up to this gap still carries, for the gaps-closed reading
SPACING = 0.025
DOWN, UP = Vector((0, 0, -1)), Vector((0, 0, 1))
PHI = (math.sqrt(5) - 1) / 2


def samples(tris, spacing):
    for verts, normal, area in tris:
        if normal.z >= -0.2 or area <= 0:
            continue
        k = max(1, int(area / spacing ** 2 + 0.5))
        for j in range(k):
            r1, r2 = (j + 0.5) / k, (j * PHI) % 1.0
            if r1 + r2 > 1:
                r1, r2 = 1 - r1, 1 - r2
            yield verts[0] + (verts[1] - verts[0]) * r1 + (verts[2] - verts[0]) * r2, area / k


class Solid:
    """Every piece that can carry weight, as one world tree plus one tree per piece."""

    def __init__(self, scene, roles):
        depsgraph = bpy.context.evaluated_depsgraph_get()
        self.roles, self.geo, self.own, self.grid = roles, {}, {}, defaultdict(list)
        verts, tris, self.owner = [], [], []
        for name, role in roles.items():
            bm = world_bmesh(scene.objects[name], depsgraph)
            pts = [v.co.copy() for v in bm.verts]
            faces = [[v.index for v in f.verts] for f in bm.faces]
            self.geo[name] = {"tris": [(tuple(v.co.copy() for v in f.verts), f.normal.copy(), f.calc_area())
                                       for f in bm.faces], "pts": pts}
            bm.free()
            if role == "covering":
                continue
            self.own[name] = BVHTree.FromPolygons(pts, faces)
            self.index_box(name, pts)
            base = len(verts)
            verts.extend(pts)
            tris.extend([base + i for i in f] for f in faces)
            self.owner.extend([name] * len(faces))
        self.world = BVHTree.FromPolygons(verts, tris)

    def index_box(self, name, pts):
        lo = Vector([min(q[i] for q in pts) for i in range(3)])
        hi = Vector([max(q[i] for q in pts) for i in range(3)])
        self.geo[name]["box"] = (lo, hi)
        for gx in range(int(math.floor(lo.x)), int(math.floor(hi.x)) + 1):
            for gy in range(int(math.floor(lo.y)), int(math.floor(hi.y)) + 1):
                self.grid[gx, gy].append(name)

    def containing(self, p, me):
        """[(piece, depth below its top, reach below p)] for every other piece p is inside of."""
        out = []
        for name in self.grid.get((math.floor(p.x), math.floor(p.y)), ()):
            lo, hi = self.geo[name]["box"]
            if name == me or not all(lo[i] - 1e-4 <= p[i] <= hi[i] + 1e-4 for i in range(3)):
                continue
            q = p + UP * NUDGE
            up, down = self.own[name].ray_cast(q, UP, 50.0), self.own[name].ray_cast(q, DOWN, 50.0)
            if up[0] is None or up[1].z <= 0 or down[0] is None or down[1].z >= 0:
                continue
            out.append((name, up[0].z - p.z, down[3] - NUDGE))
        return out

    def top_at(self, p, z, passed):
        for name in self.grid.get((math.floor(p.x), math.floor(p.y)), ()):
            lo, hi = self.geo[name]["box"]
            if name in passed or self.roles[name] == "wall" or not (lo.x <= p.x <= hi.x and lo.y <= p.y <= hi.y):
                continue
            if lo.z - 1e-3 <= z <= hi.z + 1e-3:
                hit = self.own[name].ray_cast(Vector((p.x, p.y, z + 1e-4)), DOWN, 3e-4)
                if hit[0] is not None and hit[1].z > 0:
                    return name
        return None

    def first_below(self, p, me, overlaps):
        """(seat, gap): what p rests on within LOOK, or (None, None). Negative gap: sunk in."""
        holders, passed = [], {me}
        for name, depth, below in self.containing(p, me):
            if depth > SEATED:
                overlaps[name] = max(overlaps.get(name, 0.0), depth)
            if self.roles[name] != "wall" and below > LAP:
                holders.append((depth, name))
            else:
                passed.add(name)
        if holders:
            depth, name = max(holders)
            return name, -depth
        start, travelled = p + UP * 1e-4, 0.0
        for _ in range(40):
            loc, nrm, idx, dist = self.world.ray_cast(start, DOWN, LOOK - travelled)
            if loc is None:
                return None, None
            owner = self.owner[idx]
            if owner not in passed and nrm.z > 0 and self.roles[owner] != "wall":
                return owner, p.z - loc.z
            level = self.top_at(p, loc.z, passed)
            if level:
                return level, p.z - loc.z
            start, travelled = loc + DOWN * 1e-5, travelled + dist
        return None, None


def seats_of(solid, name):
    """Contacts grouped by the piece they land on, overlaps, and the near misses within SETTLE."""
    g = solid.geo[name]
    per, overlaps, near = defaultdict(lambda: [0.0, Vector(), 0.0]), {}, {}
    b_area = sum(t[2] for t in g["tris"] if t[1].z < -0.2)
    for p, a in samples(g["tris"], min(SPACING, math.sqrt(max(b_area, 1e-6) / 40))):
        owner, gap = solid.first_below(p, name, overlaps)
        if owner is None:
            continue
        if gap <= TOUCH:
            c = per[owner]
            c[0] += a
            c[1] += p * a
            c[2] = max(c[2], -gap)
        elif gap <= SETTLE:
            near[owner] = min(near.get(owner, gap), gap)
    seats = [{"on": o, "area": c[0], "at": list(c[1] / c[0]), "sunk": c[2]} for o, c in per.items()]
    return seats, overlaps, [{"on": o, "gap": gp} for o, gp in sorted(near.items(), key=lambda kv: kv[1])]


def order_pieces(names, rests_on, zmax):
    """Every piece before what it rests on: Kahn's order, highest first; a loop is cut at the
    piece the fewest unhandled pieces rest on."""
    waiting = defaultdict(int)
    for n in names:
        for s in rests_on[n]:
            waiting[s] += 1
    ready = [(-zmax[n], n) for n in names if waiting[n] == 0]
    heapq.heapify(ready)
    done, order = set(), []
    while len(order) < len(names):
        if ready:
            _, n = heapq.heappop(ready)
            if n in done:
                continue
        else:
            n = min((k for k in names if k not in done), key=lambda k: (waiting[k], -zmax[k]))
        done.add(n)
        order.append(n)
        for s in rests_on[n]:
            waiting[s] -= 1
            if waiting[s] == 0 and s not in done:
                heapq.heappush(ready, (-zmax[s], s))
    return order


def stage_pieces(names, bottom, carried_by, ground, covering):
    """Bottom-up: a piece's stage is one more than the highest stage of what carries it. Pieces
    are taken lowest bottom first, so a loop in the carrying graph breaks at the lower piece."""
    stage = {g: 0 for g in ground}
    for n in sorted(names, key=lambda k: bottom[k]):
        below = [stage[s] for s in carried_by[n] if s in stage]
        stage[n] = 1 + max(below, default=0)
    last = max((s for s in stage.values()), default=0) + 1
    for c in covering:
        stage[c] = last
    stages = defaultdict(list)
    for n, s in stage.items():
        if s > 0:
            stages[s].append(n)
    return [sorted(stages[k]) for k in sorted(stages)]


def main(out_dir):
    anatomy = json.load(open(os.path.join(out_dir, "anatomy.json")))
    roles = {n: p["role"] for n, p in anatomy["pieces"].items()}
    refuse_if_stale(bpy.context.scene, roles, "model-anatomy bearing")
    solid = Solid(bpy.context.scene, roles)
    rests_on, floating, near, overlaps, names = {}, {}, {}, {}, []
    for name, role in roles.items():
        if role not in {"timber", "rafter"}:
            continue
        seats, laps, misses = seats_of(solid, name)
        names.append(name)
        rests_on[name] = seats
        near[name] = misses
        if laps:
            overlaps[name] = laps
        if not seats:
            floating[name] = misses[0] if misses else None
    # What carries a piece: a seat, or a piece it is drawn into whose body extends below the
    # piece's own bottom (a rafter sunk into its purlin, a lintel into its column), never one it
    # merely passes through above its bottom (an ang tail in its bearing); plus the near misses,
    # the gaps-closed reading the physics check uses.
    bottom = {n: p["zmin"] for n, p in anatomy["pieces"].items()}

    def carries(c, n):
        return c["sunk"] <= SEATED or bottom.get(c["on"], 1e9) < bottom[n] - 0.05

    carried_by = {n: {c["on"] for c in rests_on[n] if carries(c, n)} | {m["on"] for m in near[n]} for n in names}
    carried_by = {n: {s for s in ss if s in roles and roles[s] != "ground"} for n, ss in carried_by.items()}
    ground = sorted(n for n, r in roles.items() if r == "ground")
    covering = sorted(n for n, r in roles.items() if r == "covering")
    zmax = {n: anatomy["pieces"][n]["zmax"] for n in names}
    order = order_pieces(names, carried_by, zmax)
    result = {"rests_on": rests_on, "floating": floating, "near": near, "overlaps": overlaps, "order": order,
              "carried_by": {n: sorted(s) for n, s in carried_by.items()},
              "stages": stage_pieces(names, bottom, carried_by, ground, covering), "ground": ground}
    with open(os.path.join(out_dir, "bearing.json"), "w") as f:
        json.dump(result, f, indent=1)
    print("BEARING", len(names), "pieces", len(floating), "floating", len(result["stages"]), "stages")


main(sys.argv[sys.argv.index("--") + 1])
