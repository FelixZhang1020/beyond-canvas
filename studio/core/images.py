from __future__ import annotations

import base64
import io
from pathlib import Path

from PIL import Image

MAX_EDGE = 1024


def to_data_uri(path: str | Path, max_edge: int = MAX_EDGE) -> str:
    """Read an image and return it as a PNG data URI, downscaled if large.

    A phone photograph is several times larger than any vision encoder reads,
    so sending it whole only buys input tokens and latency. Step 3.7 Flash
    works from a 728 pixel tile, which a 1024 pixel long edge covers.
    """
    with Image.open(path) as opened:
        image = opened.convert("RGB")
        longest = max(image.size)
        if longest > max_edge:
            scale = max_edge / longest
            size = (round(image.width * scale), round(image.height * scale))
            image = image.resize(size, Image.Resampling.LANCZOS)
        buffer = io.BytesIO()
        image.save(buffer, format="PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()
