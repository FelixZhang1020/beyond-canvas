"""Where the weight goes. Every piece weighs its volume times its density; a covering piece
hands its weight to the nearest timber or rafter below it; every other piece passes what it
carries to its seats in proportion to contact area, or equally to its near misses, and the
ground receives it all. Pieces are taken highest first, so each has received everything before
it passes on. Snow on the roof goes down the same way. Each column is then judged the way a
timber standard judges it: 1.3 times the hall's own weight plus 1.5 times the snow, over the
cross-section, reduced for how slender the column is, against what timber is allowed in compression;
a column over that is named. Plain Python, no Blender.
Usage: python3 weights.py anatomy.json bearing.json out_dir
"""
import json
import math
import os
import sys
from collections import defaultdict

DENSITY = {"timber": 500.0, "rafter": 500.0, "wall": 0.0, "ground": 0.0}
ROOF_PER_M2 = 7000.0   # tiles, boarding and the clay bed together, per square metre of roof in plan
G = 9.81
# Compression along the grain allowed in timber: the design value of the lowest softwood grade (TC11)
# in China's timber design standard GB 50005 (table 4.3.1-3; confirm against the standard before
# quoting it). The Foguang hall's heaviest column works at about 2.3 MPa, a quarter of this.
ALLOWED_MPA = 10.0
# Snow: the 100-year ground snow pressure at Yuanping, the nearest station listed in GB 50009-2012
# table E.5 (0.35 kN/m2; the temple's own village, 50 km east, is not listed), over the roof's footprint,
# with the roof-shape coefficient at 1.0, its value for slopes of 25 degrees and under and its largest.
# A tiled clay roof weighs twenty times this, so snow decides little here; it is a real load all the same.
SNOW_PER_M2 = 350.0
SNOW_SOURCE = "GB 50009-2012 table E.5, Yuanping, Shanxi, 100-year snow pressure 0.35 kN/m2; shape coefficient 1.0"
# How loads are added for a strength check: GB 50068-2018, 8.2.9.
OWN_WEIGHT_FACTOR, SNOW_FACTOR = 1.3, 1.5


def holds(slenderness):
    """The share of its crushing strength a column keeps before it bows, for the TC11 and TC13 timber
    grades: GB 50005-2003, 5.1.4 (the 2017 edition writes the same curve another way; confirm against it
    before quoting). Slenderness is the height over a quarter of the diameter."""
    return 1.0 / (1.0 + (slenderness / 65.0) ** 2) if slenderness <= 91 else 2800.0 / slenderness ** 2


def column_strength(name, piece, carries_n, snow_n=0.0):
    """A column's stress over the round section its two narrow sides give; a square post is taken as
    round, which only makes the check stricter. `stress_MPa` is the hall's own weight alone, as it
    stands today; `design_MPa` is what the column is judged on."""
    a, b, height = sorted(piece["extents"])
    area, slenderness = math.pi * a * b / 4, height / (min(a, b) / 4)
    design_n = OWN_WEIGHT_FACTOR * carries_n + SNOW_FACTOR * snow_n
    return {"name": name, "carries_N": carries_n, "carries_kN": round(carries_n / 1e3, 1),
            "diameter_m": round(min(a, b), 3), "stress_MPa": round(carries_n / area / 1e6, 2),
            "snow_kN": round(snow_n / 1e3, 1), "design_kN": round(design_n / 1e3, 1),
            "slenderness": round(slenderness, 1), "holds": round(holds(slenderness), 3),
            "design_MPa": round(design_n / (holds(slenderness) * area) / 1e6, 2)}


def on_timber(name, pieces, bearing):
    """An upright that stands only on other timber is a post of the frame, not a column: a king post on
    its beam, a hip purlin stood on end. A column stands on the ground, a stone or the platform. One
    that rests on nothing is kept as a column, so a hanging piece is never let off the strength check."""
    below = [seat["on"] for seat in bearing["rests_on"].get(name, [])]
    return bool(below) and all(pieces.get(b, {}).get("role") in ("timber", "rafter") for b in below)


def covering_weights(pieces):
    """The roof weighs ROOF_PER_M2 over its footprint; each covering piece takes a share by its own
    plan area, so tiles drawn over a bedding sheet do not count the roof twice. Covering meshes
    are often open, so their volumes mean nothing and are not used."""
    cover = {n: p for n, p in pieces.items() if p["role"] == "covering"}
    if not cover:
        return {}
    lo = [min(p["box"][0][i] for p in cover.values()) for i in range(2)]
    hi = [max(p["box"][1][i] for p in cover.values()) for i in range(2)]
    footprint = (hi[0] - lo[0]) * (hi[1] - lo[1])
    own = {n: (p["box"][1][0] - p["box"][0][0]) * (p["box"][1][1] - p["box"][0][1]) for n, p in cover.items()}
    total_own = max(sum(own.values()), 1e-9)
    return {n: ROOF_PER_M2 * footprint * own[n] / total_own for n in cover}


def under(piece, candidates):
    """What a covering piece rests on: nine points over its plan each find the highest candidate
    whose plan box holds the point and whose top is at or below the piece's bottom; the shares.
    A big sloped sheet has its bottom at the eave, where nothing is under it: when no point finds
    anything that way, each point takes the highest candidate below the sheet's top instead. The
    rebuilt hall's roof is four such sheets, and without this a third of its weight never reached
    a column."""
    shares = _points_on(piece, candidates, piece["zmin"] + 0.05) or _points_on(piece, candidates, piece["box"][1][2])
    # A covering piece is a plate: the points over a gap still bear on the supports it did find.
    found = sum(shares.values())
    return {name: share / found for name, share in shares.items()} if found else {}


