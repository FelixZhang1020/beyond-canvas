"""The parts that stand on the ground: the platform, the columns, the tie beams between column
heads, and the walls between columns. Each takes the numbers it is told and nothing else.
"""
from timber import Refused, box, fresh, need, numbers, placed, round_post, seated, write_record


def platform(args, record, out_dir):
    sx, sy = numbers(args.size, 2, "size")
    coll = fresh("01_Stone_Platform")
    box(coll, "Platform", (0, 0, args.top - args.thickness / 2), (sx, sy, args.thickness))
    write_record(out_dir, record, "platform", vars(args), {"top": args.top, "size": [sx, sy]})
    placed("platform", 1, record, top=args.top)


def grid(xs, ys, rings):
    """Grid points kept, outermost ring first: ring 0 is the perimeter, ring 1 the one inside it."""
    out = []
    for i, x in enumerate(xs):
        for j, y in enumerate(ys):
            ring = min(i, len(xs) - 1 - i, j, len(ys) - 1 - j)
            if rings <= 0 or ring < rings:
                out.append({"x": x, "y": y, "i": i, "j": j, "ring": ring})
    return out


def columns(args, record, out_dir):
    xs, ys = sorted(numbers(args.xs, what="xs")), sorted(numbers(args.ys, what="ys"))
    if len(xs) < 2 or len(ys) < 2:
        raise Refused("columns need at least two xs and two ys")
    if args.height <= 0 or args.diameter <= 0:
        raise Refused("height and diameter must be above zero")
    coll = fresh("02_Columns")
    at = grid(xs, ys, args.rings)
    for c in at:
        round_post(coll, f"Column {c['x']:.2f} {c['y']:.2f}", c["x"], c["y"], args.foot, args.foot + args.height,
                   args.diameter)
    top = args.foot + args.height
    write_record(out_dir, record, "columns", vars(args),
                 {"at": at, "xs": xs, "ys": ys, "foot": args.foot, "top": top, "diameter": args.diameter})
    placed("columns", len(at), record, foot=args.foot, top=top)


def neighbours(at):
    """Pairs of columns next to each other along their own ring."""
    by_cell = {(c["i"], c["j"]): c for c in at}
    for c in at:
        for di, dj in ((1, 0), (0, 1)):
            other = by_cell.get((c["i"] + di, c["j"] + dj))
            if other is None or other["ring"] != c["ring"]:
                continue
            ni, nj = max(v["i"] for v in at), max(v["j"] for v in at)
            r = c["ring"]
            on_edge = (dj == 0 and c["j"] in (r, nj - r)) or (di == 0 and c["i"] in (r, ni - r))
            if on_edge:
                yield c, other


def ties(args, record, out_dir):
    cols = need(record, "columns", "tie beams run between column heads")
    coll = fresh("05_Tie_Beams")
    count = 0
    for a, b in neighbours(cols["at"]):
        along_x = a["j"] == b["j"]
        length = abs(b["x"] - a["x"]) if along_x else abs(b["y"] - a["y"])
        size = (length, args.width, args.depth) if along_x else (args.width, length, args.depth)
        box(coll, f"Tie beam {a['x']:.2f} {a['y']:.2f} to {b['x']:.2f} {b['y']:.2f}",
            ((a["x"] + b["x"]) / 2, (a["y"] + b["y"]) / 2, args.top - args.depth / 2), size)
        count += 1
    write_record(out_dir, record, "ties", vars(args), {"top": args.top, "underside": args.top - args.depth})
    placed("ties", count, record, top=args.top, underside=args.top - args.depth, column_top=cols["top"])


SIDES = {"front": ("j", min), "back": ("j", max), "left": ("i", min), "right": ("i", max)}


def walls(args, record, out_dir):
    cols = need(record, "columns", "walls stand between the outer columns")
    wanted = [s.strip() for s in args.sides.split(",") if s.strip()]
    unknown = [s for s in wanted if s not in SIDES]
    if unknown:
        raise Refused(f"no such side {unknown[0]!r}; the sides are front, back, left, right")
    if args.top <= args.foot:
        raise Refused("a wall's top must be above its foot")
    coll = fresh("03_Walls")
    outer = [c for c in cols["at"] if c["ring"] == 0]
    count = 0
    for side in wanted:
        key, pick = SIDES[side]
        edge = pick(c[key] for c in outer)
        line = sorted((c for c in outer if c[key] == edge), key=lambda c: (c["x"], c["y"]))
        for a, b in zip(line, line[1:]):
            length = max(abs(b["x"] - a["x"]), abs(b["y"] - a["y"])) - cols["diameter"]
            size = (length, args.thickness, args.top - args.foot) if key == "j" else (args.thickness, length, args.top - args.foot)
            box(coll, f"Wall {side} {a['x']:.2f} {a['y']:.2f}",
                ((a["x"] + b["x"]) / 2, (a["y"] + b["y"]) / 2, (args.foot + args.top) / 2), size)
            count += 1
            if args.infill_top is not None and args.infill_top > args.top:
                band = args.infill_top - args.top
                size = (length, 0.12, band) if key == "j" else (0.12, length, band)
                box(coll, f"Wall {side} {a['x']:.2f} {a['y']:.2f} | infill between the brackets",
                    ((a["x"] + b["x"]) / 2, (a["y"] + b["y"]) / 2, args.top + band / 2), size)
                count += 1
    write_record(out_dir, record, "walls", vars(args), {"top": args.top, "sides": wanted})
    placed("walls", count, record, foot=args.foot, top=args.top)


__all__ = ["platform", "columns", "ties", "walls", "seated"]
