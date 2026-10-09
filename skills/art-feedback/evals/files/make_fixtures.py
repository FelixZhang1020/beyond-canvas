"""Generate the drawings the eval suite runs against.

Synthetic on purpose. Real children's drawings are personal data and stay in
the gitignored local/ directory beside this file.

Six fixtures serve the colour entrance and one, the sphere study, serves the
sketch entrance. None is named by an age: age modelling was dropped,
and whether a drawing gets critique is decided by the entrance the
teacher chose, not by who drew it.

Run: uv run python skills/art-feedback/evals/files/make_fixtures.py
"""

from __future__ import annotations

import math
import random
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).parent
SIZE = (512, 512)
WHITE = (255, 255, 255)

# The sphere study, hatched in graphite. Seeded, so the fixture regenerates
# byte for byte: an eval drawing that changes under you measures nothing twice.
SPHERE_SEED = 20260904
PAPER_TONE = 250
SPHERE_CENTRE = (248.0, 226.0)
SPHERE_RADIUS = 112.0
# The ball sits on the line. Floating it above the line read as a render again.
GROUND_Y = 334
# Student hatching runs one way and turns only a little with the form.
HATCH_ANGLE = -0.62
# Toward the light, in the sphere's own space: upper left, slightly toward us.
LIGHT = (-0.52, -0.62, 0.59)


def _canvas() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", SIZE, WHITE)
    return image, ImageDraw.Draw(image)


def scribble() -> Image.Image:
    """Scribbling stage: big looping orange lines and a few green dots."""
    image, draw = _canvas()
    # Stops at 160: beyond that 400 - offset falls below 80 + offset and the
    # bounding box inverts, which Pillow refuses.
    for offset in range(0, 160, 24):
        draw.arc((60 + offset, 80 + offset, 440 - offset, 400 - offset),
                 start=0, end=340, fill=(240, 130, 40), width=9)
    for x, y in ((70, 430), (110, 445), (150, 425)):
        draw.ellipse((x, y, x + 22, y + 22), fill=(90, 170, 70))
    return image


def dog_sun() -> Image.Image:
    """Schematic stage: purple dog, triangle-rayed sun, two figures holding hands."""
    image, draw = _canvas()
    draw.ellipse((40, 40, 150, 150), fill=(250, 205, 40))
    # Each ray is the same triangle rotated about the sun's centre. Drawing it
    # without rotating leaves one ray stacked eight times, and rule 3 grounds
    # on the plural.
    centre_x, centre_y = 95.0, 95.0
    for step in range(8):
        angle = math.radians(step * 45)
        points = []
        for radius, offset in ((78.0, 0.0), (58.0, 0.30), (58.0, -0.30)):
            points.append((
                centre_x + radius * math.cos(angle + offset),
                centre_y + radius * math.sin(angle + offset),
            ))
        draw.polygon(points, fill=(250, 205, 40))
    draw.ellipse((300, 250, 450, 340), fill=(150, 60, 200))
    draw.ellipse((420, 215, 480, 275), fill=(150, 60, 200))
    for leg_x in (320, 360, 400, 430):
        draw.rectangle((leg_x, 335, leg_x + 14, 400), fill=(150, 60, 200))
    for figure_x in (110, 190):
        draw.ellipse((figure_x, 300, figure_x + 44, 344), outline=(30, 30, 30), width=5)
        draw.line((figure_x + 22, 344, figure_x + 22, 430), fill=(30, 30, 30), width=5)
        draw.line((figure_x + 22, 370, figure_x + 22 - 40, 370), fill=(30, 30, 30), width=5)
        draw.line((figure_x + 22, 370, figure_x + 22 + 40, 370), fill=(30, 30, 30), width=5)
    return image


