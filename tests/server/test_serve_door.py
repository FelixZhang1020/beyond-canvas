"""The Spark's password, driven over a real socket the way a browser meets it.

Off unless BEYOND_CANVAS_DOOR names a folder, so every other test in this suite
runs without it; on, nothing but the login page, the knock and the certificate
is served to a browser without the cookie.
"""
import http.client
import secrets
import socket
import threading
import urllib.parse

import pytest

from studio.classroom.classroom import Classroom
from studio.serve import make_server
from studio.server.serve_door import COOKIE, Door

# Made fresh each run, the way door-setup.sh makes the real one: three groups of four.
THE_WORD = "-".join(secrets.token_hex(2) for _ in range(3))


@pytest.fixture
def door_folder(tmp_path):
    folder = tmp_path / "door"
    folder.mkdir()
    (folder / "password").write_text(THE_WORD + "\n")
    (folder / "key").write_bytes(secrets.token_bytes(32))
    (folder / "ca.crt").write_text("-----BEGIN CERTIFICATE-----\nfake\n-----END CERTIFICATE-----\n")
    return folder


@pytest.fixture
def serve(tmp_path, monkeypatch):
    servers = []

    def start(folder):
        if folder:
            monkeypatch.setenv("BEYOND_CANVAS_DOOR", str(folder))
        else:
            monkeypatch.delenv("BEYOND_CANVAS_DOOR", raising=False)
        page = tmp_path / "index.html"
        page.write_text("<title>the class itself</title>", encoding="utf-8")
        server = make_server(Classroom(tmp_path / "ledger.jsonl", clients={}), "127.0.0.1", 0, page)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        servers.append(server)
        return server

    yield start
    for server in servers:
        server.shutdown()


def ask(server, method, path, body=None, headers=None):
    connection = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=10)
    connection.request(method, path, body=body, headers=headers or {})
    response = connection.getresponse()
    return response.status, dict(response.getheaders()), response.read()


def knock(server, word, next_path="/"):
    form = urllib.parse.urlencode({"password": word, "next": next_path})
    return ask(server, "POST", "/door", form, {"Content-Type": "application/x-www-form-urlencoded"})


def test_without_the_folder_the_studio_asks_for_nothing(serve):
    server = serve(None)
    status, _, body = ask(server, "GET", "/", headers={"Accept": "text/html"})
    assert (status, body) == (200, b"<title>the class itself</title>")


def test_a_browser_without_the_cookie_gets_the_login_page_not_the_class(serve, door_folder):
    server = serve(door_folder)
    status, headers, body = ask(server, "GET", "/", headers={"Accept": "text/html", "Accept-Language": "en"})
    assert status == 200 and headers["Content-Type"].startswith("text/html")
    assert b'name="password"' in body and b"<title>the class itself</title>" not in body


def test_the_login_page_speaks_the_browsers_language(serve, door_folder):
    server = serve(door_folder)
    _, _, english = ask(server, "GET", "/", headers={"Accept": "text/html", "Accept-Language": "en-GB"})
    _, _, chinese = ask(server, "GET", "/", headers={"Accept": "text/html", "Accept-Language": "zh-CN,zh"})
    assert b'lang="en"' in english and b'lang="zh"' in chinese


def test_a_route_without_the_cookie_is_refused(serve, door_folder):
    server = serve(door_folder)
    assert ask(server, "GET", "/api/courses")[0] == 401
    assert ask(server, "POST", "/api/session", "{}", {"Content-Type": "application/json"})[0] == 401


def test_the_machine_panel_is_behind_the_door_too(serve, door_folder):
    """It answers before the route table does (studio/server/console_panel.py), so it needs its own check."""
    server = serve(door_folder)
    assert ask(server, "GET", "/api/console")[0] == 401
    assert ask(server, "GET", "/console.js")[0] == 401


def test_a_wrong_word_sets_no_cookie(serve, door_folder):
    server = serve(door_folder)
    status, headers, body = knock(server, "not-the-word")
    assert status == 401 and "Set-Cookie" not in headers and b'name="password"' in body


def test_the_right_word_opens_the_class_for_seven_days(serve, door_folder):
    server = serve(door_folder)
    status, headers, _ = knock(server, THE_WORD, "/showpiece/")
    assert status == 303 and headers["Location"] == "/showpiece/"
    cookie = headers["Set-Cookie"]
    assert cookie.startswith(f"{COOKIE}=") and "HttpOnly" in cookie and "SameSite=Strict" in cookie
    assert "Max-Age=604800" in cookie
    value = cookie.split(";")[0]
    status, _, body = ask(server, "GET", "/", headers={"Accept": "text/html", "Cookie": value})
    assert (status, body) == (200, b"<title>the class itself</title>")


def test_the_knock_never_sends_a_browser_off_the_site(serve, door_folder):
    server = serve(door_folder)
    # A browser reads a backslash as a slash and drops a tab, so both of these become "//x": another site (review).
    for elsewhere in ("//evil.example/", "https://evil.example/", "javascript:alert(1)",
                      "/\\evil.example/", "/\t/evil.example/", "/\\/evil.example/"):
        assert knock(server, THE_WORD, elsewhere)[1]["Location"] == "/"


def test_a_knock_of_no_honest_length_is_answered_at_once(serve, door_folder):
    """Code review: a length of -1 passed the 4096 check and read until the sender hung up, holding a studio
    thread and a connection through the public door as long as it cared to; a word for a length dropped it."""
    server = serve(door_folder)
    for length in ("-1", "not-a-number"):
        with socket.create_connection(("127.0.0.1", server.server_address[1]), timeout=5) as raw:
            raw.sendall(f"POST /door HTTP/1.1\r\nHost: x\r\nContent-Length: {length}\r\n\r\n".encode())
            first = raw.recv(200).split(b"\r\n")[0]
        assert first.startswith(b"HTTP/1.") and b" 413 " in first, length


def test_a_forged_or_expired_cookie_is_refused(door_folder):
    door = Door(door_folder)
    assert door.valid(door.cookie(now=1000.0), now=1000.0 + 3600)
    assert not door.valid(door.cookie(now=1000.0), now=1000.0 + 8 * 86400)
    expiry = door.cookie(now=1000.0).split(".")[0]
    assert not door.valid(f"{expiry}.{'0' * 64}", now=1000.0)
    assert not door.valid("", now=1000.0)


def test_the_certificate_is_served_without_the_password(serve, door_folder):
    server = serve(door_folder)
    status, headers, body = ask(server, "GET", "/door/certificate")
    assert status == 200 and headers["Content-Type"] == "application/x-x509-ca-cert"
    assert body.startswith(b"-----BEGIN CERTIFICATE-----")


def test_a_short_word_or_key_refuses_to_start(door_folder):
    (door_folder / "password").write_text("short")
    with pytest.raises(ValueError):
        Door(door_folder)
