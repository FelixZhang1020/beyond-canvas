"""A 3D toy figure inspired by a child's colour painting, checked before any child sees it (painting-to-figure).

Step 3.7 Flash does not write code here. It lists simple parts (spheres, boxes, capsules...), and nothing but
their numbers and colours is kept. The parts are then settled under gravity, because the model places heights
loosely (once a corgi's head floated 0.18 above its body and a dog stood 0.27 above its base), and
drawn on the CPU so that two checks can look before the child does: the studio-safety screen, and a look check
in which the model compares the preview with the painting. A figure that fails is written again with the
reason, three writings in all; a third failure is held back, and the class simply gets no figure that time
(docs/measured/figure-three-writings.md). Nothing here claims the
figure is the child's painting: it is a toy inspired by it, and the page says so.
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Callable

from PIL import ImageColor

from studio.core.errors import EmptyCompletion, ModelCancelled
from studio.making.figure_render import SHAPES, rotation, sheet

ROOT = Path(__file__).resolve().parents[2] / "skills/painting-to-figure/assets/prompts"
MAX_PARTS = 140
WRITE_TOKENS = 32000   # 16000 ran out on the savanna painting; its answer took 21,634
LOOK_TOKENS = 16000   # 8000 ran out once: all hidden reasoning, no answer
WRITINGS = 3   # a third showed about six more toys a class than two (docs/measured/figure-three-writings.md)
# The standing instructions and the lines added to a second writing; all are on the prompt page.
WRITE_SYSTEM = "You design toy figures. Return only the requested JSON."
LOOK_SYSTEM = "You check toys for young children. Return only JSON."
FIX_CLAUSE = "\n\nAn earlier toy was checked and not shown to the child. Fix this: {fix}"
FIX_INSTRUCTION = {
    "unreadable": "Return complete, valid JSON in exactly the requested shape.",
    "screened": "Keep it gentle and friendly for a young child.",
    "unclear": "Make it clearly the painting's main subject (in a busy scene, its one main thing alone), "
               "with each main character's face on it keeping its eyes.",
}


# Colour names, as their web colours: the 148 Pillow knows (which held every one of the twenty-five this
# file used to list itself, to the same hex), and the few the model writes that are not among
# them. A rewrite once wrote "orange" and "white" three times over; one night's run threw
# answers away whole for "lavender", "peach", "light blue", "dark_brown", "lightgray" and "medium blue".
# A name is still a closed list: no free text becomes part of a figure.
EXTRA_WORDS = {"peach": "#ffcba4", "cream": "#fffdd0", "charcoal": "#36454f", "skin": "#f1c27d"}
# "light brown" and "dark_brown" are not names anywhere; they are a known name with a known word in front.
SHADES = {"light": lambda c: tuple(round(v + .4 * (255 - v)) for v in c),
          "pale": lambda c: tuple(round(v + .4 * (255 - v)) for v in c),
          "dark": lambda c: tuple(round(v * .6) for v in c),
          "deep": lambda c: tuple(round(v * .6) for v in c),
          "medium": lambda c: c, "mid": lambda c: c, "bright": lambda c: c}


def _named(word):
    """One colour name as #rrggbb, or None. Spaces, hyphens and underscores are not part of a name.

    Pillow rewrites its own table as it is used: the first look at a name replaces "#ffffff" with
    (255, 255, 255), so both forms of the same colour have to be read (measured: reading
    only the written form refused every name once anything had drawn in one).
    """
    plain = re.sub(r"[\s_-]+", "", word)
    if plain in EXTRA_WORDS:
        return EXTRA_WORDS[plain]
    known = ImageColor.colormap.get(plain)
    if isinstance(known, tuple) and len(known) >= 3:
        return "#" + "".join(f"{channel:02x}" for channel in known[:3])
    return known if isinstance(known, str) else None


def _colour(value):
    # Red, green and blue from 0 to 1, which is how whole answers once came. Anything outside that,
    # including the 0-to-255 way of writing the same thing, is refused: a guess at the scale is a wrong colour.
    if isinstance(value, list) and len(value) == 3 and all(type(v) in (int, float) and 0 <= v <= 1 for v in value):
        return "#" + "".join(f"{round(v * 255):02x}" for v in value)
    if not isinstance(value, str):
        raise ValueError("colour must be #rrggbb or a common colour word")
    word = value.strip().lower()
    if re.fullmatch(r"#[0-9a-fA-F]{6}", word):
        return word
    shade, _gap, rest = re.sub(r"[_-]", " ", word).partition(" ")
    found = _named(word) or _shaded(shade, rest)
    if found is None:
        raise ValueError("colour must be #rrggbb or a common colour word")
    return found


def _shaded(shade, rest):
    """"light brown", "dark_brown": a known word in front of a known name, or None."""
    base = _named(rest) if shade in SHADES and rest else None
    if base is None:
        return None
    red, green, blue = SHADES[shade](tuple(int(base[i:i + 2], 16) for i in (1, 3, 5)))
    return f"#{red:02x}{green:02x}{blue:02x}"


def _numbers(value, low, high, name):
    if not isinstance(value, list) or len(value) != 3 or any(type(v) not in (int, float) for v in value):
        raise ValueError(f"{name} must be three numbers")
    if any(not math.isfinite(v) or not low <= v <= high for v in value):
        raise ValueError(f"{name} outside {low}..{high}")
    return [float(v) for v in value]


def parse(text: str) -> dict:
    """The model's answer -> a bounded figure, or ValueError. Only numbers and colours are kept, never prose."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        doc, _ = json.JSONDecoder().raw_decode(text)   # anything after the JSON is dropped, never read
    except ValueError:
        doc = _cut_off(text)
    raw = doc.get("parts") if isinstance(doc, dict) else None
    if not isinstance(raw, list) or not 3 <= len(raw) <= MAX_PARTS:
        raise ValueError("a figure needs 3 to 140 parts")
    parts = []
    for p in raw:
        if not isinstance(p, dict) or p.get("shape") not in SHAPES:
            raise ValueError("unknown part shape")
        size = p.get("size")
        if isinstance(size, list) and len(size) == 1:
            size = size * 3   # one number: the same every way, as the model means for a sphere
        parts.append({"shape": p["shape"], "at": _numbers(p.get("at"), -3, 4, "at"),
                      # A whisker or a pupil comes as 0.005; the floor only refuses a part of no size at all.
                      "size": _numbers(size, .001, 4, "size"),
                      "turn": _numbers(p.get("turn", [0, 0, 0]), -360, 360, "turn"),
                      "colour": _colour(p.get("colour", p.get("color")))})
    return {"version": 1, "parts": parts}


