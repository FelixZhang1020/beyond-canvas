"""The Spark's TLS door, with a real certificate from openssl and a stand-in studio.

What only this can show: that a browser trusting the door's own certificate authority
reaches the studio through it, that a stream arrives while it is being written, and that
setting the door up twice never changes the class password.
"""
import importlib.util
import shutil
import socket
import ssl
import subprocess
import threading
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SETUP = ROOT / "deploy/spark/door-setup.sh"
spec = importlib.util.spec_from_file_location("spark_door", ROOT / "deploy/spark/door.py")
door = importlib.util.module_from_spec(spec)
spec.loader.exec_module(door)

pytestmark = pytest.mark.skipif(not shutil.which("openssl"), reason="needs openssl")


def free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def set_up(tmp_path):
    folder = tmp_path / "door"
    subprocess.run(["sh", str(SETUP)], check=True, capture_output=True,
                   env={"HOME": str(tmp_path), "PATH": "/usr/bin:/bin", "BEYOND_CANVAS_DOOR_DIR": str(folder)})
    return folder


def studio_stand_in(port):
    """Answers each connection with 'first', waits a second, then 'second', then closes."""
    listener = socket.create_server(("127.0.0.1", port))

    def serve():
        while True:
            connection, _ = listener.accept()
            connection.recv(1024)
            connection.sendall(b"first\n")
            time.sleep(1.0)
            connection.sendall(b"second\n")
            connection.close()

    threading.Thread(target=serve, daemon=True).start()


def test_a_browser_trusting_the_door_reaches_the_studio_and_hears_it_live(tmp_path):
    folder = set_up(tmp_path)
    for name in ("ca.crt", "server.crt", "server.key", "password", "key"):
        assert (folder / name).is_file(), name
    assert oct((folder / "password").stat().st_mode)[-3:] == "600"
    assert oct(folder.stat().st_mode)[-3:] == "700"
    studio_port, door_port = free_port(), free_port()
    studio_stand_in(studio_port)
    threading.Thread(target=door.main, daemon=True, kwargs={
        "listen": ("127.0.0.1", door_port), "studio": ("127.0.0.1", studio_port), "folder": folder}).start()
    time.sleep(0.5)
    context = ssl.create_default_context(cafile=str(folder / "ca.crt"))
    with socket.create_connection(("127.0.0.1", door_port), timeout=10) as raw:
        with context.wrap_socket(raw, server_hostname="127.0.0.1", suppress_ragged_eofs=False) as client:
            client.sendall(b"GET / HTTP/1.1\r\nHost: x\r\n\r\n")
            started = time.monotonic()
            assert client.recv(64) == b"first\n"
            assert time.monotonic() - started < 0.8
            assert client.recv(64) == b"second\n"
            # The studio closes after an event stream's `done`; the door must end TLS cleanly,
            # or the reader gets an SSL error in place of the end (seen through the relay).
            assert client.recv(64) == b""


def test_the_certificate_names_the_public_address(tmp_path):
    folder = set_up(tmp_path)
    text = subprocess.run(["openssl", "x509", "-in", str(folder / "server.crt"), "-noout", "-text"],
                          check=True, capture_output=True, text=True).stdout
    assert "IP Address:203.0.113.10" in text and "TLS Web Server Authentication" in text


def test_setting_up_twice_keeps_the_password(tmp_path):
    folder = set_up(tmp_path)
    first = (folder / "password").read_text()
    set_up(tmp_path)
    assert (folder / "password").read_text() == first
    assert len(first.strip()) == 14
