"""A saved result's clips, book pictures and 3D models, sent as files of their own rather than inside the result.

A clip or a storybook picture is kept inside its result as a data URI, and it used to travel that way:
a third bigger than the file, nothing shown until all of the result had arrived and been read, nothing kept by the
browser, and a book carrying every page's clip in one reply of about a megabyte. The link from the Spark to a
classroom measured 7 to 67 KB/s at the time (operator: "voice loading and video loading are still slow").

`detach` gives the page the result with each such file replaced by an address of its own, and `media` answers that
address. The address carries a digest of the file, so a browser may keep what it fetched for good: a clip made
again gets a new address. `send` answers a range of the file too, so a clip starts playing as its first part
arrives. The saved result is never changed, and a still pose's picture, which the page reads as it is, stays inside.
"""

from __future__ import annotations

import base64
import re
from hashlib import blake2b

SENT_APART = re.compile(r"data:(video/mp4|image/(?:png|jpeg|webp));base64,")
SMALL = 16 * 1024   # smaller ones stay inside: a request of their own would cost more than they do
KEEP = "private, max-age=31536000, immutable"   # the address changes whenever the file does


def _kind(path: tuple[str, ...], value) -> tuple[str, int] | None:
    """What is sent apart: a clip anywhere, a book page's picture, a picture-book style's picture, or a 3D result's
    model. Its type, and where its base64 starts; None for anything else.

    The model is kept as bare base64, not a data URI. It travelled inside the "done" until a head of a few megabytes
    stalled on the class's link: the studio had finished in 167 s, and the page waited 491 s and called it a failure.
    """
    if not isinstance(value, str):
        return None
    if path[-2:] == ("scene", "glb"):
        return "model/gltf-binary", 0
    last = path[-1] if path else ""
    if last in ("video_url", "picture_url") or (last == "url" and len(path) >= 3 and path[-3] == "pictures"):
        found = SENT_APART.match(value)
        return (found.group(1), found.end()) if found else None
    return None


def detach(outputs, base: str):
    """`outputs` with every large clip, book picture or 3D model replaced by its address under `base`; the rest as
    it was."""
    def walk(value, path):
        if isinstance(value, dict):
            return {name: walk(item, path + (name,)) for name, item in value.items()}
        if isinstance(value, list):
            return [walk(item, path + (str(at),)) for at, item in enumerate(value)]
        if isinstance(value, str) and len(value) > SMALL and _kind(path, value):
            return f"{base}/media/{'.'.join(path)}?v={blake2b(value.encode(), digest_size=8).hexdigest()}"
        return value
    return walk(outputs, ())


def media(outputs, address: str) -> tuple[bytes, str]:
    """The file at an address `detach` gave out, with its type; KeyError for any other address."""
    path, value = tuple(address.split(".")), outputs
    for part in path:
        if isinstance(value, dict) and part in value:
            value = value[part]
        elif isinstance(value, list) and part.isdigit() and int(part) < len(value):
            value = value[int(part)]
        else:
            raise KeyError("No such file in this result.")
    kind = _kind(path, value)
    if kind is None:
        raise KeyError("No such file in this result.")
    return base64.b64decode(value[kind[1]:]), kind[0]


def _wanted(header: str | None, size: int):
    """The (start, end) a Range header asks for, None for the whole file, or False when none of it can be sent."""
    asked = re.fullmatch(r"bytes=(\d*)-(\d*)", (header or "").strip())
    if not asked or asked.groups() == ("", ""):
        return None
    first, last = asked.groups()
    if first == "":   # the last N bytes
        return (max(0, size - int(last)), size - 1) if int(last) else False
    start, end = int(first), min(int(last) if last else size - 1, size - 1)
    return (start, end) if start <= end else False


def send(handler, body: bytes, content_type: str) -> None:
    """Answer one request for a file: all of it, the range asked for, or that the browser already holds it."""
    tag = '"%s"' % blake2b(body, digest_size=16).hexdigest()
    if handler.headers.get("If-None-Match") == tag:
        handler.send_response(304)
        handler.send_header("ETag", tag)
        handler.send_header("Cache-Control", KEEP)
        handler.end_headers()
        return
    span = _wanted(handler.headers.get("Range"), len(body))
    if span is False:
        handler.send_response(416)
        handler.send_header("Content-Range", f"bytes */{len(body)}")
        handler.send_header("Content-Length", "0")
        handler.end_headers()
        return
    part = body if span is None else body[span[0]:span[1] + 1]
    handler.send_response(200 if span is None else 206)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(part)))
    handler.send_header("Accept-Ranges", "bytes")
    handler.send_header("ETag", tag)
    handler.send_header("Cache-Control", KEEP)
    if span is not None:
        handler.send_header("Content-Range", f"bytes {span[0]}-{span[1]}/{len(body)}")
    handler.end_headers()
    handler.wfile.write(part)
