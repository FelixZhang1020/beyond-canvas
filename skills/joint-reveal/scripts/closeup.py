"""One still of a place in the model, for the agent to look at through shot-judge.
Everything farther than --hide-beyond metres from the look point is hidden, which is what makes
a close-up of a bracket set render in about a second instead of six.
Usage: blender -b model.blend --python-exit-code 1 --python closeup.py -- out.png --at x,y,z --look x,y,z
           [--lens 50] [--hide-beyond 7] [--style studio|daylight] [--width 1280] [--height 720]
"""
import argparse
import os
import sys

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "model-anatomy", "scripts"))
from set_scene import (hide_above, hide_beyond, parse_xyz, place_camera, render_still,  # noqa: E402
                       set_look, set_output)


def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("out")
    parser.add_argument("--at", required=True, help="camera position x,y,z; write --at=-1,2,3 for negatives")
    parser.add_argument("--look", required=True)
    parser.add_argument("--lens", type=float, default=50.0)
    parser.add_argument("--hide-beyond", type=float, default=7.0)
    parser.add_argument("--hide-above", type=float, default=None, help="peel off every piece whose bottom is above z")
    parser.add_argument("--style", choices=("studio", "daylight"), default="studio")
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--move", action="append", default=[], metavar="NAME=dx,dy,dz",
                        help="shift a piece before the shot, to lift a block off its tenon; repeatable")
    parser.add_argument("--hide", action="append", default=[], metavar="NAME", help="hide one piece; repeatable")
    args = parser.parse_args(argv)
    scene = bpy.context.scene
    look = parse_xyz(args.look)
    kept = hide_beyond(scene, look, args.hide_beyond)
    if args.hide_above is not None:
        kept -= hide_above(scene, args.hide_above)
    for name in args.hide:
        scene.objects[name].hide_render = True
    for spec in args.move:
        name, delta = spec.rsplit("=", 1)
        scene.objects[name].matrix_world.translation += parse_xyz(delta)
    set_look(scene, args.style, centre=look, size=max(args.hide_beyond * 0.6, 1.0))
    place_camera(scene, parse_xyz(args.at), look, args.lens)
    set_output(scene, args.width, args.height)
    render_still(scene, args.out)
    print("CLOSEUP", args.out, "kept", kept, "pieces")


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1:])
