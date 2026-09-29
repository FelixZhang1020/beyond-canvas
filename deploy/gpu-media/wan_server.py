"""Loopback-only, single-job Wan 2.2 TI2V-5B worker for the shared 4090."""
from __future__ import annotations

import argparse
import base64
import binascii
import fcntl
import json
import subprocess
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

MODEL = "wan2.2-ti2v-5b"
IMAGE = "beyond-canvas/wan22-smoke:42bf4cfa"
MAX_REQUEST = 8 * 1024 * 1024
MAX_VIDEO = 12 * 1024 * 1024


def decode_image(uri: object) -> bytes:
    if not isinstance(uri, str) or len(uri) > MAX_REQUEST or not uri.startswith("data:image/"):
        raise ValueError("expected a bounded embedded image")
    header, comma, encoded = uri.partition(",")
    if not comma or not header.endswith(";base64"):
        raise ValueError("expected a base64 image")
    raw = base64.b64decode(encoded, validate=True)
    if not 256 <= len(raw) <= MAX_REQUEST:
        raise ValueError("image outside byte budget")
    return raw


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, port: int, model_root: Path, jobs_root: Path, lock_path: Path):
        self.model_root, self.jobs_root, self.lock_path = model_root, jobs_root, lock_path
        self.job = threading.Lock()
        super().__init__(("127.0.0.1", port), Handler)


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
            return self.json_reply(200, {"data": [{"id": MODEL}], "busy": self.server.job.locked()})
        self.json_reply(404, {"error": "unknown route"})

    def do_POST(self):
        if self.path != "/v1/video":
            return self.json_reply(404, {"error": "unknown route"})
        if self.headers.get("Origin") or self.headers.get("Content-Type", "").split(";")[0] != "application/json":
            return self.json_reply(403, {"error": "server-to-server JSON only"})
        if not self.server.job.acquire(blocking=False):
            return self.json_reply(503, {"error": "video worker busy"})
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= MAX_REQUEST:
                raise ValueError("request outside byte budget")
            payload = json.loads(self.rfile.read(size))
            if not isinstance(payload, dict) or payload.get("model") != MODEL:
                raise ValueError("unknown model")
            prompt = payload.get("instruction")
            if not isinstance(prompt, str) or not 1 <= len(prompt) <= 4000:
                raise ValueError("instruction outside text budget")
            image = decode_image(payload.get("image"))
            clip = self.generate(image, prompt)
            self.send_response(200)
            self.send_header("Content-Type", "video/mp4")
            self.send_header("Content-Length", str(len(clip)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(clip)
        except (ValueError, TypeError, json.JSONDecodeError, binascii.Error):
            self.json_reply(422, {"error": "invalid bounded video request"})
        except (OSError, subprocess.SubprocessError):
            self.json_reply(503, {"error": "video generation unavailable"})
        finally:
            self.server.job.release()

    def generate(self, image: bytes, prompt: str) -> bytes:
        usage = subprocess.run(
            ["nvidia-smi", "--query-compute-apps=used_memory", "--format=csv,noheader,nounits"],
            check=True, capture_output=True, text=True, timeout=10,
        )
        used_mib = sum(int(line.strip()) for line in usage.stdout.splitlines() if line.strip().isdigit())
        if used_mib > 1536:
            raise OSError("GPU is serving another model")
        self.server.jobs_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="wan-", dir=self.server.jobs_root) as folder:
            job = Path(folder)
            (job / "input.png").write_bytes(image)
            output = job / "output.mp4"
            command = [
                "docker", "run", "--rm", "--gpus", "all", "--shm-size", "16g",
                "-e", "PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True",
                "-v", f"{self.server.model_root}:/models/wan2.2-ti2v-5b:ro",
                "-v", f"{job}:/job", IMAGE,
                "--task", "ti2v-5B", "--size", "1280*704", "--frame_num", "33",
                "--sample_steps", "10", "--ckpt_dir", "/models/wan2.2-ti2v-5b",
                "--offload_model", "True", "--convert_model_dtype", "--t5_cpu",
                "--image", "/job/input.png", "--prompt", prompt, "--base_seed", "42",
                "--save_file", "/job/output.mp4",
            ]
            self.server.lock_path.parent.mkdir(parents=True, exist_ok=True)
            with self.server.lock_path.open("a+b") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                subprocess.run(command, check=True, timeout=720, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
            clip = output.read_bytes()
            if not 1 <= len(clip) <= MAX_VIDEO:
                raise OSError("video outside response budget")
            return clip


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-root", required=True, type=Path)
    parser.add_argument("--jobs-root", required=True, type=Path)
    parser.add_argument("--lock", required=True, type=Path)
    parser.add_argument("--port", type=int, default=7260)
    args = parser.parse_args()
    if not (args.model_root / ".pinned-revision").is_file():
        raise SystemExit("pinned Wan model is not prepared")
    server = Server(args.port, args.model_root.resolve(), args.jobs_root.resolve(), args.lock.resolve())
    print(f"Wan worker ready on 127.0.0.1:{args.port}", flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
