"""The dark drawings studio-safety is tested on: a battle, a hunt, a hurt friend.

Drawn by a program, because a real child's frightening drawing is the most personal data there is.
They exist to separate two sets of rules: a general safety model may flag a sword fight with blood on
it, and a children's studio must still let it in. A mild monster could not show the difference
(docs/measured/nemotron-safety-on-spark.md)."""
from pathlib import Path

import pytest
from conftest import load_script

FILES = Path("skills/studio-safety/evals/files")
EXPECTED = {"battle.png", "hunt.png", "hurt-friend.png"}


@pytest.fixture(scope="module")
def script():
    return load_script(FILES / "make_dark_drawings.py", "make_dark_drawings")


def test_every_dark_drawing_is_on_disk_and_comes_from_the_generator(script):
    assert set(script.DRAWINGS) == EXPECTED
    assert {p.name for p in FILES.glob("*.png")} == EXPECTED


def test_a_drawing_regenerates_pixel_for_pixel(script):
    """A test picture that changes under you measures nothing twice.

    Pixels, not file bytes: the same pixels compress to different PNG bytes on the Mac and on the
    Spark (their zlib builds differ), found when the suites moved to the Spark.
    """
    from PIL import Image
    for name, build in script.DRAWINGS.items():
        made = build()
        with Image.open(FILES / name) as saved:
            assert (made.mode, made.size, made.tobytes()) == (saved.mode, saved.size, saved.tobytes()), name


def test_each_is_a_full_page_with_blood_on_it_and_nothing_written(script):
    for name, build in script.DRAWINGS.items():
        image = build()
        assert image.size == (512, 512)
        raw = image.tobytes()
        pixels = [tuple(raw[i:i + 3]) for i in range(0, len(raw), 3)]
        blood = sum(1 for r, g, b in pixels if r > 170 and g < 70 and b < 70)
        drawn = sum(1 for p in pixels if p != (255, 255, 255))
        assert blood > 1500, f"{name}: {blood} red pixels is a scratch, not a drawing of blood"
        assert drawn > 0.08 * len(pixels), f"{name} is nearly a blank page"
    assert "text(" not in (FILES / "make_dark_drawings.py").read_text(), "no words: nothing for the redactor, nothing to read back"
