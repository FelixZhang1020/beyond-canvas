"""The from-nothing rebuild: one model, the carpentry skills, the adoption gate, and a scorecard.
With --brief it is a design instead: no temple to measure, only a written brief and its photograph,
and the hall is judged against the brief (operator's option C).

The model is given an empty file and the standing temple to measure, and is asked for a hall
that matches it and passes the gravity test. The harness decides whether what comes back is
adopted. The scorecard is read from the run folder's own files afterwards, never from what the
model said about them, and it says where the run spent its turns, because the point of running
this is to find what the harness should do better.
Usage: uv run python -m evalkit.fromzero --profile stepfun --slot vlm.studio --temple <temple.blend>
           [--cap 80] [--laps 6] [--bounces 3] [--runs .studio/showpiece/rebuilds] [--no-pictures] [--dry-run]
       uv run python -m evalkit.fromzero --brief evalkit/briefs/foguang-east-hall [--runs .studio/showpiece/designs]
"""
from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from pathlib import Path

from studio.showpiece import adoption, catalog
from studio.showpiece.driver import Driver, Run

REQUEST = ("Rebuild the temple from nothing. Measure the standing temple first, then place a hall that matches it, "
           "and hand it over only when it passes the gravity test and looks like the temple.")
PROTOCOL = Path(catalog.__file__).with_name("prompts") / "carpenter.txt"
TEMPLE = catalog.ROOT / "output/foguang-east-hall/foguang-east-hall-v25.blend"
ALWAYS = ("hall-carpenter",)
DESIGNER = PROTOCOL.with_name("designer.txt")
# Step 3.7 Flash under the stepfun profile, for a design's builder and its eyes alike, as in the four rebuilds.
# vlm.studio, which the rebuilds used, went to Qwen on the Spark with the class chat; a design
# must not load the class's own model, and should stay comparable with the rebuilds.
STEP = "vlm.sketch"
# A design has no numbers to copy. Design run 1 spent the rebuild's whole budget, 6,000 tokens and
# then 12,000, thinking out the column grid and returned nothing; the operator's StepFun plan has no token cap.
THINK, WAIT_S = (16000, 32000), 600
NO_TEMPLE = ("REFUSED there is no standing temple in a design: nothing to measure or compare with. Take the numbers "
             "from the brief and its photograph, and check the hall against the brief with hall-carpenter brief.")
# Operator's decision (docs/measured/engineers-review-first-run.md): eight of the
# engineer's eleven notes misread the sheet, and each named a part and a number the builder could change.
WITHHELD = {("hall-carpenter", "review"): "REFUSED the engineer's review is not part of a rebuild: the operator asks "
                                          "for it after the hall is handed over. Carry on with the checks."}


def carpenter(client, temple: Path, runs_root: Path, cap: int = 80, gate: adoption.Adoption | None = None,
              agent_name: str = "Step 3.7 Flash", pictures: bool = True) -> Driver:
    """The same driver the exhibit runs, with the carpentry skills, its protocol and the gate. A builder
    that reads text only is told when a picture was made rather than sent it."""
    return Driver(client, temple, runs_root, skills=catalog.load_skills(names=catalog.CARPENTRY), cap=cap,
                  agent_name=agent_name, quick=catalog.QUICK, protocol=PROTOCOL, always=ALWAYS,
                  gate=gate or adoption.Adoption(), withheld=WITHHELD, pictures=pictures)


def designer(client, runs_root: Path, cap: int = 80, gate: adoption.Adoption | None = None,
             agent_name: str = "Step 3.7 Flash", pictures: bool = True) -> Driver:
    """The rebuild's driver with no temple: the designer's protocol, the brief check in likeness's place,
    the two tools that read a temple refused in a sentence, before anything runs, and the eyes on STEP
    unless the builder names another slot."""
    withheld = {**WITHHELD, ("hall-carpenter", "survey"): NO_TEMPLE, ("hall-carpenter", "likeness"): NO_TEMPLE}
    return Driver(client, None, runs_root, skills=catalog.load_skills(names=catalog.CARPENTRY), cap=cap,
                  agent_name=agent_name, quick={**catalog.QUICK, "slot": STEP}, protocol=DESIGNER, always=ALWAYS,
                  gate=gate or adoption.Adoption(look=adoption.BRIEF), withheld=withheld, pictures=pictures, keep=True,
                  think=THINK)


