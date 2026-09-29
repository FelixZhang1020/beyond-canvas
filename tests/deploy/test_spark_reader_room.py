"""On the Spark one model stays loaded between jobs: NVIDIA's safety reader (~11 GiB),
for the class's second look. A clip needs ~85 GiB at its peak and the box keeps a 24 GiB floor, because
it freezes rather than failing when memory runs out. So a job that does not fit beside the reader asks
it to step aside, and it loads again after the job (deploy/spark/safety-reader.sh).
"""
import importlib
import sys
from pathlib import Path

import pytest

SPARK = Path("deploy/spark").resolve()
READER = "nemotron-safety"


class Box:
    """Memory as MemAvailable reports it, and whether the reader's container is running."""

    def __init__(self, idle, reader=True):
        self.idle, self.reader, self.stopped = idle, reader, []

    def available(self):
        return self.idle - (11 if self.reader else 0)

    def run(self, argv, **kwargs):
        if argv[:2] == ["docker", "stop"]:
            self.reader = False
            self.stopped.append(argv[-1])
        return type("Done", (), {"returncode": 0, "stdout": "", "stderr": ""})()


@pytest.fixture
def spark(monkeypatch, tmp_path):
    monkeypatch.syspath_prepend(str(SPARK))
    module = importlib.import_module("media_spark")
    waited = []

    def world(idle, reader=True):
        box = Box(idle, reader)
        monkeypatch.setattr(module, "RESIDENT", tmp_path / "resident")
        monkeypatch.setattr(module.memory_guard, "available_gib", box.available)
        monkeypatch.setattr(module, "reader_up", lambda: box.reader)
        monkeypatch.setattr(module.subprocess, "run", box.run)
        monkeypatch.setattr(module.time, "sleep", waited.append)
        return module, box, waited
    yield world
    sys.modules.pop("media_spark", None)


def test_a_clip_asks_the_reader_to_step_aside_at_once_and_it_loads_again_after(spark):
    module, box, waited = spark(idle=115)
    assert module.room_for("wan2.2-i2v-a14b")
    assert box.stopped == [READER] and waited == [], "stopped at once, no waiting out a poll"
    assert (module.RESIDENT / "paused").is_file(), "it loads again only once the job lifts the pause"
    module.resume_reader()
    assert not (module.RESIDENT / "paused").exists()


def test_a_3d_job_fits_beside_the_reader_and_stops_nothing(spark):
    module, box, _ = spark(idle=115)
    assert module.room_for("trellis2") and box.stopped == []


def test_a_job_that_would_not_fit_without_the_reader_either_leaves_it_loaded(spark):
    """Other work on the box can hold the memory; stopping the reader then only loses its looks."""
    module, box, _ = spark(idle=100)
    assert not module.room_for("wan2.2-i2v-a14b") and box.stopped == []
    assert not (module.RESIDENT / "paused").exists()


def test_with_the_reader_not_running_a_job_that_does_not_fit_is_refused(spark):
    module, box, _ = spark(idle=100, reader=False)
    assert not module.room_for("wan2.2-i2v-a14b") and box.stopped == []


def test_the_job_lifts_the_pause_it_set_and_no_other(spark):
    module, box, _ = spark(idle=115)
    module.RESIDENT.mkdir(parents=True)
    (module.RESIDENT / "paused").write_text("1")
    module.resume_reader()
    assert (module.RESIDENT / "paused").read_text() == "1", "a pause another service set is not ours to lift"


def test_the_three_places_that_name_the_readers_container_agree(spark):
    module, _, _ = spark(idle=115)
    load = (SPARK / "safety-reader-load.sh").read_text()
    loop = (SPARK / "safety-reader.sh").read_text()
    assert module.READER_NAME == READER
    assert f"NAME={READER}\n" in load and f"docker wait {READER} " in loop