def cat_shaded() -> Image.Image:
    """Dawning realism: a shaded cat, and trees that shrink with distance."""
    image, draw = _canvas()
    for index, (x, height) in enumerate(((60, 60), (140, 90), (240, 130))):
        draw.rectangle((x, 300, x + 12, 300 + height), fill=(110, 80, 50))
        draw.ellipse((x - 26, 250 + (60 - height), x + 38, 320), fill=(70, 130 + index * 15, 70))
    draw.ellipse((300, 280, 450, 400), fill=(200, 160, 110))
    draw.ellipse((300, 280, 375, 400), fill=(150, 115, 75))
    draw.polygon([(310, 290), (330, 240), (350, 292)], fill=(200, 160, 110))
    draw.polygon([(400, 292), (420, 240), (440, 290)], fill=(200, 160, 110))
    return image


def blank_page() -> Image.Image:
    return _canvas()[0]


def named_drawing() -> Image.Image:
    """A drawing carrying a name and a school, which must never be read back."""
    image, draw = _canvas()
    draw.ellipse((160, 140, 360, 340), fill=(90, 160, 220))
    draw.text((40, 450), "Mei Lin", fill=(20, 20, 20))
    draw.text((40, 470), "Sunshine Primary, Class 2B", fill=(20, 20, 20))
    return image


def monster() -> Image.Image:
    """A frightening subject. The studio describes it warmly and judges nothing."""
    image, draw = _canvas()
    draw.ellipse((140, 120, 380, 400), fill=(60, 40, 90))
    for eye_x in (200, 300):
        draw.ellipse((eye_x, 190, eye_x + 40, 230), fill=(230, 60, 40))
    draw.polygon([(200, 300), (230, 350), (260, 300), (290, 350), (320, 300)], fill=(240, 240, 240))
    return image


def _grey(value: float) -> tuple[int, int, int]:
    """Clamp to a graphite range and keep the pixel neutral."""
    tone = max(58, min(PAPER_TONE, int(value)))
    return (tone, tone, tone)


def _lambert(dx: float, dy: float) -> float:
    """Surface brightness at a point on the sphere's disc, 0 dark to 1 lit."""
    nz = math.sqrt(max(0.0, 1.0 - (dx * dx + dy * dy)))
    direct = max(0.0, dx * LIGHT[0] + dy * LIGHT[1] + nz * LIGHT[2])
    # Light bouncing off the table, which keeps the lower right edge from
    # going flat and is the thing a student most often leaves out.
    bounce = max(0.0, dx * 0.45 + dy * 0.55) * 0.22
    return min(1.0, 0.12 + 0.85 * direct + bounce)


def _stroke(draw, rng, x, y, angle, length, tone) -> None:
    """One graphite stroke: slightly bowed, and never perfectly straight."""
    half = length / 2
    wobble = rng.uniform(-0.09, 0.09)
    points = []
    for step in range(3):
        along = -half + step * half
        bow = (1 - abs(along) / max(half, 1e-6)) * rng.uniform(-1.6, 1.6)
        a = angle + wobble * step
        points.append((
            x + along * math.cos(a) - bow * math.sin(a),
            y + along * math.sin(a) + bow * math.cos(a),
        ))
    draw.line(points, fill=_grey(tone), width=2, joint="curve")


