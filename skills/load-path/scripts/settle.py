"""The settle test: every timber and rafter piece gets its weight and is let go. Pieces drawn
through one another are held together as one rigid group, the way a notched joint holds; the
rafters and the roof covering move as one roof; the ground is fixed; walls take no part. Four
seconds are baked, what moved is painted, and the frames are rendered. All on the copy in
memory; the model file is never saved. Settings are the physics check's proven ones. Run as the
shake test (shake.py) the ground also moves, along the path quake.py gives.
Usage: blender -b model.blend --python-exit-code 1 --python settle.py -- out_dir --anatomy anatomy.json
           [--seconds 4] [--fps 24] [--width 1280] [--height 720] [--camera outside|frame]
"""
import argparse
import json
import os
import sys

import math

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "model-anatomy", "scripts"))
from rigid import (CLAY, FRICTION, MARGIN, TIMBER, attach, block_stem, centre_and_volume,  # noqa: E402
                   groups, holder_for, is_box, recentre, solver_mass)
from quake import G, LEAD, PAUSE, SECONDS, SITE, ground_path, shaking_seconds, sideways_pull  # noqa: E402
from pieces import refuse_if_stale  # noqa: E402
from set_scene import (encode_video, orbit, place_camera, render_frames, render_still,  # noqa: E402
                       set_look, set_output)

FELL, SHIFTED = (0.85, 0.05, 0.03), (1.0, 0.5, 0.0)
# The solver multiplies the two touching bodies' friction, so FRICTION (0.4) on every body grips as
# 0.16: stricter than timber on timber or on stone, which is no fault in a let-go test. A sideways pull
# would slide every loose piece on that, the real temple's too, so the shake test gives each
# body 1.0 and the pair grips as 1.0: the solver lets a light block squeezed between heavy bodies
# creep under a steady pull, and the test looks for what tips, not what slides. Found in testing: a
# plank on the slab slid 1.5 m under the pull before this.
GRIP = {"friction": FRICTION}


def ctx(scene, **kw):
    return bpy.context.temp_override(scene=scene, view_layer=scene.view_layers[0], **kw)


def add_bodies(scene, objs, kind):
    if objs:
        with ctx(scene, selected_objects=objs, active_object=objs[0], object=objs[0]):
            bpy.ops.rigidbody.objects_add(type=kind)


def settle_shape(obj, volume):
    rb = obj.rigid_body
    rb.collision_shape = "BOX" if is_box(obj, volume) else "CONVEX_HULL"
    rb.use_margin, rb.collision_margin = True, MARGIN
    rb.friction, rb.restitution, rb.use_deactivation = GRIP["friction"], 0.0, False


def shake_ground(scene, ground, shake):
    """The ground follows the path, an animated body the solver cannot push, carrying what stands on
    it; then everything is pulled steadily along the same line, as gravity leaning over."""
    along = Vector((math.cos(math.radians(shake["degrees"])), math.sin(math.radians(shake["degrees"])), 0.0))
    for obj in ground:
        obj.rigid_body.kinematic = True
        home = obj.matrix_world.copy()
        for frame, offset in enumerate(shake["path"], start=1):
            moved = home.copy()
            moved.translation = home.translation + along * offset
            obj.matrix_world = moved
            obj.keyframe_insert("location", frame=frame)
        obj.matrix_world = home
    for frame, pull in enumerate(shake["pull"], start=1):
        scene.gravity = (-along.x * pull * G, -along.y * pull * G, -G)
        scene.keyframe_insert("gravity", frame=frame)


def covering_mass(scene, names):
    return sum(centre_and_volume(scene.objects[n])[1] * CLAY for n in names)


def lock_groups(scene, multi, volume, roof, covering, extra):
    """One holder per multi-piece group, a compound body; the roof group also carries the covering."""
    group_of = {}
    for i, c in enumerate(multi):
        objs = [scene.objects[n] for n in c]
        mass = sum(volume[n] * TIMBER for n in c)
        weight = max(sum(volume[n] for n in c), 1e-9)
        centre = sum((o.matrix_world.translation * volume[o.name] for o in objs), Vector()) / weight
        holder = holder_for(scene, f"SIM locked group {i:03d} ({len(c)} pieces)", centre)
        add_bodies(scene, [holder], "ACTIVE")
        holder.rigid_body.collision_shape = "COMPOUND"
        holder.rigid_body.friction, holder.rigid_body.use_deactivation = GRIP["friction"], False
        for o in objs:
            attach(o, holder)
            group_of[o.name] = holder.name
        if roof and roof[0] in c:
            for n in covering:
                attach(scene.objects[n], holder)
            mass += extra
        holder.rigid_body.mass = solver_mass(mass)
    return group_of


