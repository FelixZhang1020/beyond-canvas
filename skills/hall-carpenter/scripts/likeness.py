"""Is the hall that was built the temple that was measured? Casts the hall's three shadows in the
same frame as the temple's and says how much of each outline the two share, counts the columns
standing where the temple's stand, compares the sizes, measures the hall's frame with the survey's
own ruler (tie beams at the column heads, roof rings, ridge, rafters, a bracket set on every
column) so an outline with columns inside is not a timber frame, finds timber standing out through
the roof or past its edge and a roof left open, and joins the temple's picture and the hall's, one
above the other, for a pair of eyes.
Reads the hall, changes nothing.
Usage: blender -b hall.blend --python-exit-code 1 --python likeness.py -- out_dir --survey survey.json
"""
import argparse
import json
import os
import sys

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from shadow import building, cast, lit_view, one_above_the_other, overlap, show_only  # noqa: E402
import measures  # noqa: E402
from survey import BRACKET_PIECES, columns_of, frame_members  # noqa: E402

sys.path.insert(0, os.path.join(HERE, "..", "..", "model-anatomy", "scripts"))
from mathutils import Vector  # noqa: E402
from mathutils.bvhtree import BVHTree  # noqa: E402
from pieces import visible_pieces, world_bmesh  # noqa: E402
from set_scene import world_box  # noqa: E402

ENOUGH, NEAR = 0.90, 0.15
GAP, OPEN = 0.05, 0.05       # a pocket deeper than 5 cm is open air; an opening under 0.05 m2 is a rounding
PAINT = {"timber": (0.36, 0.17, 0.09), "rafter": (0.36, 0.17, 0.09), "wall": (0.80, 0.74, 0.62),
         "covering": (0.20, 0.21, 0.22), "ground": (0.55, 0.54, 0.52)}


def paint_by_role(scene, roles):
    mats = {}
    for name, role in roles.items():
        obj = scene.objects[name]
        if obj.type != "MESH" or obj.data.materials:
            continue
        if role not in mats:
            mats[role] = bpy.data.materials.new(f"LIKENESS {role}")
            mats[role].diffuse_color = (*PAINT[role], 1.0)
            mats[role].use_nodes = True
            mats[role].node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*PAINT[role], 1.0)
        obj.data.materials.append(mats[role])


def columns_matched(scene, roles, places):
    stood = []
    for name, role in roles.items():
        if role == "timber" and name.lower().startswith("column"):
            lo, hi = world_box(scene.objects[name])
            stood.append(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2))
    hit = sum(1 for x, y in places if any(abs(x - sx) <= NEAR and abs(y - sy) <= NEAR for sx, sy in stood))
    return {"wanted": len(places), "matched": hit, "built": len(stood)}


def frame_short(temple, hall):
    """What the hall's frame lacks of the temple's. A sheet surveyed before the frame was measured
    has no tie spans or bracket sets; those two are then not compared."""
    short, ties, sets = [], temple.get("tie_spans"), temple.get("bracket_sets")
    if ties and hall["tie_spans"]["tied"] < ties["tied"]:
        short.append(f"{hall['tie_spans']['tied']} of the {hall['tie_spans']['spans']} spans between neighbouring "
                     f"columns have tie beams at the column heads; the temple ties {ties['tied']}")
    if len(hall["roof_rings"]) != len(temple["roof_rings"]):
        short.append(f"{len(hall['roof_rings'])} roof rings (purlin lines) where the temple has {len(temple['roof_rings'])}")
    if temple.get("ridge") and not hall["ridge"]:
        short.append(f"no ridge purlin; the temple's is at {temple['ridge']['underside']} m")
    if temple.get("rafters") and not hall["rafters"]:
        short.append("no rafters running front to back; the temple has them")
    bare = hall["bracket_sets"]["columns"] - hall["bracket_sets"]["with_a_set"]
    if sets and hall["bracket_sets"]["with_a_set"] < sets["with_a_set"] and bare:
        short.append(f"{bare} of {hall['bracket_sets']['columns']} columns have no bracket sets on their heads "
                     f"(fewer than {BRACKET_PIECES} timber pieces there)")
    return short


UP, DOWN = Vector((0, 0, 1)), Vector((0, 0, -1))


