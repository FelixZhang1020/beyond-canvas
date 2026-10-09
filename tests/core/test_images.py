import base64
import io

import pytest
from PIL import Image

from studio.core.images import to_data_uri


@pytest.fixture
def big_drawing(tmp_path):
    path = tmp_path / "drawing.png"
    Image.new("RGB", (3000, 2000), "white").save(path)
    return path


def decode(uri):
    assert uri.startswith("data:image/png;base64,")
    return Image.open(io.BytesIO(base64.b64decode(uri.split(",", 1)[1])))


def test_a_large_photo_is_downscaled_to_the_long_edge_limit(big_drawing):
    image = decode(to_data_uri(big_drawing, max_edge=1024))
    assert image.size == (1024, 683)


def test_a_small_drawing_is_left_at_its_own_size(tmp_path):
    path = tmp_path / "small.png"
    Image.new("RGB", (200, 100), "white").save(path)
    assert decode(to_data_uri(path)).size == (200, 100)


def test_a_transparent_png_is_flattened_so_encoding_never_fails(tmp_path):
    path = tmp_path / "alpha.png"
    Image.new("RGBA", (50, 50), (255, 0, 0, 0)).save(path)
    assert decode(to_data_uri(path)).mode == "RGB"
