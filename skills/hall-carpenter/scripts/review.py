"""An engineer's review of the hall from its numbers, by a model from another company.

The builder and the eyes share one model, so they can share a mistake. This asks a different one,
and shows it no picture: one sheet of numbers (the temple as measured, the hall as told and as
measured, what the columns carry, the let-go test and the shake) and the question an engineer would
ask of it. What comes back is advice. It is written to review.json and told to the builder in one
line, and the hand-over gate never reads it: a model's opinion can neither pass a hall nor fail
one. An engineer who cannot be reached, or whose answer cannot be read, is said so and stops nothing.
Usage: uv run python skills/hall-carpenter/scripts/review.py <out_dir> [--profile spark] [--slot llm.engineer]
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

PROMPT = Path(__file__).resolve().parents[1] / "assets/prompts/review.txt"
SYSTEM = "You review structures from numbers for an agent. Return only the requested JSON."
MAX_TOKENS = 6000            # a reasoning model thinks before it writes; the sheet itself is about 1,500
MOST_NOTES, LONGEST = 5, 240
THINKING = re.compile(r"<think>.*?</think>", re.DOTALL)
JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)
TEMPLE = ("size", "top", "platform", "columns", "tie_beams", "roof_rings", "ridge", "eave_edge", "rafters", "walls",
          "tie_spans", "bracket_sets")


def _json(folder: Path, name: str) -> dict | None:
    path = folder / name
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def _widest(marks: list[float]) -> float:
    return round(max((b - a for a, b in zip(marks, marks[1:])), default=0.0), 2)


def _loads(loads: dict | None):
    if not loads:
        return "not run"
    s = loads["summary"]
    columns = sorted(s.get("columns", []), key=lambda c: c.get("design_MPa", c.get("stress_MPa", 0)))
    keep = ("carries_kN", "snow_kN", "design_kN", "diameter_m", "slenderness", "design_MPa")
    return {"total_kN": round(s["total_N"] / 1e3), "reaches_the_ground_kN": round(s["ground_N"] / 1e3),
            "carried_by_nothing_kN": round(s.get("not_carried_N", 0) / 1e3), "snow_kN": s.get("snow", {}).get("total_kN"),
            "allowed_MPa": s.get("allowed_MPa"), "columns": len(columns), "posts_on_the_frame": len(s.get("posts", [])),
            "columns_over_the_limit": len(s.get("overloaded", [])),
            "lightest_column": {k: columns[0][k] for k in keep if k in columns[0]} if columns else None,
            "heaviest_column": {k: columns[-1][k] for k in keep if k in columns[-1]} if columns else None}


# The first live review misread the sheet twice: a column's length against a height above ground, and
# the temple's own inner rings (inside the outer columns, as any roof's are) as a fault of the hall's.
HOW_TO_READ = [
    "Every height is in metres above the ground; every size is in metres.",
    "Everything under temple, and the temple half of every pair, is the standing temple as measured, never the hall.",
    "A column's length is top minus foot; columns_compared gives both buildings' columns the same way.",
    "Roof rings are counted from the eave; half_x and half_y are half the ring's length and width; "
    "out_from_outer_columns is how far a ring stands outside the outer column line, negative when it stands inside, "
    "as every inner ring of a roof rising to a ridge does.",
    "loads gives the temple and the hall weighed by the same tools; posts_on_the_frame are uprights standing on "
    "timber, such as king posts, judged apart from the columns.",
]


def _columns(record: dict | None) -> dict | str:
    if not record or "top" not in record or "foot" not in record:
        return "not measured"
    return {"foot": record["foot"], "top": record["top"], "length": round(record["top"] - record["foot"], 2),
            "diameter": record.get("diameter")}


def sheet(folder: Path) -> dict:
    """One screen of numbers. Piece lists and places stay out: an engineer reads sizes, spans and loads."""
    survey, hall, likeness = (_json(folder, n) for n in ("survey.json", "hall.json", "likeness.json"))
    bearing, settle, shake = (_json(folder, n) for n in ("bearing.json", "settle.json", "shake.json"))
    temple_loads = _json(folder, "temple-loads.json")      # the temple weighed by the same tools, when it was
    temple = {k: survey[k] for k in TEMPLE if k in survey} if survey else "not measured"
    if survey and "columns" in survey:
        temple["widest_bay_m"] = {"along_the_front": _widest(survey["columns"].get("xs", [])),
                                  "front_to_back": _widest(survey["columns"].get("ys", []))}
    measured = {k: likeness[k] for k in ("size", "top", "columns", "shared_outline", "through_the_roof") if k in likeness} \
        if likeness else "not run"
    if likeness:
        measured["frame"] = likeness.get("frame", {}).get("hall", "not measured")
    return {"how_to_read": HOW_TO_READ,
            "temple": temple,
            "hall_as_told": {part: made.get("told", {}) for part, made in hall["parts"].items()} if hall else "nothing placed",
            "hall_as_measured": measured,
            "columns_compared": {"temple": _columns((survey or {}).get("columns")),
                                 "hall": _columns((hall or {}).get("parts", {}).get("columns"))},
            "carrying": {"pieces": len(bearing.get("rests_on", {})), "hanging_in_mid_air": len(bearing.get("floating", {})),
                         "layers_from_ground_to_top": len(bearing.get("stages", []))} if bearing else "not run",
            "loads": {"temple": _loads(temple_loads) if temple_loads else "not measured",
                      "hall": _loads(_json(folder, "loads.json"))},
            "let_go": {k: settle["summary"].get(k) for k in ("fell", "shifted")} if settle else "not run",
            "shaken": {k: v for k, v in shake["summary"].get("shake", {}).items()
                       if k in ("peak_g", "pull_g", "came_down", "came_down_names", "moved_in_the_shaking", "drift_m")}
            if shake else "not run"}


def read_notes(text: str, parts: list[str]) -> dict | None:
    """The engineer's notes from its answer, thinking and surrounding prose set aside; None when there is
    no answer to read. A note is kept to a part the builder can change, and kept short."""
    match = JSON_BLOCK.search(THINKING.sub("", text))
    try:
        data = json.loads(match.group(0)) if match else None
    except json.JSONDecodeError:
        data = None
    if not isinstance(data, dict) or not isinstance(data.get("notes"), list):
        return None
    notes = [{"part": str(n.get("part", "")) if str(n.get("part", "")) in parts else "other",
              **{k: str(n.get(k, ""))[:LONGEST] for k in ("number", "concern", "suggest")}}
             for n in data["notes"] if isinstance(n, dict)][:MOST_NOTES]
    return {"notes": notes, "overall": "concerns" if notes else "sound"}


def review(folder: Path, client) -> dict:
    from studio.core.errors import EmptyCompletion, ModelError

    numbers = sheet(folder)
    parts = list(numbers["hall_as_told"]) if isinstance(numbers["hall_as_told"], dict) else []
    prompt = PROMPT.read_text(encoding="utf-8").replace("{parts}", ", ".join(parts)).replace("{sheet}", json.dumps(numbers, indent=1))
    found = {"available": True, "read": False, "notes": [], "overall": None, "model": None, "tokens": 0, "seconds": 0.0}
    try:
        try:
            reply = client.chat(prompt, [], system=SYSTEM, max_tokens=MAX_TOKENS)
        except EmptyCompletion:      # the whole budget went on thinking: once more, with twice the room
            reply = client.chat(prompt, [], system=SYSTEM, max_tokens=2 * MAX_TOKENS)
    except ModelError as error:
        found.update(available=False, why=str(error)[:LONGEST])
    else:
        found.update(model=reply.model, tokens=reply.input_tokens + reply.output_tokens, seconds=round(reply.latency_s, 1))
        notes = read_notes(reply.text, parts)
        if notes:
            found.update(read=True, **notes)
    (folder / "review.json").write_text(json.dumps({**found, "sheet": numbers}, indent=1), encoding="utf-8")
    return found


def told(found: dict) -> str:
    """The one line the builder reads."""
    if not found["available"]:
        return f"REVIEW not available ({found.get('why', '')}); it is advice, not a check: carry on without it"
    if not found["read"]:
        return "REVIEW the engineer's answer could not be read; it is advice, not a check: carry on without it"
    n = len(found["notes"])
    notes = " | ".join(f"{x['part']}: {x['number']}: {x['concern']} Try: {x['suggest']}" for x in found["notes"])
    return f"REVIEW {n} note{'' if n == 1 else 's'} (advice, not a check; whole list in review.json)" + (": " + notes if notes else "")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="An engineer's review of the hall from its numbers.")
    parser.add_argument("out_dir", type=Path)
    parser.add_argument("--profile", default="spark")
    parser.add_argument("--slot", default="llm.engineer")
    args = parser.parse_args(argv)
    from studio.core.env import load_dotenv
    from studio.providers import build_client
    from studio.core.slots import load_profile, resolve

    load_dotenv()
    print(told(review(args.out_dir, build_client(resolve(args.slot, load_profile(args.profile))))))


if __name__ == "__main__":
    main()
