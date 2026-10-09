"""What the temple showpiece answers, kept apart from which server answers it.

Two servers now serve these routes. The exhibit on its own port has since the
module was written; the classroom on 7060 does too, so that a person
starting Beyond Canvas does not have to know a second port exists. Beyond Canvas,
the temple showpiece and the harness diagram are one system, and the operator
said so plainly when the two-port split tripped them up.

So the bodies live here and the two handlers are thin. Each supplies one property,
`_exhibit`, naming where its driver, its page directory and its exported models
are: on the exhibit that is the server itself, and on the classroom it is an
object built the first time somebody opens a temple route, so an ordinary class
pays nothing for a demo it will not run.

Three methods are named `_showpiece_*` rather than the shorter name they had. The
classroom handler already has a `_page`, an `_asset` and an `_events` of its own,
and a mixin that quietly shadowed one of those would fail in the worst way there
is -- silently, and only for whichever route lost.

Every file the page fetches is resolved under the run's own folder and refused
otherwise.
"""
from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from studio.server.uploads import read_body
from studio.showpiece.delivery import send_file
from studio.showpiece.driver import replay
from studio.showpiece.models import export_in_background
from studio.showpiece.progress import heartbeat

PAGE = Path(__file__).with_name("page")
TOY = Path(__file__).with_name("toy.py")
TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".mjs": "text/javascript; charset=utf-8",
         ".css": "text/css; charset=utf-8", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp",
         ".mp4": "video/mp4", ".glb": "model/gltf-binary", ".json": "application/json", ".jsonl": "application/x-ndjson",
         ".gz": "application/gzip"}
TICK_S = 1.0
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}   # the studio page's own machine; nothing else is answered cross-origin


class ShowpieceRoutes:
    """The temple showpiece's routes, mixed into whichever server is serving them."""

    def _json(self, status: int, payload: Any) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._bytes(status, body, "application/json; charset=utf-8")

    def _cors(self) -> None:
        """The studio page on another local port may post a child's scene here; a page from
        anywhere else gets no cross-origin answer at all."""
        origin = self.headers.get("Origin", "")
        if urlparse(origin).hostname not in LOCAL_HOSTS:
            return
        self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _run_dir(self, run_id: str) -> Path | None:
        """The run's folder, only if it is a direct child of the runs root: no `..`, no symlink out."""
        root = self._exhibit.driver.runs_root.resolve()
        folder = (root / run_id).resolve()
        return folder if folder.parent == root and folder.is_dir() else None

    def _bytes(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")   # a page script or a model copy changes underfoot during a build
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _showpiece_page(self) -> None:
        self._bytes(200, (self._exhibit.page / "index.html").read_bytes(), TYPES[".html"])

    def _showpiece_asset(self, name: str) -> None:
        path = self._exhibit.page / name
        if not path.is_file():
            self._json(404, {"error": "no such showpiece asset"})
            return
        send_file(self, path, TYPES[path.suffix])

    def _vendor(self, name: str) -> None:
        """The 3D library kept on the box, under page/vendor."""
        path = (self._exhibit.page / "vendor" / name).resolve()
        if (self._exhibit.page / "vendor").resolve() not in path.parents or not path.is_file():
            self._json(404, {"error": "no such file"})
            return
        send_file(self, path, TYPES[".js"])

    def _model(self, name: str) -> None:
        """The GLB copy of a model, once the export has written it; 404 until then."""
        path = self._exhibit.models_root / name
        if not path.is_file():
            self._json(404, {"error": "no such model yet"})
            return
        send_file(self, path, "model/gltf-binary")

    def _runs(self) -> None:
        root = self._exhibit.driver.runs_root
        runs = []
        for folder in sorted((p for p in root.iterdir() if p.is_dir()), reverse=True) if root.is_dir() else []:
            meta, live = folder / "request.json", self._exhibit.driver.runs.get(folder.name)
            if not meta.is_file() or (live is None and not (folder / "events.jsonl").is_file()):
                continue      # a recording still being made, or a folder that never got going
            info = json.loads(meta.read_text(encoding="utf-8"))
            events = live.events if live else replay(folder)
            runs.append({"id": folder.name, "request": info.get("request", ""), "agent": info.get("agent", ""),
                         "started": info.get("started", ""), "done": live.done if live else True, "steps": len(events),
                         "model": Path(info.get("model") or "").stem, "recorded": info.get("agent") == "recorded",
                         "showpiece": showpiece_of(folder)})
        self._json(200, {"runs": runs})

    def _start(self) -> None:
        body = json.loads(read_body(self) or b"{}")   # the class's cap: an oversized request is refused unread
        request = str(body.get("request", "")).strip()
        if not request:
            self._json(400, {"error": "request is empty"})
            return
        # Every tool of a live run is Blender. The hosted Spark has one (Ubuntu's
        # 5.0.1 in a container, deploy/spark/bin/blender); a machine with none still refuses plainly
        # rather than start a run whose steps all fail.
        from studio.showpiece.blender_bin import find_blender
        if find_blender() is None:
            self._json(503, {"error": "Live runs need Blender, which this machine does not have; "
                                      "its recorded demos still play.", "code": "no_blender"})
            return
        model = None
        if isinstance(body.get("scene"), dict):
            model = toy_model(self._exhibit.driver.runs_root, body["scene"])
            if model is None:
                self._json(503, {"error": "the toy could not be built: no Blender, or a scene the converter refuses"})
                return
            export_in_background(model, self._exhibit.models_root)
        run = self._exhibit.driver.start(request, model)
        self._json(201, {"id": run.id, "model": Path(run.model).stem})

    def _showpiece_events(self, run_id: str) -> None:
        driver = self._exhibit.driver
        live, folder = driver.runs.get(run_id), self._run_dir(run_id)
        if live is None and folder is None:
            self._json(404, {"error": "no such run"})
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self._cors()
        self.end_headers()
        if live is None:
            for event in replay(folder):
                self._sse("step", event)
            self._sse("done", {})
            return
        sent = 0
        while True:
            with live.cond:
                if sent >= len(live.events) and not live.done:
                    live.cond.wait(TICK_S)
                fresh, done, busy = live.events[sent:], live.done, live.busy
            for event in fresh:
                self._sse("step", event)
            sent += len(fresh)
            if done and sent >= len(live.events):
                self._sse("done", {})
                return
            if not fresh and busy:      # nothing new this second: say what the run is doing meanwhile
                self._sse("busy", heartbeat(live.dir, busy))

    def _sse(self, name: str, payload: dict) -> None:
        self.wfile.write(f"event: {name}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8"))
        self.wfile.flush()

    def _file(self, run_id: str, name: str) -> None:
        root = self._run_dir(run_id)
        target = (root / name).resolve() if root else None
        if root is None or root not in target.parents or not target.is_file():
            self._json(404, {"error": "no such file in this run"})
            return
        send_file(self, target, TYPES.get(target.suffix.lower(), "application/octet-stream"))

    def _stats(self) -> None:
        self._json(200, machine_stats())


