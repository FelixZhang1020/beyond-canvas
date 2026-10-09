"""Bounded geometric reconstruction for tabletop sketch studies.

The VLM annotates silhouettes, not pixels or a mesh. A small CPU fit places
untextured solids on a ground plane using perspective projection. The original
shading never becomes a texture, so the browser can relight every surface.
This is an approximate explanation of the drawing, not recovered hidden geometry.
"""
from __future__ import annotations

import json
import math
import statistics
from pathlib import Path

from PIL import Image

from studio.core.images import to_data_uri
from studio.providers.base import VisionChatClient
from studio.providers.media import MediaSlot
from studio.core.errors import ModelError, ModelUnavailable, ModelRefused
from studio.making import mesh
from studio.making import still_life

MAX_OBJECTS = 6
KINDS = ("box", "sphere", "cylinder", *still_life.FRUITS)
MAX_TOKENS = 1500
PROMPT = Path(__file__).resolve().parents[2] / "skills/sketch-to-3d/assets/prompts/reconstruction.txt"
# Named, not written into the call, so the prompt page in system management can show them.
ANNOTATE_SYSTEM = "You annotate geometry. Return only the requested JSON."
RETRY_JSON_CLAUSE = ("\nYour previous response was not complete valid JSON. Recheck this image and return the matching "
                     "COMPLETE JSON object with every closing bracket and brace. No markdown fences or prose.")
RETRY_FRUIT_CLAUSE = ("\nRecheck the image: required fruit part fields were omitted. Return the COMPLETE objects list. "
                      "EVERY fruit entry MUST include stem_bbox (null if absent). EVERY pear MUST also include "
                      "neck_bbox. Do not omit these fields.")


class UnsupportedSketch(ValueError):
    """A valid answer that says this drawing is outside the supported geometry."""


class PortraitUnavailable(ModelUnavailable):
    """The drawing is a head, but its separate mesh worker cannot serve it."""


class FruitMeshUnavailable(ModelUnavailable):
    """The fruit study needs the local image-to-mesh worker."""


class MissingFruitMeasurement(ValueError):
    """A recognized fruit lacks a required part; one bounded recheck may help."""


def _number(value, low, high):
    if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError("scene number outside its finite bounds")
    return float(value)


def _vector(value, size, low, high):
    if not isinstance(value, list) or len(value) != size:
        raise ValueError("scene vector has the wrong size")
    return [_number(v, low, high) for v in value]


def _fruit_profile(obj):
    rows = obj.get("profile")
    if not isinstance(rows, list) or not 4 <= len(rows) <= 10:
        raise ValueError("fruit needs a bounded body profile")
    result = []
    for row in rows:
        t, center, radius = _vector(row, 3, -.5, 1)
        if not .01 <= t <= .99 or not -.4 <= center <= .4 or not .01 <= radius <= .55:
            raise ValueError("invalid fruit section")
        if result and t-result[-1][0] < .015:
            raise ValueError("fruit sections must rise without duplicates")
        result.append([t,center,radius])
    if result[0][0] > .15 or result[-1][0] < .85 or max(r[2] for r in result) < .35:
        raise ValueError("incomplete fruit profile")
    stem = obj.get("stem")
    if not isinstance(stem,list) or len(stem) not in (0,2):
        raise ValueError("invalid fruit stalk")
    stem = [_vector(p,2,-.7,1.6) for p in stem]
    if stem and not (abs(stem[0][0]) <= .6 and abs(stem[1][0]) <= .6
                     and .8 <= stem[0][1] <= 1.1 and .02 <= stem[1][1]-stem[0][1] <= .5):
        raise ValueError("stalk must attach near the top of the fruit")
    return {"profile":result, "stem":stem}


