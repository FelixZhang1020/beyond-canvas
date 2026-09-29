"""The password on the Spark's public door: one shared password and a signed cookie.

The organisers publish node port 7000 as public port 7100 and require a password on
anything served there (their manual, 8.2). deploy/spark/door.py answers that port with
TLS, because a browser gives the class page its camera and microphone only on a secure
address, and hands the bytes to this studio, which asks for the password first.

Off unless BEYOND_CANVAS_DOOR names a folder holding `password` and `key`, made once by
deploy/spark/door-setup.sh and never in git, so the Mac and the test suite never meet it.
A right password earns a cookie signed with `key`, good for seven days on that browser.
There are no accounts, no logout and no lockout: the password is twelve characters from
thirty-one (about 59 bits), which guessing over the internet cannot exhaust.
"""
from __future__ import annotations

import hashlib
import hmac
import html
import json
import os
import time
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

COOKIE = "bc_door"
DAYS = 7
PAGE = Path(__file__).with_name("door_page.html")
WORDS = Path(__file__).with_name("door_strings.json")


class Door:
    def __init__(self, folder: Path) -> None:
        self.folder = Path(folder)
        self.secret = (self.folder / "password").read_text().strip()
        self.key = (self.folder / "key").read_bytes()
        if len(self.secret) < 12 or len(self.key) < 32:
            raise ValueError(f"{self.folder}: the password needs 12 characters and the key 32 bytes")

    @classmethod
    def from_env(cls) -> Door | None:
        folder = os.environ.get("BEYOND_CANVAS_DOOR", "").strip()
        return cls(Path(folder).expanduser()) if folder else None

    def admits(self, offered: str) -> bool:
        return hmac.compare_digest(offered.strip().encode(), self.secret.encode())

    def cookie(self, now: float | None = None) -> str:
        expiry = str(int((time.time() if now is None else now) + DAYS * 86400))
        return f"{expiry}.{self._sign(expiry)}"

    def valid(self, value: str, now: float | None = None) -> bool:
        expiry, _, signature = value.partition(".")
        return (expiry.isdigit() and hmac.compare_digest(signature, self._sign(expiry))
                and int(expiry) > (time.time() if now is None else now))

    def _sign(self, expiry: str) -> str:
        return hmac.new(self.key, expiry.encode(), hashlib.sha256).hexdigest()


def _same_site(path: str) -> str:
    """Where to send a browser after the knock: a path on this site, or the class. A browser reads a backslash as a
    slash and drops a tab or a newline, so "/\\x" and "/\\t/x" would reach another site ("//x"): neither is allowed."""
    on_site = (path.startswith("/") and not path.startswith("//") and "\\" not in path and path.isprintable()
               and not urlsplit(path).scheme)
    return path if on_site else "/"


class DoorRoutes:
    """Mixed into StudioHandler: answers for the door, or lets the request through."""

    def _door_shut(self) -> bool:
        door = self.server.door
        if door is None:
            return False
        path = urlsplit(self.path).path
        if path == "/door/certificate" and self.command == "GET":
            return self._door_certificate(door)
        if path == "/door" and self.command == "POST":
            return self._door_knock(door)
        if door.valid(self._door_cookie()):
            return False
        if self.command == "GET" and "text/html" in self.headers.get("Accept", ""):
            self._door_page(200, wrong=False, next_path=self.path)
        else:
            self._json(401, {"error": "Open the classroom page and enter its password first."})
        return True

    def _door_cookie(self) -> str:
        for part in self.headers.get("Cookie", "").split(";"):
            name, _, value = part.strip().partition("=")
            if name == COOKIE:
                return value
        return ""

    def _door_knock(self, door: Door) -> bool:
        # Anyone may knock, so a length is checked before anything is read: -1 read until the sender hung up,
        # holding a thread and a connection through the public door (review), and a word for one dropped it.
        given = self.headers.get("Content-Length") or "0"
        length = int(given) if given.isascii() and given.isdigit() else -1
        if not 0 <= length <= 4096:
            self.close_connection = True   # what was not read must not be taken for the next request
            self._json(413, {"error": "That is not a password."})
            return True
        form = parse_qs(self.rfile.read(length).decode("utf-8", "replace"))
        next_path = _same_site(form.get("next", ["/"])[0])
        if not door.admits(form.get("password", [""])[0]):
            self._door_page(401, wrong=True, next_path=next_path)
            return True
        self.send_response(303)
        self.send_header("Location", next_path)
        self.send_header("Set-Cookie", f"{COOKIE}={door.cookie()}; Max-Age={DAYS * 86400}; "
                                       "Path=/; HttpOnly; SameSite=Strict")
        self.send_header("Content-Length", "0")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        return True

    def _door_page(self, status: int, wrong: bool, next_path: str) -> None:
        language = "zh" if self.headers.get("Accept-Language", "").lower().startswith("zh") else "en"
        words = json.loads(WORDS.read_text(encoding="utf-8"))[language]
        fill = {key: html.escape(value) for key, value in words.items()}
        fill["wrong"] = fill["wrong"] if wrong else ""
        fill["next"] = html.escape(_same_site(next_path))
        fill["lang"] = language
        self._bytes(status, PAGE.read_text(encoding="utf-8").format(**fill).encode("utf-8"),
                    "text/html; charset=utf-8")

    def _door_certificate(self, door: Door) -> bool:
        path = door.folder / "ca.crt"
        if not path.is_file():
            self._json(404, {"error": "No certificate on this machine."})
            return True
        self._bytes(200, path.read_bytes(), "application/x-x509-ca-cert")
        return True
