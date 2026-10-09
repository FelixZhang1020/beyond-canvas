"""Does a hall designed from a written brief answer it? There is no standing building to compare with,
so the hall is measured against the brief's own numbers: how many bays across the front and deep, how
far the corner columns stand apart, how many rings of columns, how tall the bracket sets are for the
columns they sit on. The frame is measured with the survey's own ruler (tie beams at the column heads,
roof rings, ridge, rafters, a bracket set on every column), so a box with columns inside does not
answer a brief for a timber hall, and timber standing out through the roof or past its edge, and a
roof left open, are found as they are in a rebuild. The brief's photograph is set above a daylight
picture of the hall, for a pair of eyes.
Reads the hall, changes nothing.
Usage: blender -b hall.blend --python-exit-code 1 --python brief.py -- out_dir --brief brief.json --photo photo.jpg
"""
import argparse
import json
import os
import statistics
import sys

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from likeness import beyond_the_eaves, open_roof, paint_by_role, through_the_roof  # noqa: E402
import measures  # noqa: E402
from shadow import building, lit_view, one_above_the_other  # noqa: E402
from survey import AROUND, columns_of, frame_members, rings_kept  # noqa: E402

sys.path.insert(0, os.path.join(HERE, "..", "..", "model-anatomy", "scripts"))
from pieces import visible_pieces  # noqa: E402
from set_scene import world_box  # noqa: E402

WIDTH, HEIGHT = 960, 540     # the daylight picture's size, which the photo is brought to


def bracket_height(scene, roles, cols, ceiling):
    """How tall the bracket sets stand over the column tops: over each column head, the top of the highest
    timber piece that starts between the column top and the lowest roof ring; the middle of those."""
    pieces = [world_box(scene.objects[n]) for n, r in roles.items() if r == "timber"]
    tops = []
    for x, y in cols["at"]:
        over = [hi.z for lo, hi in pieces if abs((lo.x + hi.x) / 2 - x) <= AROUND and abs((lo.y + hi.y) / 2 - y) <= AROUND
                and cols["top"] - 0.3 <= lo.z <= ceiling]
        if over:
            tops.append(max(over))
    return round(statistics.median(tops) - cols["top"], 2) if tops else 0.0


def short_of(brief, cols, rings, members, brackets, poking):
    """Every way the hall falls short of the brief, in words the builder can act on."""
    if not cols["count"]:
        return ["no columns stand: place the columns first"]
    short = []
    bays = [len(cols["xs"]) - 1, len(cols["ys"]) - 1]
    want = brief["bays"]
    if bays != want:
        short.append(f"{bays[0]} bays across the front and {bays[1]} deep; the brief's hall is {want[0]} by {want[1]}")
    span, (fx, fy), within = [round(cols["xs"][-1] - cols["xs"][0], 2), round(cols["ys"][-1] - cols["ys"][0], 2)], \
        brief["span_m"], brief["span_within"]
    if abs(span[0] - fx) > within * fx or abs(span[1] - fy) > within * fy:
        short.append(f"the corner columns stand {span[0]} m apart across the front and {span[1]} m deep; the brief's hall "
                     f"is {fx:g} by {fy:g} m, within {within:.0%}")
    if rings != brief["column_rings"]:
        what = "a column at every crossing of the grid" if rings == 0 else f"{rings} ring{'s' if rings != 1 else ''} of columns"
        short.append(f"{what}; the brief's hall has {brief['column_rings']}: an outer ring and an inner ring")
    ties = members["tie_spans"]
    if ties["tied"] < ties["spans"]:
        short.append(f"{ties['tied']} of the {ties['spans']} spans between neighbouring columns have tie beams at the column heads")
    if not members["roof_rings"]:
        short.append("no roof rings (purlin lines) carry the roof")
    if not members["ridge"]:
        short.append("no ridge purlin")
    if not members["rafters"]:
        short.append("no rafters running front to back")
    bare = members["bracket_sets"]["columns"] - members["bracket_sets"]["with_a_set"]
    if bare:
        short.append(f"{bare} of {members['bracket_sets']['columns']} columns have no bracket set on their heads")
    lo, hi = brief["brackets_of_column"]
    if not lo <= brackets["of_column"] <= hi:
        short.append(f"the bracket sets stand {brackets['height']} m on columns {brackets['column']} m tall, "
                     f"{brackets['of_column']:.0%} of the column; the brief's are about half (between {lo:.0%} and {hi:.0%})")
    if poking:
        short.append(measures.through_the_roof_sentence(poking))
    return short