def _cut_off(text: str) -> dict:
    """An answer that stops in the middle, closed after its last whole part.

    The commonest format loss measured in one run: 14 of 41 unreadable answers failed at their very last
    character, the model having run out of room mid-part. The parts that arrived are a toy, and the checks
    still decide whether it is shown; the half-written part is dropped. Three tries back through the text is
    enough, because a part holds numbers and a colour, never another part.
    """
    end = len(text)
    for _ in range(3):
        end = text.rfind("}", 0, end)
        if end < 0:
            break
        try:
            doc, _rest = json.JSONDecoder().raw_decode(text[:end + 1] + "]}")
            return doc
        except ValueError:
            continue
    raise ValueError("the answer is not JSON")


def _box(p):
    """The world-space box around one part: the corners of its turned extent."""
    m, (sx, sy, sz), t = rotation(p["turn"]), p["size"], p["at"]
    corners = [[m[k][0] * x + m[k][1] * y + m[k][2] * z + t[k] for k in range(3)]
               for x in (-sx / 2, sx / 2) for y in (-sy / 2, sy / 2) for z in (-sz / 2, sz / 2)]
    return [min(c[k] for c in corners) for k in range(3)], [max(c[k] for c in corners) for k in range(3)]


def _touch(a, b, gap):
    return all(a[0][k] - gap <= b[1][k] and b[0][k] - gap <= a[1][k] for k in range(3))


def _groups(boxes, members, gap):
    """The parts among members whose boxes touch within gap, grouped transitively."""
    groups, left = [], set(members)
    while left:
        group, todo = set(), [left.pop()]
        while todo:
            i = todo.pop()
            group.add(i)
            near = {j for j in left if _touch(boxes[i], boxes[j], gap)}
            left -= near
            todo += near
        groups.append(group)
    return groups


def is_ground(p):
    """A wide flat slab at the bottom: the model's ground, which the base already is. Its colour stays."""
    (w, h, d), y = p["size"], p["at"][1]
    return p["shape"] in ("cylinder", "box") and h <= .15 and min(w, d) >= 1.0 and y - h / 2 <= .15


