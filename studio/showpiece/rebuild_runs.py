"""The three earlier from-nothing rebuilds, each written as a replay record in the same
shape as the adopted run's, so the replay page can play them: run 1 (not adopted), run 2 (adopted
wrongly) and run 3 (adopted under the older checks).

Each record is read from the run's own private folder: its event log for every step, its scorecard
for how it ended, and the files its checks left behind for the pieces the page paints red. These
runs were never rebuilt stage by stage; the page shows each run's own final hall (exported on the
Spark by rebuild_bake.py --single) with each family of pieces appearing as it was placed, and the
pictures and the gravity video the run's own tools made. Run 2 was handed over before the check that
finds timber through the roof existed, so the pieces it names come from today's likeness check run
afterwards on run 2's hall, and the record says so.
Usage: python studio/showpiece/rebuild_runs.py <folder holding the run folders> [<run 2's later likeness.json>]
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "skills/load-path/scripts")]
from studio.showpiece.rebuild_events import ENDINGS, act_words, excerpt, think_title  # noqa: E402
from studio.showpiece.rebuild_facts import (CHECKING, PLACING, call_fields, failed, judged, limits,  # noqa: E402
                                           mark_repairs, seconds_by_tool)

RUNS = {1: "20260919-160856-e39518", 2: "20260919-162700-85568a", 3: "20260919-163925-883156"}
PAGE = ROOT / "studio/showpiece/page"
ORDER = ["inventory", "bearing", "weights", "settle", "shake", "likeness", "judge"]


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def steps_of(events: list[dict], run: str, said=excerpt) -> list[dict]:
    """Every logged event as a step the page plays. `said` reads a tool's answer down to the line the page
    shows; a design passes its own, which also reads a tool that stopped with an error."""
    start, frame, steps = datetime.fromisoformat(events[0]["at"]), "temple", []
    for i, event in enumerate(events):
        kind, tool, args = event["kind"], event.get("tool"), event.get("args") or {}
        text = str(event.get("text", ""))
        if kind == "think":
            title, detail = think_title(events[i + 1].get("tool") if i + 1 < len(events) else None), text.split("\n", 1)[0][:230]
        elif kind in ENDINGS:
            title, detail = ENDINGS[kind]
        else:
            title, detail = act_words(tool, args)
        step = {"step": int(event["step"]), "elapsed": round((datetime.fromisoformat(event["at"]) - start).total_seconds()),
                "kind": kind, "tool": tool, "title": title, "detail": detail, "cutaway": False, "focus": None,
                "duration_ms": 1050 if kind == "think" else 1500, **call_fields(event, run),
                "evidence": (judged(event) if tool == "judge" else said(text)) if kind == "act" else text[:800]}
        if kind == "act":
            step["args"] = {k: v for k, v in args.items() if k not in ("out_dir", "out")}
            if tool in PLACING and not failed(step):
                frame = f"step-{step['step']}"
            if tool in ("settle", "shake"):
                step["physics"] = tool
        step["frame"] = frame
        steps.append(step)
    return mark_repairs(steps)


def media(steps: list[dict], n: int, folder: Path) -> None:
    """The pictures and video each run's tools made. Each file was overwritten by the next call of its
    tool, so what is on disk belongs to the last such call, and that is the step it is shown at."""
    def last(tool):
        return next((s for s in reversed(steps) if s["kind"] == "act" and s.get("tool") == tool and not failed(s)), None)
    if (s := last("survey")):
        s["media"] = {"image": f"rebuild-run{n}-temple.jpg"}
    if (s := last("settle")) and (folder / "settle.mp4").is_file():
        s["media"] = {"video": f"rebuild-run{n}-settle.mp4", "image": f"rebuild-run{n}-settle-end.jpg"}
    if (s := last("likeness")) and (folder / "likeness.png").is_file():
        s["media"] = {"image": f"rebuild-run{n}-likeness.jpg"}


def record_of(n: int, folder: Path, later: Path | None, protocol: dict) -> dict:
    events = [json.loads(line) for line in (folder / "events.jsonl").read_text(encoding="utf-8").splitlines() if line]
    card, steps = read(folder / "scorecard.json"), steps_of(events, RUNS[n])
    media(steps, n, folder)
    used = {s.get("tool") for s in steps if s["kind"] == "act"}
    moved = read(folder / "settle.json").get("pieces", {})
    through = read(later).get("through_the_roof", []) if later else read(folder / "likeness.json").get("through_the_roof", [])
    return {
        "run": n, "source_run": RUNS[n], "source_note": "the run's own event log, scorecard and check files",
        "measured": {"wall_seconds": card["wall_seconds"], "tokens": card["tokens"], "actions": card["turns"]["actions"],
                     "adopted": card["adopted"]},
        "steps": steps, "physics_protocol": protocol,
        "faults": {"fell": sorted(k for k, v in moved.items() if v.get("moved_m", 0) > 1.0),
                   "hanging": sorted(read(folder / "bearing.json").get("floating", {})),
                   "through_the_roof": through, "found_later": bool(later)},
        "harness": {"model": {"name": "Step 3.7 Flash", "id": card["agent"]}, "limits": limits(), "turns": card["turns"], "tokens": card["tokens"],
                    "tool_seconds": card["tool_seconds"], "wall_seconds": card["wall_seconds"],
                    "seconds_by_tool": seconds_by_tool(events), "still_owed": card.get("still_owed", []),
                    "checks": [c for c in ORDER if c in used and c in CHECKING]},
    }


def main() -> None:
    runs_root = Path(sys.argv[1])
    later = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    protocol = read(PAGE / "rebuild-record.json")["physics_protocol"]
    for n, name in RUNS.items():
        record = record_of(n, runs_root / name, later if n == 2 else None, protocol)
        (PAGE / f"rebuild-run{n}-record.json").write_text(json.dumps(record, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        f = record["faults"]
        print(f"run {n}: {len(record['steps'])} steps, fell {len(f['fell'])}, hanging {len(f['hanging'])}, "
              f"through the roof {len(f['through_the_roof'])}")


if __name__ == "__main__":
    main()
