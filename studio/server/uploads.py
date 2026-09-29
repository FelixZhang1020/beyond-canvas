"""What a page sends the studio: the request's bytes, read only up to a size a class can afford.

A drawing leaves the page shrunk to 1,600 pixels, about 1 MB, and a recording as 16 kHz sound, about
2 MB a minute, so nothing the page sends comes near MAX_BODY. The studio used to read whatever
length a request declared, so one request could hold the memory the whole class shares (code review).
A request over the limit is refused before a byte of it is read, and its connection is
closed, because the unread body would otherwise be taken for the next request on it.
"""
from __future__ import annotations

import email
from email import policy

MAX_BODY = 32 * 1024 * 1024


class TooLarge(ValueError):
    """A ValueError, so the route answers 400; `code` tells the page which one."""
    code = "too_large"


def read_body(handler) -> bytes:
    """The request's body, refused unread when it declares more than MAX_BODY, or a length that is no number."""
    declared = (handler.headers.get("Content-Length") or "0").strip()
    length = int(declared) if declared.isdigit() else -1  # "-5" and "abc" alike: no body to read safely
    if not 0 <= length <= MAX_BODY:
        handler.close_connection = True
        raise TooLarge(f"a request declaring {declared!r} bytes is refused; the studio reads at most {MAX_BODY}")
    return handler.rfile.read(length)


def parse_multipart(content_type: str, body: bytes) -> dict[str, bytes]:
    """Fields of a multipart form, by name. The email parser reads the same syntax."""
    raw = b"Content-Type: " + content_type.encode() + b"\r\nMIME-Version: 1.0\r\n\r\n" + body
    message = email.message_from_bytes(raw, policy=policy.HTTP)
    fields: dict[str, bytes] = {}
    for part in message.iter_parts() if message.is_multipart() else ():
        name = part.get_param("name", header="content-disposition")
        if name:
            fields[str(name)] = part.get_payload(decode=True) or b""
    return fields
