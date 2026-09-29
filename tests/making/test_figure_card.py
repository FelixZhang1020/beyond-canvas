"""The picture on a 3D figure's card is the figure as the class page's viewer shows it. Drawn on the CPU, no model.

Operator: "the original model looks good, but preview is ugly". The card was the checks' flat paint
shading: a grey, dim toy with no shadow, windows painted over by their own wall, and round parts in facets.
"""
import io
import json

from PIL import Image, ImageChops

from studio.making import figure, figure_card
from studio.making.figure_card import PAPER, card, picture


def part(shape="box", at=(0, .5, 0), size=(.5, .5, .5), colour="#aa5533"):
    return {"shape": shape, "at": list(at), "size": list(size), "turn": [0, 0, 0], "colour": colour}


def toy(*parts):
    return {"version": 1, "parts": list(parts)}


DOG = {"parts": [part("capsule", (0, .6, 0), (.5, .8, .4), "#f5f0e1"), part("sphere", (0, 1.4, 0), (.4, .4, .4), "#f5f0e1"),
                 part("sphere", (-.08, 1.45, .19), (.06, .06, .06), "#111111"),
                 part("sphere", (.08, 1.45, .19), (.06, .06, .06), "#111111")]}
# A cream wall with four blue windows standing .03 proud of it, as the studio wrote a tower from a painting.
WALL = part("box", (0, .625, 0), (.5, .7, .35), "#f0e6d2")
WINDOWS = [part("box", (x, y, .18), (.06, .08, .05), "#2050c0") for x in (-.12, .12) for y in (.425, .675)]


def pixels_near(image, colour, tolerance=3):
    return sum(n for n, c in image.getcolors(image.width * image.height)
               if max(abs(a - b) for a, b in zip(colour, c)) <= tolerance)


def test_the_card_picture_shows_the_toy_close_up():
    """Operator: on the figure's card the toy was small in a wide empty picture, framed to leave room
    for any turn. The card is cropped to what was drawn, so the toy fills its height whatever the base's width."""
    with Image.open(io.BytesIO(card(figure.settle(figure.parse(json.dumps(DOG)))))) as drawn:
        drawn = drawn.convert("RGB")
    box = ImageChops.difference(drawn, Image.new("RGB", drawn.size, PAPER)).getbbox()
    assert drawn.size == (840, 360) and box[3] - box[1] >= .9 * 360, box   # 840 by 360 stays sharp on a phone


def test_the_card_is_lit_in_the_colours_the_viewer_shows():
    """Measured from the operator's screenshot of the viewer: the base's top reads (223, 211, 188) in the sun and
    (161, 150, 131) in the toy's shadow. The flat paint shading gave neither anywhere on the card."""
    drawn = picture(toy(WALL, *WINDOWS), width=320, height=320)
    assert pixels_near(drawn, (223, 211, 188)) > 5000, 'the sunlit base, 12842 pixels when measured'
    assert pixels_near(drawn, (161, 150, 131)) > 1000, "the toy's shadow on the base, 2703 when measured"


def test_every_window_on_a_wall_shows():
    """Painter's order sorted the wall by its middle, so the wall's far half was painted over both windows on that
    side (0 blue pixels each). The card cuts a flat face small and leaves out the faces turned away."""
    for window in WINDOWS:
        drawn = picture(toy(WALL, window), width=320, height=320)
        shown = sum(n for n, c in drawn.getcolors(320 * 320) if c[2] > c[0] + 50 and c[2] > c[1] + 20)
        assert shown > 100, (window["at"], shown)   # 138 to 169 when measured


def test_a_house_stands_on_its_painted_ground_without_saw_teeth():
    """A ground slab sorted with the parts cut saw teeth into the foot of the house standing on it (18 pixels of
    ground inside the house here); painted before whatever stands on it, the foot is clean."""
    drawn = picture(toy(part("cylinder", (0, .025, 0), (1.2, .05, 1.2), "#a0522d"),
                        part("box", (0, .7, 0), (.4, 1.4, .4), "#ffd700")), width=320, height=320)
    px, teeth = drawn.load(), 0
    for x in range(320):
        yellow = [px[x, y][0] > 100 and px[x, y][1] > .7 * px[x, y][0] and px[x, y][2] < .3 * px[x, y][1] for y in range(320)]
        house = [y for y in range(320) if yellow[y]]
        teeth += sum(1 for y in range(min(house), max(house)) if px[x, y][1] < .6 * px[x, y][0]) if house else 0
    assert teeth == 0


def test_a_round_part_is_smooth_not_a_disco_ball():
    """The viewer shades a ball smooth; flat patches read as a disco ball (7 sudden steps across this one).
    Blended within the part, the colour runs across it without a step."""
    drawn = picture(toy(part("sphere", (0, .6, 0), (1.2, 1.2, 1.2), "#c04040")), width=320, height=320)
    px, y = drawn.load(), 320 * 2 // 5
    ball = [x for x in range(320) if px[x, y][1] < .6 * px[x, y][0]]
    steps = [x for x in range(ball[0] + 4, ball[-1] - 3) if max(abs(a - b) for a, b in zip(px[x, y], px[x - 1, y])) > 3]
    assert len(ball) > 100 and steps == [], steps


def test_blending_never_carries_one_part_s_colour_into_the_next(monkeypatch):
    """Only a round part is blended, and only where the whole blend stays on it: a box beside a ball keeps every
    pixel of its faces exactly as it is drawn with no blending at all."""
    scene = toy(part("box", (.35, .3, 0), (.3, .6, .6), "#2050c0"), part("sphere", (-.25, .35, 0), (.7, .7, .7), "#c04040"))
    blended = list(picture(scene, width=320, height=320).get_flattened_data())
    monkeypatch.setattr(figure_card, "_smooth", lambda image, *rest: image)
    plain = list(picture(scene, width=320, height=320).get_flattened_data())
    box = [i for i, c in enumerate(plain) if c[2] > c[0] + 50]
    assert len(box) > 1000 and all(blended[i] == plain[i] for i in box)
    assert blended != plain, "the ball itself is blended"
