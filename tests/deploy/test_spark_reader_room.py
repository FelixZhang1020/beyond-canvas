"""On the Spark NVIDIA's safety reader (~11 GiB) is always loaded, for the class's second look (operator).

No job asks it to step aside: a clip (~85 GiB at its peak) fits beside it under the node's ceiling of
115 GiB in use (memory_guard.py), a job that does not fit asks the other kept-loaded models for room, and
one that fits with none of them is refused with the reader still up (deploy/spark/safety-reader.sh).
"""
import importlib
import sys
from pathlib import Path

import pytest

SPARK = Path("deploy/spark").resolve()
READER = "nemotron-safety"
TOTAL = 121.69   # the node's MemTotal in GiB, as its monitor reports it


class Box:
    """Memory as MemAvailable reports it with the reader holding its 11 GiB, and what docker was told."""

    def __init__(self, idle):
        self.idle, self.stopped = idle, []

    def available(self):
        return self.idle - 11

    def run(self, argv, **kwargs):
        if argv[:2] == ["docker", "stop"]:
            self.stopped.append(argv[-1])
        return type("Done", (), {"returncode": 0, "stdout": "", "stderr": ""})()


@pytest.fixture
def spark(monkeypatch, tmp_path):
    monkeypatch.syspath_prepend(str(SPARK))
    module = importlib.import_module("media_spark")
    waited = []

    def world(idle):
        box = Box(idle)
        monkeypatch.setattr(module, "RESIDENT", tmp_path / "resident")
        monkeypatch.setattr(module.memory_guard, "available_gib", box.available)
        monkeypatch.setattr(module.memory_guard, "total_gib", lambda: TOTAL)
        monkeypatch.setattr(module, "trellis_ready", lambda: False)
        monkeypatch.setattr(module, "front_up", lambda: False)
        monkeypatch.setattr(module.subprocess, "run", box.run)
        monkeypatch.setattr(module.time, "sleep", waited.append)
        return module, box, waited
    yield world
    sys.modules.pop("media_spark", None)


def test_a_clip_fits_beside_the_reader_under_the_ceiling_and_stops_nothing(spark):
    module, box, waited = spark(idle=115)   # 104 GiB available: the clip's 85 lands at 102.7 in use
    assert module.room_for("wan2.2-i2v-a14b")
    assert box.stopped == [] and waited == []
    assert not (module.RESIDENT / "paused").exists(), "nothing pauses the reader"


def test_a_3d_job_fits_beside_the_reader_and_stops_nothing(spark):
    module, box, _ = spark(idle=115)
    assert module.room_for("trellis2") and box.stopped == []


def test_a_job_that_does_not_fit_with_every_other_model_gone_is_refused_and_the_reader_stays(spark):
    """Other work on the box can hold the memory; stopping the reader would only lose its looks."""
    module, box, _ = spark(idle=90)   # 79 GiB available: the clip would pass the ceiling even beside the reader alone
    assert not module.room_for("wan2.2-i2v-a14b") and box.stopped == []
    assert not (module.RESIDENT / "paused").exists()


def test_a_running_job_is_stopped_only_under_the_stop_level(spark):
    module, _, _ = spark(idle=17)   # 6 GiB available: the stop level itself
    assert not module.memory_low(), "at the stop level a job goes on"
    module, _, _ = spark(idle=16.9)
    assert module.memory_low(), "under it, it is stopped"


def test_nothing_in_the_service_the_keeper_or_the_loader_pauses_the_reader(spark):
    module, _, _ = spark(idle=115)
    service = (SPARK / "media_spark.py").read_text()
    assert not hasattr(module, "resume_reader") and "_step_aside('paused'" not in service
    loop = (SPARK / "safety-reader.sh").read_text()
    assert "paused" not in loop and "job_waiting" in loop, "it yields the lock to a waiting job only when it is down"


def test_the_three_places_that_name_the_readers_container_agree(spark):
    module, _, _ = spark(idle=115)
    load = (SPARK / "safety-reader-load.sh").read_text()
    loop = (SPARK / "safety-reader.sh").read_text()
    assert module.READER_NAME == READER
    assert f"NAME={READER}\n" in load and f"docker wait {READER} " in loop
