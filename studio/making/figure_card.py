"""The picture on a 3D figure's card, drawn as the class page's viewer shows the figure.

The checks' picture (figure_render.render) is shaded flat in paint, which made the card a grey, dim toy beside
the bright one the teacher then opened (operator: "the original model looks good, but preview is ugly"). The card
uses the viewer's own light instead (studio/showcase_3d/figure.js): a sky-and-ground light and a sun, mixed as
light in three.js's physical units, the sun's shadow on the base and on every wide flat top, and the viewer's
paper behind it. Faces turned away are left out and flat faces are cut small, so painter's order no longer
paints a wall over the window in front of it; round parts are blended smooth, as the viewer shades them. What
the checks see is not changed by any of this.
"""
from __future__ import annotations

import functools
import io
import json
import math

from PIL import Image, ImageChops, ImageDraw, ImageFilter

from studio.making.figure_render import _camera, _lathe, _torus, _triangles

PAPER = (247, 244, 238)   # the viewer's background
SUN = tuple(c / math.hypot(-2.5, 5, 3.5) for c in (-2.5, 5, 3.5))   # towards the viewer's sun
ROUND = ("sphere", "capsule", "torus")   # shaded smooth in the viewer, so their flat patches are blended here
SMOOTH = .006   # how far, as a share of the picture's height


def _linear(v):
    v /= 255
    return v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4


def _srgb(v):
    v = min(1.0, max(0.0, v))
    return round(255 * (12.92 * v if v <= .0031308 else 1.055 * v ** (1 / 2.4) - .055))


SKY, GROUND = [_linear(c) for c in (0xff, 0xfa, 0xf0)], [_linear(c) for c in (0x9d, 0x94, 0x86)]


def _lit(colour, n, sunlit):
    """A face of this colour under the viewer's hemisphere light (1.6) and sun (2.2), as three.js r180 lights it."""
    w = .5 * n[1] + .5
    sun = 2.2 * max(0.0, sum(a * b for a, b in zip(n, SUN))) if sunlit else 0.0
    return tuple(_srgb(_linear(c) * ((g + (s - g) * w) * 1.6 + sun) / math.pi) for c, s, g in zip(colour, SKY, GROUND))


def _normal(a, b, c):
    u, v = [b[k] - a[k] for k in range(3)], [c[k] - a[k] for k in range(3)]
    n = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
    size = math.hypot(*n)
    return tuple(x / size for x in n) if size > 1e-12 else None


def _outward(tris, centre=lambda mid: (0, 0, 0)):
    """Each triangle wound so its normal points out of the shape, away from centre(its middle)."""
    out = []
    for a, b, c in tris:
        n, mid = _normal(a, b, c), [(a[k] + b[k] + c[k]) / 3 for k in range(3)]
        if n:
            o = centre(mid)
            out.append((a, b, c) if sum(n[k] * (mid[k] - o[k]) for k in range(3)) >= 0 else (a, c, b))
    return out


def _grid_box(n=6):
    """The unit box with each face cut into n by n squares."""
    s = [i / n - .5 for i in range(n + 1)]
    def at(axis, side, a, b):
        p = [0.0, 0.0, 0.0]
        p[axis], p[(axis + 1) % 3], p[(axis + 2) % 3] = side, a, b
        return tuple(p)
    quads = [[at(x, side, s[i], s[j]), at(x, side, s[i + 1], s[j]),
              at(x, side, s[i + 1], s[j + 1]), at(x, side, s[i], s[j + 1])]
             for x in range(3) for side in (-.5, .5) for i in range(n) for j in range(n)]
    return [t for q in quads for t in ((q[0], q[1], q[2]), (q[0], q[2], q[3]))]


def _ring_torus(mid):
    far = math.hypot(mid[0], mid[2]) or 1
    return (.375 * mid[0] / far, 0, .375 * mid[2] / far)


