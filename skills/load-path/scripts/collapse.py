"""The collapse: one mortise-and-tenon joint is taken out and the hall comes down link by link, to show
how every piece of the frame depends on the pieces under it and the pieces joined into it.

The piece the joint held gives way first. Then, one link at a time, everything resting on a piece that
gave way (bearing.json's rests_on) and everything drawn into one (its overlaps: the mortises and
tenons) gives way too. The columns, the walls and the ground stand. That rule is the model's: it is
stricter than a real hall, where a piece with another sound support might hang on, and it is what makes
the dependence visible (operator: take out one joint and the hall comes down, "a chain you
can follow"). Letting physics decide showed nothing of the kind: a block whose tenon is gone still sits
on its column, and a beam with one support left stays up, so the settle test's column taken away
brought down a corner at most (measured on the Spark).

So the fall is drawn, not solved: each piece glows as it gives way, drops under gravity, tipping and
drifting a little outward, and lands on whatever still stands beneath it or on the ground, never
through it. Falling pieces may come to rest in one another. Everything happens on the copy in memory;
the model file is never saved.
Usage: blender -b model.blend --python-exit-code 1 --python collapse.py -- out_dir --anatomy anatomy.json
           --bearing bearing.json --joint COLUMN PIECE [--step 0.4] [--fps 24] [--width 1280] [--height 720] [--lang zh|en]
"""
import argparse
import json
import math
import os
import random
import sys
from collections import defaultdict

import bmesh
import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "model-anatomy", "scripts"))
from rigid import block_stem, centre_and_volume, recentre  # noqa: E402
from pieces import refuse_if_stale  # noqa: E402
from set_scene import (GHOST, ROLE_TINT, captions, encode_video, orbit, place_camera, plain_look,  # noqa: E402
                       render_frames, render_still, set_output)

G = 9.81
GLOW, FALLEN = (1.0, 0.45, 0.08), (0.78, 0.22, 0.12)
LEAD_S, GLOW_S, HOLD_S = 3.0, 0.35, 3.0   # the joint close and glowing; a piece glows before it drops; the ruins
SLOW_S, SMALL = 1.0, 10                   # a link of SMALL pieces or fewer is given a second, so the first ones can be followed
PULL_S = 3.0                              # the camera's pull back from the joint to the whole hall
WORDS = os.path.join(HERE, "..", "assets", "collapse-words.json")
DRIFT = 0.5                               # metres a second outward from the hall's middle while falling
TIP_DEG = 20.0                            # degrees of tumble for each metre fallen, up to TIP_MAX,
TIP_MAX = 75.0                            # for a piece up to TIP_LONG metres long; a longer one tips less,
TIP_LONG = 1.5                            # or a whole slope of roof stood on end like a sail
SAMPLES = 48                              # points of a piece's surface tried for where it first touches


def links_from(piece, anatomy, bearing):
    """The pieces that give way, link by link, from the one the joint held. What stands is never reached."""
    pieces = anatomy["pieces"]
    stands = {n for n, p in pieces.items() if p["role"] not in ("timber", "rafter") or p["kind"] == "column"}
    next_to = defaultdict(set)
    for n, contacts in bearing["rests_on"].items():
        for c in contacts:
            next_to[c["on"]].add(n)                   # what rests on it goes when it goes
    for n, others in bearing["overlaps"].items():
        for m in others:
            next_to[n].add(m)                         # a joint binds both ways
            next_to[m].add(n)
    level, seen, links = [piece], {piece}, []
    while level:
        links.append(sorted(level))
        new = {m for n in level for m in next_to.get(n, ()) if m in pieces and m not in seen and m not in stands}
        seen |= new
        level = new
    return links


