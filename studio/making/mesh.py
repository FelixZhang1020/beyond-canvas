"""The bounded, untextured surface exchanged with the local mesh worker.

No tensor libraries enter the classroom process. The worker prepares a grounded
mesh; this boundary checks its actual arrays before they reach a tablet.
"""
from __future__ import annotations

import json
import math

MAX_VERTICES = 60000
MAX_FACES = 60000
MAX_BYTES = 8 * 1024 * 1024


def _number(value, low, high):
    if type(value) not in (float, int) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError("invalid mesh coordinate")
    return value


def validate(value: dict) -> dict:
    if not isinstance(value, dict):
        raise ValueError("missing mesh")
    positions, normals, indices = (value.get(k) for k in ("positions", "normals", "indices"))
    if not all(isinstance(a, list) for a in (positions, normals, indices)):
        raise ValueError("missing mesh arrays")
    if len(positions) % 3 or not 4 <= len(positions) // 3 <= MAX_VERTICES:
        raise ValueError("mesh vertex budget exceeded")
    if len(normals) != len(positions) or len(indices) % 3 or not 4 <= len(indices) // 3 <= MAX_FACES:
        raise ValueError("invalid mesh array size")
    for i, p in enumerate(positions):
        _number(p, -.002 if i % 3 == 1 else -6, 6)
    for i in range(0, len(normals), 3):
        normal = [_number(n, -1.001, 1.001) for n in normals[i:i+3]]
        if abs(math.hypot(*normal) - 1) > .02:
            raise ValueError("mesh normals must be unit length")
    if any(type(i) is not int or not 0 <= i < len(positions) // 3 for i in indices):
        raise ValueError("mesh index outside vertex array")
    size = [max(positions[i::3]) - min(positions[i::3]) for i in range(3)]
    if any(not .01 < s <= 6 for s in size) or abs(min(positions[1::3])) > .002:
        raise ValueError("mesh must have volume and rest on the ground")
    # Reject degenerate triangles, which cause unstable normals and shadows.
    for a, b, c in zip(indices[::3], indices[1::3], indices[2::3]):
        u = [positions[3*b+i] - positions[3*a+i] for i in range(3)]
        v = [positions[3*c+i] - positions[3*a+i] for i in range(3)]
        if math.hypot(u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0]) < 1e-9:
            raise ValueError("degenerate mesh triangle")
    return {"positions": positions, "normals": normals, "indices": indices, "size": size}


def scene(content: bytes, aspect: float, *, subject: str = "head") -> dict:
    if subject not in ("head", "fruit"):
        raise ValueError("unknown mesh subject")
    if not content or len(content) > MAX_BYTES:
        raise ValueError("mesh response outside byte budget")
    payload = json.loads(content)
    mesh = validate(payload.get("mesh") if isinstance(payload, dict) else None)
    _number(aspect, .1, 10)
    height = mesh["size"][1]
    distance = max(5, height * 1.95, mesh["size"][0] / (max(aspect, .7) * .55))
    if distance > 20:
        raise ValueError("mesh cannot fit the viewer")
    return {"version": 1, "method": "single-image-mesh", "mesh": mesh,
            **({"subject": "fruit"} if subject == "fruit" else {}),
            "camera": {"target": [0, height / 2, 0], "distance": distance,
                       "elevation": 20 if subject == "fruit" else 10, "azimuth": 0, "fov": 40},
            "light": [-3, 6, 5], "source_aspect": aspect}
