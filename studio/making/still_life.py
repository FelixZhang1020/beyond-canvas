"""Small, measured surfaces for fruit among geometric study objects.

Only the visible silhouette is measured. Rotation assumes rounded cross sections;
unseen depth is approximate. No tensor runtime or template fruit model is loaded.
"""
from __future__ import annotations

import math

from studio.making import mesh

FRUITS = ("pear", "apple", "orange")
SIDES = 40
ROWS = 32


def _curve(rows, t, column):
    """Shape-preserving cubic interpolation, with no radius overshoot."""
    x = [r[0] for r in rows]
    y = [r[column] for r in rows]
    h = [b-a for a, b in zip(x, x[1:])]
    slopes = [(b-a)/step for a, b, step in zip(y, y[1:], h)]
    tangents = [slopes[0]]
    for i in range(1, len(rows)-1):
        a, b = slopes[i-1:i+1]
        w1, w2 = 2*h[i]+h[i-1], h[i]+2*h[i-1]
        tangents.append((w1+w2)/(w1/a+w2/b) if a*b > 0 else 0)
    tangents.append(slopes[-1])
    i = next((i for i in range(len(h)) if t <= x[i+1]), len(h)-1)
    u = min(1, max(0, (t-x[i])/h[i]))
    return ((2*u**3-3*u*u+1)*y[i] + (u**3-2*u*u+u)*h[i]*tangents[i]
            + (-2*u**3+3*u*u)*y[i+1] + (u**3-u*u)*h[i]*tangents[i+1])


def body_rows(profile, count=ROWS):
    # Close only at the measured body's ends. Keep its measured lean/neck/belly.
    rows = [[0, profile[0][1], 0], *profile, [1, profile[-1][1], 0]]
    return [[i/count, _curve(rows, i/count, 1), max(0, _curve(rows, i/count, 2))]
            for i in range(count+1)]


def lathe(rows, sides=SIDES):
    positions, rings, faces = [], [], []
    for t, offset, radius in rows:
        ring = []
        for i in range(sides if radius > 1e-8 else 1):
            angle = i * math.tau / sides
            ring.append(len(positions))
            positions.append([offset+radius*math.cos(angle), t-.5, radius*math.sin(angle)])
        rings.append(ring if len(ring) > 1 else ring*sides)
    for lower, upper in zip(rings, rings[1:]):
        for i in range(sides):
            j = (i+1) % sides
            for face in ([lower[i], upper[i], upper[j]], [lower[i], upper[j], lower[j]]):
                if len(set(face)) == 3:
                    faces.append(face)
    return positions, faces


def body_points(profile):
    return lathe(body_rows(profile, 20), 16)[0]


def _unit_object(obj):
    kind = obj["kind"]
    if kind in FRUITS:
        return lathe(body_rows(obj["profile"]))
    if kind == "sphere":
        return lathe([[(1-math.cos(i*math.pi/24))/2, 0, math.sin(i*math.pi/24)/2]
                      for i in range(25)])
    if kind == "cylinder":
        return lathe([[0,0,0], [0,0,.5], [1,0,.5], [1,0,0]])
    if kind != "box":
        raise ValueError("unknown still-life object")
    corners = [[x,y,z] for x in (-.5,.5) for y in (-.5,.5) for z in (-.5,.5)]
    positions, faces = [], []
    for face in ((0,1,3,2), (4,6,7,5), (0,4,5,1), (2,3,7,6), (0,2,6,4), (1,5,7,3)):
        base = len(positions)
        positions.extend(corners[i] for i in face)
        faces.extend([[base,base+1,base+2], [base,base+2,base+3]])
    return positions, faces


def _stem(obj, elevation):
    points = obj.get("stem", [])
    if not points:
        return [], []
    # Stem measurements are in the source body frame. The part box sets length
    # and lateral placement; tilt and unseen front/back depth remain estimates.
    (bx, by), (tx, ty) = points
    w, h, _ = obj["size"]
    start = [bx*w, (by-.5)*h, 0]
    end = [tx*w, start[1]+(ty-by)*h/math.cos(math.radians(elevation)), 0]
    delta = [b-a for a,b in zip(start,end)]
    length = math.hypot(*delta)
    direction = [v/length for v in delta]
    side = [direction[1],-direction[0],0]
    vertices, faces = [], []
    radius = w*.018
    for j in range(5):
        t = j/4
        center = [a+t*d for a,d in zip(start,delta)]
        for i in range(10):
            a = math.tau*i/10
            vertices.append([center[k]+radius*(1-.2*t)*(side[k]*math.cos(a)+(math.sin(a) if k == 2 else 0)) for k in range(3)])
    for j in range(4):
        for i in range(10):
            a,b = j*10+i, j*10+(i+1)%10
            faces.extend([[a,a+10,b+10],[a,b+10,b]])
    for j, reverse in ((0, False), (4, True)):
        center = len(vertices)
        vertices.append(start if j == 0 else end)
        for i in range(10):
            face = [center,j*10+i,j*10+(i+1)%10]
            faces.append(face[::-1] if reverse else face)
    return vertices, faces


def scene(fitted):
    """Combine the fitted solids into one bounded mesh for shared occlusion."""
    positions, faces = [], []
    for obj in fitted["objects"]:
        local, triangles = _unit_object(obj)
        local = [[v*s for v,s in zip(p,obj["size"])] for p in local]
        stem, stem_faces = _stem(obj, fitted["camera"]["elevation"])
        offset = len(local)
        triangles.extend([[i+offset for i in f] for f in stem_faces])
        local.extend(stem)
        angle = math.radians(obj["yaw"])
        sn, cs = math.sin(angle), math.cos(angle)
        offset = len(positions)
        for x,y,z in local:
            positions.append([obj["position"][0]+x*cs+z*sn, obj["position"][1]+y,
                              obj["position"][2]-x*sn+z*cs])
        faces.extend([[i+offset for i in f] for f in triangles])
    low = [min(p[i] for p in positions) for i in range(3)]
    high = [max(p[i] for p in positions) for i in range(3)]
    shift = [(low[0]+high[0])/2, 0, (low[2]+high[2])/2]
    scale = min(1, 5.5/max(b-a for a,b in zip(low,high)))
    positions = [[round((v-shift[i])*scale,6) for i,v in enumerate(p)] for p in positions]
    normals = [[0.,0.,0.] for _ in positions]
    for a,b,c in faces:
        u = [positions[b][i]-positions[a][i] for i in range(3)]
        v = [positions[c][i]-positions[a][i] for i in range(3)]
        n = [u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0]]
        for index in (a,b,c):
            for i in range(3):
                normals[index][i] += n[i]
    normals = [[round(v/math.hypot(*n),6) for v in n] for n in normals]
    surface = mesh.validate({"positions":[v for p in positions for v in p],
                             "normals":[v for n in normals for v in n],
                             "indices":[i for f in faces for i in f]})
    camera = {**fitted["camera"], "target":[(v-shift[i])*scale for i,v in enumerate(fitted["camera"]["target"])],
              "distance":fitted["camera"]["distance"]*scale}
    camera.pop("position", None)
    if camera["distance"] < 4:
        raise ValueError("still life cannot fit the bounded viewer")
    objects = [{**o, "position":[(v-shift[i])*scale for i,v in enumerate(o["position"])],
                "size":[v*scale for v in o["size"]]} for o in fitted["objects"]]
    light = [max(-8,min(8,(v-shift[i])*scale)) for i,v in enumerate(fitted["light"])]
    light[1] = max(3, light[1])
    return {**fitted, "method":"parametric-still-life", "mesh":surface,
            "objects":objects, "camera":camera, "light":light}
