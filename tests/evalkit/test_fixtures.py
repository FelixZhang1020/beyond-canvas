import re
from pathlib import Path

import pytest
from conftest import load_script
from PIL import Image

FILES = Path("skills/art-feedback/evals/files")
EXPECTED = [
    "scribble.png",
    "dog-sun.png",
    "cat-shaded.png",
    "monster.png",
    "blank-page.png",
    "named-drawing.png",
    "sphere-study.png",
]
AGE_BAND = re.compile(r"-\d+-\d+\.png$")


@pytest.mark.parametrize("name", EXPECTED)
def test_every_fixture_exists_and_is_a_square_image(name):
    with Image.open(FILES / name) as image:
        assert image.size == (512, 512)


def test_the_generator_and_the_suite_agree_on_the_fixtures():
    """A fixture the script does not build is one nobody can regenerate."""
    script = load_script(FILES / "make_fixtures.py", "make_fixtures")
    assert set(script.FIXTURES) == set(EXPECTED)


def test_no_fixture_is_named_by_an_age_band():
    """Age modelling was dropped. A name like dog-sun-6-8 keeps it alive."""
    for path in FILES.glob("*.png"):
        assert not AGE_BAND.search(path.name), path.name


def test_the_sphere_study_is_a_grey_drawing_for_the_sketch_entrance():
    """A plaster-cast study is tone, not colour: every pixel is a grey, and graded."""
    with Image.open(FILES / "sphere-study.png") as image:
        colours = image.convert("RGB").getcolors(maxcolors=100000) or []
    greys = [colour for _, colour in colours if colour[0] == colour[1] == colour[2]]
    assert len(greys) == len(colours) > 8


def _ink_roughness(path):
    """Mean step between neighbouring pixels, counted only where there is ink.

    Hatching makes this large because every stroke has two edges. A smooth
    gradient makes it small, because neighbouring pixels barely differ.
    """
    with Image.open(path) as image:
        grey = image.convert("L")
    width, height = grey.size
    pixel = grey.load()
    total = counted = 0
    for y in range(height):
        for x in range(width - 1):
            left, right = pixel[x, y], pixel[x + 1, y]
            if left < 244 or right < 244:
                total += abs(left - right)
                counted += 1
    return total / max(counted, 1)


def test_the_sphere_study_is_drawn_in_strokes_rather_than_rendered():
    """A fixture for a drawing skill has to look like a drawing.

    The first sphere study was a smooth mathematical gradient, and a live run
    had the model refuse it on both entrances as "a photograph of a
    round, gray ball" and "a digital image rather than a hand-drawn sketch".
    Both refusals were correct and both measured nothing about the entrance.

    Ink roughness separates the two cleanly: the render scored 2.58 and the
    hatched study 9.83, so the threshold sits between them with room either
    side. Run `_ink_roughness` on a replacement before lowering it.
    """
    assert _ink_roughness(FILES / "sphere-study.png") > 6.0


def test_the_blank_page_really_is_blank():
    with Image.open(FILES / "blank-page.png") as image:
        assert image.convert("RGB").getcolors() == [(512 * 512, (255, 255, 255))]


@pytest.mark.skipif(not Path(".gitignore").exists(), reason="the public copy is published without one")
def test_the_local_drawings_directory_is_gitignored():
    """Real children's drawings are personal data and must never be committed."""
    ignored = Path(".gitignore").read_text(encoding="utf-8")
    assert "skills/art-feedback/evals/files/local/" in ignored
