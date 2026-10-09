"""How the showpiece's files cross the class link: smaller, and only once.

A class reaches the studio through the organisers' relay, which carried about 100 KB a second
when it was measured in the operator's Chrome. At that rate the 18 MB model took
three minutes, a 1 MB rendered frame ten seconds and the 16 MB tour film nearly three minutes
before it could start. A replay moves on to its next frame every half second, so its pictures
never arrived, and the 3D view was still blank when the replay ended. The Spark's chip was not
the limit: nothing is rendered during a replay at all.

So each file goes the lightest way the browser says it can take:

- a PNG as WebP when the browser accepts it: a 1280x720 render, 1,047 KB, is 33 KB;
- models, scripts and JSON gzip-compressed when the browser accepts that: the hall's GLB,
  17.8 MB, is 5.2 MB, made in a quarter of a second;
- a film re-encoded to start at once and to play at about the link's rate: the raise film is
  3.4 MB as Blender writes it and about 0.7 MB here, the tour film 16 MB and about 1.5 MB.
  Blender puts the film's index at the end, so a browser had to have all of it first.

Every answer carries a tag naming the file's version, so a browser that already holds it is
told so in one short reply instead of being sent it again (`no-cache` means "ask first", not
"do not keep"). What was made is kept in memory, keyed by the file's path, size and time of
writing: a file rewritten underfoot is made again, and nothing is written beside the runs. A
lighter copy that turns out no lighter, or that cannot be made, is not used; the file goes as
it is.

The classroom page does the gzip-and-tag half of this for its own few files in
`studio/page_transfer.py`, holding each whole. The showpiece has hundreds (every frame of five
recordings and of every live run), so what is held here has a ceiling, and pictures and films
get copies of their own.
"""
from __future__ import annotations

import gzip
import io
import shutil
import subprocess
import tempfile
import threading
from collections import OrderedDict
from pathlib import Path

SQUEEZED = {".glb", ".json", ".jsonl", ".js", ".mjs", ".css", ".html"}   # pictures, films and .gz are compressed already
WEBP_QUALITY = 80
FILM = ["-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "28", "-maxrate", "800k", "-bufsize", "1600k",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart"]
FILM_TIMEOUT_S = 120
KEEP_BYTES = 64 * 1024 * 1024   # the five recordings' frames, films and plans and the hall's GLB come to about 30 MB


class Made:
    """Lighter copies, the least recently used dropped first past the limit. Each is made once
    however many requests ask for it at the same moment; one that could not be made is kept as
    None, so a failing ffmpeg is not asked again for the same file."""

    def __init__(self, limit: int = KEEP_BYTES) -> None:
        self.limit, self.size = limit, 0
        self.kept: OrderedDict = OrderedDict()
        self.making: dict = {}
        self.lock = threading.Lock()

    def get(self, key, make):
        with self.lock:
            if key in self.kept:
                self.kept.move_to_end(key)
                return self.kept[key]
            gate = self.making.setdefault(key, threading.Lock())
        with gate:
            with self.lock:
                if key in self.kept:
                    return self.kept[key]
            try:
                body = make()
            except BaseException:
                with self.lock:
                    self.making.pop(key, None)
                raise
            with self.lock:                          # kept and no longer being made in one step, or a third
                self.making.pop(key, None)           # request slipping between the two would make it again
                self.size += len(body or b"") - len(self.kept.pop(key, None) or b"")
                self.kept[key] = body
                while self.size > self.limit and len(self.kept) > 1:
                    _, old = self.kept.popitem(last=False)
                    self.size -= len(old or b"")
            return body


MADE = Made()


def webp(path: Path) -> bytes:
    from PIL import Image
    with Image.open(path) as picture:
        image = picture if picture.mode in ("RGB", "RGBA") else picture.convert("RGBA")
        out = io.BytesIO()
        image.save(out, "WEBP", quality=WEBP_QUALITY)
    return out.getvalue()


def squeezed(path: Path) -> bytes:
    return gzip.compress(path.read_bytes(), 6)


def film(path: Path) -> bytes | None:
    """The film re-encoded for the link, or None where there is no ffmpeg or it fails. On the Spark
    ffmpeg runs in a container that sees the system temp folder only (deploy/spark/bin/ffmpeg), so
    the film is copied there first, and both copies are gone when this returns."""
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        return None
    with tempfile.TemporaryDirectory(dir="/tmp", prefix="bc-film-") as folder:
        source, out = Path(folder) / "in.mp4", Path(folder) / "out.mp4"
        shutil.copyfile(path, source)
        try:
            done = subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(source), *FILM, str(out)],
                                  capture_output=True, timeout=FILM_TIMEOUT_S)
        except subprocess.TimeoutExpired:
            return None
        return out.read_bytes() if done.returncode == 0 and out.is_file() else None


MAKERS = {"webp": (webp, "image/webp"), "gzip": (squeezed, None), "film": (film, "video/mp4")}


def lighter(suffix: str, headers) -> str:
    """Which lighter copy this request may have, from what the browser said it accepts."""
    if suffix == ".png" and "image/webp" in headers.get("Accept", ""):
        return "webp"
    if suffix == ".mp4":
        return "film"
    if suffix in SQUEEZED and "gzip" in headers.get("Accept-Encoding", ""):
        return "gzip"
    return ""


def made_for(path: Path, kind: str, size: int, stamp: int) -> bytes | None:
    """The lighter copy of this version of the file, or None where it could not be made or is no lighter."""
    def make():
        try:
            body = MAKERS[kind][0](path)
        except Exception:    # a picture Pillow cannot read, a film ffmpeg chokes on: it goes as it is, as it always did
            return None
        return body if body is not None and len(body) < size else None
    return MADE.get((str(path), stamp, size, kind), make)


def send_file(handler, path: Path, content_type: str) -> None:
    """Send `path` the lightest way this request allows, or tell the browser the copy it has is current.

    The tag is the file's version and the kind of copy, so a browser that holds either is answered
    before anything is made: after a restart nothing made is left in memory, and a film would
    otherwise be encoded again only to say "you have it". The file is read before the first header
    goes, so a file gone in between is the route's ordinary error, not a second status line.
    """
    stat, suffix = path.stat(), path.suffix.lower()
    kind = lighter(suffix, handler.headers)
    def tag(k):
        return f'"{stat.st_mtime_ns:x}-{stat.st_size:x}-{k or "as-is"}"'
    held = {t.strip().removeprefix("W/") for t in handler.headers.get("If-None-Match", "").split(",")}
    current = next((tag(k) for k in dict.fromkeys((kind, "")) if tag(k) in held), None)
    body = None
    if current is None:
        body = made_for(path, kind, stat.st_size, stat.st_mtime_ns) if kind else None
        if body is None:
            kind, body = "", path.read_bytes()
    handler.send_response(304 if current else 200)
    handler.send_header("ETag", current or tag(kind))
    handler.send_header("Cache-Control", "no-cache")   # keep it, but ask first: a live run rewrites its plan files
    if suffix == ".png":
        handler.send_header("Vary", "Accept")
    elif suffix in SQUEEZED:
        handler.send_header("Vary", "Accept-Encoding")
    if body is not None:
        handler.send_header("Content-Type", (MAKERS[kind][1] or content_type) if kind else content_type)
        handler.send_header("Content-Length", str(len(body)))
        if kind == "gzip":
            handler.send_header("Content-Encoding", "gzip")
    handler._cors()
    handler.end_headers()
    if body is not None:
        handler.wfile.write(body)