def _fruit_measurements(obj, bounds):
    """Convert native part boxes into an approximate rounded body, not a ball."""
    left,top,right,bottom = bounds
    width,height = right-left,bottom-top
    stalk = obj.get("stem_bbox")
    if "stem_bbox" not in obj:
        raise MissingFruitMeasurement("fruit needs an explicit stalk visibility decision")
    if stalk is not None:
        stalk = _vector(stalk,4,0,1000)
        a,b,c,d = stalk
        if not (0 < c-a <= width*.3 and 0 < d-b <= height*.5 and left <= a < c <= right
                and top-height*.5 <= b < d <= top+height*.25):
            raise ValueError("invalid stalk box")
    if obj["kind"] == "pear":
        if "neck_bbox" not in obj:
            raise MissingFruitMeasurement("pear needs a neck measurement")
        a,b,c,d = _vector(obj.get("neck_bbox"),4,0,1000)
        if not (left <= a < c <= right and top <= b < d <= top+height*.55
                and .12 <= (c-a)/width <= .8):
            raise ValueError("pear needs a narrow upper body")
        # Native localization may include the stalk in the whole-fruit box.
        # Remove that small overlap only when the measured neck corroborates it.
        if stalk and top < b and b-top <= height*.2 and stalk[1] <= top+height*.05:
            top = b
            height = bottom-top
        neck = 1-(d-top)/height
        offset = ((a+c)-(left+right))/(2*width)
        radius = (c-a)/(2*width)
        rows = [[.025,0,.13],[.18,0,.40],[.36,0,.5],
                [(.36+neck)/2,offset*.4,(.5+radius)/2],
                [neck,offset,radius],[.98,offset,radius*.55]]
    else:
        rows = [[.025,0,.14],[.18,0,.4],[.5,0,.5],[.82,0,.4],[.975,0,.14]]
    stem = []
    if stalk:
        a,b,c,d = stalk
        center = (a+c-left-right)/(2*width)
        stem = [[center, min(1.02,max(.9,1-(d-top)/height))], [center,1-(b-top)/height]]
    return [left,top,right,bottom], _fruit_profile({"profile":rows,"stem":stem})


def parse(text: str) -> dict:
    """Validate the intermediate annotation used by the perspective fitter."""
    if len(text) > 16000:
        raise ValueError("scene answer too large")
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    doc = json.loads(text)
    if not isinstance(doc, dict) or type(doc.get("supported")) is not bool:
        raise ValueError("missing supported decision")
    if not doc["supported"]:
        raise UnsupportedSketch("unsupported drawing")
    raw = doc.get("objects")
    if not isinstance(raw, list) or not 1 <= len(raw) <= MAX_OBJECTS:
        raise ValueError("scene must have one to six objects")
    objects = []
    for obj in raw:
        if not isinstance(obj, dict) or obj.get("kind") not in KINDS:
            raise ValueError("unknown solid")
        box = _vector(obj.get("box"), 4, 0, 1)
        if min(box[2:]) < .035 or box[0] + box[2] > 1.001 or box[1] + box[3] > 1.001:
            raise ValueError("empty or out-of-image silhouette")
        proportions = _vector(obj.get("proportions"), 3, .25, 4)
        if abs(proportions[0] - 1) > .01:
            raise ValueError("proportions must use width=1")
        objects.append({"kind": obj["kind"], "box": box, "proportions": proportions,
                        "yaw_degrees": _number(obj.get("yaw_degrees"), -90, 90)})
        if obj["kind"] in still_life.FRUITS:
            objects[-1].update(_fruit_profile(obj))
        if "top_box" in obj:
            cap = _vector(obj["top_box"], 4, 0, 1)
            if min(cap[2:]) <= 0 or cap[0]+cap[2] > 1.001 or cap[1]+cap[3] > 1.001:
                raise ValueError("invalid top face")
            objects[-1]["top_box"] = cap
    light = _vector(doc.get("light"), 3, -8, 8)
    if light[1] < 3:
        raise ValueError("light must be above the tabletop")
    return {"objects": objects, "light": light,
            "camera_elevation_degrees": _number(doc.get("camera_elevation_degrees"), 10, 65)}


BOX_KEYS = ("bbox", "top_bbox", "stem_bbox", "neck_bbox")


def _as_thousandths(raw: list) -> list:
    """Step 3.7 Flash sometimes writes 0.128 where the prompt asks for 128; read that answer as thousandths.

    Only when every box number is at most 1 and at least one is a fraction, so an answer already in
    thousandths is never rescaled; a tiny whole-number box stays tiny and is still rejected.
    """
    numbers = [v for obj in raw if isinstance(obj, dict) for key in BOX_KEYS if isinstance(obj.get(key), list)
               for v in obj[key] if type(v) in (int, float)]
    if not numbers or max(numbers) > 1 or all(float(v).is_integer() for v in numbers):
        return raw
    scale = lambda box: [round(v * 1000, 3) if type(v) in (int, float) else v for v in box]
    return [{**obj, **{key: scale(obj[key]) for key in BOX_KEYS if isinstance(obj.get(key), list)}}
            if isinstance(obj, dict) else obj for obj in raw]


