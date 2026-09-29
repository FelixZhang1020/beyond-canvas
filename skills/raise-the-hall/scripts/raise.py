"""The building goes up scene by scene in its carrying order. Every piece is hidden until its
scene, appears a few metres above its place and eases down; scenes start a fraction of a second
apart; the camera orbits slowly. Keyframed on the copy in memory; the model file is never saved.
Usage: blender -b model.blend --python-exit-code 1 --python raise.py -- out_dir --scenes scenes.json
           --anatomy anatomy.json [--drop 3.0] [--scene-seconds 0.4] [--settle-seconds 0.6] [--fps 30]
           [--width 1280] [--height 720] [--orbit-degrees 90] [--style daylight|studio]
"""
import argparse
import json
import os
import sys

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "model-anatomy", "scripts"))
from set_scene import (encode_video, orbit, place_camera, render_frames, render_still,  # noqa: E402
                       set_look, set_output)


def ease_out(t):
    return 1.0 - (1.0 - min(max(t, 0.0), 1.0)) ** 3


def arrive(obj, first, last, drop):
    """Hidden until `first`; from `first` to `last` comes down `drop` metres onto its place."""
    home = obj.matrix_world.translation.copy()
    if first > 1:
        obj.hide_render = True
        obj.keyframe_insert("hide_render", frame=1)
        obj.keyframe_insert("hide_render", frame=first - 1)
    obj.hide_render = False
    obj.keyframe_insert("hide_render", frame=first)
    for f in range(first, last + 1):
        t = (f - first) / max(last - first, 1)
        obj.matrix_world.translation = home + Vector((0, 0, drop * (1.0 - ease_out(t))))
        obj.keyframe_insert("location", frame=f)
    obj.matrix_world.translation = home


def keyframe_orbit(cam, centre, radius, height, degrees, frames):
    """A steady turn: linear keyframes, set through the preference new keys are made with."""
    prefs = bpy.context.preferences.edit
    was = prefs.keyframe_new_interpolation_type
    prefs.keyframe_new_interpolation_type = "LINEAR"
    for f in (1, frames):
        a = -110 + degrees * (f - 1) / max(frames - 1, 1)
        cam.location = orbit(centre, radius, height, a)
        cam.rotation_euler = (Vector(centre) - cam.location).to_track_quat("-Z", "Y").to_euler()
        cam.keyframe_insert("location", frame=f)
        cam.keyframe_insert("rotation_euler", frame=f)
    prefs.keyframe_new_interpolation_type = was


def parse(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("out_dir")
    parser.add_argument("--scenes", required=True)
    parser.add_argument("--anatomy", required=True)
    parser.add_argument("--drop", type=float, default=3.0)
    parser.add_argument("--scene-seconds", type=float, default=0.4)
    parser.add_argument("--settle-seconds", type=float, default=0.6)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--orbit-degrees", type=float, default=90.0)
    parser.add_argument("--style", choices=("studio", "daylight"), default="daylight")
    return parser.parse_args(argv)


def main(argv):
    args = parse(argv)
    scene = bpy.context.scene
    scenes = json.load(open(args.scenes))["scenes"]
    anatomy = json.load(open(args.anatomy))
    lo, hi = (Vector(v) for v in anatomy["model"]["box"])
    centre, size, height = (lo + hi) / 2, max(hi - lo), hi.z - lo.z
    step = max(1, int(round(args.scene_seconds * args.fps)))
    settle = max(1, int(round(args.settle_seconds * args.fps)))
    plan = []
    for i, sc in enumerate(scenes):
        first = 1 + i * step
        last = first + settle
        for name in sc["pieces"]:
            obj = scene.objects.get(name)
            if obj is not None:
                arrive(obj, first, last, args.drop)
        plan.append({"index": sc["index"], "label": sc["label"], "frames": [first, last], "pieces": len(sc["pieces"])})
    frames = plan[-1]["frames"][1] + 1
    set_look(scene, args.style, centre=centre, size=size)
    pivot = Vector((centre.x, centre.y, lo.z + 0.4 * height))
    radius = 1.45 * size   # the judge cut a 1.15 orbit off at the frame edges on the finished hall
    cam = place_camera(scene, orbit(pivot, radius, 0.55 * height, -110), pivot, 35.0, focus=False)
    keyframe_orbit(cam, pivot, radius, 0.55 * height, args.orbit_degrees, frames)
    set_output(scene, args.width, args.height)
    for p in plan:
        scene.frame_set(p["frames"][1])
        render_still(scene, os.path.join(args.out_dir, f"raise-{p['index']}.png"))
    render_frames(scene, os.path.join(args.out_dir, "raise"), 1, frames)
    video = encode_video(os.path.join(args.out_dir, "raise"), os.path.join(args.out_dir, "raise.mp4"), args.fps)
    with open(os.path.join(args.out_dir, "raise.json"), "w") as f:
        json.dump({"scenes": plan, "frames": frames, "fps": args.fps, "video": video}, f, indent=1)
    print("RAISE", len(plan), "scenes", frames, "frames")


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1:])
