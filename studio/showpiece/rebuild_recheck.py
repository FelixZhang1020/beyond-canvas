"""Today's brief check on the hall a design ended with, run inside Blender for the replay (rebuild_designs.py):
a check added after a design was handed over may find what its own day's did not, and every design's final
hall is measured the same way as the real one for the page to set them side by side.

It runs hall-carpenter's own brief.py unchanged, so the verdict and the sentences are today's check's,
word for word. brief.py keeps the first twenty names of what stands through the roof or past the eaves;
the replay paints every such piece red, so the same two functions brief.py calls are asked once more
here for the whole lists, before brief.py paints the hall for its picture. Reads the hall, changes
nothing, and writes only into the folder it is given: never the run's own folder.
Usage: blender -b hall.blend --python-exit-code 1 --python rebuild_recheck.py -- out_dir --brief brief.json --photo photo.jpg
"""
import json
import os
import sys

import bpy

SCRIPTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "skills", "hall-carpenter", "scripts")
sys.path.insert(0, SCRIPTS)
import brief  # noqa: E402  (it puts model-anatomy's scripts on the path too)
from likeness import beyond_the_eaves, through_the_roof  # noqa: E402
from pieces import visible_pieces  # noqa: E402
from survey import columns_of  # noqa: E402


def main(argv):
    scene = bpy.context.scene
    roles = visible_pieces(scene)
    top = columns_of(scene, roles)["top"] or 0.0
    whole = {"through_the_roof": through_the_roof(scene, roles), "beyond_the_eaves": beyond_the_eaves(scene, roles, top)["pieces"]}
    brief.main(argv)
    with open(os.path.join(argv[0], "brief-check.json")) as f:
        found = json.load(f)
    with open(os.path.join(argv[0], "recheck.json"), "w") as f:
        json.dump({**found, **whole}, f, indent=1)
    print("RECHECK", "meets the brief" if found["meets"] else "does NOT meet the brief",
          f"| {len(whole['through_the_roof'])} through the roof, {len(whole['beyond_the_eaves'])} past the eaves", flush=True)


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1:])
