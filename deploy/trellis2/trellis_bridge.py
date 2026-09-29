"""Bounded HTTP bridge from the classroom contract to the TRELLIS.2 Gradio app."""
from __future__ import annotations

import argparse
import base64
import binascii
import fcntl
import json
import struct
import tempfile
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

MODEL = "trellis2"
MAX_REQUEST = 9 * 1024 * 1024
MAX_IMAGE = 8 * 1024 * 1024
MAX_MODEL = 8 * 1024 * 1024


def decode_image(uri: object) -> bytes:
    if not isinstance(uri, str) or len(uri) > MAX_IMAGE or not uri.startswith("data:image/"):
        raise ValueError("expected a bounded embedded image")
    header, comma, encoded = uri.partition(",")
    if not comma or not header.endswith(";base64"):
        raise ValueError("expected a base64 image")
    raw = base64.b64decode(encoded, validate=True)
    if not 256 <= len(raw) <= MAX_IMAGE:
        raise ValueError("image outside byte budget")
    return raw


def find_glb(value):
    if isinstance(value, str) and value.lower().endswith(".glb"):
        return Path(value)
    if isinstance(value, dict):
        if isinstance(value.get("path"), str) and value["path"].lower().endswith(".glb"):
            return Path(value["path"])
        for item in value.values():
            found = find_glb(item)
            if found:
                return found
    if isinstance(value, (list, tuple)):
        for item in value:
            found = find_glb(item)
            if found:
                return found
    return None


def validate_glb(content: bytes) -> None:
    if not 20 <= len(content) <= MAX_MODEL:
        raise OSError("GLB outside response budget")
    magic, version, declared = struct.unpack_from("<4sII", content)
    if magic != b"glTF" or version != 2 or declared != len(content):
        raise OSError("invalid GLB response")


class GradioEngine:
    def __init__(self, upstream: str):
        self.upstream = upstream.rstrip("/")
        self._client = None

    def ready(self) -> bool:
        try:
            with urllib.request.urlopen(self.upstream + "/", timeout=1.5) as response:
                return response.status == 200
        except (urllib.error.URLError, OSError, ValueError):
            return False

    def generate(self, image: bytes) -> bytes:
        from gradio_client import Client, handle_file

        try:
            if self._client is None:
                self._client = Client(self.upstream, verbose=False)
            with tempfile.NamedTemporaryFile(prefix="trellis-input-", suffix=".png", dir="/app/tmp") as source:
                source.write(image)
                source.flush()
                preprocessed = self._client.predict(handle_file(source.name), api_name="/preprocess_image_1")
                self._client.predict(
                    handle_file(preprocessed), 42, "1024",
                    7.5, 0.7, 12, 5.0,
                    7.5, 0.5, 12, 3.0,
                    1.0, 0.0, 12, 3.0,
                    api_name="/image_to_3d",
                )
                extracted = self._client.predict(100000, 1024, api_name="/extract_glb")
        except Exception as error:
            # A restarted Gradio app invalidates its session. Recreate the
            # client on the next request instead of retaining a dead session.
            self._client = None
            raise OSError("TRELLIS.2 upstream request failed") from error
        path = find_glb(extracted)
        if path is None or not path.is_file():
            raise OSError("TRELLIS.2 returned no GLB")
        try:
            content = path.read_bytes()
            validate_glb(content)
            return content
        finally:
            path.unlink(missing_ok=True)


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, port: int, engine, lock_path: Path):
        self.engine, self.lock_path = engine, lock_path
        self.job = threading.Lock()
        super().__init__(("0.0.0.0", port), Handler)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def json_reply(self, status: int, payload: dict):
        body = json.dumps(payload, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/v1/models":
            if not self.server.engine.ready():
                return self.json_reply(503, {"error": "TRELLIS.2 is loading"})
            return self.json_reply(200, {"data": [{"id": MODEL}], "busy": self.server.job.locked()})
        self.json_reply(404, {"error": "unknown route"})

    def do_POST(self):
        if self.path != "/v1/mesh":
            return self.json_reply(404, {"error": "unknown route"})
        if self.headers.get("Origin") or self.headers.get("Content-Type", "").split(";")[0] != "application/json":
            return self.json_reply(403, {"error": "server-to-server JSON only"})
        if not self.server.job.acquire(blocking=False):
            return self.json_reply(503, {"error": "TRELLIS.2 worker busy"})
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= MAX_REQUEST:
                raise ValueError("request outside byte budget")
            payload = json.loads(self.rfile.read(size))
            if not isinstance(payload, dict) or payload.get("model") != MODEL:
                raise ValueError("unknown model")
            if payload.get("subject") not in (None, "head", "fruit"):
                raise ValueError("unknown subject")
            image = decode_image(payload.get("image"))
            self.server.lock_path.parent.mkdir(parents=True, exist_ok=True)
            with self.server.lock_path.open("a+b") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                content = self.server.engine.generate(image)
            self.send_response(200)
            self.send_header("Content-Type", "model/gltf-binary")
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(content)
        except (ValueError, TypeError, json.JSONDecodeError, binascii.Error):
            self.json_reply(422, {"error": "invalid bounded mesh request"})
        except OSError:
            self.json_reply(503, {"error": "TRELLIS.2 generation unavailable"})
        finally:
            self.server.job.release()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream", default="http://127.0.0.1:7860")
    parser.add_argument("--lock", required=True, type=Path)
    parser.add_argument("--port", type=int, default=7240)
    args = parser.parse_args()
    server = Server(args.port, GradioEngine(args.upstream), args.lock)
    print(f"TRELLIS.2 bridge ready on 0.0.0.0:{args.port}", flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
