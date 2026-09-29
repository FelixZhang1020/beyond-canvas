"""Bracket sets: on every column head, and between columns on the outer ring, a base block and
tiers of crossed arms with small blocks on them, each tier stepping further out. The top of the
last tier's blocks is the bracket top, where the lowest beams sit. An outrigger is a long lever
arm across an outer set, reaching out under the eave; its top is given, not worked out.
"""
from timber import LET_IN, Refused, fresh, need, numbers, placed, rest, seated, write_record

BLOCK, SMALL = 0.60, 0.30


def outer_sets(cols, ties_top, seat):
    """Every column, then the middle of every outer bay; (x, y, level the base stands on, faces)."""
    at = cols["at"]
    ni, nj = max(c["i"] for c in at), max(c["j"] for c in at)
    for c in at:
        faces = [a for a, on in (("y", c["j"] in (0, nj)), ("x", c["i"] in (0, ni))) if on and c["ring"] == 0]
        yield c["x"], c["y"], seat, faces, True
    if ties_top is None:
        return
    outer = {(c["i"], c["j"]): c for c in at if c["ring"] == 0}
    for (i, j), c in outer.items():
        for di, dj in ((1, 0), (0, 1)):
            other = outer.get((i + di, j + dj))
            if other is None or not ((dj == 0 and j in (0, nj)) or (di == 0 and i in (0, ni))):
                continue
            yield (c["x"] + other["x"]) / 2, (c["y"] + other["y"]) / 2, ties_top, ["y" if dj == 0 else "x"], False


def one_set(coll, tag, x, y, stands_on, seat, args, faces, on_column):
    """Base block up to seat + block, then the tiers; returns the pieces placed."""
    arm_w, arm_d = args.arm
    rest(coll, f"{tag} | base block", x, y, stands_on, (BLOCK, BLOCK, seat - stands_on + args.block))
    count, level = 1, seat + args.block
    for t in range(1, args.tiers + 1):
        for axis in ("x", "y"):
            reach = args.reach * t if axis in faces else 0.5 + 0.15 * t     # only an outer set steps out under the eave
            size = (2 * reach + 0.4, arm_w, arm_d) if axis == "x" else (arm_w, 2 * reach + 0.4, arm_d)
            rest(coll, f"{tag} | tier {t} arm {axis}", x, y, level, size)
            for sign in (-1, 1):
                dx, dy = (sign * reach, 0) if axis == "x" else (0, sign * reach)
                seated(coll, f"{tag} | tier {t} block {axis}{'+' if sign > 0 else '-'}", x + dx, y + dy,
                       level + arm_d, (SMALL, SMALL, args.rise - arm_d))
            count += 3
        seated(coll, f"{tag} | tier {t} block centre", x, y, level + arm_d, (SMALL, SMALL, args.rise - arm_d))
        count += 1
        level += args.rise
    for k, (reach, top) in enumerate(args.outriggers):
        for axis in faces:
            size = (2 * reach + 0.4, arm_w, arm_d) if axis == "x" else (arm_w, 2 * reach + 0.4, arm_d)
            rest(coll, f"{tag} | outrigger {k + 1} {axis}", x, y, top - arm_d, size)
            count += 1
    return count


def brackets(args, record, out_dir):
    cols = need(record, "columns", "bracket sets stand on column heads")
    args.arm = numbers(args.arm, 2, "arm")
    args.outriggers = [numbers(v, 2, "outrigger") for v in (args.outrigger or [])]
    if args.tiers < 1 or args.tiers > 8:
        raise Refused("tiers must be between 1 and 8")
    if args.rise <= args.arm[1] + LET_IN:
        raise Refused(f"rise {args.rise} leaves no room for a block above an arm {args.arm[1]} deep")
    ties_top = None
    if args.inter == "yes":
        ties_top = need(record, "ties", "a set between columns stands on the tie beam; or say inter no")["top"]
    coll = fresh("04_Brackets")
    count = sets = 0
    for x, y, stands_on, faces, on_column in outer_sets(cols, ties_top, args.seat):
        tag = f"Bracket {x:.2f} {y:.2f}" if on_column else f"Bracket between {x:.2f} {y:.2f}"
        count += one_set(coll, tag, x, y, stands_on, args.seat, args, faces, on_column)
        sets += 1
    top = args.seat + args.block + args.tiers * args.rise
    told = {k: v for k, v in vars(args).items()}
    write_record(out_dir, record, "brackets", told,
                 {"top": top, "sets": sets, "outrigger_tops": [t for _, t in args.outriggers]})
    placed("brackets", count, record, sets=sets, seat=args.seat, column_top=cols["top"], bracket_top=top,
           outrigger_underside=min((t - args.arm[1] for _, t in args.outriggers), default=top))