def picture(scene, roles, photo, out_dir):
    """The brief's photograph above a daylight picture of the hall, both at the picture's own size."""
    _, lo, hi = building(scene)
    for obj in scene.objects:
        if obj.name in roles:
            obj.hide_render = False
    paint_by_role(scene, roles)
    work = os.path.join(out_dir, "masks")
    os.makedirs(work, exist_ok=True)
    lit_view(scene, lo, hi, os.path.join(work, "hall-lit.png"), WIDTH, HEIGHT)
    image = bpy.data.images.load(os.path.abspath(photo))
    if tuple(image.size) != (WIDTH, HEIGHT):
        image.scale(WIDTH, HEIGHT)
    image.filepath_raw, image.file_format = os.path.join(work, "photo.png"), "PNG"
    image.save()
    one_above_the_other(os.path.join(work, "photo.png"), os.path.join(work, "hall-lit.png"),
                        os.path.join(out_dir, "brief.png"))


def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("out_dir")
    parser.add_argument("--brief", required=True)
    parser.add_argument("--photo", required=True)
    args = parser.parse_args(argv)
    brief = json.load(open(args.brief))
    scene = bpy.context.scene
    roles = visible_pieces(scene)
    cols = columns_of(scene, roles)
    rings = rings_kept(cols) if cols["count"] else 0
    members = frame_members(scene, roles, cols)
    ceiling = min((r["underside"] for r in members["roof_rings"]), default=(cols["top"] or 0.0) + 3.0)
    column = round((cols["top"] or 0.0) - (cols["foot"] or 0.0), 2)
    height = bracket_height(scene, roles, cols, ceiling) if cols["count"] else 0.0
    brackets = {"height": height, "column": column, "of_column": round(height / column, 2) if column > 0 else 0.0}
    poking = through_the_roof(scene, roles)
    outside = beyond_the_eaves(scene, roles, cols["top"] or 0.0)
    short = short_of(brief, cols, rings, members, brackets, poking)
    if outside["pieces"] and cols["count"]:
        short.append(measures.beyond_the_eaves_sentence(outside))
    opened = open_roof(scene, roles)
    if opened and cols["count"]:
        short.append(measures.open_roof_sentence(opened))
    picture(scene, roles, args.photo, args.out_dir)
    _, lo, hi = building(scene)
    result = {"bays": [max(len(cols["xs"]) - 1, 0), max(len(cols["ys"]) - 1, 0)],
              "span": [round(cols["xs"][-1] - cols["xs"][0], 2), round(cols["ys"][-1] - cols["ys"][0], 2)] if cols["count"] else None,
              "column_rings": rings, "columns": cols["count"], "brackets": brackets,
              "frame": {**members, "roof_rings": len(members["roof_rings"])}, "through_the_roof": poking[:20],
              "beyond_the_eaves": outside["pieces"][:20], "open_roof": opened,
              "size": [round(hi[i] - lo[i], 2) for i in range(3)], "top": round(hi.z, 2),
              "meets": not short, "short_of_the_brief": short, "brief": {k: v for k, v in brief.items() if k != "about"}}
    with open(os.path.join(args.out_dir, "brief-check.json"), "w") as f:
        json.dump(result, f, indent=1)
    print("BRIEF", f"{result['bays'][0]} by {result['bays'][1]} bays | corner columns {result['span']} m apart |",
          f"{rings} rings of columns | bracket sets {brackets['of_column']:.0%} of the column |",
          "meets the brief" if not short else "does NOT meet the brief: " + "; ".join(short),
          "| brief.png: the photograph above, the hall below")


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1:])
