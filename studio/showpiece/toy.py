"""A child's toy as a little building: the studio's sketch scene (the solids its sketch entrance
fitted to a drawing) becomes a .blend the six skills can work on, with a ground slab under it.

The page's scene is y-up with each solid's position at its centre and its size in metres; the
model is z-up, so y and z trade places. Every solid is one mesh in the pieces collection, the
slab is the ground, and roles come from the collection names the way they do for the hall.
Usage: blender -b --python-exit-code 1 --python toy.py -- scene.json out.blend
"""
import json
import math
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

SLAB = 0.12
MARGIN = 0.4


def solid(kind, size):
    bm = bmesh.new()
    if kind == "sphere":
        bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=16, radius=0.5)
    elif kind == "cylinder":
        bmesh.ops.create_cone(bm, cap_ends=True, segments=32, radius1=0.5, radius2=0.5, depth=1.0)
    else:
        bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=size, verts=bm.verts)
    return bm


def place(bm, position, yaw_deg):
    x, y, z = position          # the page's y is up
    bmesh.ops.rotate(bm, cent=Vector(), matrix=Matrix.Rotation(math.radians(yaw_deg), 3, "Z"), verts=bm.verts)
    bmesh.ops.translate(bm, vec=Vector((x, -z, y)), verts=bm.verts)


def mesh_object(name, bm, material):
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    mesh.materials.append(material)
    return bpy.data.objects.new(name, mesh)


def timber_material():
    mat = bpy.data.materials.new("TOY | warm timber")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (0.72, 0.56, 0.38, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.7
    return mat


def stone_material():
    mat = bpy.data.materials.new("TOY | pale stone")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (0.62, 0.62, 0.6, 1.0)
    return mat


def main(scene_path, out_path):
    scene_doc = json.load(open(scene_path))
    objects = scene_doc["objects"]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    ground_coll, pieces_coll = bpy.data.collections.new("01_Ground"), bpy.data.collections.new("05_Pieces")
    scene.collection.children.link(ground_coll)
    scene.collection.children.link(pieces_coll)
    timber, stone = timber_material(), stone_material()
    counts = {}
    for o in objects:
        kind = o["kind"] if o["kind"] in ("box", "sphere", "cylinder") else "sphere"
        sx, sy, sz = o["size"]          # the page's y is the height
        bm = solid(kind, Vector((sx, sz, sy)))
        place(bm, o["position"], o.get("yaw", 0.0))
        counts[kind] = counts.get(kind, 0) + 1
        pieces_coll.objects.link(mesh_object(f"{kind.capitalize()} {counts[kind]}", bm, timber))
    xs = [o["position"][0] for o in objects]
    zs = [-o["position"][2] for o in objects]
    reach = max(max(o["size"]) for o in objects) / 2 + MARGIN
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector((max(xs) - min(xs) + 2 * reach, max(zs) - min(zs) + 2 * reach, SLAB)), verts=bm.verts)
    bmesh.ops.translate(bm, vec=Vector(((max(xs) + min(xs)) / 2, (max(zs) + min(zs)) / 2, -SLAB / 2)), verts=bm.verts)
    ground_coll.objects.link(mesh_object("Slab", bm, stone))
    bpy.ops.wm.save_as_mainfile(filepath=out_path)
    print("TOY", out_path, len(objects), "solids", counts)


if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1:]
    main(args[0], args[1])
