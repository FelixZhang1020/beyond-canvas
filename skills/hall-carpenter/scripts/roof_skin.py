"""The roof's skin: rafters laid from purlin to purlin on all four slopes with hip rafters at the
corners, then the covering over them, sheet to sheet, with a cap along every hip and the ridge. Both
read the rings the purlins tool wrote down, so they follow whatever roof line the purlins were given.
"""
import math

from timber import LET_IN, fresh, need, numbers, placed, slab, stick, write_record

SHORT = 0.4
CLEAR, TAPER = 0.05, 0.002      # the cap at the eave corner is 2 mm wide: the corner does not grow


def eave(line, out):
    """The eave's own station: `out` further out down the first segment's slope, and as much wider."""
    (r0, w0, z0), (r1, _, z1) = line[0], line[1]
    return r0 + out, w0 + out, z0 - (z1 - z0) / (r0 - r1) * out


def stations(purl, slope):
    """(reach from the centre, other half extent, top height) from the eave ring up to the ridge."""
    key, other, top = ("half_y", "half_x", "long_top") if slope == "long" else ("half_x", "half_y", "end_top")
    out = [(r[key], r[other], r[top]) for r in purl["rings"]]
    ridge = purl.get("ridge")
    if ridge:
        out.append((0.0, ridge["half_x"], ridge["top"]) if slope == "long" else (ridge["half_x"], 0.0, ridge["top"]))
    return out


def point(slope, sign, reach, across, z):
    return (across, sign * reach, z) if slope == "long" else (sign * reach, across, z)


def spots(half, spacing):
    n = int(half / spacing)
    return [i * spacing for i in range(-n, n + 1)]


def lay_segment(coll, tag, slope, sign, low, high, args, eave_out):
    """Rafters of one slope between two stations; outside the upper station they stop at the hip."""
    (r0, w0, z0), (r1, w1, z1) = low, high
    run = r0 - r1
    grade = (z1 - z0) / run
    count = 0
    for across in spots(w0, args.spacing):
        share = 1.0 if abs(across) <= w1 else (w0 - abs(across)) / max(w0 - w1, 1e-9)
        if share * run < SHORT:
            continue
        start = point(slope, sign, r0 + eave_out, across, z0 - grade * eave_out - LET_IN)
        end = point(slope, sign, r0 - share * run, across, z0 + share * (z1 - z0) - LET_IN)
        stick(coll, f"{tag} | {count:03d}", start, end, args.size, args.size)
        count += 1
    return count


def rafters(args, record, out_dir):
    purl = need(record, "purlins", "rafters lie from purlin to purlin")
    coll, count = fresh("06_Rafters"), 0
    for slope in ("long", "end"):
        line = stations(purl, slope)
        for sign, side in ((-1, "front" if slope == "long" else "left"), (1, "back" if slope == "long" else "right")):
            for k, (low, high) in enumerate(zip(line, line[1:])):
                count += lay_segment(coll, f"Rafter {side} {k + 1}", slope, sign, low, high, args,
                                     args.eave_out if k == 0 else 0.0)
    ends = stations(purl, "end")
    for sx in (-1, 1):
        for sy in (-1, 1):
            for k, ((x0, y0, z0), (x1, y1, z1)) in enumerate(zip(ends, ends[1:])):
                stick(coll, f"Hip rafter {'+' if sx > 0 else '-'}{'+' if sy > 0 else '-'} {k}",
                      (sx * x0, sy * y0, z0 - LET_IN), (sx * x1, sy * y1, z1 - LET_IN), 0.2, 0.25)
                count += 1
    write_record(out_dir, record, "rafters", vars(args), {"size": args.size, "eave_out": args.eave_out})
    placed("rafters", count, record, spacing=args.spacing, eave_out=args.eave_out)


def sheet(coll, name, slope, sign, low, high, lift, thickness):
    """One slope's covering between two stations, each (reach, other half extent, height). Its corners stand
    on the hips, so a long sheet and an end sheet meet edge to edge there, and the hip cap closes the seam."""
    corners = [[point(slope, sign, r, s * w, z + lift) for s in (-1, 1)] for r, w, z in (low, high)]
    slab(coll, name, corners[0], corners[1], thickness)


