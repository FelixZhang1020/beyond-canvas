"""Record the five temple showpieces as runs the dashboard replays, made by the tools themselves:

    python -m studio.showpiece.record --model <model.blend> [--runs .studio/showpiece/runs]
        [--kinds raise,tour,explode,load,settle] [--assembly "Column -12.50 -8.83"] [--quick]
        [--lang zh|en] [--reword]

Each showpiece becomes one run folder, `recorded-<kind>`, with the same request.json and
events.jsonl a driven run writes (the agent is "recorded"), the tools' real seconds, every
third render frame kept so the replay can paint the render, and the plan file the live 3D view
moves the pieces by. The words of each run live in prompts/recorded.json in both languages;
`--lang` picks the one the recording speaks, and `--reword` changes the words of a recording
already made without running any tool again (and fills in the command each step ran). No model is asked anything; the judge is not run.
`--quick` renders small and short, for a test.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import time
from datetime import UTC, datetime
from pathlib import Path

from studio.showpiece import catalog
from studio.showpiece.blender_bin import run_tool
from studio.showpiece.driver import command_line

WORDS = Path(__file__).with_name("prompts") / "recorded.json"
FRAME = re.compile(r"^f(\d{4})\.png$")
KEEP_EVERY = 3
QUICK = {"fps": "6", "width": "320", "height": "180"}


# The three real joints each bracket set is shown with, cut on a copy of the hall by joint-reveal's
# joints tool; the skill keeps which sets have them, in assets/sets.json, for its explode tool too. The
# pull-apart recording films them close, one at a time, instead of the whole set among
# its neighbours, which hid them; a set not listed there is still pulled apart whole.
JOINTS = json.loads((catalog.SKILLS / "joint-reveal" / "assets" / "sets.json").read_text(encoding="utf-8"))
JOINTED = "jointed"     # a step that runs on the copy the joints tool wrote, not the hall itself
# 松开手: the tenon on top of that column is taken out and the hall comes
# down link by link; the same joint 拆开来 shows close.
COLLAPSE_JOINT = ["Perimeter timber column.002", "Column -12.50 -8.83 | Ludou foot"]


def jointed_copy(model: Path, run_dir: Path) -> Path:
    return run_dir / f"{Path(model).stem}-joints.blend"


def steps_for(kind: str, assembly: str, quick: bool) -> list[tuple]:
    """The tool calls of one showpiece, after inventory and bearing, as (skill, tool, args[, JOINTED])."""
    q = QUICK if quick else {}
    short = {"seconds": "1"} if quick else {}
    if kind == "raise":
        return [("raise-the-hall", "stages", {"bearing": "bearing.json", "anatomy": "anatomy.json", "out_dir": "."}),
                ("raise-the-hall", "raise", {"out_dir": ".", "scenes": "scenes.json", "anatomy": "anatomy.json", **q})]
    if kind == "tour":
        return [("structure-tour", "tour", {"out_dir": ".", "anatomy": "anatomy.json", **q, **({"seconds-per": "1"} if quick else {})})]
    if kind == "explode":
        if assembly not in JOINTS:
            return [("joint-reveal", "explode", {"out_dir": ".", "anatomy": "anatomy.json", "assembly": assembly, **q, **short})]
        return [("joint-reveal", "joints", {"out_dir": ".", **JOINTS[assembly]}),
                ("model-anatomy", "inventory", {"out_dir": JOINTED}, JOINTED),
                ("joint-reveal", "explode", {"out_dir": ".", "anatomy": f"{JOINTED}/anatomy.json", "assembly": assembly,
                                             "joints": "joints.json", "closeups": True, "seconds": "6", **q, **short}, JOINTED)]
    if kind == "load":
        return [("load-path", "weights", {"anatomy": "anatomy.json", "bearing": "bearing.json", "out_dir": "."}),
                ("load-path", "flow", {"out_dir": ".", "anatomy": "anatomy.json", "loads": "loads.json", **q, **short})]
    if kind == "settle":
        return [("load-path", "collapse", {"out_dir": ".", "anatomy": "anatomy.json", "bearing": "bearing.json",
                                            "joint": [COLLAPSE_JOINT], **q})]
    raise ValueError(f"no such showpiece: {kind}")


def thin_frames(run_dir: Path) -> int:
    """Keep every third frame of each render folder; the replay paints from what is left."""
    removed = 0
    for folder in (p for p in run_dir.iterdir() if p.is_dir()):
        for frame in folder.iterdir():
            m = FRAME.match(frame.name)
            if m and int(m.group(1)) % KEEP_EVERY != 1:
                frame.unlink()
                removed += 1
    return removed


def words_for(kind: str, lang: str) -> dict:
    """The request, the thought and the answer of one showpiece, in one language."""
    words = json.loads(WORDS.read_text(encoding="utf-8"))[kind]
    return {key: words[key][lang] for key in ("request", "think", "final")}


def reword(runs_root: Path, kind: str, lang: str) -> Path:
    """Change the words of a recording already made; the tool steps stay exactly as they ran."""
    run_dir = runs_root / f"recorded-{kind}"
    words = words_for(kind, lang)
    meta = json.loads((run_dir / "request.json").read_text(encoding="utf-8"))
    (run_dir / "request.json").write_text(json.dumps({**meta, "request": words["request"], "lang": lang}, ensure_ascii=False), encoding="utf-8")
    lines = [json.loads(line) for line in (run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    model = Path(meta.get("model", ""))
    for event in lines:
        if event["kind"] in ("think", "final"):
            event["text"] = words[event["kind"]]
        if event["kind"] == "act" and (event["skill"], event["tool"]) in catalog.TOOLS:   # the command is derived, so it is always refreshed
            spec = catalog.TOOLS[(event["skill"], event["tool"])]
            used = jointed_copy(model, run_dir) if event.get("on") == JOINTED else model
            event["command"] = command_line(catalog.argv_for(spec, event["args"], used if spec.needs_model else None, run_dir))
    with open(run_dir / "events.jsonl", "w", encoding="utf-8") as f:
        for event in lines:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
    return run_dir


def record(model: Path, runs_root: Path, kind: str, assembly: str, quick: bool = False,
           timeout_s: int | None = None, lang: str = "zh") -> Path:
    """One showpiece as a run folder; the tools run for real and their seconds are kept.

    Built aside as `recorded-<kind>.part`, so the exhibit keeps showing the last whole
    recording until this one is finished; a failed attempt stays aside to be read.
    """
    words = words_for(kind, lang)
    final = runs_root / f"recorded-{kind}"
    run_dir = final.with_name(final.name + ".part")
    if run_dir.exists():
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True)
    (run_dir / "request.json").write_text(json.dumps({"request": words["request"], "model": str(model), "agent": "recorded", "lang": lang,
                                                      "started": datetime.now(UTC).isoformat()}, ensure_ascii=False), encoding="utf-8")
    events: list[dict] = [{"step": 1, "kind": "think", "text": words["think"], "tokens": 0}]
    calls = [("model-anatomy", "inventory", {"out_dir": "."}), ("model-anatomy", "bearing", {"out_dir": "."})] + steps_for(kind, assembly, quick)
    for skill, tool, args, *on in calls:
        spec = catalog.TOOLS[(skill, tool)]
        used = jointed_copy(model, run_dir) if on else model
        argv = catalog.argv_for(spec, args, used if spec.needs_model else None, run_dir)
        before = {p.name for p in run_dir.iterdir()}
        started = time.monotonic()
        code, tail = run_tool(argv, timeout_s or spec.timeout_s, cwd=catalog.ROOT)
        seconds = round(time.monotonic() - started, 1)
        if code != 0:
            raise RuntimeError(f"{skill}/{tool} failed ({code}) on {kind}:\n{tail[-1500:]}")
        new = sorted(p.name for p in run_dir.iterdir() if p.name not in before and ".blend" not in p.suffix)   # the jointed copy goes
        picture = next((n for n in new if n.lower().endswith(".png")), None)
        events.append({"step": len(events) + 1, "kind": "act", "skill": skill, "tool": tool, "args": args, "command": command_line(argv).replace(str(run_dir), str(final)), "text": tail,   # named by the folder the run ends up in
                       "files": new, "picture": picture, "verdict": None, "tokens": 0, "seconds": seconds, **({"on": JOINTED} if on else {})})
    events.append({"step": len(events) + 1, "kind": "final", "text": words["final"], "tokens": 0})
    stamp = datetime.now(UTC).isoformat()
    with open(run_dir / "events.jsonl", "w", encoding="utf-8") as f:
        for e in events:
            f.write(json.dumps({**e, "at": stamp}, ensure_ascii=False) + "\n")
    thin_frames(run_dir)
    for copy in run_dir.glob(f"{Path(model).stem}-joints.blend*"):
        copy.unlink()      # 47 MB the replay never reads; joints.json says how it was made
    if final.exists():
        shutil.rmtree(final)
    run_dir.rename(final)
    return final


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Record the temple showpieces as replayable runs, made by the tools.")
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--runs", type=Path, default=Path(".studio/showpiece/runs"))
    parser.add_argument("--kinds", default="raise,tour,explode,load,settle")
    parser.add_argument("--assembly", default="Column -12.50 -8.83", help="the bracket set the pull-apart takes apart")
    parser.add_argument("--quick", action="store_true", help="small and short renders, for a test")
    parser.add_argument("--timeout", type=int, default=None, help="seconds one tool may take; several recordings sharing a GPU need more")
    parser.add_argument("--lang", default="zh", choices=("zh", "en"), help="the language the recording speaks")
    parser.add_argument("--reword", action="store_true", help="change the words of recordings already made; no tool runs")
    args = parser.parse_args(argv)
    for kind in [k.strip() for k in args.kinds.split(",") if k.strip()]:
        started = time.monotonic()
        if args.reword:
            print(f"REWORDED {kind} {reword(args.runs, kind, args.lang)} {args.lang}", flush=True)
            continue
        folder = record(args.model, args.runs, kind, args.assembly, args.quick, args.timeout, args.lang)
        print(f"RECORDED {kind} {folder} {time.monotonic() - started:.0f} s", flush=True)


if __name__ == "__main__":
    main()