def parse_detections(text: str, aspect: float, *, generative_fruit: bool = False) -> dict:
    """Read native 0..1000 xyxy localization; do the arithmetic on the CPU.

    Asking Step3-VL for world ratios and fractional widths in the same reply
    produced copied example coordinates. Its native localization is much more
    useful. Top ellipses estimate elevation; absent one, use an explicit 25°
    teaching view. Backside depth and box yaw remain assumptions of this model.
    """
    if len(text) > 16000:
        raise ValueError("detection answer too large")
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    doc = json.loads(text)
    if isinstance(doc, dict) and "supported" in doc and type(doc["supported"]) is not bool:
        raise ValueError("invalid supported decision")
    if isinstance(doc, dict) and doc.get("supported") is False:
        raise UnsupportedSketch("unsupported drawing")
    if isinstance(doc, dict) and doc.get("subject") == "head":
        if doc.get("objects"):
            raise UnsupportedSketch("head mixed with other subjects")
        return {"subject": "head"}
    raw = doc.get("objects") if isinstance(doc, dict) else doc
    if not isinstance(raw, list) or not 1 <= len(raw) <= MAX_OBJECTS:
        raise ValueError("expected one to six detections")
    raw = _as_thousandths(raw)
    if generative_fruit and all(isinstance(o, dict) and o.get("kind") in still_life.FRUITS for o in raw):
        # The image model reconstructs the actual surface. Part measurements are
        # needed only for CPU approximation; bad/missing stalk boxes must not
        # prevent a recognized fruit study from reaching the image-to-mesh path.
        for obj in raw:
            a,b,c,d = _vector(obj.get("bbox"), 4, 0, 1000)
            if min(c-a,d-b) < 35:
                raise ValueError("empty fruit detection")
        return {"subject": "fruit"}
    shapes, elevations = [], []
    for obj in raw:
        if not isinstance(obj, dict) or obj.get("kind") not in KINDS:
            raise UnsupportedSketch("unsupported object")
        left, top, right, bottom = _vector(obj.get("bbox"), 4, 0, 1000)
        if min(right-left, bottom-top) < 35:
            raise ValueError("empty detection")
        fruit = {}
        if obj["kind"] in still_life.FRUITS:
            (left,top,right,bottom), fruit = _fruit_measurements(obj,[left,top,right,bottom])
        elif obj.get("stem_bbox") is not None or obj.get("neck_bbox") is not None:
            raise UnsupportedSketch("fruit parts cannot be assigned to a primitive")
        box = [v/1000 for v in (left, top, right-left, bottom-top)]
        shapes.append({"kind": obj["kind"], "box": box, **fruit})
        if obj["kind"] == "cylinder" and "top_bbox" in obj:
            a,b,c,d = _vector(obj["top_bbox"], 4, 0, 1000)
            # Independent localization of the rim and complete cylinder can
            # differ slightly. Union nearby boxes, never clip the top ellipse
            # (its aspect controls the camera). Large disagreement still fails.
            tolerance = min(20, (right-left)*.1, (bottom-top)*.1)
            if not (a < c and b < d and left-tolerance <= a and c <= right+tolerance
                    and top-tolerance <= b and d <= bottom+tolerance):
                raise ValueError("top ellipse outside its cylinder")
            left,top,right,bottom = min(left,a),min(top,b),max(right,c),max(bottom,d)
            shapes[-1]["box"] = [v/1000 for v in (left,top,right-left,bottom-top)]
            ratio = (d-b)/((c-a)*aspect)
            if .17 <= ratio <= .91:
                elevations.append(math.degrees(math.asin(ratio)))
                shapes[-1]["top_box"] = [v/1000 for v in (a,b,c-a,d-b)]
    elevation = max(10, min(65, statistics.median(elevations) if elevations else 25))
    sn, cs = math.sin(math.radians(elevation)), math.cos(math.radians(elevation))
    for obj in shapes:
        image_ratio = obj["box"][3] / (obj["box"][2]*aspect)
        if obj["kind"] in still_life.FRUITS:
            height, yaw = image_ratio / cs, 0
        elif obj["kind"] == "sphere":
            height, yaw = image_ratio, 0
        elif obj["kind"] == "cylinder":
            height, yaw = (image_ratio-sn)/cs, 0
        else:
            # A two-face teaching view. No claim that unseen depth is recovered.
            footprint = math.sin(math.radians(40)) + math.cos(math.radians(40))
            height, yaw = footprint*(image_ratio-sn)/cs, 40
        if not .25 <= height <= 4:
            raise UnsupportedSketch("unsupported proportions")
        obj.update(proportions=[1, height, 1], yaw_degrees=yaw)
    return parse(json.dumps({"supported": True, "objects": shapes,
                            "camera_elevation_degrees": elevation, "light": [-3,6,5]}))


