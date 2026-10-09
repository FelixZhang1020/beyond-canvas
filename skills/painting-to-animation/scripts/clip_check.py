"""Look at a finished clip beside the child's painting for a person Wan painted into it.

Wan sometimes paints what a film of a painting usually shows: a hand reaching in with a brush, as
if someone were still painting (seen on the corgi, one of the sample colour
drawings). The clip instruction tells it not to; this is the check that the instruction was kept,
made before the teacher sees the clip. One call reads one comparison sheet, the original first and
the clip's frames after it, so it asks the kind of one-picture question the safety check already
asks.

It asks only about a person's hands or arms, a person, and art tools. Asking also about a paw that
grows fingers or a figure the child did not paint held back good clips (toes read as fingers,
falling leaves as new figures) and still missed the real cases, so those are not asked:
docs/measured/clip-hands-and-check.md has the three versions and their numbers.

The answer is codes from a closed list, never words about the child, because what it finds
becomes a ledger note. A reply it cannot read is reported as no answer, not as a pass or a fail:
the caller decides what that means.

    uv run python skills/painting-to-animation/scripts/clip_check.py DRAWING CLIP.mp4
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import re
from collections.abc import Sequence
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from studio.core.errors import ModelError

PROMPT = Path(__file__).parent.parent / "assets" / "prompts" / "clip-check.txt"
FOUND = ("hands", "tools", "people")
PANEL = 448
COLUMNS = 3


def _picture(data_uri: str) -> Image.Image:
    with Image.open(io.BytesIO(base64.b64decode(data_uri.split(",", 1)[1]))) as opened:
        return opened.convert("RGB")


def _font():
    try:
        return ImageFont.load_default(size=24)
    except TypeError:  # Pillow before 10.1 has one small default font
        return ImageFont.load_default()


def sheet(original: str, frames: Sequence[str]) -> str:
    """The original and the frames on one picture, three across, each panel labelled."""
    pictures = [_picture(original), *(_picture(frame) for frame in frames)]
    labels = ["ORIGINAL", *(str(n) for n in range(1, len(frames) + 1))]
    rows = -(-len(pictures) // COLUMNS)
    board = Image.new("RGB", (COLUMNS * PANEL, rows * PANEL), "white")
    draw, font = ImageDraw.Draw(board), _font()
    for n, (picture, label) in enumerate(zip(pictures, labels)):
        picture.thumbnail((PANEL - 8, PANEL - 40))
        x, y = (n % COLUMNS) * PANEL, (n // COLUMNS) * PANEL
        board.paste(picture, (x + 4, y + 36))
        draw.text((x + 8, y + 6), label, fill="black", font=font)
    buffer = io.BytesIO()
    board.save(buffer, format="JPEG", quality=88)
    return "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode()


# The answer object. Step 3.7 Flash often writes its frame-by-frame reasoning first and the JSON
# last, whatever the instruction says (measured: the rabbit clip's reply named the
# added figure in prose before its answer, and reading the reply whole found no answer), so the
# last answer object in the reply is the one that counts.
ANSWER = re.compile(r'\{[^{}]*"found"\s*:\s*\[[^\[\]]*\][^{}]*\}')


def _answer(text: str) -> dict:
    answers = ANSWER.findall(text)
    if not answers:
        raise ValueError("no answer object")
    return json.loads(answers[-1])


def check(original: str, frames: Sequence[str], reader) -> list[str] | None:
    """What the clip added, as codes from FOUND; [] when nothing; None when there was no usable answer."""
    try:
        reply = reader.chat(PROMPT.read_text(encoding="utf-8"), [sheet(original, frames)], max_tokens=12000)
        payload = _answer(reply.text)
    except (ModelError, ValueError, OSError):  # a JSON decode error is a ValueError
        return None
    found = payload.get("found") if isinstance(payload, dict) else None
    if not isinstance(found, list):
        return None
    return [code for code in FOUND if code in found]


def main() -> None:
    from studio.making.animation import normalize_video
    from studio.core.env import load_dotenv
    from studio.core.images import to_data_uri
    from studio.providers import build_client
    from studio.core.slots import load_profile

    parser = argparse.ArgumentParser(description="Name anything a clip added to the child's painting.")
    parser.add_argument("drawing")
    parser.add_argument("clip")
    parser.add_argument("--profile", default="stepfun")
    arguments = parser.parse_args()
    load_dotenv()
    reader = build_client(load_profile(arguments.profile)["safety.image"])
    frames = normalize_video(Path(arguments.clip).read_bytes()).screen_images
    print(json.dumps({"found": check(to_data_uri(arguments.drawing), frames, reader)}))


if __name__ == "__main__":
    main()