def toy_model(runs_root: Path, scene: dict) -> Path | None:
    """A child's sketch scene as a .blend under the runs folder, built by toy.py, or None."""
    from studio.showpiece.blender_bin import find_blender, run_tool

    blender = find_blender()
    if blender is None or not isinstance(scene.get("objects"), list) or not scene["objects"]:
        return None
    folder = runs_root / "toys"
    folder.mkdir(parents=True, exist_ok=True)
    stamp = uuid.uuid4().hex[:8]
    scene_path, model = folder / f"scene-{stamp}.json", folder / f"toy-{stamp}.blend"
    scene_path.write_text(json.dumps(scene), encoding="utf-8")
    code, _ = run_tool([str(blender), "-b", "--python-exit-code", "1", "--python", str(TOY), "--", str(scene_path), str(model)], 120)
    return model if code == 0 and model.is_file() else None


PLAN_FILES = (("explode.json", "explode"), ("scenes.json", "raise"), ("loads.json", "load"), ("tour.json", "tour"), ("settle.json", "settle"),
              ("collapse.json", "settle"))   # 松开手's collapse is the settle button's recording


def showpiece_of(folder: Path) -> str | None:
    """Which showpiece a run holds, by the newest plan file it wrote."""
    present = [(f.stat().st_mtime, kind) for name, kind in PLAN_FILES if (f := folder / name).is_file()]
    return max(present)[1] if present else None


def gpu_stats(text: str) -> dict | None:
    """The first GPU's memory and use from nvidia-smi's csv line "used, total, util" in MiB and %.

    Every field is read on its own, because a card may report some and not others. A DGX Spark
    reports no GPU memory at all — chip and system share one pool, so "[N/A], [N/A], 96" is its
    ordinary answer while it is busy. Requiring the memory fields threw that 96 away and left the
    console saying the GPU was unavailable on a machine working at full tilt.
    """
    lines = [line for line in text.strip().splitlines() if line.strip()]
    if not lines:
        return None
    parts = [v.strip() for v in lines[0].split(",")]
    if len(parts) < 2:
        return None

    def reading(index):
        try:
            return float(parts[index])
        except (ValueError, IndexError):
            return None      # "[N/A]" where a card reports nothing
    used, total, util = reading(0), reading(1), reading(2)
    if used is None and total is None and util is None:
        return None          # nothing usable is not a reading
    return {"used_gb": used / 1024 if used is not None else None,
            "total_gb": total / 1024 if total is not None else None, "util_percent": util}


GIB = 1024 ** 3


def machine_stats() -> dict:
    """Memory in use and available, and the GPU's when nvidia-smi is present.

    Memory is counted in 1024s (GiB), as the Spark's own terminal monitor and nvidia-smi count it. Counted
    in thousands, as it used to be, the console said "88.5 / 130.7 G" beside the monitor's "82 of 122 GB"
    for the same memory, and read as two machines disagreeing.
    """
    used = total = None
    if platform.system() == "Darwin":
        out = subprocess.run(["vm_stat"], capture_output=True, text=True).stdout
        pages = {k.strip(): int(v.strip(" ."))
                 for k, v in (line.split(":") for line in out.splitlines()[1:] if ":" in line) if v.strip(" .").isdigit()}
        page = 16384
        total = int(subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True).stdout or 0) / GIB
        free = (pages.get("Pages free", 0) + pages.get("Pages inactive", 0)) * page / GIB
        used = total - free if total else None
    elif Path("/proc/meminfo").is_file():
        info = {}
        for line in Path("/proc/meminfo").read_text().splitlines():
            key, _, value = line.partition(":")
            info[key] = int(value.split()[0]) * 1024 / GIB
        total, used = info.get("MemTotal"), info.get("MemTotal", 0) - info.get("MemAvailable", 0)
    gpu = None
    if shutil.which("nvidia-smi"):
        gpu = gpu_stats(subprocess.run(["nvidia-smi", "--query-gpu=memory.used,memory.total,utilization.gpu",
                                        "--format=csv,noheader,nounits"], capture_output=True, text=True).stdout)
    try:
        cpu = min(100.0, os.getloadavg()[0] / (os.cpu_count() or 1) * 100)   # the minute's load over the cores
    except OSError:
        cpu = None
    return {"memory_used_gb": used, "memory_total_gb": total, "gpu": gpu, "cpu_percent": cpu,
            "cpu_count": os.cpu_count(), "host": platform.node()}