def tiles_link(anatomy, links):
    """A sheet of roof tiles goes with the rafters under it: at the middle link of those, in plan."""
    pieces, link_of = anatomy["pieces"], {n: k for k, level in enumerate(links) for n in level}
    rafters = [(Vector(pieces[n]["centre"]).to_2d(), k) for n, k in link_of.items() if pieces[n]["role"] == "rafter"]
    out = {}
    for n, p in pieces.items():
        if p["role"] != "covering" or not rafters:
            continue
        (x0, y0, _), (x1, y1, _) = p["box"]
        under = sorted(k for c, k in rafters if x0 <= c.x <= x1 and y0 <= c.y <= y1) or sorted(k for _, k in rafters)
        out[n] = under[len(under) // 2]
    return out


def ground_under(scene, falling):
    """One tree of every face that stands, the ground's, the walls' and the columns', for landing on."""
    bm = bmesh.new()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    for obj in scene.objects:
        if obj.type != "MESH" or obj.name in falling or obj.hide_render:
            continue
        mesh = obj.evaluated_get(depsgraph).to_mesh()
        mesh.transform(obj.matrix_world)
        bm.from_mesh(mesh)
        obj.evaluated_get(depsgraph).to_mesh_clear()
    tree = BVHTree.FromBMesh(bm)
    bm.free()
    return tree


def plain(scene, roles):
    """Each piece a flat colour by its role, the roof's tiles and rafters a faint ghost, so the frame shows
    through (operator: the roof covered everything and the chain could not be seen)."""
    plain_look(scene)
    for obj in scene.objects:
        obj.color = colour_of(roles.get(obj.name))


def colour_of(role, tint=None):
    rgb = tint or ROLE_TINT.get(role, (0.82, 0.79, 0.73))
    return (*rgb, GHOST if role in ("covering", "rafter") else 1.0)


def give_way(obj, role, frame, frames, standing=True):
    """Stands in its own colour, flashes as it gives way, and stays red once it has gone."""
    for f, tint in ((frame - 1, None),) * standing + ((frame, GLOW), (frame + frames, FALLEN)):
        obj.color = colour_of(role, tint)
        obj.keyframe_insert("color", frame=f)


def link_times(links, lead, step, fps):
    """The frame each link gives way: a small link a second after the one before, a wide one `step` after."""
    times, at = [], lead
    for level in links:
        times.append(at)
        at += int(round(SLOW_S * fps)) if len(level) <= SMALL else step
    return times


def surface_points(obj):
    """Up to SAMPLES points of the piece, in the world: its vertices, or its box's corners."""
    if obj.type == "MESH" and len(obj.data.vertices):
        verts = obj.data.vertices
        every = max(1, len(verts) // SAMPLES)
        return [obj.matrix_world @ verts[i].co for i in range(0, len(verts), every)]
    return [obj.matrix_world @ Vector(c) for c in obj.bound_box]


def first_touch(points, tree, shift, floor):
    """How far the piece can drop, moved by `shift`, before its first point meets what stands."""
    gaps = []
    for p in points:
        hit = tree.ray_cast(Vector((p.x + shift.x, p.y + shift.y, p.z - 0.01)), Vector((0, 0, -1)))
        gaps.append(p.z - (hit[0].z if hit[0] is not None else floor))
    return max(0.0, min(gaps))


def fall(obj, start, fps, tree, middle, floor, rng):
    """Drop from `start` under gravity, drifting outward and tipping, until the first point of the piece
    meets what stands below it; the frames it took, and how far it came down."""
    placed = obj.matrix_world.copy()
    home = placed.translation.copy()
    out = (home - middle).to_2d()
    out = (out.normalized() if out.length > 1e-6 else Vector((1, 0))) * DRIFT
    axis = Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), 0)).normalized()
    points = surface_points(obj)
    drop = first_touch(points, tree, Vector((0, 0)), floor)
    seconds = math.sqrt(2 * drop / G) if drop > 0 else 0.0
    drop = first_touch(points, tree, out * seconds, floor)       # once more where the drift takes it
    seconds = math.sqrt(2 * drop / G) if drop > 0 else 0.0
    frames = max(1, int(math.ceil(seconds * fps)))
    tip = math.radians(min(TIP_MAX, TIP_DEG * drop) * min(1.0, TIP_LONG / max(max(obj.dimensions), 1e-6)))
    for i in range(frames + 1):
        t = min(seconds, i / fps)
        k = t / seconds if seconds else 1.0
        moved = home + Vector((out.x * t, out.y * t, -0.5 * G * t * t))
        obj.matrix_world = Matrix.Translation(moved) @ Matrix.Rotation(tip * k, 4, axis) @ Matrix.Translation(-home) @ placed
        obj.keyframe_insert("location", frame=start + i)
        obj.keyframe_insert("rotation_euler", frame=start + i)
    obj.matrix_world = placed
    return frames, drop


def film_camera(scene, anatomy, piece, middle, lo, size, height, times, links, fps):
    """Close on the joint while its first links go, then back to the whole hall as the chain widens."""
    joint = Vector(anatomy["pieces"][piece]["centre"])
    around = math.degrees(math.atan2(joint.y - middle.y, joint.x - middle.x)) + 20
    pivot = Vector((middle.x, middle.y, lo.z + 0.4 * height))
    wide = (orbit(pivot, 1.15 * size, 0.45 * height, around), pivot)
    close = (orbit(joint, 7.0, 1.5, around), joint)
    held = next((times[k] for k, level in enumerate(links) if len(level) > SMALL), times[-1])
    camera = place_camera(scene, *close, 35.0, focus=False)
    for frame, (at, look) in ((1, close), (held, close), (held + int(PULL_S * fps), wide)):
        camera.location = at
        camera.rotation_euler = (look - at).to_track_quat("-Z", "Y").to_euler()
        camera.keyframe_insert("location", frame=frame)
        camera.keyframe_insert("rotation_euler", frame=frame)
    return camera


