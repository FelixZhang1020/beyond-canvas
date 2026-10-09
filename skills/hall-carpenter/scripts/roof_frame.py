"""The roof frame: on every cross line of inner columns, beams stacked narrower as they go up,
with posts cut to stand between them and a king post to the ridge; then the purlins, ring by
ring from the eave to the ridge. A beam's top and a purlin's underside are both given: when they
are the same number the purlin sits, and when they are not the checks will say so.
"""
from timber import Refused, fresh, need, numbers, placed, rest, seated, write_record

POST = 0.30


def cross_lines(cols):
    xs = cols["xs"]
    return xs[1:-1] if len(xs) > 2 else xs


def on_column_lines(cols, wanted, what):
    """Each x snapped to the column line it names. The first live run gave the ys here, and its
    frames stood over nothing; three checks later the model still did not know why."""
    out = []
    for x in wanted:
        near = min(cols["xs"], key=lambda line: abs(line - x))
        if abs(near - x) > 0.05:
            raise Refused(f"{what}: no columns stand on the cross line x = {x}. A frame line is an x, and the columns "
                          f"stand on x = {cols['xs']}; leave `lines` out to frame every line of inner columns")
        out.append(near)
    return out


def lowest_beams(coll, cols, args, lines):
    """Beams from column to column on each cross line, and along the end bays, on the bracket tops."""
    count = 0
    for x in lines:
        ys = sorted(c["y"] for c in cols["at"] if abs(c["x"] - x) < 1e-6)
        for a, b in zip(ys, ys[1:]):
            rest(coll, f"Frame {x:.2f} | lowest beam {a:.2f} to {b:.2f}", x, (a + b) / 2, args.seat,
                   (args.width, b - a + args.width, args.depth))
            count += 1
    xs = cols["xs"]
    for outer, inner in ((xs[0], xs[1]), (xs[-1], xs[-2])):
        for y in sorted(c["y"] for c in cols["at"] if abs(c["x"] - inner) < 1e-6 and c["ring"] == 1):
            rest(coll, f"Frame end {outer:.2f} | lowest beam {y:.2f}", (outer + inner) / 2, y, args.seat,
                   (abs(outer - inner) + args.width, args.width, args.depth))
            count += 1
    return count


def end_beams(text, low_lines, most):
    """How many beams each end line keeps: one whole number for all of them, or one per end line.
    Models write both, and the fourth live run lost five repair laps to a tool that took only one."""
    if text is None:
        return {x: most for x in low_lines}
    counts = numbers(text, what="end-beams")
    if len(counts) == 1:
        counts = counts * len(low_lines)
    if len(counts) != len(low_lines) or any(c != int(c) or c < 0 for c in counts):
        raise Refused(f"end-beams takes one whole number, used for every end line, or one for each of the {len(low_lines)} "
                      f"end lines, got {text!r}; name every end line in one call, because placing the frames again replaces them")
    return {x: int(c) for x, c in zip(low_lines, counts)}


def metres(value):
    """A height as the model would write it back: 10.15, not 10.149999999999999 or 10.150."""
    return f"{round(value, 3):g}"


def too_low(k, top, below_top, args):
    """A beam stands on posts above the one below it, so its underside, a depth under its top, must be
    above that beam's top. Design run 2 was told only of "the beam below it", did not know the frames lay
    the lowest beam on the seat themselves, and spent about 30 of its 80 actions guessing beam tops."""
    least = f"{metres(below_top)} + {metres(args.depth)} = {metres(below_top + args.depth)}"
    if k > 1:
        return (f"beam {k} (top {metres(top)}) leaves no room for a post above beam {k - 1} (top {metres(below_top)}): "
                f"a beam's underside is a depth under its top, so beam {k}'s top must be more than {least}")
    return (f"beam 1 (top {metres(top)}) leaves no room for a post: the frames lay their lowest beam on the seat "
            f"themselves, its top at seat + depth = {metres(args.seat)} + {metres(args.depth)} = {metres(below_top)}, "
            f"and every beam you give stands on posts above it, its underside a depth under its top, so beam 1's top "
            f"must be more than {least}")


def frames(args, record, out_dir):
    cols = need(record, "columns", "the frames stand over the inner column lines")
    beams = [numbers(v, 2, "beam") for v in (args.beam or [])]
    lines = on_column_lines(cols, numbers(args.lines, what="lines"), "lines") if args.lines else cross_lines(cols)
    below_top, below_half = args.seat + args.depth, max(abs(y) for y in cols["ys"])
    for k, (top, half) in enumerate(beams, 1):
        if top - args.depth <= below_top:
            raise Refused(too_low(k, top, below_top, args))
        if half - POST > below_half:
            raise Refused(f"beam {k} is wider than the one below it; its posts would stand on nothing")
        below_top, below_half = top, half
    if args.king is not None and args.king <= below_top:
        raise Refused(f"the king post must rise above the top beam (top {below_top:.3f})")
    low_lines = on_column_lines(cols, numbers(args.end_lines, what="end lines"), "end-lines") if args.end_lines else []
    if any(x not in lines for x in low_lines):
        raise Refused(f"end-lines name lines that carry a frame; the frames stand on x = {lines}")
    kept = end_beams(args.end_beams, low_lines, len(beams))
    coll = fresh("05_Roof_Frame")
    count, kings = lowest_beams(coll, cols, args, lines), []
    for x in lines:
        under = args.seat + args.depth
        low = next((v for v in low_lines if abs(x - v) < 0.05), None)      # a line under the hip end of the roof carries less
        for k, (top, half) in enumerate(beams[:kept[low]] if low is not None else beams, 1):
            for sign in (-1, 1):
                seated(coll, f"Frame {x:.2f} | post {k} {'+' if sign > 0 else '-'}", x, sign * (half - POST), under,
                       (POST, POST, top - args.depth - under + 0.02))
            rest(coll, f"Frame {x:.2f} | beam {k}", x, 0, top - args.depth, (args.width, 2 * half, args.depth))
            under, count = top, count + 3
        if args.king is not None and low is None:
            seated(coll, f"Frame {x:.2f} | king post", x, 0, under, (POST, POST, args.king - under))
            count, kings = count + 1, kings + [x]
    tops = [args.seat + args.depth] + [t for t, _ in beams]
    write_record(out_dir, record, "frames", vars(args), {"lines": lines, "beam_tops": tops, "king": args.king,
                                                         "kings": kings})
    placed("frames", count, record, lines=len(lines), end_lines=low_lines, lowest_beam_top=tops[0],
           top_beam_top=tops[-1], king_top=args.king if args.king is not None else tops[-1])