def block_pairs(rests_on):
    """Seats of one block (an ear on its seat, a seat on its foot), read off the bearing map."""
    return [(n, c["on"]) for n, contacts in rests_on.items() for c in contacts
            if block_stem(n) is not None and block_stem(n) == block_stem(c["on"])]


def build(scene, roles, frames, pairs=(), shake=None):
    names = [n for n, r in roles.items() if r in ("timber", "rafter") and n in scene.objects]
    ground = [scene.objects[n] for n, r in roles.items() if r == "ground" and n in scene.objects]
    covering = [n for n, r in roles.items() if r == "covering" and n in scene.objects]
    volume = {}
    for o in [scene.objects[n] for n in names] + ground:
        centre, volume[o.name] = centre_and_volume(o)
        recentre(o, centre, ease=roles.get(o.name) != "ground")
    scene.view_layers[0].update()
    before = {n: scene.objects[n].matrix_world.translation.copy() for n in names}
    roof = [n for n in names if roles[n] == "rafter"]
    multi = sorted((c for c in groups(scene, names, roof, block_stem, pairs) if len(c) > 1), key=len, reverse=True)
    with ctx(scene):
        bpy.ops.rigidbody.world_add()
    world = scene.rigidbody_world
    world.substeps_per_frame, world.solver_iterations, world.use_split_impulse = 60, 60, True
    world.point_cache.frame_start, world.point_cache.frame_end = 1, frames
    scene.frame_start, scene.frame_end = 1, frames
    add_bodies(scene, ground, "PASSIVE")
    for o in ground:
        settle_shape(o, volume[o.name])
    if shake:
        shake_ground(scene, ground, shake)
    movers = [scene.objects[n] for n in names]
    add_bodies(scene, movers, "ACTIVE")
    for o in movers:
        settle_shape(o, volume[o.name])
        o.rigid_body.mass = solver_mass(volume[o.name] * TIMBER)
    group_of = lock_groups(scene, multi, volume, roof, covering, covering_mass(scene, covering))
    return names, group_of, len(multi), before


def run(scene, names, group_of, before, frames, midway=None):
    """Bake and measure what moved by the last frame; in the shake test also by `midway`, the frame
    the shaking ends and before the steady pull begins, so a fall is known by which push caused it."""
    depsgraph = bpy.context.evaluated_depsgraph_get()

    def pose():
        return {n: scene.objects[n].evaluated_get(depsgraph).matrix_world.copy() for n in names}

    scene.frame_set(1)
    start = pose()
    drift = max((start[n].translation - before[n]).length for n in names)
    if drift > 1e-4:
        raise SystemExit(f"pieces do not start where the model has them: {drift:.4f} m")
    with ctx(scene):
        bpy.ops.ptcache.bake_all(bake=True)
    half = None
    if midway:
        scene.frame_set(midway)
        half = pose()
    scene.frame_set(frames)
    end = pose()
    moved = {}
    for n in names:
        a, b = start[n], end[n]
        turn = a.to_quaternion().rotation_difference(b.to_quaternion()).angle
        turn = min(turn, 2 * math.pi - turn)      # a quaternion and its negative are one pose: 360 degrees is none
        moved[n] = {"moved_m": (b.translation - a.translation).length, "drop_m": a.translation.z - b.translation.z,
                    "turned_deg": turn * 57.2958, "group": group_of.get(n)}
        if half:
            moved[n]["moved_in_the_shaking_m"] = (half[n].translation - a.translation).length
    return moved


def paint(name, colour):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*colour, 1.0)
    bsdf.inputs["Emission Color"].default_value = (*colour, 1.0)
    bsdf.inputs["Emission Strength"].default_value = 0.6
    return mat


def paint_movers(scene, moved):
    fell, shifted = paint("SHOWPIECE fell", FELL), paint("SHOWPIECE shifted", SHIFTED)
    counts = {"fell": 0, "shifted": 0}
    for name, rec in moved.items():
        mat = fell if rec["moved_m"] > 1.0 else shifted if rec["moved_m"] > 0.10 else None
        if mat is None:
            continue
        counts["fell" if mat is fell else "shifted"] += 1
        obj = scene.objects[name]
        if not obj.material_slots:
            obj.data.materials.append(None)
        for slot in obj.material_slots:
            slot.link, slot.material = "OBJECT", mat
    return counts


