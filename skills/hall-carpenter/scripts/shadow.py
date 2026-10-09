"""A building's shadow from the front, the side and above, and one lit view of it.

A shadow is the flat outline a building throws straight onto a wall behind it: every piece drawn
white on nothing, through a camera with no perspective. Two buildings framed the same way can be
laid over each other, and the share of the outline they have in common is the overlap. The ground
takes no part, so a courtyard or a platform cannot make two halls look alike.
"""
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "model-anatomy", "scripts"))
from pieces import visible_pieces  # noqa: E402
from set_scene import place_camera, render_still, set_look, set_output, world_box  # noqa: E402

VIEWS = {"front": ((0, -1, 0), (math.pi / 2, 0, 0), (0, 2)),
         "side": ((-1, 0, 0), (math.pi / 2, 0, -math.pi / 2), (1, 2)),
         "above": ((0, 0, 1), (0, 0, 0), (0, 1))}
WIDE, PAD, FAR = 640, 0.05, 400.0


def building(scene):
    """Names of the pieces that make the building, and the box around them."""
    roles = visible_pieces(scene)
    names = [n for n, r in roles.items() if r != "ground"]
    boxes = [world_box(scene.objects[n]) for n in names]
    lo = Vector([min(b[0][i] for b in boxes) for i in range(3)])
    hi = Vector([max(b[1][i] for b in boxes) for i in range(3)])
    return names, lo, hi


def frame_of(lo, hi):
    """What every shadow is framed by: the box the first building was measured in, a little wider."""
    return {"centre": list((Vector(lo) + Vector(hi)) / 2), "size": [(hi[i] - lo[i]) * (1 + PAD) for i in range(3)]}


def show_only(scene, names):
    keep = set(names)
    for obj in scene.objects:
        if obj.type in {"MESH", "CURVE", "SURFACE", "FONT", "META"}:
            obj.hide_render = obj.name not in keep


def cast(scene, frame, folder, tag):
    """Render the three shadows as <folder>/<tag>-<view>.png; returns their paths by view."""
    os.makedirs(folder, exist_ok=True)
    scene.render.engine = "BLENDER_WORKBENCH"
    shading = scene.display.shading
    shading.light, shading.color_type, shading.single_color = "FLAT", "SINGLE", (1, 1, 1)
    shading.show_shadows = shading.show_cavity = False
    scene.display.render_aa = "OFF"
    scene.render.film_transparent = True
    scene.render.image_settings.file_format, scene.render.image_settings.color_mode = "PNG", "RGBA"
    scene.render.resolution_percentage = 100
    data = bpy.data.cameras.new("SHADOW cam")
    data.type, data.clip_start, data.clip_end = "ORTHO", 0.1, 4 * FAR
    cam = bpy.data.objects.new("SHADOW cam", data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    out = {}
    for view, (back, turn, (a, b)) in VIEWS.items():
        w, h = frame["size"][a], frame["size"][b]
        data.ortho_scale = max(w, h)
        scene.render.resolution_x, scene.render.resolution_y = WIDE, max(8, int(round(WIDE * h / w)))
        cam.location = Vector(frame["centre"]) + Vector(back) * FAR
        cam.rotation_euler = turn
        out[view] = render_still(scene, os.path.join(folder, f"{tag}-{view}.png"))
    return out


def mask(path):
    image = bpy.data.images.load(path)
    w, h = image.size
    alpha = np.array(image.pixels[:], dtype=np.float32).reshape(h, w, 4)[:, :, 3] > 0.5
    bpy.data.images.remove(image)
    return alpha


def overlap(path_a, path_b):
    """The share of the two outlines that is common to both: 1.0 is the same shadow."""
    a, b = mask(path_a), mask(path_b)
    if a.shape != b.shape:
        return 0.0
    joined = np.logical_or(a, b).sum()
    return float(np.logical_and(a, b).sum() / joined) if joined else 0.0


def lit_view(scene, lo, hi, path, width=960, height=540):
    """One daylight picture from the front corner, the same place for any building of this box."""
    lo, hi = Vector(lo), Vector(hi)
    centre, size = (lo + hi) / 2, max(hi - lo)
    set_look(scene, "studio", centre=centre, size=size)
    look = Vector((centre.x, centre.y, lo.z + 0.45 * (hi.z - lo.z)))
    place_camera(scene, look + Vector((0.55 * size, -1.05 * size, 0.30 * size)), look, 35.0, focus=False)
    set_output(scene, width, height)
    return render_still(scene, path)


def one_above_the_other(upper, lower, path):
    """Two pictures of one size, the first above the second. Side by side they were 1,932 wide and
    reached the eyes at half size; a post through the roof was six pixels and went unseen."""
    a, b = bpy.data.images.load(lower), bpy.data.images.load(upper)     # image rows run bottom-up
    (w, h), (w2, h2) = a.size, b.size
    if (w, h) != (w2, h2):
        raise SystemExit(f"the two views are not one size: {w}x{h} and {w2}x{h2}")
    pa = np.array(a.pixels[:], dtype=np.float32).reshape(h, w, 4)
    pb = np.array(b.pixels[:], dtype=np.float32).reshape(h, w, 4)
    gap = np.ones((12, w, 4), dtype=np.float32)
    joined = np.concatenate([pa, gap, pb], axis=0)
    out = bpy.data.images.new("ONE ABOVE THE OTHER", width=w, height=joined.shape[0], alpha=True)
    out.pixels = joined.ravel().tolist()
    out.filepath_raw, out.file_format = path, "PNG"
    out.save()
    return path
