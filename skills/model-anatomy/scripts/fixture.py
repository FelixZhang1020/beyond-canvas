"""Build the small stack the skills are tested on: a slab, four columns, two lintels, a ridge
beam, two rafter boards and one tile sheet, in the collection names the role keywords expect.

Boxes only, placed so every piece rests squarely on the one below it: columns on the slab, each
lintel on two columns, the ridge on both lintels, the rafters on the ridge, the sheet on the
rafters. Nothing here is a building; it is the smallest thing every tool must get right.
Usage: blender -b --python-exit-code 1 --python fixture.py -- out.blend
"""
import sys

import bpy

PIECES = [
    # collection, name, centre (x, y, z), size (x, y, z)
    ("01_Platform", "Slab", (0, 0, 0.15), (6.0, 4.0, 0.3)),
    ("02_Columns", "Column SW", (-2, -1.2, 1.5), (0.3, 0.3, 2.4)),
    ("02_Columns", "Column SE", (2, -1.2, 1.5), (0.3, 0.3, 2.4)),
    ("02_Columns", "Column NW", (-2, 1.2, 1.5), (0.3, 0.3, 2.4)),
    ("02_Columns", "Column NE", (2, 1.2, 1.5), (0.3, 0.3, 2.4)),
    ("05_Beams", "Lintel front", (0, -1.2, 2.85), (4.6, 0.3, 0.3)),
    ("05_Beams", "Lintel back", (0, 1.2, 2.85), (4.6, 0.3, 0.3)),
    ("05_Beams", "Ridge beam", (0, 0, 3.15), (0.3, 3.0, 0.3)),
    ("06_Rafters", "Rafter front", (0, -0.75, 3.325), (4.6, 1.4, 0.05)),
    ("06_Rafters", "Rafter back", (0, 0.75, 3.325), (4.6, 1.4, 0.05)),
    ("07_Covering", "Tile sheet", (0, 0, 3.375), (4.6, 3.0, 0.05)),
]


def box(name, centre, size):
    cx, cy, cz = centre
    hx, hy, hz = (s / 2 for s in size)
    verts = [(cx + sx * hx, cy + sy * hy, cz + sz * hz)
             for sz in (-1, 1) for sy in (-1, 1) for sx in (-1, 1)]
    faces = [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)]
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    return bpy.data.objects.new(name, mesh)


def main(out):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    collections = {}
    for collection, name, centre, size in PIECES:
        if collection not in collections:
            collections[collection] = bpy.data.collections.new(collection)
            scene.collection.children.link(collections[collection])
        collections[collection].objects.link(box(name, centre, size))
    bpy.ops.wm.save_as_mainfile(filepath=out)
    print("FIXTURE", out, len(bpy.data.objects), "objects")


main(sys.argv[sys.argv.index("--") + 1])
