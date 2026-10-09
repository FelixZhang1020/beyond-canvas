"""The harness facts the replay page shows beside the adopted run: the limits and checks
as the harness code sets them, and what the run's own files say each check found.

Everything here is read, never typed in: from the private run folder (scorecard, likeness, loads,
settle, shake, survey and the event log) and from the code that ran it (the adoption gate, the
driver, the rebuild runner). The page may then say "71 of 80 actions" or "8.08 of 10 MPa" only
because these files hold those numbers. The limits were the same on the run's day: its own record
shows the 0.2 to 5 m rafter range refused at step 26 and six repair laps used.
"""
from __future__ import annotations

import inspect
import json
import re
from pathlib import Path


PLACE = Path(__file__).resolve().parents[2] / "skills/hall-carpenter/scripts/place.py"


def guards() -> dict:
    """The placing tool's own argument limits, read from its source: the ranges it refuses outside."""
    text = PLACE.read_text(encoding="utf-8")
    section = re.search(r"not ([\d.]+) <= value <= ([\d.]+)", text)
    spacing = re.search(r"not ([\d.]+) <= spacing <= ([\d.]+)", text)
    if not (section and spacing):
        raise SystemExit(f"{PLACE} no longer states its section and spacing limits the way this reads them")
    return {"section_m": [float(v) for v in section.groups()], "spacing_m": [float(v) for v in spacing.groups()]}


def public(command: str, run: str) -> str:
    """A logged command without the private run folder's name: the page shows the call, not the disk.
    A rebuild's folder is under rebuilds/, a design's under designs/."""
    for kind in ("rebuilds", "designs"):
        command = command.replace(f".studio/showpiece/{kind}/{run}", "run")
    return command.replace(".venv/bin/python3", "python")


def call_fields(event: dict, run: str) -> dict:
    """What the page's call card needs from one logged event: the model's tokens for its turn, or the
    skill, the tool's seconds and the command the harness ran for an action."""
    if event["kind"] == "act":
        return {"skill": event.get("skill"), "seconds": round(float(event.get("seconds") or 0), 1),
                "command": public(event.get("command", ""), run)[:600]}
    return {"tokens": int(event.get("tokens") or 0)}


def judged(event: dict) -> str:
    """What the picture judge said: its verdict and the one change it asked for, or that it gave no
    answer at all; its own output is a JSON object, not the one-line result the other tools print."""
    verdict = event.get("verdict") or {}
    if isinstance(verdict, dict) and verdict.get("verdict"):
        return f"JUDGE {verdict['verdict']} | {verdict.get('change') or verdict.get('seen') or ''}"[:360]
    found = re.search(r"returned no text[^\n]*", str(event.get("text", "")))
    return found.group(0)[:360] if found else ""


PLACING = {"platform", "columns", "ties", "walls", "brackets", "frames", "purlins", "rafters", "roof"}
CHECKING = {"inventory", "bearing", "weights", "settle", "shake", "likeness", "brief", "judge", "faults"}


def failed(step: dict) -> bool:
    """A call the tool itself turned down: its own guard refused it, or its arguments could not be read,
    or it stopped with an error before it finished (a design's evidence then starts "exit 1:")."""
    text = step.get("evidence") or ""
    return text.startswith(("REFUSED", "exit ")) or ": error: " in text


def mark_repairs(steps: list[dict]) -> list[dict]:
    """A placing call after any check has run is a repair, the harness's own sense of a lap."""
    checked = False
    for step in steps:
        if step["kind"] != "act":
            continue
        if step.get("tool") in PLACING and not failed(step):
            step["repair"] = checked
        elif step.get("tool") in CHECKING:
            checked = True
    return steps


def _json(run_dir: Path, name: str) -> dict:
    path = run_dir / name
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def _last(events: list[dict], tool: str, pattern: str) -> str | None:
    for event in reversed(events):
        found = event.get("tool") == tool and re.search(pattern, str(event.get("text", "")))
        if found:
            return found.group(1)
    return None


def _asked(events: list[dict], tool: str, flag: str) -> float | None:
    """A number the last call of a tool was given on its command line; the day's settle.py wrote no
    length into its summary, so how long it let go is read from what it was asked for."""
    for event in reversed(events):
        found = event.get("tool") == tool and re.search(rf"--{flag} (\S+)", str(event.get("command", "")))
        if found:
            return float(found.group(1))
    return None