def brief_of(folder: Path) -> tuple[str, dict[str, Path]]:
    """A brief's request in its own words, and the files every run of it starts with."""
    folder = Path(folder)
    return ((folder / "brief.md").read_text(encoding="utf-8").strip(),
            {"brief.json": folder / "brief.json", "photo.jpg": folder / "photo.jpg"})


def temple_loads(temple: Path, cache: Path) -> Path:
    """The standing temple weighed by the three tools that weigh the hall (inventory, bearing, weights),
    once per temple file: its carrying check takes about 80 s on the Foguang hall. The engineer's review
    reads it beside the hall's; the gate never does."""
    import hashlib

    from studio.showpiece.blender_bin import run_tool

    temple, cache = Path(temple).resolve(), Path(cache).resolve()     # each tool runs inside the cache folder
    folder = cache / hashlib.sha256(temple.read_bytes()).hexdigest()[:12]
    made = folder / "loads.json"
    if made.is_file():
        return made
    folder.mkdir(parents=True, exist_ok=True)
    steps = (("model-anatomy", "inventory", {}, temple), ("model-anatomy", "bearing", {}, temple),
             ("load-path", "weights", {"anatomy": "anatomy.json", "bearing": "bearing.json"}, None))
    for skill, tool, args, model in steps:
        spec = catalog.TOOLS[(skill, tool)]
        code, tail = run_tool(catalog.argv_for(spec, {"out_dir": ".", **args}, model, folder), spec.timeout_s, cwd=folder)
        if code != 0:
            raise RuntimeError(f"weighing the temple failed at {skill}/{tool}: {tail[-300:]}")
    return made


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def scorecard(run: Run, gate: adoption.Adoption, seconds: float) -> dict:
    """What the run folder says, whatever the model said."""
    events, folder = run.events, run.dir
    acts = [e for e in events if e["kind"] == "act"]
    settle, likeness, brief = _json(folder / "settle.json"), _json(folder / "likeness.json"), _json(folder / "brief-check.json")
    groups = Counter(p["group"] for p in settle.get("pieces", {}).values() if p.get("group"))
    pieces = len(settle.get("pieces", {}))
    last = events[-1] if events else {}
    owed = gate.outstanding(folder, events)
    return {
        "run": run.id, "agent": run.agent_name, "adopted": last.get("kind") == "final" and not owed,
        "ended": {"kind": last.get("kind"), "text": last.get("text", "")[:600]}, "still_owed": owed,
        "hanging": len(_json(folder / "bearing.json").get("floating", {})) if (folder / "bearing.json").is_file() else None,
        "gravity": settle.get("summary"), "pieces_let_go": pieces,
        "bodies": {"joined_groups": len(groups), "loose_pieces": pieces - sum(groups.values()),
                   "largest_group_share": round(max(groups.values(), default=0) / pieces, 2) if pieces else None},
        "likeness": {k: likeness.get(k) for k in ("shared_outline", "columns", "size", "top", "frame", "alike")},
        "brief": {k: brief.get(k) for k in ("bays", "span", "column_rings", "brackets", "size", "top", "meets",
                                            "short_of_the_brief")} if gate.look == adoption.BRIEF else None,
        "too_weak": _json(folder / "loads.json").get("summary", {}).get("overloaded"),
        "shaken": _json(folder / "shake.json").get("summary", {}).get("shake"),
        "engineer": {k: v for k, v in _json(folder / "review.json").items() if k != "sheet"} or None,
        "turns": {"actions": len(acts), "placing": sum(1 for e in acts if adoption.placing(e)),
                  "tools_that_failed": sum(1 for e in acts if not adoption.ran(e) and e.get("tool") != "read"),
                  "reads": sum(1 for e in acts if e.get("tool") == "read"), "repair_laps": gate.laps_used(events),
                  "hand_overs_refused": sum(1 for e in events if e["kind"] == "bounce"),
                  "by_tool": dict(Counter(f"{e['skill']}/{e['tool']}" for e in acts))},
        "tokens": sum(e.get("tokens", 0) for e in events), "tool_seconds": round(sum(e.get("seconds", 0) for e in acts), 1),
        "wall_seconds": round(seconds, 1),
    }


