"""The hall designed from a written brief, written as replay records the rebuild page
already plays, so each design run is watched as the four rebuilds are: rebuild.html?design=N.

A design is the from-nothing rebuild with no temple: the builder had a brief and one photograph, survey
and likeness were refused in a sentence, and the last check was the brief's own (hall-carpenter brief).
Its record is the earlier runs' shape (rebuild_runs.py) with the brief in likeness's place: what the
page paints red through the roof, and the bays, span, rings and bracket share it quotes, come from the
run's brief-check.json. Each step's own pictures and videos, which a design keeps by step in media/,
become the page's jpg and mp4; the 3D is the stage models the run kept after every placing call, joined
into one GLB on the Spark (rebuild_bake.py), so the page shows the design as it stood at each step. A
run that stopped before it kept stages is exported from its last hall alone, as runs 1 to 3 are.
Nothing is re-run: gravity and the shake are the run's own results and videos.

A check file that describes an earlier hall than the one the run ended with is left out of what the
last step paints: pieces that floated at step 76 say nothing about a hall rebuilt at step 129. The
words a step shows are the page's own (rebuild-strings.json). A run keeps its design number in
rebuild-designs.json; a new run takes the next.

An adopted design passed the checks of its day, and a check added since may fail it: design 4 was
handed over with 240 bracket pieces out past the eaves, before the brief check looked for them. So
today's brief check is run again on the hall an adopted design ended with (rebuild_recheck.py, in
Blender's scratch folder); if the hall no longer meets the brief, the record says it was found later,
names the pieces for the last step to paint red, and says which check the run's own day did not have,
as rebuild run 2's record does for the king posts through its roof.

Adopted here means the hall answers the brief and stands, not that it looks like the real hall: the brief
never described the look. So every design's record also carries five numbers measured on the hall it ended
with, the same ones hall-carpenter measures of the real hall (roof rings, the ridge's length, the eaves past
the corner columns, the outline, the top), and rebuild-real-hall.json carries the real hall's, from the
survey of our measured model that the adopted rebuild's record already holds; the page sets them side by side.
Usage, on the Spark (from the Mac, sh deploy/spark/test-on-spark.sh python -m studio.showpiece.rebuild_designs ...):
  python -m studio.showpiece.rebuild_designs <run id> [<run id> ...] [--from DIR] [--bake DIR] [--no-bake] [--no-media]
                                            [--no-recheck]
"""
from __future__ import annotations

import argparse
import functools
import json
import re
import shutil
import subprocess
import tempfile
from datetime import date
from pathlib import Path

from studio.showpiece.rebuild_runs import PAGE, read, steps_of  # first: it puts the load-path scripts on the path
from studio.showpiece import adoption, rebuild_bake
from studio.showpiece.rebuild_events import excerpt
from studio.showpiece.rebuild_facts import PLACING, failed, limits, seconds_by_tool

RUNS = Path.home() / "beyond-canvas-design/.studio/showpiece/designs"
BAKE = Path.home() / "beyond-canvas-design-bake"      # Blender's own scratch folder on the Spark
MANIFEST = PAGE / "rebuild-designs.json"
REAL = PAGE / "rebuild-real-hall.json"
RECHECK = Path(__file__).with_name("rebuild_recheck.py")
RUN_ID = re.compile(r"\b\d{8}-\d{6}-[0-9a-f]{6}\b")
# How a design run can stop, read from the driver's own sentence; the thinking stop keeps the rebuilds' words.
STOPS = {"cap": "the cap of", "refused": "not adopted after", "laps": "repair laps are used",
         "unreadable": "could not be read twice", "failed": "the run failed"}


@functools.cache
def _strings() -> dict:
    return json.loads((PAGE / "rebuild-strings.json").read_text(encoding="utf-8"))


def words(key: str, **values) -> str:
    text = _strings()[key]
    for name, value in values.items():
        text = text.replace("{" + name + "}", str(value))
    return text