def sheets(scene, roles):
    """The covering sheets' faces in world space, and the sheet each face belongs to. Only the carpenter's
    sheets: a tiled roof is all small overlapping pieces, and the temple has no sheet."""
    verts, faces, owner = [], [], []
    depsgraph = bpy.context.evaluated_depsgraph_get()
    for name, role in roles.items():
        if role == "covering" and "sheet" in name.lower():
            bm = world_bmesh(scene.objects[name], depsgraph)
            base = len(verts)
            verts += [v.co.copy() for v in bm.verts]
            faces += [[base + v.index for v in f.verts] for f in bm.faces]
            owner += [name] * len(bm.faces)
            bm.free()
    return verts, faces, owner


def covering(scene, roles):
    """The covering sheets as one surface a ray can hit, and how far they reach from the middle along the
    hall and across it; (None, None) when nothing covers the hall."""
    verts, faces, _ = sheets(scene, roles)
    if not faces:
        return None, None
    return BVHTree.FromPolygons(verts, faces), [max(abs(v[i]) for v in verts) for i in (0, 1)]


def timber_tops(scene, roles):
    """Each timber piece's name, its height and its highest points: the real points of the piece, not its
    box. Rafters lie in the covering by design and are not timber here."""
    for name, role in roles.items():
        obj = scene.objects[name]
        if role != "timber" or obj.type != "MESH":
            continue
        points = [obj.matrix_world @ v.co for v in obj.data.vertices]
        height = max(p.z for p in points)
        yield name, height, [p for p in points if p.z > height - 1e-3]


def through_the_roof(scene, roles):
    """Timber whose top is above the covering it should be under. The second live run left two king
    posts standing out of the roof; the shadows barely changed and the eyes wrote "nothing protruding"."""
    skin, _ = covering(scene, roles)
    if skin is None:
        return []
    out = []
    for name, _, tops in timber_tops(scene, roles):
        for top in tops:
            below = skin.ray_cast(top, DOWN, 50.0)
            if below[0] is not None and below[3] > 0.05 and skin.ray_cast(top + UP * 1e-3, UP, 50.0)[0] is None:
                out.append(name)
                break
    return out


def beyond_the_eaves(scene, roles, above):
    """Timber up among the bracket sets and the roof frame that stands past the edge of the roof, in the open
    air: a top point with no covering over it or under it, further from the middle than the covering reaches.
    Design run 4 was adopted with its bracket arms and outriggers out past the eaves, and the eyes passed it.
    The reach matters: measured against every tile of the Foguang hall, rays alone found 30 pieces under the
    gaps between clay tiles, every one inside the covering's reach. What stands no higher than `above`, the
    column tops, is the columns', ties' and walls' business, not the eaves'. Returns the pieces, and how far
    they and the covering reach from the middle along the hall and across it, for the builder's numbers."""
    skin, edge = covering(scene, roles)
    found = {"pieces": [], "reach": [0.0, 0.0], "edge": [round(e, 2) for e in edge] if edge else None}
    if skin is None:
        return found
    for name, height, tops in timber_tops(scene, roles):
        if height <= above + 1e-3:
            continue
        out = [p for p in tops if (abs(p.x) > edge[0] + 0.01 or abs(p.y) > edge[1] + 0.01)
               and skin.ray_cast(p, DOWN, 50.0)[0] is None and skin.ray_cast(p + UP * 1e-3, UP, 50.0)[0] is None]
        if out:
            found["pieces"].append(name)
            found["reach"] = [round(max(found["reach"][i], *(abs(p[i]) for p in out)), 2) for i in (0, 1)]
    return found


def stacked(skin, owner, x, y, high):
    """The covering met on the way down through (x, y), as solid spans (bottom, top, sheet), highest first."""
    hits, origin = {}, Vector((x, y, high))
    for _ in range(64):
        hit = skin.ray_cast(origin, DOWN, 1000.0)
        if hit[0] is None:
            break
        lo, hi = hits.get(owner[hit[2]], (hit[0].z, hit[0].z))
        hits[owner[hit[2]]] = (min(lo, hit[0].z), max(hi, hit[0].z))
        origin = hit[0] + DOWN * 1e-4
    spans = []
    for name, (lo, hi) in sorted(hits.items(), key=lambda item: -item[1][1]):
        if spans and hi >= spans[-1][0] - 1e-3:
            spans[-1] = (min(spans[-1][0], lo), spans[-1][1], spans[-1][2])
        else:
            spans.append((lo, hi, name))
    return spans


