"""The GLB copies of the models the exhibit shows in its live 3D view, one per .blend, kept under
the runs folder and remade only when the model is newer. Exporting a big model takes a minute,
so it runs in the background and the page asks again until the file is there.
"""
from __future__ import annotations

import threading
from pathlib import Path

from studio.showpiece.blender_bin import find_blender, run_tool

GLB_SCRIPT = Path(__file__).with_name("glb.py")
TIMEOUT_S = 900
_running: set[str] = set()
_lock = threading.Lock()


def glb_path(model: Path, models_root: Path) -> Path:
    return models_root / f"{Path(model).stem}.glb"


def is_fresh(model: Path, target: Path) -> bool:
    return target.is_file() and Path(model).is_file() and target.stat().st_mtime >= Path(model).stat().st_mtime


def export_glb(model: Path, models_root: Path, light: bool = True) -> Path | None:
    """Export now, in this thread; the GLB's path, or None without Blender or on failure."""
    blender = find_blender()
    model, target = Path(model), glb_path(model, models_root)
    if blender is None or not model.is_file():
        return None
    if is_fresh(model, target):
        return target
    models_root.mkdir(parents=True, exist_ok=True)
    argv = [str(blender), "-b", str(model), "--python-exit-code", "1", "--python", str(GLB_SCRIPT), "--", str(target)]
    code, _tail = run_tool(argv + (["--light"] if light else []), TIMEOUT_S)
    return target if code == 0 and target.is_file() else None


def export_in_background(model: Path | None, models_root: Path) -> None:
    """Start the export unless it is fresh or already running."""
    if not model or not Path(model).is_file() or is_fresh(model, glb_path(model, models_root)):
        return
    key = str(Path(model).resolve())
    with _lock:
        if key in _running:
            return
        _running.add(key)

    def work() -> None:
        try:
            export_glb(model, models_root)
        finally:
            with _lock:
                _running.discard(key)

    threading.Thread(target=work, daemon=True).start()