def surface_points(kind: str):
    """Unit solid surface samples, solely for fitting the projected silhouette."""
    if kind == "box":
        return [(x, y, z) for x in (-.5, .5) for y in (-.5, .5) for z in (-.5, .5)]
    points = []
    for j in range(13 if kind == "sphere" else 2):
        phi = math.pi * j / 12 if kind == "sphere" else math.pi * j
        radius = .5 * math.sin(phi) if kind == "sphere" else .5
        for i in range(32):
            angle = 2 * math.pi * i / 32
            points.append((radius * math.cos(angle), .5 * math.cos(phi), radius * math.sin(angle)))
    return points


def camera(elevation: float) -> dict:
    angle = math.radians(elevation)
    return {"target": [0, 1, 0], "distance": 10,
            "elevation": elevation, "azimuth": 0, "fov": 40,
            "position": [0, 1 + 10 * math.sin(angle), 10 * math.cos(angle)]}


def projected_box(points, x, z, scale, cam, aspect):
    """Perspective, +Y up and +Z toward the initial viewer; image Y points down."""
    angle = math.radians(cam["elevation"])
    sn, cs = math.sin(angle), math.cos(angle)
    focal = 1 / math.tan(math.radians(cam["fov"] / 2))
    px, py = [], []
    # points are pre-rotated and grounded in proportion space.
    for a, b, c in points:
        wx, wy, wz = x + a * scale, b * scale - 1, z + c * scale
        depth = 10 - wy * sn - wz * cs
        if depth <= .1:
            return [10, 10, 10, 10]
        px.append(.5 + wx * focal / (2 * aspect * depth))
        py.append(.5 - (wy * cs - wz * sn) * focal / (2 * depth))
    return [min(px), min(py), max(px) - min(px), max(py) - min(py)]


def _fit_at_elevation(annotation: dict, aspect: float, elevation: float) -> tuple[dict, float]:
    """Fit x, z and common scale to each silhouette; preserve estimated proportions.

    Fixed iteration/sample/object budgets avoid per-image GPU optimization.
    Scale of a single view is ambiguous; world units are arbitrary.
    """
    cam = camera(elevation)
    objects, total_error = [], 0.0
    for obj in annotation["objects"]:
        w, h, d = obj["proportions"]
        angle = math.radians(obj["yaw_degrees"])
        sn, cs = math.sin(angle), math.cos(angle)
        samples = still_life.body_points(obj["profile"]) if obj["kind"] in still_life.FRUITS else surface_points(obj["kind"])
        points = [(a * w * cs + c * d * sn, (b + .5) * h, -a * w * sn + c * d * cs)
                  for a, b, c in samples]
        target = obj["box"]

        def loss(params):
            x, z, scale = params
            if abs(x) > 6 or abs(z) > 6 or not .15 <= scale <= 4:
                return 1e6
            box = projected_box(points, x, z, scale, cam, aspect)
            return sum((box[i] - target[i]) ** 2 for i in range(4))

        params = [(target[0] + target[2] / 2 - .5) * 7 * aspect, 0, 1.5]
        score = loss(params)
        for step in (.8, .4, .2, .1, .05, .025, .0125):
            for _ in range(20):
                improved = False
                for axis in range(3):
                    for direction in (-1, 1):
                        trial = params.copy()
                        trial[axis] += direction * step
                        candidate = loss(trial)
                        if candidate < score:
                            params, score, improved = trial, candidate, True
                if not improved:
                    break
        x, z, scale = params
        bbox = projected_box(points, x, z, scale, cam, aspect)
        # This guards layout failures; it does not prove semantic recognition.
        error = max(abs(a - b) for a, b in zip(bbox, target))
        total_error += sum((a-b)**2 for a,b in zip(bbox,target))
        if "top_box" in obj:
            cap = projected_box([p for p in points if abs(p[1]-h) < .0001], x,z,scale,cam,aspect)
            total_error += sum((a-b)**2 for a,b in zip(cap,obj["top_box"]))
            error = max(error, max(abs(a-b) for a,b in zip(cap,obj["top_box"])))
        objects.append({"kind": obj["kind"], "position": [round(x, 4), round(h * scale / 2, 4), round(z, 4)],
                        "size": [round(v * scale, 4) for v in (w, h, d)],
                        "yaw": obj["yaw_degrees"], "source_box": target,
                        "fit_error": round(error, 4)})
        if obj["kind"] in still_life.FRUITS:
            objects[-1].update(profile=obj["profile"], stem=obj["stem"])
    return ({"version": 1, "method": "geometric-approximation", "objects": objects,
             "camera": cam, "light": annotation["light"], "source_aspect": aspect}, total_error)