HALF_X = "half_x is how far the ridge runs each way from the middle, along the hall"


def spots(xs):
    """Where posts stand, as the model reads them back: ±2.429 and ±7.286, not four numbers."""
    said = []
    for v in sorted({round(abs(x), 3) for x in xs}):
        signs = {x > 0 for x in xs if abs(abs(x) - v) < 1e-3}
        if v == 0 or signs == {True}:
            said.append(metres(v))
        elif signs == {False}:
            said.append(metres(-v))
        else:
            said.append(f"±{metres(v)}")
    return said[0] if len(said) == 1 else ", ".join(said[:-1]) + " and " + said[-1]


def ridge_rests(rx, top_ring, record):
    """The ridge lies on the king posts, and a king post it does not reach stands where the roof comes down:
    a line further out than the ridge's half_x is an end line. Design run 2 gave half_x 0, a ridge of no length
    between king posts at ±2.429 and ±7.286; the fault report said it hung 12 m above the platform, and the
    builder added a ninth column line under it. Before the frames are placed there is nothing to reach."""
    frame = record["parts"].get("frames") or {}
    kings = frame.get("kings") or []
    least = max((abs(x) for x in kings), default=0.0)
    if rx >= least - 1e-6:
        return
    missed = "rests on no king post" if all(abs(x) > rx + 1e-6 for x in kings) else "misses the outer king posts"
    said = (f"the ridge (half_x {metres(rx)}) {missed}: {HALF_X}; the frames' king posts stand at x = {spots(kings)}, "
            f"their tops at {metres(frame['king'])}")
    if least < top_ring[0]:
        raise Refused(f"{said}, so give half_x of at least {metres(least)}")
    far = [x for x in kings if abs(x) >= top_ring[0]]
    raise Refused(f"{said}, and no ridge shorter than the top ring (half_x {metres(top_ring[0])}) reaches them: "
                  f"the lines x = {spots(far)} stand under the sloping end of the roof, so place the frames again "
                  f"naming them in end-lines")


def purlins(args, record, out_dir):
    rings = [numbers(v, 3, "ring") for v in (args.ring or [])]
    if not rings:
        raise Refused("purlins need at least one ring: half x, half y, underside")
    for low, high in zip(rings, rings[1:]):
        if not (high[0] < low[0] and high[1] < low[1] and high[2] > low[2]):
            raise Refused("rings go from the eave up: each one narrower in x and y and higher than the one before")
    told = numbers(args.ridge, 2, "ridge") if args.ridge else None
    if told:
        rx, under = told
        if rx >= rings[-1][0] or under <= rings[-1][2]:
            raise Refused(f"the ridge (half_x {metres(rx)}, underside {metres(under)}) must be shorter than the top "
                          f"ring and higher than it: {HALF_X}, so give half_x less than {metres(rings[-1][0])} and an "
                          f"underside above {metres(rings[-1][2])}")
        ridge_rests(rx, rings[-1], record)
    size, coll, count = args.size, fresh("05_Purlins"), 0
    made = []
    for k, (hx, hy, under) in enumerate(rings):
        for sign in (-1, 1):
            side = "+" if sign > 0 else "-"
            rest(coll, f"Purlin ring {k + 1} | long y{side}", 0, sign * hy, under, (2 * (hx + args.overhang), size, size))
            seated(coll, f"Purlin ring {k + 1} | end x{side}", sign * hx, 0, under + size - 0.02,
                   (size, 2 * (hy + args.overhang), size))
        count += 4
        made.append({"half_x": hx, "half_y": hy, "underside": under, "long_top": under + size,
                     "end_top": under + 2 * size - 0.02})
    ridge = None
    if told:
        rx, under = told
        rest(coll, "Purlin ridge", 0, 0, under, (2 * rx, size, size))
        ridge, count = {"half_x": rx, "underside": under, "top": under + size}, count + 1
    write_record(out_dir, record, "purlins", vars(args), {"rings": made, "ridge": ridge, "size": size})
    placed("purlins", count, record, rings=len(made), lowest_underside=rings[0][2],
           ridge_underside=ridge["underside"] if ridge else 0.0)