def found(run_dir: Path, events: list[dict]) -> dict:
    """What each of the seven checks found on the hall that was handed over."""
    card, like = _json(run_dir, "scorecard.json"), _json(run_dir, "likeness.json")
    loads = _json(run_dir, "loads.json").get("summary", {})
    settle = _json(run_dir, "settle.json").get("summary", {})
    shaken = _json(run_dir, "shake.json").get("summary", {}).get("shake", {})
    heaviest = max(loads["columns"], key=lambda c: c.get("design_MPa") or 0)
    judged = next(e for e in reversed(events) if e.get("tool") == "judge")
    pieces = _last(events, "inventory", r"ANATOMY (\d+) pieces")
    if pieces is None:
        raise SystemExit("the run's log holds no inventory count")
    return {
        "inventory": {"pieces": int(pieces)},
        "bearing": {"hanging": card["hanging"]},
        "weights": {"total_MN": round(float(loads["total_N"]) / 1e6, 2), "allowed_MPa": loads["allowed_MPa"],
                    "not_carried_N": loads["not_carried_N"], "snow": loads["snow"],
                    "heaviest": {k: heaviest[k] for k in ("name", "carries_kN", "design_MPa", "slenderness")}},
        "settle": {"fell": settle["fell"], "shifted": settle["shifted"], "pieces": card["pieces_let_go"],
                   "frames": settle["frames"], "seconds": _asked(events, "settle", "seconds")},
        "shake": {k: shaken[k] for k in ("peak_g", "hz", "pull_g", "came_down", "drift_m", "source")},
        "likeness": {"outline": like["shared_outline"], "enough": like["enough"], "columns": like["columns"],
                     "through_the_roof": like["through_the_roof"], "size": like["size"], "top": like["top"],
                     "frame": like["frame"]["hall"]},
        "eyes": {"verdict": (judged.get("verdict") or {}).get("verdict"), "meant": (judged.get("args") or {}).get("meant")},
    }


def seconds_by_tool(events: list[dict]) -> dict:
    seconds: dict[str, float] = {}
    for event in events:
        if event["kind"] == "act":
            key = f"{event.get('skill')}/{event.get('tool')}"
            seconds[key] = seconds.get(key, 0.0) + float(event.get("seconds") or 0)
    return {tool: round(s, 1) for tool, s in sorted(seconds.items(), key=lambda kv: -kv[1])}


def limits() -> dict:
    """The rebuild's limits as the harness code sets them: the runner's action cap and the gate's laps,
    hand-overs and let-go time. The three earlier runs ran under the same ones: their measured note's
    command reads "cap 80, 6 repair laps, 3 refusals"."""
    from evalkit import fromzero
    from studio.showpiece import adoption
    gate = adoption.Adoption()
    return {"actions": inspect.signature(fromzero.carpenter).parameters["cap"].default, "laps": gate.laps,
            "hand_overs": gate.bounces, "let_go_seconds": gate.min_seconds}


def harness_facts(run_dir: Path, events: list[dict]) -> dict:
    from evalkit import fromzero
    from studio.showpiece import adoption, driver
    card, survey = _json(run_dir, "scorecard.json"), _json(run_dir, "survey.json")
    return {
        "model": {"name": "Step 3.7 Flash", "id": card["agent"], "provider": "StepFun", "reasoning": "low",
                  "max_tokens": driver.MAX_TOKENS, "retry_tokens": driver.RETRY_TOKENS},
        "limits": limits(),
        "skills": list(fromzero.catalog.CARPENTRY),
        "guards": guards(),
        "checks": [f"{skill}/{tool}" for skill, tool in adoption.CHECKS] + ["shot-judge/judge"],
        "turns": card["turns"], "tokens": card["tokens"],
        "tool_seconds": card["tool_seconds"], "wall_seconds": card["wall_seconds"],
        "seconds_by_tool": seconds_by_tool(events),
        "found": found(run_dir, events),
        "survey": {k: survey[k] for k in ("size", "top", "platform", "columns", "tie_beams", "ridge", "eave_edge", "rafters", "walls")}
                  | {"roof_rings": len(survey["roof_rings"])},
    }