def said(text: str) -> str:
    """A tool's answer down to the line the page shows; for a tool that stopped with an error, which the
    rebuilds' excerpt leaves blank, the exit and the error it stopped on."""
    line = excerpt(text)
    if line or not text.startswith("exit "):
        return line
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    errors = [line for line in lines if re.match(r"[A-Za-z_.]+(?:Error|Exception):", line)]
    return f"{text.split(':', 1)[0]}: {(errors or lines)[-1]}"[:360]


def scrub(value, folder: Path, run: str):
    """Every string of the record without the run's private folder or any home folder: a path in a
    traceback becomes the repository's own, the run's folder becomes "run"."""
    if isinstance(value, dict):
        return {k: v if k == "source_run" else scrub(v, folder, run) for k, v in value.items()}
    if isinstance(value, list):
        return [scrub(v, folder, run) for v in value]
    if not isinstance(value, str):
        return value
    text = value.replace(str(folder), "run").replace(f".studio/showpiece/designs/{run}", "run")
    text = re.sub(r"/(?:home|Users)/[^/\s\"']+/(?:[\w.-]+/)*?(?=(?:skills|studio|evalkit|deploy|output)/)", "", text)
    text = re.sub(r"/(?:home|Users)/[^\s\"']*", lambda m: Path(m.group(0)).name, text)
    return RUN_ID.sub("run", text)


def worded(steps: list[dict], events: list[dict]) -> None:
    """A design's own words where a rebuild's would be wrong: no measured numbers, a brief check, the eyes
    on the photograph, a hand-over sent back, and how the run stopped."""
    for i, (step, event) in enumerate(zip(steps, events)):
        kind, tool = step["kind"], step.get("tool")
        if kind == "think" and i + 1 < len(events) and events[i + 1].get("tool") == "brief":
            step["title"] = words("design.think.brief")
        elif kind in ("look", "bounce"):
            step["title"], step["detail"] = words(f"design.{kind}.title"), words(f"design.{kind}.detail")
        elif kind == "stop" and (why := next((k for k, s in STOPS.items() if s in step["evidence"]), None)):
            cap = re.search(r"the cap of (\d+)", step["evidence"])
            step["title"], step["detail"] = words(f"design.stop.{why}.title"), words(f"design.stop.{why}.detail",
                                                                                   cap=cap.group(1) if cap else "")
        elif kind == "act" and not event.get("command") and step["evidence"].startswith("REFUSED"):
            step["detail"] = words("design.detail.withheld")          # refused before anything ran
        elif kind == "act" and tool == "brief":
            step["title"], step["detail"] = words("design.tool.brief"), words("design.detail.brief")
        elif kind == "act" and tool in ("judge", *PLACING):
            step["detail"] = words("design.detail.judge" if tool == "judge" else "design.detail.place")


def on_kept_stages(steps: list[dict], kept: set[int]) -> None:
    """A design kept its hall after every placing call that finished; each step shows the last of them."""
    frame = "temple"
    for step in steps:
        if step["kind"] == "act" and step["step"] in kept:
            frame = f"step-{step['step']}"
        step["frame"] = frame


def media_of(steps: list[dict], folder: Path, n: int) -> list[tuple[Path, str]]:
    """Each step's own pictures and video from media/step-N-<name>, named for the page; the eyes' step
    shows the picture they were given. Returns what to convert: the run's file and the page's name."""
    kept, plan, latest = folder / "media", [], {}
    for step in (s for s in steps if s["kind"] == "act"):
        prefix, made = f"step-{step['step']}-", {}
        for source in sorted(kept.glob(f"step-{step['step']}-*")) if kept.is_dir() else []:
            stem, ext = source.name[len(prefix):].rsplit(".", 1)
            name = f"rebuild-design{n}-step{step['step']}-{stem}.{'mp4' if ext.lower() == 'mp4' else 'jpg'}"
            plan.append((source, name))
            made[stem] = latest[source.name[len(prefix):]] = name
        video = next((stem for stem, name in made.items() if name.endswith(".mp4")), None)
        if video:
            step["media"] = {"video": made[video], **({"image": made[f"{video}-end"]} if f"{video}-end" in made else {})}
        elif made:
            step["media"] = {"image": next(iter(made.values()))}
        elif step.get("tool") == "judge" and (seen := latest.get(str((step.get("args") or {}).get("image", "")))):
            step["media"] = {"image": seen}
    return plan


