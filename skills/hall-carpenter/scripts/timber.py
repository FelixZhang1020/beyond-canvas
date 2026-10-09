"""What every part of the hall is made with: the hall file, one collection per part, boxes and
round columns, and the running record of what was placed where.

A part is placed where it is told, never where it would fit: no tool here measures the hall to
make a piece land, so a height given right seats the piece and a height given wrong leaves it
hanging or sunk for the checks to find. Timber that simply sits on timber is drawn touching it
(`rest`); only a joint a carpenter cuts to lock (a tenon, a dowelled block, a halved crossing) is
drawn LET_IN (`seated`), because the settle test holds pieces drawn through one another as one
body, and a hall let in everywhere is one lump that no gravity test can fail. Re-placing a part replaces its collection, so a repair is the
same tool with better numbers.
"""
import json
import math
import os

import bpy
from mathutils import Matrix, Vector

LET_IN = 0.02
RECORD = "hall.json"
FACES = [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)]
# What each part stands on or reads from the record when it is placed, in the order the hall is built.
# Placing one again moves nothing already standing on it. Walls stand on the platform between the
# columns and carry nothing; a frame's lowest beams sit on the bracket top; the purlins' eave ring
# lies on the outriggers and the rings above it on the frames; the roof reads the rings and the rafters.
STANDS_ON = {"platform": (), "columns": ("platform",), "ties": ("columns",), "walls": ("platform", "columns"),
             "brackets": ("columns", "ties"), "frames": ("columns", "brackets"), "purlins": ("brackets", "frames"),
             "rafters": ("purlins",), "roof": ("purlins", "rafters")}
ONE = ("platform", "roof")      # the parts named in the singular


class Refused(SystemExit):
    """A part that cannot be placed as told; the sentence is what the agent reads."""

    def __init__(self, sentence):
        print("REFUSED", sentence)
        super().__init__(1)


def open_hall(path):
    if os.path.isfile(path):
        bpy.ops.wm.open_mainfile(filepath=path)
    else:
        bpy.ops.wm.read_factory_settings(use_empty=True)


def save_hall(path):
    bpy.ops.wm.save_as_mainfile(filepath=path, check_existing=False)


def fresh(name):
    """The part's collection, emptied if it was placed before."""
    old = bpy.data.collections.get(name)
    if old is not None:
        for obj in list(old.objects):
            mesh = obj.data
            bpy.data.objects.remove(obj)
            if mesh is not None and mesh.users == 0:
                bpy.data.meshes.remove(mesh)
        bpy.data.collections.remove(old)
    made = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(made)
    return made


def _solid(coll, name, verts, faces, world=None):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    coll.objects.link(obj)
    if world is not None:
        obj.matrix_world = world
    return obj


def _corners(sx, sy, sz):
    hx, hy, hz = sx / 2, sy / 2, sz / 2
    return [(i * hx, j * hy, k * hz) for k in (-1, 1) for j in (-1, 1) for i in (-1, 1)]


def box(coll, name, centre, size):
    return _solid(coll, name, _corners(*size), FACES, Matrix.Translation(Vector(centre)))


def seated(coll, name, x, y, level, size, let_in=LET_IN):
    """A box whose underside is meant to be at `level`: drawn let_in lower, its top where told."""
    sx, sy, sz = size
    return box(coll, name, (x, y, level + (sz - let_in) / 2), (sx, sy, sz + let_in))


def rest(coll, name, x, y, level, size):
    """A box that simply sits at `level`, touching what is under it."""
    return seated(coll, name, x, y, level, size, let_in=0.0)


def stick(coll, name, start, end, width, depth):
    """A straight member from start to end, `width` across and `depth` up from its underside line."""
    a, b = Vector(start), Vector(end)
    along = b - a
    length = along.length
    if length < 1e-6:
        raise Refused(f"{name} has no length")
    ux = along / length
    uy = Vector((0, 0, 1)).cross(ux)
    uy = uy.normalized() if uy.length > 1e-6 else Vector((0, 1, 0))
    uz = ux.cross(uy)
    world = Matrix(((ux.x, uy.x, uz.x, 0), (ux.y, uy.y, uz.y, 0), (ux.z, uy.z, uz.z, 0), (0, 0, 0, 1)))
    world.translation = (a + b) / 2 + uz * (depth / 2)
    return _solid(coll, name, _corners(length, width, depth), FACES, world)