def hip_points(purl, out):
    """Up the hip from the eave corner to the ridge end, where x and y are positive: (x, y, the long covering's
    height, the end covering's height). The end purlins lie on the long ones, so at every ring the end
    covering stands a purlin's depth higher; at the ridge the two are one."""
    longs, ends = stations(purl, "long"), stations(purl, "end")
    points = [(end[0], long[0], long[2], end[2]) for long, end in zip(longs, ends)]
    if out > 0:
        (y, _, zl), (x, _, ze) = eave(longs, out), eave(ends, out)
        points.insert(0, (x, y, zl, ze))
    return points


def hip_caps(coll, purl, raft, lift, args):
    """A cap along each hip, from the eave corner to the ridge, over the seam where an end slope's covering
    meets a long one's a purlin's depth higher, and over the end purlins' tips, which reach out under the long
    covering there. The end sheets used to be stretched flat past the hips to hide the tips; at
    their own height they stood over the long slopes like flaps, up to 1.01 m in design run 6, and from the
    front corner the air under them read as holes in the roof. The cap reaches from under the lower covering,
    by as much as a slope falls across half the cap, to the ridge cap's height over the higher one. It tapers
    to nothing at the eave corner, which stays where it is: a first lap there made the hall 0.8 m deeper."""
    width, height = numbers(args.ridge_cap, 2, "ridge cap")
    wide = max(width, purl["size"] + 2 * (purl["told"].get("overhang", 0.0) + CLEAR))
    steep = max(abs((b[2] - a[2]) / (a[0] - b[0])) for s in ("long", "end")
                for a, b in zip(stations(purl, s), stations(purl, s)[1:]))
    points = hip_points(purl, raft["eave_out"])
    tops = [max(p[2], p[3]) + lift + args.thickness + height for p in points]
    depths = [abs(p[2] - p[3]) + args.thickness + height + steep * wide / 2 for p in points]
    count = 0
    for sx in (-1, 1):
        for sy in (-1, 1):
            for k, (a, b) in enumerate(zip(points, points[1:])):
                run = math.hypot(b[0] - a[0], b[1] - a[1])
                nx, ny = -sy * (b[1] - a[1]) / run, sx * (b[0] - a[0]) / run
                deep = max(depths[k], depths[k + 1])
                ends = []
                for p, top, w in ((a, tops[k], TAPER if k == 0 else wide), (b, tops[k + 1], wide)):
                    ends.append([(sx * p[0] + s * nx * w / 2, sy * p[1] + s * ny * w / 2, top - deep) for s in (-1, 1)])
                slab(coll, f"Roof sheet hip {'+' if sx > 0 else '-'}{'+' if sy > 0 else '-'} {k + 1}", ends[0],
                     ends[1], deep)
                count += 1
    return count


def roof(args, record, out_dir):
    purl = need(record, "purlins", "the covering follows the purlin rings")
    raft = need(record, "rafters", "the covering lies on the rafters")
    lift, out = raft["size"] - LET_IN, raft["eave_out"]
    coll, count = fresh("07_Roof_Tiles"), 0
    for slope in ("long", "end"):
        line = stations(purl, slope)
        for sign, side in ((-1, "front" if slope == "long" else "left"), (1, "back" if slope == "long" else "right")):
            if out > 0:
                sheet(coll, f"Roof sheet {side} eave", slope, sign, eave(line, out), line[0], lift, args.thickness)
                count += 1
            for k, (low, high) in enumerate(zip(line, line[1:])):
                sheet(coll, f"Roof sheet {side} {k + 1}", slope, sign, low, high, lift, args.thickness)
                count += 1
    caps = fresh("08_Ridges")
    count += hip_caps(caps, purl, raft, lift, args)
    ridge = purl.get("ridge")
    top = max(r["end_top"] for r in purl["rings"]) + lift + args.thickness
    if ridge:
        width, height = numbers(args.ridge_cap, 2, "ridge cap")
        base = ridge["top"] + lift + args.thickness
        stick(caps, "Ridge cap", (-ridge["half_x"] - 0.5, 0, base), (ridge["half_x"] + 0.5, 0, base), width, height)
        top, count = base + height, count + 1
        if args.finial > 0:
            for sign in (-1, 1):
                x = sign * ridge["half_x"]
                stick(caps, f"Ridge finial {'+' if sign > 0 else '-'}", (x - 0.4, 0, base), (x + 0.4, 0, base), 0.5,
                      args.finial)
                count += 1
            top = base + args.finial
    write_record(out_dir, record, "roof", vars(args), {"top": top})
    placed("roof", count, record, top=top)
