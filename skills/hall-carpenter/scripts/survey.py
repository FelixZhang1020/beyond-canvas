"""Measure a standing building into a sheet of numbers a carpenter can work from: where the
columns stand and how tall, where the tie beams run, the purlin rings of the roof from the eave
to the ridge, the eave's edge and the top. Also measures the frame the way likeness measures the
hall — which spans between neighbouring columns carry a tie beam, and which column heads carry a
bracket set — so a box with the right outline cannot pass for a timber frame. Casts the building's
three shadows and takes one lit picture, for the likeness tool to compare against. Reads the
model, changes nothing.
Usage: blender -b temple.blend --python-exit-code 1 --python survey.py -- out_dir
"""
import json
import os
import sys
from collections import Counter

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from shadow import building, cast, frame_of, lit_view, show_only  # noqa: E402

sys.path.insert(0, os.path.join(HERE, "..", "..", "model-anatomy", "scripts"))
from pieces import visible_pieces  # noqa: E402
from set_scene import world_box  # noqa: E402

import measures  # noqa: E402
from lower import neighbours  # noqa: E402  the carpenter's own rule for which columns a tie beam joins

AROUND, BRACKET_PIECES = 0.8, 3     # a bracket set: this many timber pieces centred this close over a column head


def common(values):
    """The value most pieces share, to the centimetre: one odd piece does not move the sheet."""
    return Counter(round(v, 2) for v in values).most_common(1)[0][0] if values else None


def lines_of(values, apart=0.3):
    """Column lines: values closer than `apart` are one line, given as their mean (columns lean)."""
    groups = []
    for v in sorted(values):
        if groups and v - groups[-1][-1] < apart:
            groups[-1].append(v)
        else:
            groups.append([v])
    return [round(sum(g) / len(g), 2) for g in groups]


def boxes(scene, roles, role, word):
    out = []
    for name, r in roles.items():
        if r == role and word in name.lower():
            lo, hi = world_box(scene.objects[name])
            out.append((name, lo, hi, hi - lo))
    return out


def columns_of(scene, roles):
    posts = [(n, lo, hi, d) for n, lo, hi, d in boxes(scene, roles, "timber", "column")
             if d.z > 2.0 and d.z > 3 * max(d.x, d.y)]
    xs = lines_of([(lo.x + hi.x) / 2 for _, lo, hi, _ in posts])
    ys = lines_of([(lo.y + hi.y) / 2 for _, lo, hi, _ in posts])
    at = {(round((lo.x + hi.x) / 2, 2), round((lo.y + hi.y) / 2, 2)) for _, lo, hi, _ in posts}
    return {"count": len(posts), "xs": xs, "ys": ys,
            "foot": common([lo.z for _, lo, _, _ in posts]), "top": common([hi.z for _, _, hi, _ in posts]),
            "diameter": round(common([max(d.x, d.y) for _, _, _, d in posts]), 2),
            "at": sorted([list(p) for p in at])}