def settle(figure: dict, gap: float = .04, reach: float = .3) -> dict:
    """Let gravity settle the toy. Ground slabs lie flat on the base; parts that touch stay together; small loose
    bits (an eye, an ear) join the nearest group within reach rather than fall; then each group drops straight
    down onto the base (y = 0) or onto a part directly under it. Parts only ever move down."""
    parts = [dict(p, at=list(p["at"])) for p in figure["parts"]]
    for p in parts:
        if is_ground(p):
            p["at"][1] = p["size"][1] / 2
    boxes = [_box(p) for p in parts]
    grounds = {i for i, p in enumerate(parts) if is_ground(p)}
    groups = [{i} for i in grounds] + _groups(boxes, set(range(len(parts))) - grounds, gap)
    _fold_small(groups, boxes, reach)
    for _ in range(len(groups)):
        moved = False
        for g in sorted(groups, key=lambda g: min(boxes[i][0][1] for i in g)):
            drop = min(boxes[i][0][1] - _support(boxes, i, g) for i in g)
            if drop > 1e-3:
                for i in g:
                    parts[i]["at"][1] -= drop
                    boxes[i] = ([boxes[i][0][0], boxes[i][0][1] - drop, boxes[i][0][2]],
                                [boxes[i][1][0], boxes[i][1][1] - drop, boxes[i][1][2]])
                moved = True
        if not moved:
            break
    return dict(figure, parts=parts)


def _volume(boxes, group):
    return sum(max(1e-6, math.prod(boxes[i][1][k] - boxes[i][0][k] for k in range(3))) for i in group)


def _fold_small(groups, boxes, reach):
    """Groups under 3% of the biggest join the biggest neighbour within reach, in place."""
    biggest = max(_volume(boxes, g) for g in groups)
    span = lambda g: ([min(boxes[i][0][k] for i in g) for k in range(3)], [max(boxes[i][1][k] for i in g) for k in range(3)])
    for g in sorted(groups, key=lambda g: _volume(boxes, g)):
        if _volume(boxes, g) >= .03 * biggest:
            continue
        near = [h for h in groups if h is not g and _touch(span(g), span(h), reach)]
        if near:
            max(near, key=lambda h: _volume(boxes, h)).update(g)
            groups.remove(g)


def _support(boxes, i, group):
    """The height part i would land on: the base, or the top of another group's part directly under it."""
    lo, hi = boxes[i]
    tops = [boxes[j][1][1] for j in range(len(boxes)) if j not in group and boxes[j][1][1] <= lo[1] + 1e-6
            and all(lo[k] < boxes[j][1][k] and boxes[j][0][k] < hi[k] for k in (0, 2))]
    return max([0.0] + tops)


def look(painting: str, figure: dict, client) -> tuple[bool, str]:
    """The model compares the painting with a preview of the figure. Only a clear pass passes."""
    reply = client.chat(_prompt("look.txt"), [painting, sheet(figure)],
                        system=LOOK_SYSTEM, max_tokens=LOOK_TOKENS)
    try:
        text = reply.text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        verdict = json.loads(text)
        passed = (verdict.get("same_subject") is True and verdict.get("faces") in ("ok", "none")
                  and verdict.get("broken") is False and verdict.get("upsetting") is False)
        fix = verdict.get("fix") if isinstance(verdict.get("fix"), str) else ""
    except (ValueError, AttributeError):
        return False, ""
    return passed, fix[:200]


def make(painting: str, client, screen: Callable[[str], bool] | None = None,
         cancelled: Callable[[], bool] = lambda: False, looker=None) -> dict:
    """Write, settle and check a figure, at most three times. Returns {"held_back": False, "figure": ...} or
    {"held_back": True, "reason_code": "figure_held_back"}. A model outage is raised, never hidden; an empty
    or unreadable answer is a failed writing. The teacher's stop is read before every call.

    Writing a toy and judging one are different jobs: the writer needs room to list a hundred parts, the
    check needs to be careful about a picture. They used to be one model, which is why the
    overnight speed trial could not say which half it had sped up. A deployment that names no looker keeps
    using the writer for both, as every deployment did before.
    """
    def call(step, *args):
        if cancelled():
            raise ModelCancelled("Figure cancelled")
        return step(*args)

    looker = looker or client
    fix = ""
    for writing in range(1, WRITINGS + 1):
        prompt = _prompt("figure.txt") + (FIX_CLAUSE.format(fix=fix) if fix else "")
        try:
            reply = call(lambda: client.chat(prompt, [painting], max_tokens=WRITE_TOKENS, system=WRITE_SYSTEM))
            figure = settle(parse(reply.text))
        except (ValueError, EmptyCompletion):
            fix = FIX_INSTRUCTION["unreadable"]
            continue
        if screen is not None and not call(screen, sheet(figure)):
            fix = FIX_INSTRUCTION["screened"]
            continue
        passed, fix = call(look, painting, figure, looker)
        if passed:   # both must pass: the check gave different answers on the same toy (operator)
            passed, fix = call(look, painting, figure, looker)
        if passed:
            return {"held_back": False, "figure": figure, "writings": writing}
        fix = fix or FIX_INSTRUCTION["unclear"]
    return {"held_back": True, "reason_code": "figure_held_back", "writings": WRITINGS}


def _prompt(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")