def current(steps: list[dict], tool: str) -> bool:
    """Whether the last finished call of a check came after the last finished placing call: only then does
    its file describe the hall the run ended with."""
    done = [i for i, s in enumerate(steps) if s["kind"] == "act" and not failed(s)]
    placed = max((i for i in done if steps[i].get("tool") in PLACING), default=-1)
    return max((i for i in done if steps[i].get("tool") == tool), default=-1) > placed


def versus(size, top, span, rings, ridge_half_x) -> dict | None:
    """The five numbers a hall is set beside the real one by, from what hall-carpenter measures of any hall
    (its survey of the real one, its brief check of a design): the roof rings; the ridge's length, twice the
    half the survey measures; how far the outline stands past the corner columns across the front and at the
    ends (half the outline less half the corner columns' span, each way); the outline; and the top."""
    if not (size and span):
        return None
    return {"roof_rings": rings, "ridge_m": round(2 * ridge_half_x, 2) if ridge_half_x is not None else None,
            "eaves_m": [round((size[1] - span[1]) / 2, 2), round((size[0] - span[0]) / 2, 2)],
            "outline_m": list(size[:2]), "top_m": top}


def real_hall(survey: dict) -> dict:
    """The real hall's five numbers, from the survey of our measured model that the adopted rebuild's record
    carries (rebuild_facts.harness_facts): its outline and top, the corner columns' span from its column lines,
    its roof rings and its ridge. Nothing here is typed in."""
    xs, ys = survey["columns"]["xs"], survey["columns"]["ys"]
    return {"source": "hall-carpenter survey of our measured model of the hall, as rebuild-record.json carries it (harness.survey)",
            **versus(survey["size"], survey["top"], [round(xs[-1] - xs[0], 2), round(ys[-1] - ys[0], 2)],
                     survey["roof_rings"], survey["ridge"]["half_x"])}


def measured(found: dict | None) -> dict | None:
    """A design's five numbers, from a brief check of the hall it ended with."""
    frame = (found or {}).get("frame") or {}
    return versus(found.get("size"), found.get("top"), found.get("span"), frame.get("roof_rings"),
                  (frame.get("ridge") or {}).get("half_x")) if found else None


def found_later(faults: dict, own: dict, later: dict) -> None:
    """What today's brief check found on the hall an adopted design ended with, beside what its own day's
    found. The check its day did not have is whatever today's file holds that the run's own did not."""
    faults["later"] = {"on": later["on"], "checked": later["checked"], "meets": later["meets"],
                       "short_of_the_brief": later["short_of_the_brief"],
                       "new_checks": sorted(set(later) - set(own) - {"on", "checked"})}
    if not later["meets"]:
        faults.update(found_later=True, through_the_roof=later["through_the_roof"], beyond_the_eaves=later["beyond_the_eaves"])


