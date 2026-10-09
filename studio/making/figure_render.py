"""The picture of a toy figure that its checks look at, drawn on the CPU before any child sees the figure.

Flat shading in painter's order: good enough to judge whether the toy shows the painting's subject with its
face, but not the figure itself; the card's picture is lit as the viewer lights it (figure_card.py). The class page
draws the real figure with three.js from the same parts and the same unit shapes
(studio/showcase_3d/figure.html), so what is checked is what is shown.

Every unit shape is centred on the origin with a full extent of 1 along each axis, so a part's "size" scales
it directly: sphere, box, cylinder and capsule upright along y, cone pointing up, torus lying flat.
"""
from __future__ import annotations

import base64
import io
import math

from PIL import Image, ImageDraw

SHAPES = ("sphere", "box", "cylinder", "cone", "capsule", "torus")
BASE_COLOUR = "#d9cfbd"
BACKGROUND = (236, 234, 228)


def _ring(y, radius, n):
    return [(radius * math.cos(2 * math.pi * i / n), y, radius * math.sin(2 * math.pi * i / n)) for i in range(n)]


def _band(a, b):
    n = len(a)
    return [t for i in range(n) for t in ((a[i], a[(i + 1) % n], b[(i + 1) % n]), (a[i], b[(i + 1) % n], b[i]))]


def _lathe(profile, n=20):
    """profile: (y, radius) from bottom to top, turned about y into triangles, ends closed."""
    rings = [_ring(y, r, n) for y, r in profile]
    tris = [t for a, b in zip(rings, rings[1:]) for t in _band(a, b)]
    for ring, (y, r) in ((rings[0], profile[0]), (rings[-1], profile[-1])):
        if r > 0:
            tris += [(ring[i], ring[(i + 1) % n], (0, y, 0)) for i in range(n)]
    return tris


def _torus(n=20, m=12):
    # The tube is stretched four times upright so the ring's thickness is its size along y, like every shape.
    point = lambda i, j: ((.375 + .125 * math.cos(2 * math.pi * j / m)) * math.cos(2 * math.pi * i / n),
                          .5 * math.sin(2 * math.pi * j / m),
                          (.375 + .125 * math.cos(2 * math.pi * j / m)) * math.sin(2 * math.pi * i / n))
    return [t for i in range(n) for j in range(m) for t in (
        (point(i, j), point(i + 1, j), point(i + 1, j + 1)), (point(i, j), point(i + 1, j + 1), point(i, j + 1)))]


def _box():
    c = [(x, y, z) for x in (-.5, .5) for y in (-.5, .5) for z in (-.5, .5)]
    quads = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    return [t for a, b, d, e in quads for t in ((c[a], c[b], c[d]), (c[a], c[d], c[e]))]


def _capsule():
    """A cylinder with half-height round ends, total height 1 (three.js CapsuleGeometry squashed to fit)."""
    low = [(-.25 - .25 * math.cos(math.pi / 2 * j / 5), .5 * math.sin(math.pi / 2 * j / 5)) for j in range(6)]
    high = [(.25 + .25 * math.sin(math.pi / 2 * j / 5), .5 * math.cos(math.pi / 2 * j / 5)) for j in range(6)]
    return _lathe(low + high)


UNITS = {
    "sphere": _lathe([(-.5 * math.cos(math.pi * j / 10), .5 * math.sin(math.pi * j / 10)) for j in range(11)]),
    "box": _box(), "cylinder": _lathe([(-.5, .5), (.5, .5)]), "cone": _lathe([(-.5, .5), (.5, 0)]),
    "capsule": _capsule(), "torus": _torus(),
}


