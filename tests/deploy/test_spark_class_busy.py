"""A full test run waits while the class is making something, and only then.

class-busy.sh is asked with a made-up home: its job folders and its studio are stand-ins, so nothing
here looks at, or waits on, the class on the node.
"""
import os
import subprocess
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
BUSY = ROOT / "deploy/spark/class-busy.sh"
TESTS = ROOT / "deploy/spark/test-on-spark.sh"


def ask(home, studio_exit=0):
    """Run class-busy.sh under `home`, with a studio that answers idle (0) or busy (3)."""
    idle = home / "beyond-canvas/deploy/spark/studio_idle.py"
    idle.parent.mkdir(parents=True, exist_ok=True)
    idle.write_text(f"import sys\nsys.exit({studio_exit})\n")
    return subprocess.run(["sh", str(BUSY)], env={**os.environ, "HOME": str(home)}).returncode


def job(home, age_hours=0):
    folder = home / "spark-media/media-extra/jobs/job-1"
    folder.mkdir(parents=True)
    then = time.time() - age_hours * 3600
    os.utime(folder, (then, then))


def test_a_quiet_class_is_not_busy(tmp_path):
    assert ask(tmp_path) == 1


def test_a_clip_or_3d_job_in_flight_makes_the_class_busy(tmp_path):
    job(tmp_path)
    assert ask(tmp_path) == 0


def test_a_job_folder_a_crash_left_hours_ago_does_not(tmp_path):
    job(tmp_path, age_hours=4)
    assert ask(tmp_path) == 1


@pytest.mark.parametrize("answer", [3, 1], ids=["saving a request", "cannot tell"])
def test_a_studio_still_saving_a_request_or_unable_to_say_makes_it_busy(tmp_path, answer):
    assert ask(tmp_path, studio_exit=answer) == 0


def test_only_a_full_run_waits_and_it_waits_before_taking_the_lock():
    script = TESTS.read_text()
    wait = script.index('while sh "$HOME/$MIRROR/deploy/spark/class-busy.sh"')
    assert script.index('if [ $# -eq 0 ] && [ -z "$WHILE_BUSY" ]') < wait, "a run given a command must not wait"
    assert wait < script.index('exec 9> "$HOME/beyond-canvas-test.lock"'), \
        "waiting while holding the lock would hold up every run queued behind this one"
