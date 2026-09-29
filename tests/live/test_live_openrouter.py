"""Opt-in tests that spend real money. Run with: uv run pytest -m live -v"""

import pytest
from PIL import Image, ImageDraw

from studio.core.env import load_dotenv
from studio.core.images import to_data_uri
from studio.providers import build_client
from studio.core.slots import load_profile, resolve

pytestmark = pytest.mark.live


@pytest.fixture(scope="module")
def director():
    load_dotenv()
    return build_client(resolve("vlm.director", load_profile("cloud")))


@pytest.fixture
def yellow_sun(tmp_path):
    path = tmp_path / "sun.png"
    canvas = Image.new("RGB", (256, 256), "white")
    ImageDraw.Draw(canvas).ellipse((30, 30, 130, 130), fill=(250, 210, 40))
    canvas.save(path)
    return path


def test_the_director_answers_a_text_prompt(director):
    result = director.chat("Reply with the single word READY.")
    assert "READY" in result.text.upper()
    assert result.cost_usd > 0


def test_the_director_reads_a_drawing(director, yellow_sun):
    result = director.chat(
        "Name the single colour of the shape in this image. One word.",
        [to_data_uri(yellow_sun)],
    )
    assert "yellow" in result.text.lower()
