"""The shake test: the settle test with the ground moving like an earthquake at the temple's own
site, then pulled steadily sideways as hard as that site's frequent earthquake (quake.py has the
numbers and where they come from). Everything else is settle.py's: the same weights, the same joints held as one,
the same let-go; only the grip between pieces is real timber's, where the settle test's is stricter.
It writes shake.json, shake-start.png and shake-end.png beside the settle test's files and never
over them; shake.mp4 only when asked, because a ground that moves millimetres makes a still video.
Usage: blender -b model.blend --python-exit-code 1 --python shake.py -- out_dir --anatomy anatomy.json
           [--bearing bearing.json] [--seconds 6] [--peak-g 0.20] [--hz 2.5] [--pull-g 0.07] [--video] [--width 1280] [--height 720]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from settle import main  # noqa: E402

if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--") + 1:], shaking=True)
