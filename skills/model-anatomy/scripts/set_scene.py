"""Setting the stage for a render: what to hide, where the camera stands, how it is lit, and
how frames become a video. Shared by every showpiece tool; nothing here saves the model.

Object origins in the hall are not at the geometry, so every distance here uses the world
bounding box of a piece, never its location.
"""
import math
import os
import shutil
import subprocess

import bpy
from mathutils import Vector

CAMERA = "SHOWPIECE cam"
LIGHTS = ("SHOWPIECE key", "SHOWPIECE fill", "SHOWPIECE rim")
# The plain look: Blender's solid view, flat colours by role instead of the temple's textures, chosen
# for the films that teach (operator). The colours are the page's 3D view's
# (studio/showpiece/page/plans.mjs), so the film and the live view agree.
ROLE_TINT = {"timber": (0.72, 0.50, 0.31), "rafter": (0.60, 0.40, 0.25), "covering": (0.36, 0.40, 0.46),
             "wall": (0.90, 0.85, 0.75), "ground": (0.66, 0.63, 0.58)}
GHOST = 0.12          # how solid a see-through piece is drawn: the roof, or what is not the subject
CAPTION_FONT = "Noto Sans CJK Regular.woff2"   # Blender's own, in its datafiles, so captions need nothing installed
CAPTION_SIZE = 0.055  # at 0.6 m from the lens, Chinese letters about a twentieth of the picture high


def world_box(obj):
    corners = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    return (Vector([min(c[i] for c in corners) for i in range(3)]),
            Vector([max(c[i] for c in corners) for i in range(3)]))


def hide_beyond(scene, centre, radius):
    """Hide from the render every piece whose box centre is farther than radius; returns how many stay."""
    kept = 0
    for obj in scene.objects:
        if obj.type not in {"MESH", "CURVE"}:
            continue
        lo, hi = world_box(obj)
        far = ((lo + hi) / 2 - Vector(centre)).length > radius
        obj.hide_render = far or obj.hide_render
        kept += not obj.hide_render
    return kept


def place_camera(scene, at, look, lens_mm=50.0, focus=True):
    at, look = Vector(at), Vector(look)
    data = bpy.data.cameras.new(CAMERA)
    data.lens = lens_mm
    data.clip_end = 5000.0
    if focus:
        data.dof.use_dof = True
        data.dof.focus_distance = (look - at).length
        data.dof.aperture_fstop = 5.6
    cam = bpy.data.objects.new(CAMERA, data)
    scene.collection.objects.link(cam)
    cam.location = at
    cam.rotation_euler = (look - at).to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam
    return cam


def _light(scene, name, kind, energy, at, look, size=None):
    data = bpy.data.lights.new(name, kind)
    data.energy = energy
    if size is not None:
        data.size = size
    obj = bpy.data.objects.new(name, data)
    scene.collection.objects.link(obj)
    obj.location = Vector(at)
    obj.rotation_euler = (Vector(look) - Vector(at)).to_track_quat("-Z", "Y").to_euler()
    return obj


def set_look(scene, look, centre=(0, 0, 0), size=4.0):
    """studio: near-black backdrop and three lights around `centre`; daylight: the model's own
    lights, or the studio's when it has none (a bare fixture would otherwise render black)."""
    if look != "studio" and any(obj.type == "LIGHT" for obj in scene.objects):
        return
    world = bpy.data.worlds.new("SHOWPIECE world")
    world.use_nodes = True
    nodes = world.node_tree.nodes
    nodes.clear()
    bg, out = nodes.new("ShaderNodeBackground"), nodes.new("ShaderNodeOutputWorld")
    bg.inputs[0].default_value = (0.012, 0.012, 0.014, 1.0)
    bg.inputs[1].default_value = 1.0
    world.node_tree.links.new(bg.outputs[0], out.inputs[0])
    scene.world = world
    for obj in list(scene.objects):
        if obj.type == "LIGHT":
            obj.hide_render = True
    c = Vector(centre)
    _light(scene, LIGHTS[0], "SUN", 2.0, c + Vector((size, -size, 1.4 * size)), c)
    _light(scene, LIGHTS[1], "AREA", 220.0 * size, c + Vector((-1.5 * size, -size, 0.6 * size)), c, size=size)
    _light(scene, LIGHTS[2], "AREA", 120.0 * size, c + Vector((0.4 * size, 1.6 * size, size)), c, size=size / 2)
    # A low fill so the underside of a lifted piece (a mortise, a notch) reads instead of going black.
    _light(scene, "SHOWPIECE under", "AREA", 80.0 * size, c + Vector((-0.6 * size, -0.8 * size, -0.5 * size)), c,
           size=size / 2)


