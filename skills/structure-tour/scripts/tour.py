"""A camera tour of the building: around the outside, in through the front, up under the
ceiling, and over the top with the roof peeled off. Segments are camera moves between two poses
with some roles hidden; everything is keyframed on the copy in memory and rendered, and the
model file is never saved.
Usage: blender -b model.blend --python-exit-code 1 --python tour.py -- out_dir --anatomy anatomy.json
           [--segments outside,door,inside,overhead] [--seconds-per 4] [--fps 30] [--width 1280] [--height 720]
           [--style daylight|studio]
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

ORDER = ("outside", "door", "inside", "overhead")


def poses(lo, hi):
    """Each segment: camera start and end, look start and end, roles hidden."""
    lo, hi = Vector(lo), Vector(hi)
    c = (lo + hi) / 2
    size, height, depth = max(hi - lo), hi.z - lo.z, hi.y - lo.y
    eye = lo.z + 0.12 * height
    mid = Vector((c.x, c.y, lo.z + 0.45 * height))
    return {
        "outside": (orbit(mid, 1.1 * size, 0.0, -120), orbit(mid, 1.1 * size, 0.0, -30), mid, mid, []),
        "door": (Vector((c.x, lo.y - 0.9 * size, eye)), Vector((c.x, lo.y - 0.15 * size, eye)),
                 Vector((c.x, c.y, lo.z + 0.3 * height)), Vector((c.x, c.y, lo.z + 0.3 * height)), []),
        "inside": (Vector((c.x, lo.y + 0.25 * depth, eye)), Vector((c.x, c.y - 0.1 * depth, eye)),
                   Vector((c.x, c.y, lo.z + 0.5 * height)), Vector((c.x, c.y + 0.35 * depth, lo.z + 0.85 * height)),
                   ["wall"]),
        "overhead": (Vector((c.x, c.y - 0.4 * size, hi.z + 0.6 * size)), Vector((c.x, c.y + 0.2 * size, hi.z + 0.9 * size)),
                     Vector((c.x, c.y, lo.z + 0.5 * height)), Vector((c.x, c.y, lo.z + 0.5 * height)),
                     ["covering", "rafter"]),
    }


def interior_fill(scene, centre, height):
    """A soft light inside the hall, so the ceiling and brackets read on the inside segment."""
    data = bpy.data.lights.new("SHOWPIECE interior", "POINT")
    data.energy = 4000.0 * max(height, 1.0)
    data.shadow_soft_size = 2.0
    obj = bpy.data.objects.new("SHOWPIECE interior", data)
    scene.collection.objects.link(obj)
    obj.location = Vector((centre.x, centre.y, centre.z))


def aim(cam, at, look):
    cam.location = at
    cam.rotation_euler = (Vector(look) - Vector(at)).to_track_quat("-Z", "Y").to_euler()


def keyframe_hidden(scene, roles_by_name, segments, per):
    """Pieces of a hidden role vanish for that segment's frames and are back for the next."""
    for i, seg in enumerate(segments):
        first, last = 1 + i * per, (i + 1) * per
        for name, role in roles_by_name.items():
            obj = scene.objects.get(name)
            if obj is None or obj.hide_render:
                continue
            hidden = role in seg["hidden_roles"]
            obj.hide_render = hidden
            obj.keyframe_insert("hide_render", frame=first)
            obj.keyframe_insert("hide_render", frame=last)
            obj.hide_render = False


def keyframe_camera(cam, segments, per):
    """New keyframes are Bezier with auto-clamped handles, so each move eases in and out."""
    for i, seg in enumerate(segments):
        first, last = 1 + i * per, (i + 1) * per
        aim(cam, seg["at"][0], seg["look"][0])
        cam.keyframe_insert("location", frame=first)
        cam.keyframe_insert("rotation_euler", frame=first)
        aim(cam, seg["at"][1], seg["look"][1])
        cam.keyframe_insert("location", frame=last)
        cam.keyframe_insert("rotation_euler", frame=last)


def parse(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("out_dir")
    parser.add_argument("--anatomy", required=True)
    parser.add_argument("--segments", default=",".join(ORDER))
    parser.add_argument("--seconds-per", type=float, default=4.0)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--style", choices=("studio", "daylight"), default="daylight")
    return parser.parse_args(argv)


def main(argv):
    args = parse(argv)
    scene = bpy.context.scene
    anatomy = json.load(open(args.anatomy))
    lo, hi = anatomy["model"]["box"]
    table = poses(lo, hi)
    per = max(2, int(round(args.seconds_per * args.fps)))
    segments = []
    for name in args.segments.split(","):
        a0, a1, l0, l1, hidden = table[name]
        segments.append({"name": name, "at": [list(a0), list(a1)], "look": [list(l0), list(l1)],
                         "hidden_roles": hidden, "frames": [1 + len(segments) * per, (len(segments) + 1) * per]})
    roles = {n: p["role"] for n, p in anatomy["pieces"].items()}
    keyframe_hidden(scene, roles, segments, per)
    centre = (Vector(lo) + Vector(hi)) / 2
    set_look(scene, args.style, centre=centre, size=max(Vector(hi) - Vector(lo)))
    interior_fill(scene, centre, hi[2] - lo[2])
    cam = place_camera(scene, segments[0]["at"][0], segments[0]["look"][0], 35.0, focus=False)
    keyframe_camera(cam, segments, per)
    set_output(scene, args.width, args.height)
    for seg in segments:
        scene.frame_set(seg["frames"][1])
        render_still(scene, os.path.join(args.out_dir, f"tour-{seg['name']}.png"))
    frames = len(segments) * per
    render_frames(scene, os.path.join(args.out_dir, "tour"), 1, frames)
    video = encode_video(os.path.join(args.out_dir, "tour"), os.path.join(args.out_dir, "tour.mp4"), args.fps)
    with open(os.path.join(args.out_dir, "tour.json"), "w") as f:
        json.dump({"segments": segments, "frames": frames, "fps": args.fps, "video": video}, f, indent=1)
    print("TOUR", len(segments), "segments", frames, "frames")


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1:])