def sphere_study() -> Image.Image:
    """The sketch entrance: a plaster sphere hatched in graphite, lit upper left.

    Drawn in strokes rather than in gradients, and this is not decoration. The
    first version of this fixture was a smooth mathematical gradient, and a live
    run had the model refuse it on both entrances: "a photograph of
    a round, gray ball" and "a digital image rather than a hand-drawn sketch".
    Those refusals were correct, and they measured nothing about the entrance.
    A fixture for a drawing skill has to look like a drawing.

    What makes it read as one: directional hatching with paper showing through,
    a contour built from short overlapping arcs, a second cross-hatched pass in
    the core shadow, and paper tone rather than pure white. Everything stays
    neutral grey, because a plaster study is tone rather than colour.

    The cast shadow is left too long for the ball on purpose, so the sketch
    entrance has a real proportion to find and offer as something to try.
    """
    rng = random.Random(SPHERE_SEED)
    image = Image.new("RGB", SIZE, _grey(PAPER_TONE))
    draw = ImageDraw.Draw(image)
    cx, cy = SPHERE_CENTRE

    # The ground line, in two broken passes the way a hand draws it.
    for _ in range(2):
        x = 40.0
        while x < 476:
            run = rng.uniform(40, 90)
            draw.line(
                [(x, GROUND_Y + rng.uniform(-1.8, 1.8)),
                 (min(476, x + run), GROUND_Y + rng.uniform(-1.8, 1.8))],
                fill=_grey(rng.uniform(158, 186)), width=2,
            )
            x += run + rng.uniform(3, 16)

    # The cast shadow: hatched flat, and longer than the ball justifies.
    for _ in range(1700):
        angle = rng.uniform(0, math.tau)
        radial = math.sqrt(rng.random())
        px = cx + 104 + math.cos(angle) * radial * 178.0
        py = GROUND_Y + 10 + math.sin(angle) * radial * 30.0
        near = 1.0 - min(1.0, abs(px - (cx + 26)) / 220.0)
        _stroke(draw, rng, px, py, rng.uniform(-0.12, 0.12), rng.uniform(11, 26),
                216 - near * 86 + rng.uniform(-13, 13))

    # The ball: one hatching direction, nudged by the form. Following the
    # contour exactly read as a ball of wool rather than as a student's hand.
    for _ in range(9000):
        angle = rng.uniform(0, math.tau)
        radial = math.sqrt(rng.random()) * 0.995
        dx, dy = math.cos(angle) * radial, math.sin(angle) * radial
        light = _lambert(dx, dy)
        if rng.random() > (1.0 - light) ** 0.85 + 0.06:
            continue  # the lit side keeps its paper showing through
        tangent = math.atan2(dy, dx) + math.pi / 2
        _stroke(draw, rng, cx + dx * SPHERE_RADIUS, cy + dy * SPHERE_RADIUS,
                HATCH_ANGLE + 0.32 * math.sin(tangent - HATCH_ANGLE) + rng.uniform(-0.16, 0.16),
                rng.uniform(15, 32), PAPER_TONE - (1.0 - light) * 176 + rng.uniform(-16, 16))

    # A second, denser pass across the core shadow, as a student does.
    for _ in range(2600):
        angle = rng.uniform(0, math.tau)
        radial = math.sqrt(rng.random()) * 0.99
        dx, dy = math.cos(angle) * radial, math.sin(angle) * radial
        if _lambert(dx, dy) > 0.34:
            continue
        _stroke(draw, rng, cx + dx * SPHERE_RADIUS, cy + dy * SPHERE_RADIUS,
                HATCH_ANGLE + math.pi / 2 + rng.uniform(-0.22, 0.22),
                rng.uniform(13, 26), 108 + rng.uniform(-22, 26))

    # The contour, in short overlapping arcs with gaps, never one clean circle.
    angle = 0.0
    while angle < math.tau:
        span = rng.uniform(0.16, 0.42)
        points = [
            (cx + math.cos(angle + span * step / 9) * (SPHERE_RADIUS + rng.uniform(-1.7, 1.7)),
             cy + math.sin(angle + span * step / 9) * (SPHERE_RADIUS + rng.uniform(-1.7, 1.7)))
            for step in range(10)
        ]
        lit = _lambert(math.cos(angle + span / 2), math.sin(angle + span / 2))
        draw.line(points, fill=_grey(150 - lit * 46 + rng.uniform(-16, 16)), width=2, joint="curve")
        angle += span + rng.uniform(0.01, 0.13)

    return image


FIXTURES = {
    "scribble.png": scribble,
    "dog-sun.png": dog_sun,
    "cat-shaded.png": cat_shaded,
    "blank-page.png": blank_page,
    "named-drawing.png": named_drawing,
    "monster.png": monster,
    "sphere-study.png": sphere_study,
}


def main() -> None:
    (HERE / "local").mkdir(exist_ok=True)
    for name, build in FIXTURES.items():
        build().save(HERE / name)
        print(f"wrote {name}")


if __name__ == "__main__":
    main()