_CAP = (0, .125, .25, .375)   # a flat end cut into rings rather than long thin wedges
_SIDE = [i / 6 - .5 for i in range(7)]
_ARC = [math.pi / 2 * j / 10 for j in range(11)]   # a quarter circle, finer than the checks' shapes
FINE = {
    "box": _outward(_grid_box()),
    "cylinder": _outward(_lathe([(-.5, r) for r in _CAP] + [(y, .5) for y in _SIDE]
                                + [(.5, r) for r in _CAP[::-1]], 24)),
    "cone": _outward(_lathe([(-.5, r) for r in _CAP] + [(y, .5 * (.5 - y)) for y in _SIDE], 24)),
    "sphere": _outward(_lathe([(-.5 * math.cos(math.pi * j / 20), .5 * math.sin(math.pi * j / 20))
                               for j in range(21)], 40)),
    "capsule": _outward(_lathe([(-.25 - .25 * math.cos(a), .5 * math.sin(a)) for a in _ARC]
                               + [(.25 + .25 * math.sin(a), .5 * math.cos(a)) for a in _ARC], 40)),
    "torus": _outward(_torus(40, 16), _ring_torus),
}


def _floor(p):
    """A flat slab lying on the base, a painted ground: whatever stands on it is painted after it, wherever
    the two sort. Sorted with the parts, the slab's top cut saw teeth into the foot of a house standing on it."""
    flat = all(abs(math.sin(math.radians(p["turn"][k]))) < .01 for k in (0, 2))
    return p["shape"] in ("cylinder", "box") and flat and p["size"][1] <= .15 and p["at"][1] - p["size"][1] / 2 <= .02


def _tops(tris):
    """The heights of the flat tops wide enough to carry a shadow: a window's sill is not."""
    area = {}
    for pts, _, n in tris:
        if n and n[1] > .999:
            u, v = [pts[1][k] - pts[0][k] for k in range(3)], [pts[2][k] - pts[0][k] for k in range(3)]
            y = round(pts[0][1], 3)
            area[y] = area.get(y, 0) + abs(u[2] * v[0] - u[0] * v[2]) / 2
    widest = max(area.values(), default=0)
    return {y for y, a in area.items() if a >= .03 * widest}


def _shadows(parts, tops, screen, size):
    """For each flat top's height, where the sun's shadow of everything above it falls, in screen pixels."""
    masks = {}
    for y0 in tops:
        mask = Image.new("L", size, 0)
        pen = ImageDraw.Draw(mask)
        for pts, n in parts:
            if n[0] * SUN[0] + n[1] * SUN[1] + n[2] * SUN[2] <= 0 or max(p[1] for p in pts) <= y0 + 1e-3:
                continue
            flat = [screen((p[0] - SUN[0] * k, y0, p[2] - SUN[2] * k))
                    for p in pts for k in (max(0.0, p[1] - y0) / SUN[1],)]
            if min(z for _, z in flat) > .05:
                pen.polygon([s for s, _ in flat], fill=255)
        masks[y0] = mask
    return masks


def _shade(image, points, colour, shadow):
    """Paints colour over the part of this triangle that lies in the shadow."""
    w, h = image.size
    xs, ys = [x for x, _ in points], [y for _, y in points]
    box = (max(0, math.floor(min(xs))), max(0, math.floor(min(ys))),
           min(w, math.ceil(max(xs)) + 1), min(h, math.ceil(max(ys)) + 1))
    if box[2] > box[0] and box[3] > box[1]:
        piece = Image.new("L", (box[2] - box[0], box[3] - box[1]), 0)
        ImageDraw.Draw(piece).polygon([(x - box[0], y - box[1]) for x, y in points], fill=255)
        image.paste(colour, box, ImageChops.multiply(piece, shadow.crop(box)))


def _smooth(image, tags, rounds, r):
    """Blends the flat patches of round parts into one another, only where the whole blur stays on one part: no
    colour crosses from one part into the next, and a box's edges stay sharp."""
    stray = ImageChops.difference(tags.filter(ImageFilter.BoxBlur(2 * r)), tags).split()
    alone = ImageChops.lighter(ImageChops.lighter(stray[0], stray[1]), stray[2]).point(lambda v: 255 if v == 0 else 0)
    blur = ImageFilter.BoxBlur(r)
    return Image.composite(image.filter(blur).filter(blur), image, ImageChops.multiply(alone, rounds))


