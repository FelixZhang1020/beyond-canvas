"""Where the weight goes, as colour coming down: every timber and rafter piece is painted by
what it carries, on a log scale from deep blue to red, and the colours are revealed from the
roof downward. One shared material reads each object's own colour, which is keyframed, so no
material is made per piece. The covering is hidden so the frame shows. Keyframed on the copy
in memory; the model file is never saved.
Usage: blender -b model.blend --python-exit-code 1 --python flow.py -- out_dir --anatomy anatomy.json --loads loads.json
           [--seconds 6] [--hold 2] [--fps 30] [--width 1280] [--height 720] [--lo-kN 0.5] [--hi-kN 1000]
           [--orbit-degrees 40] [--style daylight|studio]
"""
import argparse
import json
import math
import os
import sys

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "model-anatomy", "scripts"))
from set_scene import (encode_video, orbit, place_camera, render_frames, render_still,  # noqa: E402
                       set_look, set_output)

RAMP = [(0.0, (0.12, 0.10, 0.45)), (0.25, (0.05, 0.55, 0.85)), (0.5, (0.15, 0.75, 0.30)),
        (0.7, (0.95, 0.85, 0.15)), (0.85, (0.95, 0.45, 0.08)), (1.0, (0.75, 0.05, 0.05))]
GREY = (0.32, 0.30, 0.27, 1.0)
BLEND = 6


def colour_for(kn, lo, hi):
    t = 0.0 if kn <= lo else min(1.0, math.log(kn / lo) / math.log(hi / lo))
    for (t0, c0), (t1, c1) in zip(RAMP, RAMP[1:]):
        if t <= t1:
            u = (t - t0) / (t1 - t0)
            return tuple(c0[i] + (c1[i] - c0[i]) * u for i in range(3)) + (1.0,)
    return RAMP[-1][1] + (1.0,)


def load_material():
    mat = bpy.data.materials.new("SHOWPIECE load")
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    bsdf = nodes.get("Principled BSDF")
    info = nodes.new("ShaderNodeObjectInfo")
    links.new(info.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.65
    return mat


def paint(obj, mat):
    if not obj.material_slots:
        obj.data.materials.append(None)
    for slot in obj.material_slots:
        slot.link = "OBJECT"
        slot.material = mat


def reveal(obj, colour, frame, blend=BLEND):
    obj.color = GREY
    obj.keyframe_insert("color", frame=max(1, frame - blend))
    obj.color = colour
    obj.keyframe_insert("color", frame=frame)


def turn(cam, pivot, radius, height, degrees, frames):
    prefs = bpy.context.preferences.edit
    was = prefs.keyframe_new_interpolation_type
    prefs.keyframe_new_interpolation_type = "LINEAR"
    for f, a in ((1, -125), (frames, -125 + degrees)):
        cam.location = orbit(pivot, radius, height, a)
        cam.rotation_euler = (pivot - cam.location).to_track_quat("-Z", "Y").to_euler()
        cam.keyframe_insert("location", frame=f)
        cam.keyframe_insert("rotation_euler", frame=f)
    prefs.keyframe_new_interpolation_type = was


def parse(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("out_dir")
    parser.add_argument("--anatomy", required=True)
    parser.add_argument("--loads", required=True)
    parser.add_argument("--seconds", type=float, default=6.0)
    parser.add_argument("--hold", type=float, default=2.0)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--lo-kN", type=float, default=0.5)
    parser.add_argument("--hi-kN", type=float, default=1000.0)
    parser.add_argument("--orbit-degrees", type=float, default=40.0)
    parser.add_argument("--style", choices=("studio", "daylight"), default="daylight")
    return parser.parse_args(argv)


def main(argv):
    args = parse(argv)
    scene = bpy.context.scene
    anatomy = json.load(open(args.anatomy))
    loads = json.load(open(args.loads))["pieces"]
    pieces = anatomy["pieces"]
    lo, hi = (Vector(v) for v in anatomy["model"]["box"])
    centre, size, height = (lo + hi) / 2, max(hi - lo), hi.z - lo.z
    mat = load_material()
    frames_reveal = max(2, int(round(args.seconds * args.fps)))
    frames = frames_reveal + int(round(args.hold * args.fps))
    blend = min(BLEND, max(1, frames_reveal // 4))
    span = max(1, frames_reveal - blend - 1)
    plan = []
    for name, p in pieces.items():
        obj = scene.objects.get(name)
        if obj is None:
            continue
        if p["role"] == "covering":
            obj.hide_render = True
            continue
        if p["role"] not in ("timber", "rafter"):
            continue
        paint(obj, mat)
        colour = colour_for(loads[name]["carries_N"] / 1e3, args.lo_kN, args.hi_kN)
        frame = 1 + blend + int((hi.z - p["zmax"]) / max(height, 1e-6) * span)
        reveal(obj, colour, frame, blend)
        plan.append({"name": name, "colour": list(colour[:3]), "reveal_frame": frame, "carries_N": loads[name]["carries_N"]})
    set_look(scene, args.style, centre=centre, size=size)
    pivot = Vector((centre.x, centre.y, lo.z + 0.4 * height))
    cam = place_camera(scene, orbit(pivot, 1.15 * size, 0.5 * height, -125), pivot, 35.0, focus=False)
    turn(cam, pivot, 1.15 * size, 0.5 * height, args.orbit_degrees, frames)
    set_output(scene, args.width, args.height)
    for tag, f in (("start", 1), ("half", frames_reveal // 2), ("end", frames)):
        scene.frame_set(f)
        render_still(scene, os.path.join(args.out_dir, f"flow-{tag}.png"))
    render_frames(scene, os.path.join(args.out_dir, "flow"), 1, frames)
    video = encode_video(os.path.join(args.out_dir, "flow"), os.path.join(args.out_dir, "flow.mp4"), args.fps)
    with open(os.path.join(args.out_dir, "flow.json"), "w") as f:
        json.dump({"pieces": plan, "scale_kN": [args.lo_kN, args.hi_kN], "frames": frames, "fps": args.fps,
                   "video": video}, f, indent=1)
    print("FLOW", len(plan), "pieces", frames, "frames")


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1:])
