"""Turn the bearing stages into construction scenes: merge the small stages forward so no scene
is under two per cent of the pieces, keep the covering as its own last scene, cap the count, and
name each scene by what it mostly is. Plain Python, no Blender.
Usage: python3 stages.py bearing.json anatomy.json out_dir [--max-scenes 24]
"""
import argparse
import json
import os
from collections import Counter

LABELS = {("timber", "column"): "columns", ("timber", "beam"): "beams", ("timber", "block"): "bracket blocks",
          ("timber", "sheet"): "ceiling", ("rafter", "beam"): "rafters", ("rafter", "sheet"): "rafters",
          ("covering", "block"): "roof covering", ("covering", "sheet"): "roof covering",
          ("covering", "beam"): "roof covering", ("wall", "sheet"): "walls"}


def label_of(pieces, anatomy):
    votes = Counter(LABELS.get((anatomy[n]["role"], anatomy[n]["kind"]), anatomy[n]["role"]) for n in pieces)
    top = votes.most_common(1)[0][0]
    if top == "beams" and all("tie" in n.lower() or "lintel" in n.lower() for n in pieces):
        return "tie beams"
    return top


def merge(stages, total, max_scenes):
    """Merge forward until every scene but the last holds at least 2 % of the pieces, then merge
    the smallest neighbours until at most max_scenes remain. The last stage stays alone."""
    body, last = [list(s) for s in stages[:-1]], list(stages[-1])
    floor = max(1, int(0.02 * total))
    merged = []
    for s in body:
        if merged and len(merged[-1]) < floor:
            merged[-1].extend(s)
        else:
            merged.append(s)
    while len(merged) + 1 > max_scenes and len(merged) > 1:
        i = min(range(len(merged) - 1), key=lambda k: len(merged[k]) + len(merged[k + 1]))
        merged[i:i + 2] = [merged[i] + merged[i + 1]]
    return merged + [last]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("bearing")
    parser.add_argument("anatomy")
    parser.add_argument("out_dir")
    parser.add_argument("--max-scenes", type=int, default=24)
    args = parser.parse_args()
    stages = json.load(open(args.bearing))["stages"]
    anatomy = json.load(open(args.anatomy))["pieces"]
    total = sum(len(s) for s in stages)
    scenes = merge(stages, total, args.max_scenes)
    out = [{"index": i + 1, "pieces": sorted(s), "label": label_of(s, anatomy)} for i, s in enumerate(scenes)]
    os.makedirs(args.out_dir, exist_ok=True)
    with open(os.path.join(args.out_dir, "scenes.json"), "w") as f:
        json.dump({"scenes": out, "stages": len(stages), "pieces": total}, f, indent=1)
    print("SCENES", len(out), "from", len(stages), "stages")


if __name__ == "__main__":
    main()
