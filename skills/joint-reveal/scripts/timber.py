"""Making and cutting timber on copies: boxes and plan prisms with the hall's Timber UV
convention, and a boolean cut that leaves end grain on the new faces. Nothing here touches the
source mesh: `own_mesh` gives a piece its own data first, and callers save to a new file."""
import bmesh
import bpy
from mathutils import Vector

U_SCALE, V_SCALE = 1.333, 0.556
END_GRAIN = "STUDY | exposed end grain"
UV_NAME = "Timber UV"


def own_mesh(obj):
    if obj.data.users > 1:
        obj.data = obj.data.copy()
    return obj


def new_bm():
    bm = bmesh.new()
    return bm, bm.loops.layers.uv.new(UV_NAME)


def _uv_box_face(loop, uv, quad_index, along):
    w = loop.vert.co
    a, c = (w.x, w.y) if along == "x" else (w.y, w.x)
    loop[uv].uv = (U_SCALE * c, V_SCALE * a) if quad_index < 2 else (U_SCALE * w.z, V_SCALE * a)


def add_box(bm, uv, x0, x1, y0, y1, z0, z1, along="x", material=0):
    vs = [bm.verts.new((x, y, z)) for z in (z0, z1) for y in (y0, y1) for x in (x0, x1)]
    quads = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    for i, q in enumerate(quads):
        f = bm.faces.new([vs[j] for j in q])
        f.material_index = material
        for loop in f.loops:
            _uv_box_face(loop, uv, i, along)


def add_plan_prism(bm, uv, plan, z0, z1, material=0):
    """A polygon in plan (counter-clockwise (x, y) points) extruded from z0 to z1."""
    r0 = [bm.verts.new((x, y, z0)) for x, y in plan]
    r1 = [bm.verts.new((x, y, z1)) for x, y in plan]
    for cap in (bm.faces.new(r0[::-1]), bm.faces.new(r1)):
        cap.material_index = material
        for loop in cap.loops:
            loop[uv].uv = (U_SCALE * loop.vert.co.x, V_SCALE * loop.vert.co.y)
    n = len(plan)
    for i in range(n):
        f = bm.faces.new((r0[i], r0[(i + 1) % n], r1[(i + 1) % n], r1[i]))
        f.material_index = material
        for loop in f.loops:
            loop[uv].uv = (U_SCALE * loop.vert.co.z, V_SCALE * (loop.vert.co.x + loop.vert.co.y))


def end_grain(obj):
    mat = bpy.data.materials.get(END_GRAIN) or bpy.data.materials.new(END_GRAIN)
    for i, slot in enumerate(obj.data.materials):
        if slot is mat:
            return i
    obj.data.materials.append(mat)
    return len(obj.data.materials) - 1


def join_into(obj, bm):
    """Add world-space bmesh geometry to the object's own mesh, welding coincident vertices."""
    own_mesh(obj)
    bm.transform(obj.matrix_world.inverted())
    merged = bmesh.new()
    merged.from_mesh(obj.data)
    if UV_NAME not in merged.loops.layers.uv:
        merged.loops.layers.uv.new(UV_NAME)
    tmp = bpy.data.meshes.new("tmp")
    bm.to_mesh(tmp)
    merged.from_mesh(tmp)
    bpy.data.meshes.remove(tmp)
    bmesh.ops.remove_doubles(merged, verts=merged.verts, dist=1e-5)
    bmesh.ops.recalc_face_normals(merged, faces=merged.faces[:])
    merged.to_mesh(obj.data)
    merged.free()
    obj.data.update()


def cut(obj, cutter_bm):
    """Boolean difference with a temporary world-space cutter; new faces get end grain."""
    own_mesh(obj)
    grain = end_grain(obj)
    for f in cutter_bm.faces:
        f.material_index = 0
    # Faces out, whichever way round the plan was walked: an inside-out cutter cuts nothing. Until this
    # the dovetail's slot never opened in its column, and the lifted block over a tenon
    # showed no mortise, though the joints were reported made.
    bmesh.ops.recalc_face_normals(cutter_bm, faces=cutter_bm.faces[:])
    mesh = bpy.data.meshes.new("cutter")
    cutter_bm.to_mesh(mesh)
    cutter_bm.free()
    mesh.materials.append(obj.data.materials[grain])
    cutter = bpy.data.objects.new("cutter", mesh)
    bpy.context.scene.collection.objects.link(cutter)
    mod = obj.modifiers.new("JOINT cut", "BOOLEAN")
    mod.operation, mod.solver, mod.object, mod.material_mode = "DIFFERENCE", "EXACT", cutter, "TRANSFER"
    mod.use_self = True     # a piece that took a tenon is two overlapping shells; the cut must read them as one
    bpy.context.view_layer.update()
    bpy.context.view_layer.objects.active = obj
    with bpy.context.temp_override(object=obj, active_object=obj, selected_objects=[obj]):
        bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(cutter)
    bpy.data.meshes.remove(mesh)


def box_of(obj):
    corners = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    return (Vector([min(c[i] for c in corners) for i in range(3)]),
            Vector([max(c[i] for c in corners) for i in range(3)]))
