"""Pull a group of pieces apart in stacking order and render it. Pieces are ranked into tiers
by the height of their bottom; each tier rises a little farther than the one below and starts a
little later, and arms that cross the group's centre also slide along their own length so the
lap shows. Joints from joints.json move the way the joint opens. Everything happens on the
copy in memory; the model file is never saved.

With --closeups the film is the joints instead of the group (joint_film.py): the set in its hall,
then each joint of joints.json close, coming apart and locking again, captioned, and a still of each
held open (joint-<kind>.png). The group's pull-apart is still planned in explode.json, for the live 3D
view. A pulled-apart bracket set among its neighbours hid the joints it was meant to show.
Given --assembly of a set whose joints are known (assets/sets.json) and no --joints, it cuts them on
this copy itself and films them so: one call, which is what a live model makes.
Usage: blender -b model.blend --python-exit-code 1 --python explode.py -- out_dir --anatomy anatomy.json
           (--assembly TAG | --pieces A,B,C | --near x,y,z RADIUS) [--joints joints.json [--closeups]]
           [--seconds 6] [--fps 30] [--width 1280] [--height 720] [--at=x,y,z --look=x,y,z]
           [--style studio|daylight] [--lang zh|en]
"""
import argparse
import json
import math
import os
import sys

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "model-anatomy", "scripts"))
from set_scene import (encode_video, hide_above, hide_beyond, orbit, parse_xyz,  # noqa: E402
                       place_camera, plain_look, render_frames, render_still, set_look, set_output)
from joint_film import film  # noqa: E402
from joints import crosslap, dovetail, tenon  # noqa: E402
from pieces import world_bmesh  # noqa: E402

RISE, STAGGER, SLIDE = 0.18, 0.12, 0.25
WORDS = os.path.join(HERE, "..", "assets", "closeup-words.json")
SETS = os.path.join(HERE, "..", "assets", "sets.json")
CUT = " | JOINT"
CUTS = {"tenon": tenon, "crosslap": crosslap, "dovetail": dovetail}


def cut_known(scene, assembly, sets=SETS):
    """The joints of a set whose joints are known (sets.json), cut here on the copy in memory, so one
    call films how that set locks. A live model once never cut the joints, took stock of the
    copy and then filmed it; it pulled the set apart whole, or tried stills until its context ran out.
    A joint whose pieces this model lacks is left out."""
    known = json.load(open(sets, encoding="utf-8")).get(assembly or "", {})
    return [CUTS[kind](scene, *names) for kind in CUTS for names in known.get(kind, [])
            if all(n in scene.objects for n in names if n not in ("min", "max"))]


def with_cut_copies(scene, pieces, joints):
    """The anatomy's pieces with every cut copy the joints name in place of the piece it was copied
    from, which the copy of the hall keeps hidden: measured where the copy stands, with the original's
    role and tags. A live run hands over the hall's anatomy.json, read before any joint was cut, and
    the joints would otherwise be filmed as nothing; an anatomy of the copy already lists them."""
    out = dict(pieces)
    for name in {n for j in joints for n in j["pieces"]}:
        original = name.removesuffix(CUT)
        if name in out or original not in out or name not in scene.objects:
            continue
        bm = world_bmesh(scene.objects[name])
        lo = [min(v.co[i] for v in bm.verts) for i in range(3)]
        hi = [max(v.co[i] for v in bm.verts) for i in range(3)]
        bm.free()
        out[name] = {**out.pop(original), "box": [lo, hi], "centre": [(a + b) / 2 for a, b in zip(lo, hi)],
                     "zmin": lo[2], "zmax": hi[2]}
    return out


