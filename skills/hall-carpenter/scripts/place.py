"""Place one part of the hall into the hall file, by the numbers given, and write down what was
placed. One script, one part per call: the first word after `--` names the part.
Usage: blender -b --python-exit-code 1 --python place.py -- <part> <out_dir> --hall hall.blend [the part's flags]
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import brackets as brackets_part  # noqa: E402
import lower  # noqa: E402
import roof_frame  # noqa: E402
import roof_skin  # noqa: E402
from timber import Refused, open_hall, read_record, save_hall  # noqa: E402


def flags(parser, part):
    add = parser.add_argument
    if part == "platform":
        add("--size", required=True), add("--top", type=float, required=True)
        add("--thickness", type=float, default=1.9)
    elif part == "columns":
        add("--xs", required=True), add("--ys", required=True), add("--rings", type=int, default=0)
        add("--foot", type=float, required=True), add("--height", type=float, required=True)
        add("--diameter", type=float, default=0.55)
    elif part == "ties":
        add("--top", type=float, required=True), add("--depth", type=float, default=0.46)
        add("--width", type=float, default=0.32)
    elif part == "walls":
        add("--sides", default="front,back,left,right"), add("--foot", type=float, required=True)
        add("--top", type=float, required=True), add("--thickness", type=float, default=0.3)
        add("--infill-top", dest="infill_top", type=float)
    elif part == "brackets":
        add("--seat", type=float, required=True), add("--tiers", type=int, default=4)
        add("--rise", type=float, default=0.43), add("--reach", type=float, default=0.4)
        add("--block", type=float, default=0.35), add("--arm", default="0.21,0.315")
        add("--inter", type=lambda v: "yes" if str(v).lower() in ("yes", "true", "1") else "no", default="yes"), add("--outrigger", action="append", nargs="+")
    elif part == "frames":
        add("--seat", type=float, required=True), add("--beam", action="append", nargs="+"), add("--king", type=float)
        add("--width", type=float, default=0.4), add("--depth", type=float, default=0.5), add("--lines")
        add("--end-lines", dest="end_lines"), add("--end-beams", dest="end_beams")
    elif part == "purlins":
        add("--ring", action="append", nargs="+"), add("--ridge"), add("--size", type=float, default=0.32)
        add("--overhang", type=float, default=0.0)
    elif part == "rafters":
        add("--spacing", type=float, default=0.6), add("--size", type=float, default=0.14)
        add("--eave-out", dest="eave_out", type=float, default=0.55)
    elif part == "roof":
        add("--thickness", type=float, default=0.15), add("--ridge-cap", dest="ridge_cap", default="0.5,0.6")
        add("--finial", type=float, default=0.0)


PARTS = {"platform": lower.platform, "columns": lower.columns, "ties": lower.ties, "walls": lower.walls,
         "brackets": brackets_part.brackets, "frames": roof_frame.frames, "purlins": roof_frame.purlins,
         "rafters": roof_skin.rafters, "roof": roof_skin.roof}


SECTION = ("width", "depth", "diameter", "size", "thickness", "rise", "reach", "block")


def sane(args):
    """A timber's section is centimetres to a few metres. A beam told to be 960 m wide once kept
    the bearing check busy for ten minutes; a number like that is refused here, in a sentence."""
    for key in SECTION:
        value = getattr(args, key, None)
        if isinstance(value, float) and not 0.02 <= value <= 5.0:
            raise Refused(f"{key} {value} is not a timber's size in metres; give between 0.02 and 5")
    spacing = getattr(args, "spacing", None)
    if spacing is not None and not 0.2 <= spacing <= 5.0:
        raise Refused(f"spacing {spacing} is out of range; give between 0.2 and 5 metres")


class Asked(argparse.ArgumentParser):
    """A flag the tool cannot read is answered in a sentence. The usage text argparse prints is a
    page a model cannot act on: the fourth live rebuild read it twice and changed nothing."""

    def error(self, message):
        raise Refused(f"{message}; a number list is one string like \"1.5,2\", and a count is one whole number")


def main(argv):
    part = argv[0]
    parser = Asked(prog=f"place {part}")
    parser.add_argument("out_dir")
    parser.add_argument("--hall", required=True)
    flags(parser, part)
    args = parser.parse_args(argv[1:])
    out_dir, hall = args.out_dir, args.hall
    del args.out_dir, args.hall
    sane(args)
    open_hall(hall)
    PARTS[part](args, read_record(out_dir), out_dir)
    save_hall(hall)


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1:])