def open_roof(scene, roles, step=0.1):
    """Where the covering is open, looked at straight down over its own outline: places no sheet covers, and
    pockets where one sheet stands over another with open air between. Design run 6 was adopted with its end
    sheets stretched flat past the hips, standing up to 1.01 m over the long slopes; from the front corner the
    gaps under them were dark wedges in the roof, and the eyes passed it. None when the covering is closed."""
    verts, faces, owner = sheets(scene, roles)
    if not faces:
        return None
    skin, high = BVHTree.FromPolygons(verts, faces), max(v.z for v in verts) + 1.0
    ex, ey = (max(abs(v[i]) for v in verts) for i in (0, 1))
    holes, pockets = [], []
    for i in range(int(2 * ex / step)):
        for j in range(int(2 * ey / step)):
            x, y = -ex + (i + 0.5) * step + 1.3e-3, -ey + (j + 0.5) * step + 1.7e-3      # off every shared edge
            spans = stacked(skin, owner, x, y, high)
            if not spans:
                holes.append((x, y))
            elif len(spans) > 1 and spans[0][0] - spans[1][1] > GAP:
                pockets.append((spans[0][0] - spans[1][1], x, y, f"{spans[0][2]} over {spans[1][2]}"))
    if (len(holes) + len(pockets)) * step * step < OPEN:
        return None
    deep, x, y, over = max(pockets) if pockets else (0.0, *holes[0], "")
    sides = over.replace(" over ", " ").split()
    return {"holes_m2": round(len(holes) * step * step, 2), "pockets_m2": round(len(pockets) * step * step, 2),
            "deepest": round(deep, 2), "at": [round(x, 2), round(y, 2)], "over": over,
            "at_hips": bool({"left", "right"} & set(sides) and {"front", "back"} & set(sides))}


def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("out_dir")
    parser.add_argument("--survey", required=True)
    args = parser.parse_args(argv)
    survey = json.load(open(args.survey))
    scene = bpy.context.scene
    roles = visible_pieces(scene)
    names, lo, hi = building(scene)
    masks = os.path.join(args.out_dir, "masks")
    show_only(scene, names)
    mine = cast(scene, survey["frame"], masks, "hall")
    shared = {view: round(overlap(path, os.path.join(masks, f"temple-{view}.png")), 3) for view, path in mine.items()}
    columns = columns_matched(scene, roles, survey["column_places"])
    built = [round(hi[i] - lo[i], 2) for i in range(3)]
    short = [f"the {view} shadow shares {share:.0%} with the temple's, under {ENOUGH:.0%}"
             for view, share in shared.items() if share < ENOUGH]
    if columns["matched"] < columns["wanted"] or columns["built"] != columns["wanted"]:
        short.append(f"{columns['matched']} of the temple's {columns['wanted']} columns have a column standing "
                     f"in their place, and {columns['built']} columns were built")
    members = frame_members(scene, roles)
    frame_missing = frame_short(survey, members)
    short += frame_missing
    poking = through_the_roof(scene, roles)
    if poking:
        short.append(measures.through_the_roof_sentence(poking))
    outside = beyond_the_eaves(scene, roles, columns_of(scene, roles)["top"] or 0.0)
    if outside["pieces"]:
        short.append(measures.beyond_the_eaves_sentence(outside))
    opened = open_roof(scene, roles)
    if opened:
        short.append(measures.open_roof_sentence(opened))
    for obj in scene.objects:
        if obj.name in roles:
            obj.hide_render = False
    paint_by_role(scene, roles)
    blo, bhi = survey["box"]
    lit_view(scene, blo, bhi, os.path.join(masks, "hall-lit.png"))
    one_above_the_other(os.path.join(args.out_dir, "temple.png"), os.path.join(masks, "hall-lit.png"),
                        os.path.join(args.out_dir, "likeness.png"))
    result = {"shared_outline": shared, "enough": ENOUGH, "columns": columns, "top": {"temple": survey["top"], "hall": round(hi.z, 2)},
              "size": {"temple": survey["size"], "hall": built}, "through_the_roof": poking[:20],
              "beyond_the_eaves": outside["pieces"][:20], "open_roof": opened, "alike": not short,
              "short_of_the_temple": short,
              "frame": {"hall": {**members, "roof_rings": len(members["roof_rings"])}, "short": frame_missing}}
    with open(os.path.join(args.out_dir, "likeness.json"), "w") as f:
        json.dump(result, f, indent=1)
    print("LIKENESS", " ".join(f"{v} {s:.3f}" for v, s in shared.items()), f"| columns {columns['matched']} of "
          f"{columns['wanted']} | size hall {built} temple {survey['size']} |", "alike" if not short else
          "NOT alike: " + "; ".join(short), "| likeness.png: temple above, hall below")


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1:])