def shake_summary(shake, moved):
    """What the shake test found, and the sentence that says so. A piece has come down when it dropped
    10 cm, tipped 10 degrees or ended a metre from where it stood. Sliding level is drift, and is told
    but is not a fall: the adopted rebuilt hall's roof slid 17 cm on its column heads under the pull
    and nothing in it dropped or tipped."""
    down = [n for n, r in moved.items() if r["drop_m"] > 0.10 or r["turned_deg"] > 10.0 or r["moved_m"] > 1.0]
    early = sum(1 for r in moved.values() if r["moved_in_the_shaking_m"] > 0.10)
    drift = max((r["moved_m"] for n, r in moved.items() if n not in down), default=0.0)
    found = {**{k: v for k, v in shake.items() if k not in ("path", "pull")}, "amplitude_mm": round(max(shake["path"]) * 1000, 1),
             "moved_in_the_shaking": early, "came_down": len(down), "came_down_names": down[:20], "drift_m": round(drift, 3)}
    told = (f" | the ground moved {found['amplitude_mm']} mm each way at {shake['hz']:g} Hz, peak {shake['peak_g']:g} g, for "
            f"{shake['shaking_seconds']:g} s, then a steady sideways pull of {shake['pull_g']:g} g | {len(down)} came down"
            + (": " + ", ".join(down[:4]) if down else "") + f" | {early} had moved when the shaking ended | the rest "
            f"drifted at most {drift:.2f} m")
    return found, told


def parse(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("out_dir")
    parser.add_argument("--anatomy", required=True)
    parser.add_argument("--bearing", help="bearing.json; a block's foot, seat and ears then travel as one piece")
    parser.add_argument("--seconds", type=float)
    parser.add_argument("--peak-g", type=float, default=SITE["peak_g"], help="shake test only")
    parser.add_argument("--hz", type=float, default=SITE["hz"], help="shake test only")
    parser.add_argument("--pull-g", type=float, default=SITE["pull_g"], help="shake test only")
    parser.add_argument("--video", action="store_true", help="shake test only: render every frame, not just the stills")
    parser.add_argument("--fps", type=int, default=24)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--camera", choices=("outside", "frame"), default="frame")
    parser.add_argument("--style", choices=("studio", "daylight"), default="daylight")
    return parser.parse_args(argv)


def main(argv, shaking=False):
    args = parse(argv)
    tag, seconds = ("shake", args.seconds or SECONDS) if shaking else ("settle", args.seconds or 4.0)
    scene = bpy.context.scene
    anatomy = json.load(open(args.anatomy))
    roles = {n: p["role"] for n, p in anatomy["pieces"].items()}
    refuse_if_stale(scene, roles, f"load-path {tag}")
    frames = max(2, int(round(seconds * args.fps)))
    pairs = block_pairs(json.load(open(args.bearing))["rests_on"]) if args.bearing else ()
    shake = {"peak_g": args.peak_g, "hz": args.hz, "pull_g": args.pull_g, "degrees": SITE["degrees"], "source": SITE["source"],
             "shaking_seconds": round(shaking_seconds(frames, args.fps), 2),
             "path": ground_path(frames, args.fps, args.peak_g, args.hz),
             "pull": sideways_pull(frames, args.fps, args.pull_g)} if shaking else None
    GRIP["friction"] = 1.0 if shaking else FRICTION
    names, group_of, n_groups, before = build(scene, roles, frames, pairs, shake)
    midway = int((LEAD + shake["shaking_seconds"] + PAUSE / 2) * args.fps) if shake else None
    moved = run(scene, names, group_of, before, frames, midway)
    counts = paint_movers(scene, moved)
    lo, hi = (Vector(v) for v in anatomy["model"]["box"])
    centre, size, height = (lo + hi) / 2, max(hi - lo), hi.z - lo.z
    if args.camera == "frame":
        for n, r in roles.items():
            if r in ("covering", "rafter") and n in scene.objects:
                scene.objects[n].hide_render = True
    pivot = Vector((centre.x, centre.y, lo.z + 0.45 * height))
    set_look(scene, args.style, centre=centre, size=size)
    place_camera(scene, orbit(pivot, 1.1 * size, 0.5 * height, -60), pivot, 35.0, focus=False)
    set_output(scene, args.width, args.height)
    for when, f in (("start", 1), ("end", frames)):
        scene.frame_set(f)
        render_still(scene, os.path.join(args.out_dir, f"{tag}-{when}.png"))
    video = False
    if args.video or not shaking:     # the ground moves millimetres: the shake's stills say what a video would
        render_frames(scene, os.path.join(args.out_dir, tag), 1, frames)
        video = encode_video(os.path.join(args.out_dir, tag), os.path.join(args.out_dir, f"{tag}.mp4"), args.fps)
    summary = {**counts, "groups": n_groups, "frames": frames, "seconds": round(frames / args.fps, 2), "video": video}
    summary["shake"], told = shake_summary(shake, moved) if shake else (None, "")
    with open(os.path.join(args.out_dir, f"{tag}.json"), "w") as f:
        json.dump({"pieces": moved, "summary": summary}, f, indent=1)
    print(f"{tag.upper()} {len(names)} pieces fell {counts['fell']} shifted {counts['shifted']}{told}")


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1:])