def fit(annotation: dict, aspect: float) -> dict:
    # The ellipse measures the ray TO THE TOP FACE, not the camera's orbit
    # elevation about the scene centre. Equating these put the eye below the
    # tops of the solids. Fit the camera against the detected top ellipse too.
    calibrated = any("top_box" in obj for obj in annotation["objects"])
    angles = range(10,66,5) if calibrated else [annotation["camera_elevation_degrees"]]
    scene, error = min((_fit_at_elevation(annotation,aspect,a) for a in angles), key=lambda pair:pair[1])
    if calibrated:
        centre = scene["camera"]["elevation"]
        for offset in (-2,-1,1,2):
            if 10 <= centre+offset <= 65:
                trial, score = _fit_at_elevation(annotation,aspect,centre+offset)
                if score < error:
                    scene,error = trial,score
    if any(obj["fit_error"] > .09 for obj in scene["objects"]):
        raise UnsupportedSketch("silhouette does not fit a grounded solid")
    return scene


def clean_solids(image: str, aspect: float, client: VisionChatClient | None) -> dict | None:
    """Clean solids for a sketch of only cubes, balls and cylinders; None sends it to the 3D model as before.

    TRELLIS.2 turned three of four geometry sketches into hollow shells, so by operator
    decision the automatic route looks first and the fit above builds them. An explicit TRELLIS.2
    selection skips this shortcut. Heads, fruit, anything else, and every failed automatic look
    (no model, no answer, a bad answer, a poor fit) go to the 3D model unchanged.
    No token cap: Step 3.7 Flash spent the old 1500 on hidden reasoning and answered nothing.
    """
    if client is None:
        return None
    try:
        reply = client.chat(PROMPT.read_text(encoding="utf-8"), [image],
                            system=ANNOTATE_SYSTEM)
        found = parse_detections(reply.text, aspect, generative_fruit=True)
        if "subject" in found or any(o["kind"] in still_life.FRUITS for o in found["objects"]):
            return None
        return fit(found, aspect)
    except (ModelError, ValueError, TypeError, KeyError):
        return None


def reconstruct(image_path: str, client: VisionChatClient, portrait: MediaSlot | None = None, *, model_choice: str = "auto") -> dict:
    with Image.open(image_path) as image:
        aspect = image.width / image.height
    if not .1 <= aspect <= 10:
        raise UnsupportedSketch("image aspect ratio is outside the viewer bounds")
    if portrait is not None and portrait.extra.get("scene_format") == "glb":
        from studio.making import glb, view_calibration
        source = to_data_uri(image_path, max_edge=1024)
        solids = clean_solids(source, aspect, client) if model_choice == "auto" else None
        if solids is not None:
            return solids
        result = portrait.to_mesh(image=source, model_choice="trellis2" if model_choice == "auto" else model_choice)
        scene = glb.scene(result.content, aspect, result.model)
        scene.update(view_calibration.calibrate(result.content, source, client))
        return scene
    prompt = PROMPT.read_text(encoding="utf-8")
    image = to_data_uri(image_path, max_edge=1024)
    for attempt in range(2):
        reply = client.chat(prompt, [image], system=ANNOTATE_SYSTEM, max_tokens=MAX_TOKENS)
        try:
            annotation = parse_detections(reply.text, aspect, generative_fruit=True)
            break
        except (MissingFruitMeasurement, json.JSONDecodeError) as error:
            if attempt:
                raise
            # One metered annotation repair, before any expensive generation.
            # Unsupported subjects and invalid numeric bounds are not retried.
            if isinstance(error, json.JSONDecodeError):
                prompt += RETRY_JSON_CLAUSE
            else:
                prompt += RETRY_FRUIT_CLAUSE
    if annotation.get("subject") in ("head", "fruit"):
        fruit = annotation["subject"] == "fruit"
        unavailable = FruitMeshUnavailable if fruit else PortraitUnavailable
        if portrait is None:
            raise unavailable("image-to-mesh worker is not configured")
        try:
            result = portrait.to_mesh(image=image, subject="fruit") if fruit else portrait.to_mesh(image=image)
        except ModelUnavailable as error:
            raise unavailable("image-to-mesh worker did not answer") from error
        except ModelRefused as error:
            raise ValueError("generated mesh failed its surface checks") from error
        return mesh.scene(result.content, aspect, subject="fruit" if fruit else "head")
    fitted = fit(annotation, aspect)
    if any(o["kind"] in still_life.FRUITS for o in fitted["objects"]):
        return still_life.scene(fitted)
    return fitted