def rings_kept(cols):
    """How many rings of the xs-by-ys grid the columns fill, outermost first; 0 when it is every point."""
    nx, ny = len(cols["xs"]), len(cols["ys"])
    for rings in range(1, min(nx, ny) // 2 + 2):
        kept = sum(1 for i in range(nx) for j in range(ny) if min(i, nx - 1 - i, j, ny - 1 - j) < rings)
        if kept == cols["count"]:
            return rings
    return 0


def purlin_lines(scene, roles):
    long_lines, end_lines, ridge = {}, {}, None
    for _, lo, hi, d in boxes(scene, roles, "timber", "purlin"):
        if max(d.x, d.y) < 5 * d.z:          # a saddle or a cradle named after its purlin is not a purlin
            continue
        if d.x > d.y:
            y = abs((lo.y + hi.y) / 2)
            if y < 0.3:
                ridge = {"half_x": round(hi.x, 2), "underside": round(lo.z, 2)}
            else:
                long_lines[round(y, 2)] = (round(lo.z, 2), round(max(abs(lo.x), abs(hi.x)), 2), round(d.z, 2))
        else:
            end_lines[round(abs((lo.x + hi.x) / 2), 2)] = round(lo.z, 2)
    return long_lines, end_lines, ridge


def rings_of(long_lines, end_lines, ridge, outer_y):
    """One ring per long purlin line: how far the roof reaches in x at that line's height, read
    off the end slope, so both slopes are given by the same list."""
    profile = sorted(((z, x) for x, z in end_lines.items()), key=lambda p: p[0])
    if ridge:
        profile.append((ridge["underside"], ridge["half_x"]))
    rings = []
    for y in sorted(long_lines, reverse=True):
        under, own_half, size = long_lines[y]
        half_x = own_half
        for (z0, x0), (z1, x1) in zip(profile, profile[1:]):
            if z0 - 0.05 <= under <= z1:
                half_x = x0 + (x1 - x0) * max(0.0, under - z0) / max(z1 - z0, 1e-9)
        rings.append({"ring": len(rings) + 1, "half_x": round(half_x, 2), "half_y": y, "underside": under, "size": size,
                      "out_from_outer_columns": round(y - outer_y, 2)})
    return rings


def rafters_of(scene, roles):
    """The size and spacing of the rafters that run front to back; measures.py says how the boxes are read."""
    runs = [{"x": (lo.x + hi.x) / 2, "width": d.x, "y": (lo.y + hi.y) / 2, "foot": lo.z}
            for _, lo, hi, d in boxes(scene, roles, "rafter", "rafter") if d.y > 3 * d.x and d.y > 1.0]
    return measures.rafters(runs)


def grid_places(cols):
    """The columns on their grid lines, each with the ring it stands in, outermost ring 0."""
    xs, ys = cols["xs"], cols["ys"]
    nx, ny = len(xs) - 1, len(ys) - 1
    at = []
    for x, y in cols["at"]:
        i = min(range(len(xs)), key=lambda k: abs(xs[k] - x))
        j = min(range(len(ys)), key=lambda k: abs(ys[k] - y))
        at.append({"x": x, "y": y, "i": i, "j": j, "ring": min(i, nx - i, j, ny - j)})
    return at


def tie_spans(scene, roles, cols):
    """Spans between neighbouring columns of a ring that are tied at the column heads: a timber piece
    over the span's middle, reaching the tops of the columns, running at least 0.6 of the span."""
    beams = [world_box(scene.objects[n]) for n, r in roles.items() if r == "timber"]
    top, spans, tied = cols["top"], 0, 0
    for a, b in neighbours(grid_places(cols)):
        spans += 1
        mx, my = (a["x"] + b["x"]) / 2, (a["y"] + b["y"]) / 2
        along = 0 if a["j"] == b["j"] else 1
        length = abs(b["x"] - a["x"]) + abs(b["y"] - a["y"])
        tied += any(lo.x - 0.1 <= mx <= hi.x + 0.1 and lo.y - 0.1 <= my <= hi.y + 0.1 and hi.z >= top - 0.8
                    and lo.z <= top + 0.3 and hi[along] - lo[along] >= 0.6 * length for lo, hi in beams)
    return {"spans": spans, "tied": tied}


def bracket_sets(scene, roles, cols, rings):
    """Columns whose head carries a bracket set: at least BRACKET_PIECES timber pieces centred over it,
    starting between the top of the column and the lowest roof ring. The Foguang hall has 18 to 37."""
    ceiling = min((r["underside"] for r in rings), default=cols["top"] + 3.0)
    starts = []
    for name, role in roles.items():
        if role == "timber":
            lo, hi = world_box(scene.objects[name])
            starts.append(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z))
    carried = sum(1 for x, y in cols["at"] if sum(1 for cx, cy, z in starts if abs(cx - x) <= AROUND and abs(cy - y)
                                                   <= AROUND and cols["top"] - 0.3 <= z <= ceiling) >= BRACKET_PIECES)
    return {"columns": len(cols["at"]), "with_a_set": carried}


