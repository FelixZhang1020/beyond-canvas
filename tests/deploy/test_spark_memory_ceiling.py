"""The Spark's class jobs keep the node at or under a ceiling of memory in use, with a stop level under it.

The node freezes rather than failing one process when memory runs out, and nobody can reboot it. Until the
operator set the ceiling, every class job kept 24 GiB available, which left about a fifth of the node idle;
now a job or a kept-loaded model's load may take the node to 115 GiB in use (total minus available, the
figure the node's monitor shows), and a job already running is stopped under 6 GiB available, the lowest the
node has been measured to survive. Builds keep their own wider floor: a compile has no measured peak.
"""
import importlib
import os
import subprocess
import sys
from pathlib import Path

import pytest

SPARK = Path("deploy/spark").resolve()
GUARD = SPARK / "memory_guard.py"
KB = 1024 * 1024   # kB in a GiB, as /proc/meminfo counts


def meminfo(tmp_path, total_gib, available_gib):
    path = tmp_path / "meminfo"
    path.write_text(f"MemTotal:       {int(total_gib * KB)} kB\nMemFree:  1 kB\n"
                    f"MemAvailable:   {int(available_gib * KB)} kB\nSwapTotal: 16777212 kB\n")
    return path


@pytest.fixture
def guard(monkeypatch):
    monkeypatch.syspath_prepend(str(SPARK))
    module = importlib.import_module("memory_guard")
    yield module
    sys.modules.pop("memory_guard", None)


def test_the_room_is_what_the_ceiling_leaves_above_memory_in_use(guard, monkeypatch, tmp_path):
    monkeypatch.setattr(guard, "MEMINFO", str(meminfo(tmp_path, 121.69, 43.33)))
    assert round(guard.used_gib(), 2) == 78.36 and round(guard.room_gib(), 2) == 36.64
    assert not guard.low()
    monkeypatch.setattr(guard, "MEMINFO", str(meminfo(tmp_path, 121.69, 5.0)))
    assert round(guard.room_gib(), 2) == -1.69, "past the ceiling the room is negative, never clamped"
    assert guard.low(), "under the stop level a running job must stop"


def test_the_numbers_are_the_operators(guard):
    assert guard.CEILING_GIB == 115.0 and guard.STOP_GIB == 6.0
    assert guard.FLOOR_GIB == 24.0, "builds keep their wider floor"
    assert guard.STOP_GIB < 121.69 - guard.CEILING_GIB, "a job allowed to the ceiling is not stopped on arrival"


def run_guard(tmp_path, available_gib, *flags):
    env = {**os.environ, "MEMORY_GUARD_MEMINFO": str(meminfo(tmp_path, 121.69, available_gib))}
    return subprocess.run([sys.executable, str(GUARD), *flags], capture_output=True, text=True, env=env)


def test_the_loaders_ask_the_same_file_for_the_room_and_the_stop(tmp_path):
    """The shell loaders cannot import this, so they ask it: a whole number of GiB, and an exit status."""
    assert run_guard(tmp_path, 43.33, "--room").stdout.strip() == "36", "rounded down, so a loader never over-counts"
    assert run_guard(tmp_path, 5.0, "--room").stdout.strip() == "-2"
    assert run_guard(tmp_path, 43.33, "--low").returncode == 1
    assert run_guard(tmp_path, 5.0, "--low").returncode == 0


def test_every_loader_reads_the_room_from_the_guard_and_names_what_it_needs():
    """One source for the rule: a loader that kept its own floor would drift from the service's ceiling."""
    needs = {"safety-reader-load.sh": 11, "qwen-front-load.sh": 52, "trellis-resident-load.sh": 38}
    for loader, gib in needs.items():
        text = (SPARK / loader).read_text()
        assert "memory_guard.py" in text and "--room" in text, loader
        assert f'-lt {gib} ]' in text, f"{loader} asks for the {gib} GiB its model takes at its peak"
        assert "FLOOR=" not in text and "24 GiB floor" not in text, f"{loader} still keeps the old floor"
    for watched in ("qwen-front-load.sh", "trellis-resident-load.sh"):
        assert "--low" in (SPARK / watched).read_text(), f"{watched}'s watcher stops a load at the stop level"


def test_the_builds_keep_their_floor():
    for build in SPARK.glob("build-*.sh"):
        text = build.read_text()
        if "memory_guard.py" in text:
            assert "--floor 24" in text, build.name
