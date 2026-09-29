"""Arithmetic the survey does on what it has measured, kept free of Blender so a test runs in
milliseconds. The boxes come from survey.py; what they mean is worked out here.

Rafters first, because the fourth live rebuild was told "0.36 m thick, 0.05 m apart". The Foguang
hall's rafters lie in tiers, one above the other up the slope, and fan out toward the corners. Read
as one row, two tiers a few centimetres out of step look like rafters a few centimetres apart; and a
fanned rafter's box is wider than the rafter. So the spacing is taken within a tier, and the size is
the narrowest box that several rafters share: the ones that run straight.
"""
from collections import Counter

TIER_APART = 0.15     # rafters whose feet differ by less than this stand in the same tier
SEVERAL = 3           # one odd piece does not move the sheet


def common(values):
    """The value most pieces share, to the centimetre."""
    return Counter(round(v, 2) for v in values).most_common(1)[0][0] if values else None


def tiers_of(runs):
    """The rafters of each slope, split where their feet step up."""
    tiers = []
    for front in (True, False):
        last = None
        for run in sorted((r for r in runs if (r["y"] < 0) == front), key=lambda r: r["foot"]):
            if last is None or run["foot"] - last > TIER_APART:
                tiers.append([])
            tiers[-1].append(run["x"])
            last = run["foot"]
    return tiers


def rafters(runs):
    """Size and spacing of the rafters that run front to back. Each run is one rafter's box: `x` its
    centre along the hall, `width` its box across x, `y` its centre front to back, `foot` its lowest z."""
    if len(runs) < SEVERAL:
        return None
    gaps = [b - a for xs in tiers_of(runs) for a, b in zip(sorted(xs), sorted(xs)[1:]) if b - a > 0.005]
    shared = Counter(round(r["width"], 2) for r in runs)
    straight = [width for width, pieces in sorted(shared.items()) if pieces >= SEVERAL]
    return {"size": straight[0] if straight else common([r["width"] for r in runs]), "spacing": common(gaps)}


def through_the_roof_sentence(poking):
    """The likeness fault for timber standing out of the covering, with the remedy that fits what stands
    out. A remedy that cannot work costs the builder a repair lap, so each is given only where it mends."""
    sentence = f"{len(poking)} timber pieces stand out through the roof: " + ", ".join(poking[:4])
    if any(name.startswith("Frame") for name in poking):
        sentence += ("; a frame line under the sloping end of the roof is named in frames' end-lines, every such line"
                     " in one call, because placing the frames again replaces them")
    if any(not name.startswith("Frame") for name in poking):
        sentence += ("; a purlin or beam end shows where the covering lies close over it: the covering sits on the"
                     " rafters, so thicker rafters lift it")
    return sentence


KINDS = (("outrigger", "outriggers"), ("arm", "bracket arms"), ("block", "bracket blocks"), ("purlin", "purlins"),
         ("king post", "king posts"), ("post", "posts"), ("beam", "beams"))


def beyond_the_eaves_sentence(found):
    """The fault for timber standing past the edge of the roof, counted by kind of piece, with how far it
    reaches and where the covering ends. Design run 4 was adopted with bracket arms and outriggers in the open
    air at both short ends; a builder told only the names would not know which number falls short."""
    pieces, reach, edge = found["pieces"], found["reach"], found["edge"]
    kinds = Counter(next((kind for word, kind in KINDS if word in name.lower()), "other timber") for name in pieces)
    sentence = (f"{len(pieces)} timber pieces stand past the edge of the roof, with no covering over them: "
                + ", ".join(f"{count} {kind}" for kind, count in kinds.most_common()))
    far = [f"{way} they reach {reach[i]:g} m from the middle and the covering ends at {edge[i]:g}"
           for i, way in enumerate(("along the hall", "across it")) if reach[i] > edge[i]]
    if far:
        sentence += "; " + ", and ".join(far)
    return sentence + ": the eave ring must stand further out than the bracket sets reach, or the eave-out be longer"


def open_roof_sentence(found):
    """The fault for a roof with openings in it: how much, how deep, and where the worst is. Design run 6 was
    adopted with its covering open at the hips, dark wedges from the front corner, and the eyes passed it."""
    said, (x, y) = [], found["at"]
    if found["pockets_m2"]:
        said.append(f"{found['pockets_m2']:g} m2 where one covering sheet stands up to {found['deepest']:g} m over "
                    f"another with open air between ({found['over']}, the worst at x = {x:g}, y = {y:g})")
    if found["holes_m2"]:
        said.append(f"{found['holes_m2']:g} m2 inside its outline with no covering at all")
    return (f"the roof is open{' at the hips' if found['at_hips'] else ''}: " + ", and ".join(said)
            + "; place the roof again after the purlins and the rafters, and give the purlins a ridge: the roof "
              "closes each hip with a cap and its top at the ridge")
