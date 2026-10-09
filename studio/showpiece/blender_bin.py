"""Finding Blender and running one tool in it, for the exhibit.

The three places the binary can be are the same the test harness looks in; the exhibit must not
import from the tests, so they are repeated here. A tool run returns its exit code and the tail
of what it printed, which is what an agent reads.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

MAC_BLENDER = Path("/Applications/Blender.app/Contents/MacOS/Blender")
TAIL = 4000
# A tool's own verdict is one line that opens with its name in capitals (SETTLE, BEARING, PLACED,
# REFUSED). Blender flushes its progress after Python's prints, so the verdict sat above thirty
# "bake: frame" lines and outside the 600 characters an agent is shown: the settle test's answer
# never reached the model. The verdict lines are repeated last, where the agent reads.
VERDICT = re.compile(r"^[A-Z]{4,}\b.*$", re.MULTILINE)


def find_blender() -> Path | None:
    """The Blender binary, from BLENDER_BIN, the Mac application, or the PATH."""
    named = os.environ.get("BLENDER_BIN")
    if named and Path(named).is_file():
        return Path(named)
    if MAC_BLENDER.is_file():
        return MAC_BLENDER
    on_path = shutil.which("blender")
    return Path(on_path) if on_path else None


def run_tool(argv: list[str], timeout_s: int, cwd: Path | None = None) -> tuple[int, str]:
    """Run one tool as a plain argv list; (exit code, the last TAIL characters it printed)."""
    try:
        done = subprocess.run(argv, capture_output=True, text=True, timeout=timeout_s, cwd=cwd)
    except subprocess.TimeoutExpired:
        return 124, f"timed out after {timeout_s} s"
    except OSError as error:
        return 127, str(error)
    text = (done.stdout or "") + ("\n" + done.stderr if done.stderr else "")
    verdicts = VERDICT.findall(text)[-3:]
    return done.returncode, text[-TAIL:] + ("\n" + "\n".join(verdicts) if verdicts else "")
