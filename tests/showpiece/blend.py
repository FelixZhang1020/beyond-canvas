"""Running a skill tool inside headless Blender, for the showpiece tests.

The tools are Blender scripts, so a test that exercises one needs the binary. `find_blender`
looks in the three places it can be; `run_in_blender` runs one tool and hands back what it
printed, or raises with the log so a failure is readable in the test output.
"""
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILLS = ROOT / "skills"
MAC_BLENDER = Path("/Applications/Blender.app/Contents/MacOS/Blender")


def find_blender() -> Path | None:
    """The Blender binary, from BLENDER_BIN, the Mac application, or the PATH."""
    named = os.environ.get("BLENDER_BIN")
    if named and Path(named).is_file():
        return Path(named)
    if MAC_BLENDER.is_file():
        return MAC_BLENDER
    on_path = shutil.which("blender")
    return Path(on_path) if on_path else None


def run_in_blender(blender: Path, model: Path | None, script: Path, *args: str, timeout: int = 600) -> str:
    """Run one tool headless and return what it printed; a failure raises with the log."""
    command = [str(blender), "-b"]
    if model is not None:
        command.append(str(model))
    command += ["--python-exit-code", "1", "--python", str(script), "--", *args]
    done = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    if done.returncode != 0:
        raise RuntimeError(f"blender failed ({done.returncode}):\n{done.stdout[-3000:]}\n{done.stderr[-3000:]}")
    return done.stdout


def brightness(path: Path) -> float:
    """Mean grey level of a still, 0 to 255: a black frame or a washed-out one is a lighting fault."""
    from PIL import Image, ImageStat
    with Image.open(path) as image:
        return ImageStat.Stat(image.convert("L")).mean[0]


# A six-column hall: one eave ring carried by outriggers, one ring on a beam, a ridge on a king post.
RIGHT = [
    ("platform", "--size", "12,9", "--top", "0.5", "--thickness", "0.5"),
    ("columns", "--xs=-4,0,4", "--ys=-3,3", "--foot", "0.5", "--height", "3.0", "--diameter", "0.4"),
    ("ties", "--top", "3.3", "--depth", "0.3", "--width", "0.2"),
    ("walls", "--foot", "0.5", "--top", "3.0"),
    ("brackets", "--seat", "3.5", "--tiers", "2", "--rise", "0.45", "--outrigger", "1.2,5.065"),
    ("frames", "--seat", "4.75", "--beam", "5.9,1.8", "--king", "6.6", "--lines", "0"),
    ("purlins", "--ring", "5.2,4.2,5.065", "--ring", "3.5,1.5,5.9", "--ridge", "2.0,6.6"),
    ("rafters", "--spacing", "0.8"),
    ("roof", "--finial", "0.5"),
]
# The same hall with its eave ring at the outer columns, as design run 4 gave its own: the bracket arms and
# outriggers reach 5.4 m from the middle along the hall, and the covering ends at 4.0 + 0.55 of eave-out.
TIGHT = [s if s[0] != "purlins" else ("purlins", "--ring", "4.0,3.0,5.065", "--ring", "3.5,1.5,5.9", "--ridge",
                                      "2.0,6.6") for s in RIGHT]
# Design run 6's roof on the same hall: rings that step in far less along the hall (0.9 m) than across it (2.7 m),
# a long ridge and a long eave-out. The end sheets once stood 1 m over the long slopes at the hips, flat.
SEAMS = [{"purlins": ("purlins", "--ring", "5.2,4.2,5.065", "--ring", "4.3,1.5,5.9", "--ridge", "3.0,6.6"),
          "rafters": ("rafters", "--spacing", "0.8", "--eave-out", "1.0")}.get(s[0], s) for s in RIGHT]


def place(blender, folder, steps):
    out = []
    for part, *flags in steps:
        out.append(run_in_blender(blender, None, SKILLS / "hall-carpenter/scripts/place.py", part, str(folder), "--hall",
                                  str(folder / "hall.blend"), *flags))
    return out