def round_post(coll, name, x, y, foot, top, diameter, sides=16):
    r = diameter / 2
    ring = [(r * math.cos(2 * math.pi * i / sides), r * math.sin(2 * math.pi * i / sides)) for i in range(sides)]
    verts = [(px, py, 0.0) for px, py in ring] + [(px, py, top - foot) for px, py in ring]
    faces = [tuple(reversed(range(sides))), tuple(range(sides, 2 * sides))]
    faces += [(i, (i + 1) % sides, sides + (i + 1) % sides, sides + i) for i in range(sides)]
    return _solid(coll, name, verts, faces, Matrix.Translation(Vector((x, y, foot))))


def slab(coll, name, lower, upper, thickness):
    """A roof sheet over four corner points (two low, two high), `thickness` up from them."""
    base = [Vector(p) for p in (*lower, *upper)]
    verts = [tuple(p) for p in base] + [tuple(p + Vector((0, 0, thickness))) for p in base]
    return _solid(coll, name, verts, [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)])


def read_record(out_dir):
    path = os.path.join(out_dir, RECORD)
    return json.load(open(path)) if os.path.isfile(path) else {"parts": {}}


def need(record, part, why):
    got = record["parts"].get(part)
    if got is None:
        raise Refused(f"place the {part} first: {why}")
    return got


def supports(part, parts):
    """The placed parts this one stands on; bracket sets only on column heads stand on no tie beam."""
    on = ("columns",) if part == "brackets" and parts[part]["told"].get("inter") == "no" else STANDS_ON[part]
    return [s for s in on if s in parts]


def stale_parts(parts):
    """{part: the part placed again under it} for each part standing on an older placing of what carries it,
    directly or through a part that does; in the order the hall is built."""
    out = {}
    for part in STANDS_ON:
        if part not in parts:
            continue
        seen = parts[part].get("on", {})
        for s in supports(part, parts):
            if s in out or seen.get(s, parts[s].get("version")) != parts[s].get("version"):
                out[part] = out.get(s, s)
                break
    return out


def write_record(out_dir, record, part, told, made):
    """What this part was told and what came of it; parts placed later read it instead of the model.
    A placing that changes the part gives it a new version, and every part keeps the versions of what it
    was placed on, so the record knows what stands on an old part (`stale`). Design run 7
    lengthened the rafters twice and never laid the roof again, and the covering stayed where the first
    rafters had put it. The same numbers again change nothing and keep the version."""
    parts = record["parts"]
    entry, old = json.loads(json.dumps({"told": told, **made})), parts.get(part) or {}
    if "version" in old and {k: v for k, v in old.items() if k not in ("version", "on")} == entry:
        entry["version"] = old["version"]
    else:
        record["placings"] = entry["version"] = record.get("placings", 0) + 1
    parts[part] = entry
    entry["on"] = {s: parts[s].get("version") for s in supports(part, parts)}
    for other, placing in parts.items():      # placed before this part was ever placed: it was placed for this one
        if not old and part in supports(other, parts) and part not in placing.get("on", {}):
            placing.setdefault("on", {})[part] = entry["version"]
    record["stale"] = stale_parts(parts)
    with open(os.path.join(out_dir, RECORD), "w") as f:
        json.dump(record, f, indent=1)


def stale_note(record):
    """' | ' and the sentence that says what stands on an old part, in the order to place it again; ''
    when nothing does. It rides on the PLACED line, which the driver repeats last for the builder."""
    stale = record.get("stale") or {}
    if not stale:
        return ""
    under = {}
    for part, below in stale.items():
        under.setdefault(below, []).append(part)
    said = []
    for below, ps in under.items():
        names = ps[0] if len(ps) == 1 else ", ".join(ps[:-1]) + " and " + ps[-1]
        said.append(f"the {names} {'stands' if ps == [ps[0]] and ps[0] in ONE else 'stand'} on the old {below}")
    one = len(stale) == 1 and next(iter(stale)) in ONE
    order = ", in that order," if len(stale) > 1 else ""
    return f" | {' and '.join(said)}: place {'it' if one else 'them'} again{order} before checking"


def numbers(text, count=None, what="numbers"):
    """Numbers given as "a,b,c", as separate words, or as a list: models write all three."""
    if isinstance(text, (list, tuple)):
        text = ",".join(str(v) for v in text)
    try:
        out = [float(v) for v in str(text).replace(";", ",").split(",") if v.strip()]
    except ValueError:
        raise Refused(f"{what} must be numbers separated by commas, got {text!r}") from None
    if count is not None and len(out) != count:
        raise Refused(f"{what} takes {count} numbers, got {len(out)} in {text!r}")
    return out


def placed(part, pieces, record, **levels):
    shown = " ".join(f"{k.replace('_', ' ')} {v:.3f}" if isinstance(v, float) else f"{k.replace('_', ' ')} {v}"
                     for k, v in levels.items())
    print(f"PLACED {part}: {pieces} pieces | {shown}{stale_note(record)}")