def record_of(n: int, folder: Path, protocol: dict, later: dict | None = None) -> tuple[dict, list[tuple[Path, str]]]:
    """`later` is today's brief check on the hall the run ended with (recheck): its verdict matters for an
    adopted design, its measurements for every design whose hall has a roof."""
    run, card = folder.name, read(folder / "scorecard.json")
    if not card:
        raise SystemExit(f"{run} has no scorecard: it is still running, or it stopped before writing one")
    events = [json.loads(line) for line in (folder / "events.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    steps = steps_of(events, run, said)
    worded(steps, events)
    kept = {int(p.stem.split("-")[1]) for p in (folder / "stages").glob("step-*.blend")}
    if kept:
        on_kept_stages(steps, kept)
    plan = media_of(steps, folder, n)
    photo = f"rebuild-design{n}-photo.jpg" if (folder / "photo.jpg").is_file() else None
    plan += [(folder / "photo.jpg", photo)] if photo else []
    check, fresh = read(folder / "brief-check.json"), {tool: current(steps, tool) for tool in ("bearing", "settle", "brief")}
    moved = read(folder / "settle.json").get("pieces", {}) if fresh["settle"] else {}
    gate = adoption.Adoption(look=adoption.BRIEF)
    record = {
        "run": n, "design": True, "source_run": run, "date": f"{run[:4]}-{run[4:6]}-{run[6:8]}",
        "source_note": "the design run's own event log, scorecard, check files, kept stage models and pictures",
        "opening": photo, "stages_kept": bool(kept),
        "measured": {"wall_seconds": card["wall_seconds"], "tokens": card["tokens"], "actions": card["turns"]["actions"],
                     "adopted": card["adopted"]},
        "steps": steps, "physics_protocol": protocol,
        "faults": {"fell": sorted(k for k, v in moved.items() if v.get("moved_m", 0) > 1.0),
                   "hanging": sorted(read(folder / "bearing.json").get("floating", {})) if fresh["bearing"] else [],
                   "through_the_roof": check.get("through_the_roof", []) if fresh["brief"] else [],
                   "beyond_the_eaves": check.get("beyond_the_eaves", []) if fresh["brief"] else [], "found_later": False},
        "harness": {"model": {"name": "Step 3.7 Flash", "id": card["agent"], "reasoning": "low"}, "limits": limits(),
                    "turns": card["turns"], "tokens": card["tokens"], "tool_seconds": card["tool_seconds"],
                    "wall_seconds": card["wall_seconds"], "seconds_by_tool": seconds_by_tool(events),
                    "still_owed": card.get("still_owed", []),
                    "checks": [f"{skill}/{tool}" for skill, tool in gate.checks] + ["shot-judge/judge"],
                    "brief": {**{k: check.get(k) for k in ("bays", "span", "column_rings", "brackets", "meets", "short_of_the_brief")},
                              "current": fresh["brief"]} if check else None},
    }
    if later and card["adopted"]:
        found_later(record["faults"], check, later)
    roofed = any(s["kind"] == "act" and s.get("tool") == "roof" and not failed(s) for s in steps)
    record["versus_real"] = measured(later or (check if fresh["brief"] else None)) if roofed else None
    return scrub(record, folder, run), plan


def convert(plan: list[tuple[Path, str]], page: Path) -> None:
    """The run's pictures as jpg and its videos as H.264 a browser plays, made by ffmpeg on the Spark,
    whose wrapper sees only /tmp; so the work is done there."""
    with tempfile.TemporaryDirectory(dir="/tmp", prefix="bc-design-media-") as work:
        for source, name in plan:
            if source.suffix.lower() in (".jpg", ".jpeg") and name.endswith(".jpg"):
                shutil.copyfile(source, page / name)
                continue
            taken, made = Path(work) / f"in{source.suffix}", Path(work) / name
            shutil.copyfile(source, taken)
            how = (["-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "26", "-movflags", "+faststart", "-an"]
                   if name.endswith(".mp4") else ["-q:v", "3"])
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(taken), *how, str(made)], check=True)
            shutil.move(made, page / name)


def recheck(folder: Path, scratch: Path) -> dict:
    """Today's brief check on the design's last stage model (its last hall if it kept none), run on copies
    in Blender's scratch folder: the run's own folder is only ever read. It measures the hall the run ended
    with, whichever check the run itself last ran on it."""
    stages = sorted((folder / "stages").glob("step-*.blend"), key=lambda p: int(p.stem.split("-")[1]))
    hall, out = (stages or [folder / "hall.blend"])[-1], scratch / folder.name / "recheck"
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    for source, name in ((hall, "hall.blend"), (folder / "brief.json", "brief.json"), (folder / "photo.jpg", "photo.jpg")):
        shutil.copyfile(source, out / name)
    exe = shutil.which("blender")
    if not exe:
        raise SystemExit("Blender is required to check an adopted design again")
    with (out / "recheck.log").open("w") as log:
        subprocess.run([exe, "-b", str(out / "hall.blend"), "--python-exit-code", "1", "--python", str(RECHECK), "--", str(out),
                        "--brief", str(out / "brief.json"), "--photo", str(out / "photo.jpg")], check=True, stdout=log,
                       stderr=subprocess.STDOUT)
    return {**read(out / "recheck.json"), "on": hall.stem, "checked": date.today().isoformat()}


def bake(n: int, folder: Path, scratch: Path, page: Path) -> None:
    """The design's 3D, made by Blender in its own scratch folder and copied to the page."""
    stem, out = f"rebuild-design{n}-hall", scratch / folder.name
    out.mkdir(parents=True, exist_ok=True)
    if any((folder / "stages").glob("step-*.blend")):
        rebuild_bake.kept_stages(folder / "stages", out, stem)
    else:
        rebuild_bake.blender(["single", "--blend", str(folder / "hall.blend"), "--out", str(out / stem)],
                             out / f"{stem}.log", folder / "hall.blend")
    for suffix in (".glb", ".json"):
        shutil.copyfile(out / f"{stem}{suffix}", page / f"{stem}{suffix}")


def listed(manifest: dict, numbers: dict[str, int]) -> dict:
    """The page's list of designs with every run in its number's place, and anything else the list holds, such
    as the success path the page draws above the cards, kept as it was."""
    return {**manifest, "designs": [{"n": n, "run": run} for run, n in sorted(numbers.items(), key=lambda kv: kv[1])]}


def numbered(runs: list[str], manifest: dict) -> dict[str, int]:
    """Each run's design number: the one it already has on the page, or the next free one."""
    known = {d["run"]: d["n"] for d in manifest.get("designs", [])}
    for run in runs:
        known.setdefault(run, max(known.values(), default=0) + 1)
    return known


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Make design runs playable on the rebuild replay page.")
    parser.add_argument("runs", nargs="+", help="design run ids, each a folder under --from")
    parser.add_argument("--from", dest="root", type=Path, default=RUNS)
    parser.add_argument("--bake", type=Path, default=BAKE, help="Blender's scratch folder")
    parser.add_argument("--no-bake", action="store_true", help="keep the page's 3D as it is")
    parser.add_argument("--no-media", action="store_true", help="keep the page's pictures as they are")
    parser.add_argument("--no-recheck", action="store_true", help="do not measure and check the hall each run ended with")
    a = parser.parse_args(argv)
    if bad := [run for run in a.runs if not RUN_ID.fullmatch(run)]:
        parser.error(f"not a run id: {', '.join(bad)}")
    manifest = read(MANIFEST)
    protocol, numbers = read(PAGE / "rebuild-record.json")["physics_protocol"], numbered(a.runs, manifest)
    for run in a.runs:
        n, folder = numbers[run], a.root / run
        adopted, later = read(folder / "scorecard.json").get("adopted"), None
        try:
            later = None if a.no_recheck else recheck(folder, a.bake.expanduser())
        except subprocess.CalledProcessError:
            if adopted:
                raise                                   # an adopted hall must be checked again
            print(f"design {n}: Blender could not measure its last hall; it gets no numbers beside the real hall")
        record, plan = record_of(n, folder, protocol, later)
        if not a.no_media:
            convert(plan, PAGE)
        if not a.no_bake:
            bake(n, folder, a.bake.expanduser(), PAGE)
        (PAGE / f"rebuild-design{n}-record.json").write_text(json.dumps(record, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        f = record["faults"]
        print(f"design {n} ({run}): {len(record['steps'])} steps, {len(plan)} pictures, adopted {record['measured']['adopted']}, "
              f"hanging {len(f['hanging'])}, fell {len(f['fell'])}, through the roof {len(f['through_the_roof'])}, "
              f"past the eaves {len(f['beyond_the_eaves'])}, found later {f['found_later']}, beside the real hall {record['versus_real']}")
    MANIFEST.write_text(json.dumps(listed(manifest, numbers), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    REAL.write_text(json.dumps(real_hall(read(PAGE / "rebuild-record.json")["harness"]["survey"]), indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