def hide_above(scene, z):
    """Hide from the render every piece whose bottom is above z: peel the roof off a close-up."""
    hidden = 0
    for obj in scene.objects:
        if obj.type in {"MESH", "CURVE"} and not obj.hide_render and world_box(obj)[0].z > z:
            obj.hide_render = True
            hidden += 1
    return hidden


def set_output(scene, width, height, fmt="PNG"):
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x, scene.render.resolution_y = int(width), int(height)
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = fmt
    scene.render.film_transparent = False


def render_still(scene, path):
    scene.render.filepath = os.path.abspath(path)
    bpy.ops.render.render(write_still=True)
    return path


def render_frames(scene, folder, first, last):
    os.makedirs(folder, exist_ok=True)
    scene.frame_start, scene.frame_end = first, last
    scene.render.filepath = os.path.join(os.path.abspath(folder), "f")
    bpy.ops.render.render(animation=True)
    return folder


def encode_video(folder, mp4_path, fps):
    """Frames f0001.png... into an H.264 MP4 any browser plays; False when ffmpeg is missing."""
    ffmpeg = shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"
    if not os.path.isfile(ffmpeg):
        return False
    subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-framerate", str(fps),
                    "-i", os.path.join(folder, "f%04d.png"), "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-crf", "18", os.path.abspath(mp4_path)], check=True)
    return True


def plain_look(scene, background=(0.93, 0.91, 0.87)):
    """Render with the solid engine: each object in its own colour (obj.color, alpha for see-through),
    studio light, cavities and outlines so the pieces read. Call after set_output, which picks EEVEE."""
    scene.render.engine = "BLENDER_WORKBENCH"
    shading = scene.display.shading
    shading.light, shading.color_type = "STUDIO", "OBJECT"
    shading.show_cavity, shading.cavity_type = True, "BOTH"
    shading.show_object_outline, shading.object_outline_color = True, (0.25, 0.22, 0.2)
    world = scene.world or bpy.data.worlds.new("SHOWPIECE plain")
    scene.world, world.color = world, background


def card_mesh(width, height):
    mesh = bpy.data.meshes.new("SHOWPIECE caption card")
    mesh.from_pydata([(0, 0, 0), (width, 0, 0), (width, height, 0), (0, height, 0)], [], [(0, 1, 2, 3)])
    return mesh


def captions(scene, camera, lines):
    """Words burned into the film, top left on a pale card, each shown over its frames: (text, first, last).
    For the plain look below; a 35 mm camera, which every showpiece film uses."""
    path = os.path.join(bpy.utils.system_resource("DATAFILES") or "", "fonts", CAPTION_FONT)
    if not os.path.isfile(path):
        print(f"no {CAPTION_FONT} in this Blender; the film has no captions")
        return
    font = bpy.data.fonts.load(path, check_existing=True)
    for text, first, last in lines:
        data = bpy.data.curves.new("SHOWPIECE caption", "FONT")
        data.body, data.font, data.size = text, font, CAPTION_SIZE
        obj = bpy.data.objects.new("SHOWPIECE caption", data)
        scene.collection.objects.link(obj)
        # 0.6 m in front of a 35 mm lens shows 0.62 m across and 0.35 m up: top left, inside the margin.
        obj.parent, obj.location, obj.color = camera, (-0.285, 0.125, -0.6), (0.16, 0.1, 0.07, 1.0)
        bpy.context.view_layer.update()
        pad = 0.25 * CAPTION_SIZE                   # the card is the words' own measured size and a margin
        card = bpy.data.objects.new("SHOWPIECE caption card", card_mesh(obj.dimensions.x + 2 * pad, obj.dimensions.y + 2 * pad))
        scene.collection.objects.link(card)
        card.parent, card.location, card.color = camera, (-0.285 - pad, 0.125 - pad - 0.12 * CAPTION_SIZE, -0.601), (1, 1, 1, 0.8)
        for shown in (obj, card):
            for frame, hidden in ((first - 1, True), (first, False), (last, False), (last + 1, True)):
                shown.hide_render = hidden
                shown.keyframe_insert("hide_render", frame=max(0, frame))


def parse_xyz(text):
    return Vector([float(v) for v in text.split(",")])


def orbit(centre, radius, height, angle_deg):
    """A camera position on a circle around `centre`, for tours and slow turns."""
    a = math.radians(angle_deg)
    return Vector(centre) + Vector((radius * math.cos(a), radius * math.sin(a), height))