def frame_members(scene, roles, cols=None):
    """The members that make a timber frame, measured the same way on the temple and on a hall."""
    cols = cols or columns_of(scene, roles)
    long_lines, end_lines, ridge = purlin_lines(scene, roles)
    rings = rings_of(long_lines, end_lines, ridge, max(cols["ys"], default=0.0))
    if not cols["count"]:
        return {"tie_spans": {"spans": 0, "tied": 0}, "roof_rings": rings, "ridge": ridge,
                "rafters": rafters_of(scene, roles), "bracket_sets": {"columns": 0, "with_a_set": 0}}
    return {"tie_spans": tie_spans(scene, roles, cols), "roof_rings": rings, "ridge": ridge,
            "rafters": rafters_of(scene, roles), "bracket_sets": bracket_sets(scene, roles, cols, rings)}


def main(out_dir):
    scene = bpy.context.scene
    roles = visible_pieces(scene)
    names, lo, hi = building(scene)
    cols = columns_of(scene, roles)
    cols["rings"] = rings_kept(cols)
    tie = boxes(scene, roles, "timber", "tie beam")
    tie = [b for b in tie if abs(b[2].z - common([t[2].z for t in tie])) < 0.02]   # the ring at the column heads
    members = frame_members(scene, roles, cols)
    ridge = members["ridge"]
    stone = [b for b in boxes(scene, roles, "ground", "") if any("platform" in c.name.lower()
             for c in scene.objects[b[0]].users_collection)]
    paving = [b[2].z for b in stone if abs(b[2].z - cols["foot"]) < 0.2]
    if paving:                                  # the stones the columns stand on; a lower terrace is not the platform top
        cols["foot"] = common(paving)
    frame = frame_of(lo, hi)
    by_role = Counter(roles.values())
    sheet = {
        "about": "Measured from the standing temple, in metres; z is height, x runs along the front, y front to back.",
        "size": [round(hi[i] - lo[i], 2) for i in range(3)], "top": round(hi.z, 2), "pieces": dict(by_role),
        "platform": {"top": cols["foot"], "size": [round(max(b[2].x for b in stone) - min(b[1].x for b in stone), 1),
                                                   round(max(b[2].y for b in stone) - min(b[1].y for b in stone), 1)]
                     if stone else None},
        "columns": {k: v for k, v in cols.items() if k != "at"},
        "tie_beams": {"top": common([b[2].z for b in tie]), "depth": common([b[3].z for b in tie]),
                      "width": common([min(b[3].x, b[3].y) for b in tie])} if tie else None,
        "tie_spans": members["tie_spans"],
        "bracket_sets": members["bracket_sets"],
        "roof_rings": members["roof_rings"],
        "ridge": ridge,
        "eave_edge": {"half_x": round((hi.x - lo.x) / 2, 2), "half_y": round((hi.y - lo.y) / 2, 2)},
        "rafters": members["rafters"],
        "walls": {"foot": round(min((b[1].z for b in boxes(scene, roles, "wall", "")), default=cols["foot"]), 2), "top": round(common([b[1].z for b in tie]), 2) if tie else None,
                  "thickness": common([min(b[3].x, b[3].y) for b in boxes(scene, roles, "wall", "wall")]),
                  "sides": ["front", "back", "left", "right"]},
    }
    if sheet["roof_rings"]:
        sheet["eave_edge"]["out_from_eave_ring"] = round(sheet["eave_edge"]["half_y"] - sheet["roof_rings"][0]["half_y"], 2)
    os.makedirs(out_dir, exist_ok=True)
    show_only(scene, names)
    cast(scene, frame, os.path.join(out_dir, "masks"), "temple")
    for obj in scene.objects:
        if obj.name in roles:
            obj.hide_render = False
    lit_view(scene, lo, hi, os.path.join(out_dir, "temple.png"))
    with open(os.path.join(out_dir, "survey.json"), "w") as f:
        json.dump({**sheet, "column_places": cols["at"], "frame": frame, "box": [list(lo), list(hi)]}, f, indent=1)
    print("SURVEY", cols["count"], "columns top", cols["top"], "|", len(sheet["roof_rings"]), "roof rings, ridge underside",
          ridge["underside"] if ridge else None, "| size", sheet["size"], "| wrote survey.json, temple.png")


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1])