def parse(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("out_dir")
    parser.add_argument("--anatomy", required=True)
    parser.add_argument("--bearing", required=True)
    parser.add_argument("--joint", nargs=2, required=True, metavar=("COLUMN", "PIECE"),
                        help="the joint taken out: the piece PIECE held on COLUMN by its tenon")
    parser.add_argument("--step", type=float, default=0.4, help="seconds between one link giving way and the next")
    parser.add_argument("--fps", type=int, default=24)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--lang", choices=("zh", "en"), default="zh", help="the captions' language")
    return parser.parse_args(argv)


def main(argv):
    args = parse(argv)
    scene = bpy.context.scene
    anatomy, bearing = json.load(open(args.anatomy)), json.load(open(args.bearing))
    roles = {n: p["role"] for n, p in anatomy["pieces"].items()}
    refuse_if_stale(scene, roles, "load-path collapse")
    column, piece = args.joint
    if not any(c["on"] == column for c in bearing["rests_on"].get(piece, [])):
        raise SystemExit(f"{piece} does not rest on {column}: there is no joint between them to take out")
    links = links_from(piece, anatomy, bearing)
    link_of = {n: k for k, level in enumerate(links) for n in level}
    link_of.update(tiles_link(anatomy, links))
    link_of = {n: k for n, k in link_of.items() if n in scene.objects}
    lead, step, glow_f = int(LEAD_S * args.fps), max(1, int(round(args.step * args.fps))), max(1, int(GLOW_S * args.fps))
    for n in link_of:
        obj = scene.objects[n]
        if obj.type == "MESH":                      # it tips about its own middle, not an origin left elsewhere
            recentre(obj, centre_and_volume(obj)[0], ease=False)
    scene.view_layers[0].update()
    tree = ground_under(scene, set(link_of))
    lo, hi = (Vector(v) for v in anatomy["model"]["box"])
    middle, size, height = (lo + hi) / 2, max(hi - lo), hi.z - lo.z
    plain(scene, roles)
    # The whole block the joint held glows from the first frame: its foot alone is a plate 9 cm thick,
    # hidden under its seat, and nobody could see which piece the film was about.
    stem = block_stem(piece)
    held = {n for n in link_of if n == piece or (stem and block_stem(n) == stem)}
    for n in held:
        scene.objects[n].color = colour_of(roles[n], GLOW)
        scene.objects[n].keyframe_insert("color", frame=1)
    times = link_times(links, lead, step, args.fps)
    rng, landed, results = random.Random(7), 0, {}
    for n, k in sorted(link_of.items(), key=lambda item: item[1]):
        obj = scene.objects[n]
        give_way(obj, roles[n], times[k], glow_f, standing=n not in held)
        frames, drop = fall(obj, times[k] + glow_f, args.fps, tree, middle, lo.z, rng)
        landed = max(landed, times[k] + glow_f + frames)
        results[n] = {"link": k, "drop_m": drop, "moved_m": drop}
    last = landed + int(HOLD_S * args.fps)
    scene.frame_start, scene.frame_end = 1, last
    camera = film_camera(scene, anatomy, piece, middle, lo, size, height, times, links, args.fps)
    words, gone = json.load(open(WORDS, encoding="utf-8"))[args.lang], 0
    lines = [(words["start_tenon"] if piece.endswith("Ludou foot") else words["start"].format(piece=piece), 1, times[0] - 1)]
    for k, level in enumerate(links):
        gone += len(level)
        lines.append((words["link"].format(n=k + 1, gone=gone), times[k], (times[k + 1] if k + 1 < len(links) else landed) - 1))
    lines.append((words["end"].format(total=len(results)), landed, last))
    captions(scene, camera, lines)
    set_output(scene, args.width, args.height)
    plain_look(scene)                                 # set_output picks EEVEE; the plain look is the solid one
    for tag, f in (("start", 1), ("mid", times[len(links) // 2]), ("end", last)):
        scene.frame_set(f)
        render_still(scene, os.path.join(args.out_dir, f"collapse-{tag}.png"))
    render_frames(scene, os.path.join(args.out_dir, "collapse"), 1, last)
    video = encode_video(os.path.join(args.out_dir, "collapse"), os.path.join(args.out_dir, "collapse.mp4"), args.fps)
    fell = sum(1 for r in results.values() if r["drop_m"] > 1.0)
    summary = {"joint": [column, piece], "links": len(links), "pieces": len(results), "fell": fell, "frames": last,
               "seconds": round(last / args.fps, 2), "video": video}
    plan = {"links": [{"index": k, "frame": times[k], "pieces": level} for k, level in enumerate(links)],
            "pieces": results, "summary": summary}
    with open(os.path.join(args.out_dir, "collapse.json"), "w") as f:
        json.dump(plan, f, indent=1)
    print(f"COLLAPSE {len(results)} pieces in {len(links)} links from the joint between {column} and {piece}; "
          f"{fell} fell more than a metre; the columns, walls and ground stand; {last} frames")   # the replay paints by it


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1:])
