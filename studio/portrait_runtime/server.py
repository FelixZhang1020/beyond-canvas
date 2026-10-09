"""Loopback-only, single-job mesh worker. Start after preparing local weights.

The classroom imports neither torch nor the model repository. Generation has
fixed settings; the HTTP caller can provide only an image and the model name.
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from PIL import Image, ImageOps

from studio.making.mesh import MAX_BYTES, MAX_FACES, validate

MODEL = "triposg"
WEIGHT_REVISION = "2c1c516d22d58db486a058d98d31bb6177344e06"
CODE_REVISION = "fc5c40990181e2a756c4e0b1c2f4d6b5202faf8c"


def decode_image(uri):
    if not isinstance(uri, str) or len(uri) > MAX_BYTES or not uri.startswith("data:image/"):
        raise ValueError("expected a bounded embedded image")
    header, separator, data = uri.partition(",")
    if not separator or not header.endswith(";base64"):
        raise ValueError("expected base64 image")
    raw = base64.b64decode(data, validate=True)
    with Image.open(io.BytesIO(raw)) as opened:
        if min(opened.size) < 32 or max(opened.size) > 2048:
            raise ValueError("image dimensions outside worker budget")
        image = ImageOps.exif_transpose(opened).convert("RGB")
        image.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
    return image


class Engine:
    def __init__(self, source: Path, weights: Path, masks: Path, device: str):
        if not (weights / "revision.txt").is_file() or (weights / "revision.txt").read_text().strip() != WEIGHT_REVISION:
            raise ValueError("prepare the pinned TripoSG weights before starting")
        if not (masks / "u2net.onnx").is_file():
            raise ValueError("prepare the local U2Net mask before starting")
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["HF_HOME"] = str(weights.parent / "hf-portrait")
        os.environ["U2NET_HOME"] = str(masks)
        os.environ.setdefault("OMP_NUM_THREADS", "6")
        os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
        sys.path.insert(0, str(source))
        import torch
        from rembg import new_session, remove
        from triposg.pipelines.pipeline_triposg import TripoSGPipeline

        torch.set_num_threads(6)
        if device == "auto":
            device = "cuda" if torch.cuda.is_available() else "mps"
        if device == "cuda":
            total = torch.cuda.get_device_properties(0).total_memory
            torch.cuda.set_per_process_memory_fraction(min(1, 12 * 1024**3 / total))
        elif device != "mps" or not torch.backends.mps.is_available():
            raise ValueError("this worker needs a CUDA or Apple Metal GPU")
        self.torch, self.remove, self.device = torch, remove, device
        self.mask = new_session("u2net", providers=["CPUExecutionProvider"])
        # FP16 on this MPS stack produced fragmented heads in the measured
        # comparison. CUDA's upstream FP16 path still needs a Spark benchmark.
        dtype = torch.float32 if device == "mps" else torch.float16
        self.pipe = TripoSGPipeline.from_pretrained(str(weights), torch_dtype=dtype, local_files_only=True).to(device)
        self.pipe.set_progress_bar_config(disable=True)
        decode = self.pipe.vae.decode
        self.pipe.vae.decode = lambda *args, **kw: decode(*args, num_chunks=4096, **kw)

    def make(self, image, *, subject="head"):
        if subject not in ("head", "fruit"):
            raise ValueError("unsupported mesh subject")
        torch = self.torch
        start = time.monotonic()
        cutout = self.remove(image, session=self.mask)
        bbox = cutout.getchannel("A").getbbox()
        if not bbox or (bbox[2]-bbox[0]) * (bbox[3]-bbox[1]) < image.width*image.height*.02:
            raise ValueError("no usable foreground")
        cutout = cutout.crop(bbox)
        side = int(max(cutout.size) * 1.2)
        prepared = Image.new("RGB", (side, side), "white")
        prepared.paste(cutout, ((side-cutout.width)//2, (side-cutout.height)//2), cutout)
        if self.device == "cuda":
            torch.cuda.reset_peak_memory_stats()
        with torch.inference_mode():
            output = self.pipe(image=prepared, generator=torch.Generator(device="cpu").manual_seed(42),
                               num_inference_steps=20, dense_octree_depth=7, hierarchical_octree_depth=7,
                               use_flash_decoder=False)
        mesh = prepare_surface(output.meshes[0], subject=subject)
        result = {"mesh": mesh, "model": MODEL, "revision": WEIGHT_REVISION,
                  "elapsed_s": round(time.monotonic()-start, 3)}
        if self.device == "cuda":
            result["peak_allocated_gib"] = round(torch.cuda.max_memory_allocated() / 1024**3, 3)
        return result


def prepare_surface(surface, *, subject="head"):
    """Clean numerical debris; refuse a fragmented head rather than invent one."""
    import numpy as np
    import trimesh
    if not 4 <= len(surface.faces) <= 200000:
        raise ValueError("raw surface outside budget")
    components = sorted(surface.split(only_watertight=False), key=lambda m: m.area, reverse=True)
    if not components or components[0].area < sum(m.area for m in components) * .98:
        raise ValueError("fragmented portrait surface")
    surface = components[0]
    if len(surface.faces) > MAX_FACES:
        surface = surface.simplify_quadric_decimation(face_count=MAX_FACES)
    # TripoSG is Y-up. Keep its generated orientation and ground the bust.
    p = np.asarray(surface.vertices).copy()
    if not np.isfinite(p).all() or np.ptp(p[:,1]) < 1e-6:
        raise ValueError("empty or nonfinite surface")
    p[:,0] -= (p[:,0].min()+p[:,0].max()) / 2
    p[:,2] -= (p[:,2].min()+p[:,2].max()) / 2
    p[:,1] -= p[:,1].min()
    p *= 3 / p[:,1].max()
    surface = trimesh.Trimesh(np.round(p, 6), surface.faces, process=True)
    surface.update_faces(surface.nondegenerate_faces() & (surface.area_faces > 1e-9))
    surface.remove_unreferenced_vertices()
    surface.fix_normals()
    before_faces = len(surface.faces)
    for _ in range(4):
        good = np.linalg.norm(surface.vertex_normals, axis=1) > .98
        if good.all():
            break
        surface.update_faces(good[surface.faces].all(axis=1))
        surface.remove_unreferenced_vertices()
    if len(surface.faces) < before_faces * .99:
        raise ValueError("too many invalid surface normals")
    # A bounded Taubin pass reduces voxel stair steps without a texture or a
    # replacement head. Reject excessive displacement instead of smoothing away
    # the features that the model failed to reconstruct.
    before = surface.vertices.copy()
    # Rounded fruit exposes grid ripples more strongly than the faceted busts.
    # More CPU smoothing keeps the same decode field and GPU memory budget.
    trimesh.smoothing.filter_taubin(surface, lamb=.5, nu=.53, iterations=80 if subject == "fruit" else 8)
    if np.linalg.norm(surface.vertices-before, axis=1).max() > .06:
        raise ValueError("unstable surface")
    surface.vertices[:,1] -= surface.vertices[:,1].min()
    surface.vertices = np.round(surface.vertices, 6)
    return validate({"positions": surface.vertices.flatten().tolist(),
                     "normals": np.round(surface.vertex_normals, 6).flatten().tolist(),
                     "indices": surface.faces.flatten().tolist()})


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, port, engine):
        self.engine, self.job = engine, threading.Lock()
        super().__init__(("127.0.0.1", port), Handler)


class Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(20)

    def log_message(self, *_):
        pass  # No image data or request bodies in logs.

    def reply(self, status, payload):
        body = json.dumps(payload, separators=(",", ":"), allow_nan=False).encode()
        if len(body) > MAX_BYTES:
            status, body = 422, b'{"error":"surface exceeds byte budget"}'
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_GET(self):
        if self.path == "/v1/models":
            self.reply(200, {"data": [{"id": MODEL}], "busy": self.server.job.locked()})
        else:
            self.reply(404, {"error": "unknown route"})

    def do_POST(self):
        if self.path != "/v1/mesh":
            return self.reply(404, {"error": "unknown route"})
        if self.headers.get("Origin") or self.headers.get("Content-Type", "").split(";")[0] != "application/json":
            return self.reply(403, {"error": "server-to-server JSON only"})
        if not self.server.job.acquire(blocking=False):
            return self.reply(503, {"error": "mesh worker busy"})
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= MAX_BYTES:
                raise ValueError("request outside byte budget")
            payload = json.loads(self.rfile.read(size))
            if not isinstance(payload, dict) or payload.get("model") != MODEL:
                raise ValueError("unknown model")
            subject = payload.get("subject", "head")
            if subject not in ("head", "fruit"):
                raise ValueError("unsupported mesh subject")
            image = decode_image(payload.get("image"))
            result = self.server.engine.make(image, subject="fruit") if subject == "fruit" else self.server.engine.make(image)
            self.reply(200, result)
        except (ValueError, TypeError, OSError):
            self.reply(422, {"error": "could not build a bounded surface"})
        except Exception as error:
            print("Portrait generation failed:", type(error).__name__, flush=True)
            self.reply(503, {"error": "mesh generation unavailable"})
        finally:
            self.server.job.release()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--weights", required=True, type=Path)
    parser.add_argument("--masks", required=True, type=Path)
    parser.add_argument("--device", choices=("auto", "cuda", "mps"), default="auto")
    parser.add_argument("--port", type=int, default=7240)
    args = parser.parse_args()
    engine = Engine(args.source.resolve(), args.weights.resolve(), args.masks.resolve(), args.device)
    server = Server(args.port, engine)
    print(f"Portrait worker ready on 127.0.0.1:{args.port} ({engine.device})", flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