def _tag(j):
    v = (j + 2) * 2654435761 & 0xFFFFFF   # a colour of its own for each part; never the paper's black
    return v >> 16, v >> 8 & 255, v & 255


def picture(figure, yaw=35.0, width=720, height=720, elevation=14.0):
    """The figure on its base from angle yaw (0 = front, degrees), as the class page's viewer lights it."""
    tris = [(pts, colour, _normal(*pts)) for pts, colour in _triangles(figure, FINE)]
    eye, fwd, right, up, focal = _camera([(pts, c) for pts, c, _ in tris], yaw, elevation)
    w, h = width * 2, height * 2   # drawn at twice the size, then reduced, for smoother edges
    dot = lambda a, b: a[0] * b[0] + a[1] * b[1] + a[2] * b[2]
    def screen(p):
        d = [p[k] - eye[k] for k in range(3)]
        z = max(dot(d, fwd), 1e-6)
        return (w / 2 + dot(d, right) / z * focal * h / 2, h / 2 - dot(d, up) / z * focal * h / 2), z
    # The base first, then any painted ground on it, then everything else in painter's order.
    parts = figure["parts"]
    layer = [0] * len(FINE["cylinder"]) + [1 if _floor(p) else 2 for p in parts for _ in FINE[p["shape"]]]
    owner = [-1] * len(FINE["cylinder"]) + [j for j, p in enumerate(parts) for _ in FINE[p["shape"]]]
    tops = _tops(tris)
    shadows = _shadows([(pts, n) for i, (pts, _, n) in enumerate(tris) if n and layer[i]], tops, screen, (w, h))
    drawn = []
    for i, (pts, colour, n) in enumerate(tris):
        seen = [screen(p) for p in pts]
        if not n or min(z for _, z in seen) <= .05 or dot(n, [eye[k] - pts[0][k] for k in range(3)]) <= 0:
            continue   # behind the camera, or turned away from it
        top = round(pts[0][1], 3) if n[1] > .999 and round(pts[0][1], 3) in tops else None
        drawn.append((layer[i], sum(z for _, z in seen) / 3, [s for s, _ in seen], _lit(colour, n, True),
                      top, _lit(colour, n, False), owner[i]))
    image, tags, rounds = Image.new("RGB", (w, h), PAPER), Image.new("RGB", (w, h)), Image.new("L", (w, h))
    paint, mark, smooth = ImageDraw.Draw(image), ImageDraw.Draw(tags), ImageDraw.Draw(rounds)
    for _, _, points, fill, top, shade, j in sorted(drawn, key=lambda d: (d[0], -d[1])):
        paint.polygon(points, fill=fill)
        mark.polygon(points, fill=_tag(j))
        smooth.polygon(points, fill=255 if j >= 0 and parts[j]["shape"] in ROUND else 0)
        if top is not None:
            _shade(image, points, shade, shadows[top])
    image = _smooth(image, tags, rounds, max(1, round(h * SMOOTH)))
    return image.resize((width, height), Image.Resampling.LANCZOS)


def card(figure) -> bytes:
    """The figure turned a little, as a PNG for its card beside the clip's (operator). A saved figure
    never changes and its card is drawn again with every screen, so each picture is kept once it is drawn."""
    return _card(json.dumps(figure, sort_keys=True))


@functools.lru_cache(maxsize=64)
def _card(figure: str, size=(840, 360), room=1.08) -> bytes:
    # Drawn large, then cut to what was drawn with a little room and set in the card's shape: the camera frames
    # the toy for any turn, which left it small in a wide card (operator). 840 by 360 stays sharp on a phone.
    drawn = picture(json.loads(figure))
    blank = Image.new("RGB", drawn.size, PAPER)
    left, top, right, bottom = ImageChops.difference(drawn, blank).getbbox() or (0, 0, *drawn.size)
    high = max(bottom - top, (right - left) * size[1] / size[0]) * room
    wide = high * size[0] / size[1]
    framed = Image.new("RGB", (round(wide), round(high)), PAPER)
    framed.paste(drawn, (round((wide - left - right) / 2), round((high - top - bottom) / 2)))
    buffer = io.BytesIO()
    framed.resize(size, Image.Resampling.LANCZOS).save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()