def _points_on(piece, candidates, ceiling):
    lo, hi = piece["box"]
    shares = defaultdict(float)
    for i in range(3):
        for j in range(3):
            x = lo[0] + (hi[0] - lo[0]) * (0.15 + 0.35 * i)
            y = lo[1] + (hi[1] - lo[1]) * (0.15 + 0.35 * j)
            best, best_top = None, -1e9
            for name, p in candidates.items():
                plo, phi = p["box"]
                if plo[0] <= x <= phi[0] and plo[1] <= y <= phi[1] and phi[2] <= ceiling and phi[2] > best_top:
                    best, best_top = name, phi[2]
            if best:
                shares[best] += 1.0 / 9
    return shares


def pass_down(bearing, carries, ground):
    """Every piece, highest first, hands what it carries to what the bearing tool settled carries
    it: its seats there by contact area, else its near misses equally, else the ground it sits
    on; returns what reached the ground, what nothing carried, and the shares."""
    passes = defaultdict(dict)
    ground_total, lost = 0.0, 0.0
    carriers = bearing.get("carried_by", {})
    for n in bearing["order"]:
        allowed = set(carriers.get(n, [])) | ground
        seats = [c for c in bearing["rests_on"].get(n, []) if c["on"] in allowed]
        shares = {c["on"]: c["area"] for c in seats}
        if not shares:
            shares = {m["on"]: 1.0 for m in bearing["near"].get(n, []) if m["on"] in allowed}
        total = sum(shares.values())
        if total <= 0:
            lost += carries[n]
            continue
        for on, share in shares.items():
            part = carries[n] * share / total
            passes[n][on] = part
            if on in ground:
                ground_total += part
            else:
                carries[on] += part
    return ground_total, lost, passes


def carried(pieces, bearing, weight):
    """Send these weights down: what each piece ends up carrying, who passed what to whom, what reached
    the ground and what nothing carried."""
    carries = dict(weight)
    cover_passes = {}
    bearers = {n: p for n, p in pieces.items() if p["role"] in ("timber", "rafter")}
    unplaced = 0.0
    for n, p in pieces.items():
        if p["role"] == "covering":
            shares = under(p, bearers)
            cover_passes[n] = {below: weight[n] * share for below, share in shares.items()}
            for below, part in cover_passes[n].items():
                carries[below] += part
            unplaced += weight[n] * (1.0 - sum(shares.values()))
    ground_total, lost, passes = pass_down(bearing, carries, set(bearing["ground"]))
    passes.update(cover_passes)
    return carries, passes, ground_total, lost + unplaced


def main(anatomy_path, bearing_path, out_dir):
    pieces = json.load(open(anatomy_path))["pieces"]
    bearing = json.load(open(bearing_path))
    weight = {n: p["volume"] * DENSITY.get(p["role"], 0.0) * G for n, p in pieces.items()}
    roof = covering_weights(pieces)
    weight.update(roof)
    carries, passes, ground_total, lost = carried(pieces, bearing, weight)
    snow = {n: roof[n] * SNOW_PER_M2 / ROOF_PER_M2 if n in roof else 0.0 for n in pieces}
    snow_carried = carried(pieces, bearing, snow)[0]
    upright = [n for n, p in pieces.items() if p["role"] == "timber" and p["kind"] == "column"]
    judged = {n: {**column_strength(n, pieces[n], carries[n], snow_carried[n]),
                  "what": "post" if on_timber(n, pieces, bearing) else "column"} for n in upright}
    columns = [c for c in judged.values() if c["what"] == "column"]
    posts = [c for c in judged.values() if c["what"] == "post"]
    weak = [c for c in judged.values() if c["design_MPa"] > ALLOWED_MPA]
    total = sum(weight.values())
    out = {"pieces": {n: {"weight_N": weight[n], "carries_N": carries[n], "passes_to": passes.get(n, {})}
                      for n in pieces},
           "summary": {"total_N": total, "ground_N": ground_total, "not_carried_N": lost, "columns": columns, "posts": posts,
                       "allowed_MPa": ALLOWED_MPA, "overloaded": weak,
                       "snow": {"per_m2_kN": SNOW_PER_M2 / 1e3, "total_kN": round(sum(snow.values()) / 1e3, 1),
                                "source": SNOW_SOURCE}}}
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "loads.json"), "w") as f:
        json.dump(out, f, indent=1)
    counted = [f"{k} {what}{'s' if k != 1 else ''}" for what in ("column", "post")
               if (k := sum(c["what"] == what for c in weak))]
    strength = (" and ".join(counted) + f" too weak (over {ALLOWED_MPA:g} MPa): "
                + ", ".join(f"{c['name']} at {c['design_MPa']} MPa" for c in weak[:4])) if weak else \
        f"every column within {ALLOWED_MPA:g} MPa" + (f", and the {len(posts)} posts standing on the frame" if posts else "")
    strength += f", with {round(sum(snow.values()) / 1e3)} kN of snow on the roof and each column's slenderness counted"
    print("LOADS", len(pieces), "pieces total", round(total / 1e6, 3), "MN ground", round(ground_total / 1e6, 3), "MN |",
          strength)


if __name__ == "__main__":
    main(*sys.argv[1:4])
