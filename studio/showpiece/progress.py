"""What a run is doing between two events, for the exhibit's one-second heartbeat: the model is
thinking, or a tool is running and its frames are landing in the run folder one by one. The
frame count expected is an estimate from the tool's arguments and defaults, good enough for a
bar; nothing here is written down or trusted for anything else.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

FRAME = re.compile(r"^f\d{4}\.png$")
DEFAULTS = {"explode": {"seconds": 6.0, "fps": 30}, "tour": {"seconds-per": 4.0, "fps": 30, "segments": 4},
            "settle": {"seconds": 4.0, "fps": 24}, "flow": {"seconds": 6.0, "hold": 2.0, "fps": 30},
            "raise": {"scene-seconds": 0.4, "settle-seconds": 0.6, "fps": 30}}


def _num(args: dict, key: str, default: float) -> float:
    try:
        return float(args.get(key, default))
    except (TypeError, ValueError):
        return default


def expected_frames(tool: str, args: dict, run_dir: Path) -> int | None:
    """How many frames the render will write, from its arguments; None for a tool with no frames."""
    d = DEFAULTS.get(tool)
    if d is None:
        return None
    fps = _num(args, "fps", d["fps"])
    if tool == "tour":
        segments = args.get("segments")
        count = len([s for s in str(segments).split(",") if s.strip()]) if segments else d["segments"]
        return count * max(2, round(_num(args, "seconds-per", d["seconds-per"]) * fps))
    if tool == "flow":
        return max(2, round(_num(args, "seconds", d["seconds"]) * fps)) + round(_num(args, "hold", d["hold"]) * fps)
    if tool == "raise":
        scenes = Path(str(args.get("scenes") or "scenes.json"))
        scenes = scenes if scenes.is_absolute() else run_dir / scenes
        try:
            count = len(json.loads(scenes.read_text(encoding="utf-8")).get("scenes", []))
        except (OSError, ValueError, AttributeError):
            return None
        per = _num(args, "scene-seconds", d["scene-seconds"]) + _num(args, "settle-seconds", d["settle-seconds"])
        return count * max(1, round(per * fps)) + round(fps) if count else None
    return max(2, round(_num(args, "seconds", d["seconds"]) * fps))


def frames_so_far(run_dir: Path, tool: str) -> tuple[int, str | None]:
    """Frames the tool has written into its own subfolder, and the newest one's path in the run."""
    folder = run_dir / tool
    if not folder.is_dir():
        return 0, None
    names = sorted(p.name for p in folder.iterdir() if FRAME.match(p.name))
    return len(names), f"{tool}/{names[-1]}" if names else None


def heartbeat(run_dir: Path, busy: dict) -> dict:
    """One line of what is happening now: the phase, the tool, seconds so far, frames so far and expected."""
    beat = {"phase": busy.get("phase", "thinking"), "skill": busy.get("skill"), "tool": busy.get("tool"),
            "seconds": round(time.monotonic() - float(busy.get("started", time.monotonic())))}
    if beat["phase"] == "tool" and beat["tool"]:
        count, newest = frames_so_far(run_dir, beat["tool"])
        beat.update({"frames": count, "newest": newest,
                     "expected": expected_frames(beat["tool"], dict(busy.get("args") or {}), run_dir)})
    return beat
