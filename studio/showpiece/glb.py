"""Export a model's pieces as one GLB for the exhibit's live 3D view, every piece its own node
under its Blender name, so the page can move the pieces the way the agent's plans say.

    blender -b model.blend --python-exit-code 1 --python studio/showpiece/glb.py -- out.glb [--light]

`--light` is for a big model: the ground pieces (paving) become one node, the roof covering is
thinned to a fraction of its faces, and only positions and colours ship (no normals, no textures). The changes happen to the
copy in memory only; the model file is never saved. Cameras, lights and pieces that play no part
in the anatomy are left out. Prints EXPORT <nodes> nodes <MB> MB <seconds> s.
"""
import argparse
import os
import sys
import time

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "skills", "model-anatomy", "scripts"))
from pieces import role_of  # noqa: E402

COVERING_RATIO = 0.08


def parse(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("out")
    parser.add_argument("--light", action="store_true", help="one ground node, thinned covering, small textures")
    parser.add_argument("--covering-ratio", type=float, default=COVERING_RATIO)
    parser.add_argument("--no-textures", action="store_true")
    return parser.parse_args(argv)


def keep_pieces(scene):
    """Remove everything that is not a piece; return the pieces by role."""
    roles = {}
    for obj in list(scene.objects):
        role = role_of(obj)
        if role is None:
            bpy.data.objects.remove(obj, do_unlink=True)
            continue
        obj.hide_viewport = obj.hide_render = False
        obj.hide_set(False)
        roles.setdefault(role, []).append(obj)
    return roles


def lighten(roles, ratio):
    """One node for the ground, and the covering thinned: what a browser can turn smoothly."""
    ground = [o for o in roles.get("ground", []) if o.type == "MESH"]
    if len(ground) > 1:
        with bpy.context.temp_override(active_object=ground[0], selected_editable_objects=ground, selected_objects=ground):
            bpy.ops.object.join()
        ground[0].name = "Ground"
        roles["ground"] = [ground[0]]     # the others are gone with the join
    for obj in roles.get("covering", []):
        if obj.type == "MESH" and len(obj.data.polygons) > 200:
            mod = obj.modifiers.new("thin", "DECIMATE")
            mod.ratio = ratio


def image_behind(socket, depth=6):
    """The first image texture feeding a socket, through mixes and ramps, a few hops up."""
    if depth == 0 or not socket.is_linked:
        return None
    node = socket.links[0].from_node
    if node.type == "TEX_IMAGE":
        return node.image
    for upstream in node.inputs:
        found = image_behind(upstream, depth - 1)
        if found is not None:
            return found
    return None


def bake_colours(roles):
    """A material that takes its colour from an image keeps that image's mean colour instead, since
    no textures ship in the light form: the columns stay red and the tiles grey."""
    done = set()
    for objs in roles.values():
        for obj in objs:
            for slot in obj.material_slots:
                mat = slot.material
                if mat is None or mat.name in done or not mat.use_nodes:
                    continue
                done.add(mat.name)
                bsdf = next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
                base = bsdf.inputs.get("Base Color") if bsdf else None
                image = image_behind(base) if base is not None and base.is_linked else None
                if image is None or not image.has_data or not image.size[0]:
                    continue
                small = image.copy()
                small.scale(8, 8)
                px = small.pixels[:]
                bpy.data.images.remove(small)
                n = len(px) // 4
                rgb = [sum(px[i * 4 + c] for i in range(n)) / n for c in range(3)]
                mat.node_tree.links.remove(base.links[0])
                base.default_value = (*rgb, 1.0)


def main(argv):
    args = parse(argv)
    started = time.time()
    scene = bpy.context.scene
    roles = keep_pieces(scene)
    if args.light:
        lighten(roles, args.covering_ratio)
        bake_colours(roles)
    # A light export carries positions and colours only: no normals (the page shades faces flat), no
    # texture coordinates, no images; the hall drops from 86 MB to 18 MB that way.
    slim = args.light or args.no_textures
    bpy.ops.export_scene.gltf(
        filepath=args.out, export_format="GLB", export_apply=True, export_yup=True, export_animations=False,
        export_skins=False, export_morph=False, export_cameras=False, export_lights=False, export_extras=False,
        export_normals=not args.light, export_texcoords=not slim,
        export_image_format="NONE" if slim else "JPEG", export_jpeg_quality=60)
    nodes = sum(len(v) for v in roles.values())
    print("EXPORT", nodes, "nodes", round(os.path.getsize(args.out) / 1e6, 1), "MB", round(time.time() - started, 1), "s")


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1:])
