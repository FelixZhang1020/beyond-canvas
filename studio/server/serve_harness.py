"""The Harness page, served from the classroom's own port.

Beyond Canvas is one system: the classroom, the temple showpiece and this diagram of
the harness behind them are three views of the same thing, not three products.
They were split across two ports only because they grew in two places -- the
classroom on 7060, the exhibit on 7090 -- and that split did what
an accidental split does: someone went to `7060/harness`, got a 404, and had no
way to tell whether the page was broken or merely elsewhere.

So the page answers on both ports now. The exhibit still serves it at `/harness`
because the temple demo's header links there and that link is written into the
presenter script; the classroom serves it at `/harness/` from the same files, so
there is exactly one copy of the page and no second thing to keep in step.

Static only, which is what makes this cheap. The Harness page is a demonstration
rather than a run -- one HTML file, two stylesheets, three scripts and three JSON
files, with no model behind it. The temple showpiece is the opposite (a 47 MB
Blender file and a live model driver) and is why the exhibit server still exists.

Files are allow-listed by name rather than by extension. The directory this
serves from also holds the exhibit's own page, and a classroom server has no
business handing out the rest of it.
"""

from __future__ import annotations

import mimetypes
from pathlib import Path

PAGE = Path(__file__).resolve().parents[1] / "showpiece" / "page"

# Every file the Harness page asks for, and nothing else. `harness.html` names
# the two stylesheets and `harness.js`; that module imports the two `.mjs`
# siblings and fetches the three JSON files by relative name, which is why the
# page is served at `/harness/` with a trailing slash -- at `/harness` the
# browser would resolve them against the site root and miss.
PUBLIC = frozenset({
    "harness.html",
    "style.css", "harness.css",
    "harness.js", "harnessplay.mjs", "harnessboard.mjs",
    "harness-strings.json", "harness-roster.json", "harness-journeys.json",
})


def resolve_file(route: str, root: Path = PAGE) -> Path:
    """The file this route names, or KeyError if it is not the page's to serve."""
    name = route or "harness.html"
    if name not in PUBLIC:
        raise KeyError(f"{name} is not part of the Harness page")
    path = (root / name).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        # The message reaches the browser as a 404 body, so it names the file and
        # not the directory: an absolute path on the teacher's machine is nobody
        # else's business, however local this server is meant to stay.
        raise KeyError(f"{name} is not on this machine")
    return path


def send_file(handler, route: str) -> None:
    """Write one of the page's files to an open handler."""
    path = resolve_file(route)
    body = path.read_bytes()
    handler.send_response(200)
    handler.send_header("Content-Type", mimetypes.guess_type(path.name)[0] or "application/octet-stream")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-cache")
    handler.send_header("X-Content-Type-Options", "nosniff")
    handler.end_headers()
    handler.wfile.write(body)