def render(card: dict) -> str:
    like, turns, grav = card["likeness"], card["turns"], card["gravity"] or {}
    shared = like.get("shared_outline") or {}
    lines = [
        f"{'ADOPTED' if card['adopted'] else 'NOT ADOPTED'}  ({card['agent']}, run {card['run']})",
        f"  ended: {card['ended']['kind']}: {card['ended']['text'][:300]}",
        f"  gravity: fell {grav.get('fell')} shifted {grav.get('shifted')} of {card['pieces_let_go']} let go; hanging {card['hanging']}",
        f"  bodies: {card['bodies']['joined_groups']} joined groups, {card['bodies']['loose_pieces']} loose pieces, "
        f"largest holds {card['bodies']['largest_group_share']} of the hall",
        ("  likeness: " + " ".join(f"{v} {s}" for v, s in shared.items()) + f" | columns {like.get('columns')}")
        if not card.get("brief") else (f"  brief: {card['brief']['bays']} bays, corner columns {card['brief']['span']} m apart, "
                                       f"{card['brief']['column_rings']} rings, meets {card['brief']['meets']}"),
        f"  turns: {turns['actions']} actions ({turns['placing']} placing, {turns['reads']} reads, {turns['tools_that_failed']} "
        f"failed), {turns['repair_laps']} repair laps, {turns['hand_overs_refused']} hand-overs refused",
        f"  cost: {card['tokens']:,} tokens, {card['tool_seconds']} s in tools, {card['wall_seconds']} s in all",
    ]
    return "\n".join(lines + [f"  still owed: {r}" for r in card["still_owed"]])


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run the from-nothing rebuild and score it from the run folder.")
    parser.add_argument("--profile", default="stepfun")  # api until its archive
    parser.add_argument("--slot", help=f"vlm.studio for a rebuild, {STEP} for a design")
    parser.add_argument("--temple", type=Path, default=TEMPLE)
    parser.add_argument("--brief", type=Path, help="a folder with brief.md, brief.json and photo.jpg: design, not rebuild")
    parser.add_argument("--runs", type=Path)
    parser.add_argument("--cap", type=int, default=80)
    parser.add_argument("--laps", type=int, default=6)
    parser.add_argument("--bounces", type=int, default=3)
    parser.add_argument("--no-pictures", action="store_true", help="the builder reads text only (NVIDIA's Nemotron 3 Nano)")
    parser.add_argument("--dry-run", action="store_true", help="name the model and the limits, call nothing")
    args = parser.parse_args(argv)
    from studio.core.env import load_dotenv
    from studio.providers import build_client
    from studio.core.slots import load_profile, resolve

    load_dotenv()
    args.slot = args.slot or (STEP if args.brief else "vlm.studio")
    config = resolve(args.slot, load_profile(args.profile))
    config.options.setdefault("reasoning_effort", "low")
    if args.brief:
        config.options["reasoning_effort"] = "low"      # the rebuilds' builder thought at low; the slot's own is medium
        config.options["timeout_s"] = WAIT_S             # 32,000 tokens of thinking outlast the default 180 s
    what = f"brief {args.brief.name}" if args.brief else f"temple {args.temple.name}"
    print(f"slot {args.slot} in profile {args.profile} is {config.model} via {config.provider}; {what}; "
          f"cap {args.cap}, {args.laps} repair laps, {args.bounces} refusals"
          + ("; the builder is told of pictures, not shown them" if args.no_pictures else ""))
    if args.dry_run:
        return
    runs = args.runs or catalog.ROOT / (".studio/showpiece/designs" if args.brief else ".studio/showpiece/rebuilds")
    started = time.monotonic()
    if args.brief:
        gate = adoption.Adoption(bounces=args.bounces, laps=args.laps, look=adoption.BRIEF)
        driver = designer(build_client(config), runs, cap=args.cap, gate=gate, agent_name=config.model,
                          pictures=not args.no_pictures)
        request, seed = brief_of(args.brief)
        run = driver.run_sync(request, from_nothing=True, seed=seed, show="photo.jpg")
    else:
        gate = adoption.Adoption(bounces=args.bounces, laps=args.laps)
        driver = carpenter(build_client(config), args.temple, runs, cap=args.cap, gate=gate, agent_name=config.model,
                           pictures=not args.no_pictures)
        seed = {"temple-loads.json": temple_loads(args.temple, runs / ".temple")}
        run = driver.run_sync(REQUEST, from_nothing=True, seed=seed)
    card = scorecard(run, gate, time.monotonic() - started)
    (run.dir / "scorecard.json").write_text(json.dumps(card, indent=1), encoding="utf-8")
    print(render(card))
    print(f"run folder: {run.dir}")


if __name__ == "__main__":
    main()