def rotation(turn):
    """Degrees about x, then y, then z: the matrix of three.js Euler order 'XYZ'."""
    ax, ay, az = (math.radians(v) for v in turn)
    cx, sx, cy, sy, cz, sz = math.cos(ax), math.sin(ax), math.cos(ay), math.sin(ay), math.cos(az), math.sin(az)
    rx, ry, rz = [[1, 0, 0], [0, cx, -sx], [0, sx, cx]], [[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]], [[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]]
    mul = lambda a, b: [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
    return mul(mul(rx, ry), rz)


def base_radius(figure):
    """The round base under the toy: just wider than what stands on it."""
    reach = max(math.hypot(p["at"][0], p["at"][2]) + max(p["size"][0], p["size"][2]) / 2 for p in figure["parts"])
    return min(2.2, max(.8, reach + .15))


def _triangles(figure, units=UNITS):
    r = base_radius(figure)
    base = {"shape": "cylinder", "at": [0, -.05, 0], "size": [2 * r, .1, 2 * r], "turn": [0, 0, 0], "colour": BASE_COLOUR}
    for p in [base] + figure["parts"]:   # the base first: render() paints it before anything is sorted
        m, (sx, sy, sz), t = rotation(p["turn"]), p["size"], p["at"]
        colour = tuple(int(p["colour"][i:i + 2], 16) for i in (1, 3, 5))
        for tri in units[p["shape"]]:
            yield [tuple(m[k][0] * x * sx + m[k][1] * y * sy + m[k][2] * z * sz + t[k] for k in range(3))
                   for x, y, z in tri], colour


def _camera(tris, yaw, elevation):
    xs, ys, zs = ([v[k] for t, _ in tris for v in t] for k in range(3))
    centre = ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, (min(zs) + max(zs)) / 2)
    radius = max(math.dist(centre, v) for t, _ in tris for v in t)
    fov = math.radians(35)
    dist = radius / math.sin(fov / 2) * 1.05
    y, e = math.radians(yaw), math.radians(elevation)
    eye = (centre[0] + dist * math.sin(y) * math.cos(e), centre[1] + dist * math.sin(e), centre[2] + dist * math.cos(y) * math.cos(e))
    unit = lambda v: [c / math.hypot(*v) for c in v]
    fwd = unit([c - o for c, o in zip(centre, eye)])
    right = unit([-fwd[2], 0, fwd[0]])
    up = [right[1] * fwd[2] - right[2] * fwd[1], right[2] * fwd[0] - right[0] * fwd[2], right[0] * fwd[1] - right[1] * fwd[0]]
    return eye, fwd, right, up, 1 / math.tan(fov / 2)


def render(figure, yaw=0.0, width=640, height=480, elevation=14.0):
    """The figure on its base from angle yaw (0 = front, degrees), lit from the upper left."""
    tris = list(_triangles(figure))
    eye, fwd, right, up, focal = _camera(tris, yaw, elevation)
    light = [c / math.hypot(-.45, .8, .55) for c in (-.45, .8, .55)]
    dot = lambda a, b: a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
    w, h = width * 2, height * 2   # drawn at twice the size, then reduced, for smoother edges
    drawn = []
    under = len(UNITS["cylinder"])   # the base's triangles; nothing sits below the base, so it is painted first
    for i, (pts, colour) in enumerate(tris):
        rel = [[p[k] - eye[k] for k in range(3)] for p in pts]
        cam = [(dot(d, right), dot(d, up), dot(d, fwd)) for d in rel]
        if min(c[2] for c in cam) <= .05:
            continue
        u, v = [pts[1][k] - pts[0][k] for k in range(3)], [pts[2][k] - pts[0][k] for k in range(3)]
        n = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]]
        size = math.hypot(*n) or 1
        n = [c / size for c in n]
        if dot(n, [-c for c in rel[0]]) < 0:
            n = [-c for c in n]   # light the side the camera sees; winding is not relied on
        shade = .36 + .64 * max(0.0, dot(n, light))
        screen = [(w / 2 + x / z * focal * h / 2, h / 2 - y / z * focal * h / 2) for x, y, z in cam]
        drawn.append((i >= under, sum(c[2] for c in cam) / 3, screen, tuple(min(255, int(c * shade)) for c in colour)))
    image = Image.new("RGB", (w, h), BACKGROUND)
    paint = ImageDraw.Draw(image)
    for _, _, screen, fill in sorted(drawn, key=lambda d: (d[0], -d[1])):
        paint.polygon(screen, fill=fill)
    return image.resize((width, height), Image.Resampling.LANCZOS)


def sheet(figure):
    """Front and side views side by side, as one PNG data URI for the look check and the safety screen."""
    both = Image.new("RGB", (960, 360))
    both.paste(render(figure, 0, 480, 360), (0, 0))
    both.paste(render(figure, 35, 480, 360), (480, 0))
    buffer = io.BytesIO()
    both.save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()

