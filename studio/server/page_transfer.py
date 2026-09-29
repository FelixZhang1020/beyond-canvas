"""Send the studio page cheaply enough for a classroom on a slow link.

The page is one self-contained file. It used to include the two
entrance photographs, written into it as base64 -- 437 KB, 47% of the page, and
base64 of a JPEG does not compress at all. They go out as their own files now,
so the page itself is 491 KB and gzips to 132 KB, and a teacher who has opened
the studio once downloads neither the page nor the photographs again.

Three ordinary pieces of HTTP do that. The page is gzipped once per build and
the compressed bytes are kept, so the same work is not repeated for each teacher
who opens it; photographs are sent as they are, because a JPEG is already
compressed and gzipping it only spends time. Everything carries an ETag, so a
browser that already holds a file is told to keep it rather than sent it again.

`no-cache` rather than `no-store`, deliberately: the browser must still ask on
every visit, so a page rebuilt between two classes is never served stale. What
changes is the cost of asking -- a few hundred bytes instead of a megabyte.
"""
from __future__ import annotations

import gzip
from hashlib import blake2b
from pathlib import Path

_HELD: dict[Path, tuple[tuple[int, int], bytes, bytes | None, str]] = {}


def prepare(path: Path, *, compress: bool = True) -> tuple[bytes, bytes | None, str]:
    """The file's bytes, its gzipped bytes and its tag, redone when it changes."""
    # Two classroom tablets arriving together may both compress the file and one
    # overwrite the other's entry. That costs a compression, not a wrong answer.
    info = path.stat()
    stamp = (info.st_mtime_ns, info.st_size)
    held = _HELD.get(path)
    if held is None or held[0] != stamp:
        raw = path.read_bytes()
        # No timestamp in the gzip header: the same file then compresses to the
        # same bytes whichever run of the server sends it.
        held = (stamp, raw, gzip.compress(raw, 6, mtime=0) if compress else None,
                '"%s"' % blake2b(raw, digest_size=16).hexdigest())
        _HELD[path] = held
    return held[1], held[2], held[3]


def packed_tag(tag: str) -> str:
    """The tag of a file's gzipped bytes. They are other bytes than the file's own, so they carry a tag of their
    own: with one tag for both, a browser holding the gzipped copy was told 304 when it asked without gzip, and
    kept bytes it could not read (code review)."""
    return tag[:-1] + '-gz"'


def send(handler, path: Path, content_type: str, *, compress: bool = True) -> None:
    """Answer one request for a file, with as few bytes as the browser needs."""
    raw, packed, tag = prepare(path, compress=compress)
    zipped = packed is not None and "gzip" in (handler.headers.get("Accept-Encoding") or "")
    body, tag = (packed, packed_tag(tag)) if zipped else (raw, tag)
    if handler.headers.get("If-None-Match") == tag:
        handler.send_response(304)
        handler.send_header("ETag", tag)
        handler.send_header("Cache-Control", "no-cache")
        handler.send_header("Vary", "Accept-Encoding")
        handler.end_headers()
        return
    handler.send_response(200)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("ETag", tag)
    handler.send_header("Cache-Control", "no-cache")
    handler.send_header("Vary", "Accept-Encoding")
    if zipped:
        handler.send_header("Content-Encoding", "gzip")
    handler.end_headers()
    handler.wfile.write(body)


def send_bytes(handler, body: bytes, content_type: str, *, compress: bool = False,
               private: bool = False) -> None:
    """The same answer as `send`, for bytes that never were a file.

    A child's drawing lives in the Portfolio, not on disk, and at first
    every one went out under `no-store`: the six tiles of the home screen were
    downloaded again on every visit, 232 times in one day and not once kept.
    They are not files, so they get their tag from the bytes themselves.
    """
    tag = '"%s"' % blake2b(body, digest_size=16).hexdigest()
    cache = "private, no-cache" if private else "no-cache"
    zipped = compress and len(body) > 65536 and "gzip" in (handler.headers.get("Accept-Encoding") or "")
    if zipped:
        tag = packed_tag(tag)
    if handler.headers.get("If-None-Match") == tag:
        handler.send_response(304)
        handler.send_header("ETag", tag)
        handler.send_header("Cache-Control", cache)
        if compress:
            handler.send_header("Vary", "Accept-Encoding")
        handler.end_headers()
        return
    wire = gzip.compress(body, 6, mtime=0) if zipped else body
    handler.send_response(200)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(wire)))
    handler.send_header("ETag", tag)
    handler.send_header("Cache-Control", cache)
    if compress:
        handler.send_header("Vary", "Accept-Encoding")
    if zipped:
        handler.send_header("Content-Encoding", "gzip")
    handler.end_headers()
    handler.wfile.write(wire)


class PageRoutes:
    """The studio page, and the two photographs that used to travel inside it."""

    def _page(self) -> None:
        if not self.server.page.is_file():
            self._json(404, {"error": f"{self.server.page} is not built; run sh studio/page/build.sh"})
            return
        send(self, self.server.page, "text/html; charset=utf-8")

    def _entrance(self, name: str) -> None:
        """One entrance photograph. The route's pattern is what keeps this inside
        the folder: a name it allows holds no slash and no dots of its own."""
        picture = self.server.page.parent / "assets" / "entrance" / name
        if not picture.is_file():
            self._json(404, {"error": f"no entrance picture called {name}"})
            return
        send(self, picture, "image/jpeg", compress=False)
