"""What is wrong with the hall, said once per kind of piece instead of once per piece.

The checks answer piece by piece: two thousand names when a whole tier hangs. A carpenter wants
to know which part was told a wrong number, so the hanging, fallen and shifted pieces are grouped
by what they are ("Bracket | tier 1 arm x", where they stand taken out of the name), with how many,
the typical gap to what is under them, and the numbers that part was told when it was placed.
The bearing check looks 0.3 m down and then says "nothing"; here the piece boxes in anatomy.json
are searched to the ground, so a post over no support reads as that and not as a riddle. A check
older than the hall file is reported as out of date, never as a finding. A part standing on an older placing
of what carries it (hall.json's `stale`) is named first.
Columns that carry more than their timber can bear come from loads.json, named with their stress.
Reads bearing.json, settle.json, shake.json, likeness.json, loads.json, anatomy.json and hall.json from the
folder, whichever exist; writes faults.json. A hall designed from a brief (the folder holds brief.json) is
unlike its brief, not a temple: brief-check.json is read in likeness.json's place. Plain Python, no Blender.
Usage: python faults.py <out_dir>
"""
import json
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path

PLACE = re.compile(r"\s-?\d+\.\d+")
PART = {"column": "columns", "tie": "ties", "wall": "walls", "bracket": "brackets", "frame": "frames",
        "purlin": "purlins", "rafter": "rafters", "hip": "rafters", "roof": "roof", "ridge": "roof"}


def kind_of(name):
    head, _, tail = name.partition(" | ")
    head = PLACE.sub("", head).replace(" to", "").strip()
    return head if not tail or tail.isdigit() else f"{head} | {PLACE.sub('', tail).strip()}"


def part_of(kind):
    return PART.get(kind.split()[0].lower(), "?")


def load(folder, name):
    path = folder / name
    return json.loads(path.read_text()) if path.is_file() else None


def far_below(name, pieces):
    """The highest carrying piece whose footprint is under this one, however far down."""
    me = pieces.get(name)
    if me is None:
        return None
    (x0, y0, z0), (x1, y1, _) = me["box"]
    best = None
    for other, p in pieces.items():
        (a0, b0, _), (a1, b1, top) = p["box"]
        if other == name or p["role"] in ("wall", "covering") or top > z0 + 0.05:
            continue
        if a0 < x1 and x0 < a1 and b0 < y1 and y0 < b1 and (best is None or top > best[1]):
            best = (other, top)
    return {"on": best[0], "gap": z0 - best[1]} if best else None


def hanging(bearing, pieces):
    groups = defaultdict(lambda: {"pieces": 0, "gaps": [], "under": defaultdict(int)})
    for name, below in bearing["floating"].items():
        g = groups[kind_of(name)]
        g["pieces"] += 1
        below = below or far_below(name, pieces)
        if below:
            g["gaps"].append(below["gap"])
            g["under"][kind_of(below["on"])] += 1
    return [{"kind": k, "part": part_of(k), "pieces": g["pieces"],
             "gap_m": round(statistics.median(g["gaps"]), 3) if g["gaps"] else None,
             "nearest_below": max(g["under"], key=g["under"].get) if g["under"] else
             "nothing at all, down to the ground: it stands where the hall has no support"}
            for k, g in sorted(groups.items())]


def moved(settle):
    groups = defaultdict(list)
    for name, rec in settle["pieces"].items():
        if rec["moved_m"] > 0.10:
            groups[kind_of(name)].append(rec)
    return [{"kind": k, "part": part_of(k), "pieces": len(v), "fell": sum(1 for r in v if r["moved_m"] > 1.0),
             "dropped_m": round(statistics.median(r["drop_m"] for r in v), 3)} for k, v in sorted(groups.items())]


def stale_line(older):
    """Parts standing on an older placing of what carries them lead the fault line, since what they cause is
    found piece by piece behind them: design run 8 placed the purlins again but not the rafters
    on them, and spent its six repair laps on the pieces that then hung."""
    under = defaultdict(list)
    for part, below in older.items():
        under[below].append(part)
    return "stale: " + "; ".join(f"{', '.join(ps)} (on the old {below})" for below, ps in under.items())


def fresh(folder, name):
    """The check's answer, or None when it is missing or older than the hall it was run on."""
    hall, path = folder / "hall.blend", folder / name
    if not path.is_file() or (hall.is_file() and path.stat().st_mtime < hall.stat().st_mtime):
        return None
    return load(folder, name)


def main(folder):
    folder = Path(folder)
    design = (folder / "brief.json").is_file()
    look, unlike, short = (("brief-check.json", "unlike_the_brief", "short_of_the_brief") if design else
                           ("likeness.json", "unlike_the_temple", "short_of_the_temple"))
    bearing, settle, likeness, loads, shake = (fresh(folder, n) for n in ("bearing.json", "settle.json", look,
                                                                           "loads.json", "shake.json"))
    hall, anatomy = load(folder, "hall.json"), load(folder, "anatomy.json") or {}
    stale, older = "not run since the hall last changed", (hall or {}).get("stale") or {}
    out = {"stale_parts": older,
           "hanging": hanging(bearing, anatomy.get("pieces", {})) if bearing else f"bearing: {stale}",
           "moved_under_gravity": moved(settle) if settle else f"settle: {stale}",
           unlike: likeness[short] if likeness else f"{'brief' if design else 'likeness'}: {stale}",
           "too_weak": loads["summary"].get("overloaded", []) if loads else f"weights: {stale}",
           "came_down_in_the_shake": shake["summary"]["shake"].get("came_down_names", []) if shake else f"shake: {stale}"}
    parts = {f["part"] for key in ("hanging", "moved_under_gravity") if isinstance(out[key], list) for f in out[key]}
    if isinstance(out["too_weak"], list) and out["too_weak"]:
        parts.add("columns")
    if hall:
        out["what_those_parts_were_told"] = {p: hall["parts"][p]["told"] for p in sorted(parts) if p in hall["parts"]}
    (folder / "faults.json").write_text(json.dumps(out, indent=1))
    lines = [stale_line(older)] if older else []
    if isinstance(out["hanging"], list):
        n = sum(f["pieces"] for f in out["hanging"])
        lines.append(f"hanging {n}" + "".join(f"; {f['pieces']} x {f['kind']} {f['gap_m']} m above {f['nearest_below']}"
                                              for f in out["hanging"][:3]))
    if isinstance(out["moved_under_gravity"], list):
        n = sum(f["pieces"] for f in out["moved_under_gravity"])
        lines.append(f"moved {n}" + "".join(f"; {f['pieces']} x {f['kind']} dropped {f['dropped_m']} m"
                                            for f in out["moved_under_gravity"][:3]))
    if isinstance(out[unlike], list):
        lines.append("unlike: " + ("; ".join(out[unlike]) or "nothing"))
    if isinstance(out["too_weak"], list) and out["too_weak"]:
        lines.append(f"too weak {len(out['too_weak'])}: " + "; ".join(
            f"{c['name']} at {c.get('design_MPa', c['stress_MPa']):.1f} MPa" for c in out["too_weak"][:3]))
    down = out["came_down_in_the_shake"]
    if isinstance(down, list) and down:
        lines.append(f"came down in the shake {len(down)}: " + "; ".join(down[:3]))
    lines += [out[key] for key in ("hanging", "moved_under_gravity", unlike, "too_weak", "came_down_in_the_shake")
              if isinstance(out[key], str)]
    print(("FAULTS " + " | ".join(lines))[:470], "| full list in faults.json")


if __name__ == "__main__":
    main(sys.argv[1])