def focus_of(names, pieces):
    """Where the group's mass is, and how big it looks: the median of the piece centres and
    the 80th-percentile distance from it, so one long beam cannot push the camera away."""
    centres = [Vector(pieces[n]["centre"]) for n in names]
    median = Vector([sorted(c[i] for c in centres)[len(centres) // 2] for i in range(3)])
    dists = sorted((c - median).length for c in centres)
    return median, max(dists[int(0.8 * (len(dists) - 1))], 0.5)


def choose(anatomy, args):
    pieces = anatomy["pieces"]
    if args.pieces:                          # a piece a joint was cut into is its cut copy now
        wanted = [n if n in pieces else f"{n}{CUT}" for n in args.pieces.split(",")]
        return [n for n in wanted if n in pieces]
    if args.assembly:
        return [n for n, p in pieces.items() if p["tags"].get("assembly") == args.assembly]
    c, r = parse_xyz(args.near[0]), float(args.near[1])
    return [n for n, p in pieces.items() if (Vector(p["centre"]) - c).length <= r and p["role"] != "ground"]


def tiers_of(names, pieces):
    """Distinct bottom heights, 3 cm apart or more, lowest first."""
    levels = []
    for z in sorted(pieces[n]["zmin"] for n in names):
        if not levels or z - levels[-1] > 0.03:
            levels.append(z)
    return {n: max(i for i, z in enumerate(levels) if pieces[n]["zmin"] >= z - 1e-6) for n in names}


def offsets(names, pieces, tiers, centre, joints):
    out = {}
    for n in names:
        p = pieces[n]
        off = Vector((0, 0, RISE * tiers[n]))
        axis = Vector(p["axis"])
        if p["kind"] == "beam" and abs(axis.z) < 0.5 and p["extents"][0] > 0.6:
            toward = Vector(p["centre"]) - centre
            side = 1.0 if toward.dot(axis) >= 0 else -1.0
            off += axis * (SLIDE * side)
        out[n] = off
    for joint in joints:
        for n, d in joint["explode"].items():
            if n in out:
                out[n] = Vector(d)
    return out


def ease(t):
    return 0.5 - 0.5 * math.cos(math.pi * min(max(t, 0.0), 1.0))


def keyframe(scene, names, offs, tiers, frames):
    top = max(tiers.values()) + 1
    for n in names:
        obj = scene.objects[n]
        start = obj.matrix_world.translation.copy()
        obj.animation_data_clear()
        for f in range(1, frames + 1):
            t = (f - 1) / max(frames - 1, 1)
            local = (t - STAGGER * tiers[n] / top) / max(1.0 - STAGGER, 0.01)
            obj.matrix_world.translation = start + offs[n] * ease(local)
            obj.keyframe_insert("location", frame=f)


def parse(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("out_dir")
    parser.add_argument("--anatomy", required=True)
    parser.add_argument("--assembly")
    parser.add_argument("--pieces")
    parser.add_argument("--near", nargs=2, metavar=("XYZ", "RADIUS"))
    parser.add_argument("--joints")
    parser.add_argument("--sets", default=SETS, help="the sets whose joints are known; the skill's own list")
    parser.add_argument("--closeups", action="store_true", help="with --joints: the set, then each joint close")
    parser.add_argument("--seconds", type=float, default=6.0)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--at")
    parser.add_argument("--look")
    parser.add_argument("--style", choices=("studio", "daylight"), default="studio")
    parser.add_argument("--lang", choices=("zh", "en"), default="zh", help="the close-ups' captions")
    return parser.parse_args(argv)


def main(argv):
    args = parse(argv)
    scene = bpy.context.scene
    anatomy = json.load(open(args.anatomy))
    joints = json.load(open(args.joints))["joints"] if args.joints else cut_known(scene, args.assembly, args.sets)
    closeups = args.closeups or (bool(joints) and not args.joints)     # a known set is filmed joint by joint
    anatomy["pieces"] = with_cut_copies(scene, anatomy["pieces"], joints)
    names = choose(anatomy, args)
    pieces = anatomy["pieces"]
    lo = Vector([min(pieces[n]["box"][0][i] for n in names) for i in range(3)])
    hi = Vector([max(pieces[n]["box"][1][i] for n in names) for i in range(3)])
    centre = (lo + hi) / 2
    tiers = tiers_of(names, pieces)
    offs = offsets(names, pieces, tiers, centre, joints)
    frames = max(2, int(round(args.seconds * args.fps)))
    if closeups:
        if not joints:
            raise SystemExit("--closeups films the joints of --joints; none were given")
        set_output(scene, args.width, args.height)
        plain_look(scene)
        words = json.load(open(WORDS, encoding="utf-8"))[args.lang]
        shots, end = film(scene, joints, pieces, frames, args.fps, args.out_dir, words)
        video = encode_video(os.path.join(args.out_dir, "explode"), os.path.join(args.out_dir, "explode.mp4"), args.fps)
        plan = {"pieces": [{"name": n, "tier": tiers[n], "offset": list(offs[n])} for n in sorted(names, key=lambda k: tiers[k])],
                "closeups": shots, "frames": end, "video": video}
        with open(os.path.join(args.out_dir, "explode.json"), "w") as f:
            json.dump(plan, f, indent=1)
        print("EXPLODE", len(shots), "joints", " ".join(s["kind"] for s in shots), end, "frames")
        return
    keyframe(scene, names, offs, tiers, frames)
    focus, reach = focus_of(names, pieces)
    kept = hide_beyond(scene, focus, 2.5 * reach + 2.0)
    kept -= hide_above(scene, hi.z + 0.05)
    chosen = set(names)
    for n, p in pieces.items():
        if p["role"] in ("rafter", "covering") and n not in chosen and n in scene.objects:
            scene.objects[n].hide_render = True
    for n in names:
        scene.objects[n].hide_render = False
    top = RISE * max(tiers.values())
    look = parse_xyz(args.look) if args.look else focus + Vector((0, 0, 0.3 * top))
    at = parse_xyz(args.at) if args.at else orbit(focus, 2.4 * reach + 0.5 * top, 0.4 * reach + 0.25 * top, -60)
    set_look(scene, args.style, centre=focus, size=max(reach, 1.0))
    place_camera(scene, at, look, 40.0)
    set_output(scene, args.width, args.height)
    for tag, f in (("closed", 1), ("half", (frames + 1) // 2), ("open", frames)):
        scene.frame_set(f)
        render_still(scene, os.path.join(args.out_dir, f"explode-{tag}.png"))
    render_frames(scene, os.path.join(args.out_dir, "explode"), 1, frames)
    video = encode_video(os.path.join(args.out_dir, "explode"), os.path.join(args.out_dir, "explode.mp4"), args.fps)
    plan = {"pieces": [{"name": n, "tier": tiers[n], "offset": list(offs[n])} for n in sorted(names, key=lambda k: tiers[k])],
            "camera": {"at": list(at), "look": list(look)}, "frames": frames, "kept": kept, "video": video}
    with open(os.path.join(args.out_dir, "explode.json"), "w") as f:
        json.dump(plan, f, indent=1)
    print("EXPLODE", len(names), "pieces", max(tiers.values()) + 1, "tiers", frames, "frames")


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1:])
