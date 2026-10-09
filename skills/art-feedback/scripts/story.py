"""Make the thing that goes home: the child's drawing and the child's own words.

Section 5a is explicit about what this is not. It is not a drawing with a
machine's evaluation attached. The machine's comment does not need to appear at
all, and here it does not: a parent at pickup receives what their child said,
not what a model wrote.

So this page holds two things — the picture, and the sentences the child spoke
about it, unedited. No score, no rubric, no praise, no tidying. The long road,
the wind that cannot stop, the teeth for biting stones: a model can draw those
out but it cannot write them, and a polished rewrite would replace the one thing
worth keeping.

The page is self-contained. The drawing is embedded, so it survives being
emailed, and nothing is fetched from a network that the box is not supposed to
be talking to anyway.

Usage:
    uv run python skills/art-feedback/scripts/story.py DRAWING \\
        --said "the dragon flew home because his house was on fire" \\
        --out story.html
"""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

from studio.core.images import to_data_uri

STRINGS_PATH = Path(__file__).parent.parent / "assets" / "story-strings.json"

PAGE = """<!doctype html>
<meta charset="utf-8">
<title>{title}</title>
<style>
  :root {{
    --paper: #FFFDF8;
    --ink: #26224A;
    --muted: #5A557A;
    --hair: #E4DFF2;
  }}
  body {{
    background: var(--paper);
    color: var(--ink);
    font-family: ui-rounded, "SF Pro Rounded", "Arial Rounded MT Bold", "Nunito",
                 "Avenir Next", "Segoe UI", sans-serif;
    margin: 0;
    padding: 40px 24px 64px;
    line-height: 1.6;
  }}
  .sheet {{ max-width: 680px; margin: 0 auto; }}
  figure {{ margin: 0 0 36px; }}
  img {{
    display: block;
    width: 100%;
    height: auto;
    border-radius: 20px;
    border: 1px solid var(--hair);
  }}
  .said {{ font-size: 22px; line-height: 1.65; margin: 0 0 28px; }}
  .said p {{ margin: 0 0 16px; }}
  .who {{
    font-size: 13px;
    color: var(--muted);
    border-top: 1px solid var(--hair);
    padding-top: 16px;
    margin: 0;
  }}
</style>
<div class="sheet">
  <figure><img src="{drawing}" alt="A drawing"></figure>
  <div class="said">{said}</div>
  <p class="who">{footer}</p>
</div>
"""


def load_strings(language: str) -> dict[str, str]:
    """Parent-facing text is content, so it lives in assets/ rather than here."""
    document = json.loads(STRINGS_PATH.read_text(encoding="utf-8"))
    return document[language]


def build_page(drawing_data_uri: str, child_said: str, language: str = "en") -> str:
    """Assemble the keepsake. The child's words are escaped, never edited."""
    paragraphs = [line.strip() for line in child_said.strip().splitlines() if line.strip()]
    if not paragraphs:
        raise ValueError("there is no story to keep: the child said nothing")
    strings = load_strings(language)
    said = "\n  ".join(f"<p>{html.escape(line)}</p>" for line in paragraphs)
    return PAGE.format(
        title=html.escape(strings["title"]),
        drawing=drawing_data_uri,
        said=said,
        footer=html.escape(strings["footer"]),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="What the child takes home")
    parser.add_argument("drawing", help="path to a photograph of the drawing")
    parser.add_argument("--said", required=True, help="what the child said, unedited")
    parser.add_argument("--lang", default="en", choices=["en", "zh"])
    parser.add_argument("--out", default="story.html", help="where to write the page")
    arguments = parser.parse_args()

    page = build_page(to_data_uri(arguments.drawing), arguments.said, arguments.lang)
    Path(arguments.out).write_text(page, encoding="utf-8")
    print(f"wrote {arguments.out}")


if __name__ == "__main__":
    main()
