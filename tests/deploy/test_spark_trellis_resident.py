"""TRELLIS.2 stays loaded between 3D jobs on the Spark (deploy/spark/trellis-resident.sh).

Loading is about 40% of a job and the sketch entrance is where a child waits, so the weights stay on the
chip. A clip needs ~85 GiB and the box keeps a 24 GiB floor, so a clip asks the loaded model to step aside
before it asks NVIDIA's safety reader to: memory that costs nothing to give back goes first, and a class
keeps its second safety look for as long as possible.
"""
import importlib
import socket
import sys
import threading
import time
from pathlib import Path

import pytest

SPARK = Path("deploy/spark").resolve()
TRELLIS = "beyond-canvas-trellis-resident"
READER = "nemotron-safety"


class Box:
    """Memory as MemAvailable reports it, with the loaded model and the reader each holding theirs."""

    def __init__(self, idle, resident=True, reader=True):
        self.idle, self.resident, self.reader, self.stopped = idle, resident, reader, []

    def available(self):
        return self.idle - (30 if self.resident else 0) - (11 if self.reader else 0)

    def run(self, argv, **kwargs):
        if argv[:2] == ["docker", "stop"]:
            if argv[-1] == TRELLIS:
                self.resident = False
            else:
                self.reader = False
            self.stopped.append(argv[-1])
        return type("Done", (), {"returncode": 0, "stdout": "", "stderr": ""})()


@pytest.fixture
def spark(monkeypatch, tmp_path):
    monkeypatch.syspath_prepend(str(SPARK))
    module = importlib.import_module("media_spark")

    def world(idle, resident=True, reader=True):
        box = Box(idle, resident, reader)
        monkeypatch.setattr(module, "RESIDENT", tmp_path / "resident")
        monkeypatch.setattr(module.memory_guard, "available_gib", box.available)
        monkeypatch.setattr(module, "reader_up", lambda: box.reader)
        monkeypatch.setattr(module, "trellis_ready", lambda: box.resident)
        monkeypatch.setattr(module.subprocess, "run", box.run)
        monkeypatch.setattr(module.time, "sleep", lambda seconds: None)
        return module, box
    yield world
    sys.modules.pop("media_spark", None)


def test_a_3d_job_goes_to_the_loaded_model_when_it_answers(spark, tmp_path):
    module, _ = spark(idle=145)
    command = module.command(tmp_path, tmp_path / "job-1", "trellis2", "beyond-canvas-media-job-1")
    assert command[0] == sys.executable and command[1].endswith("trellis_client.py")
    assert command[2] == str(tmp_path / "job-1")


def test_a_3d_job_starts_its_own_container_when_nothing_is_loaded(spark, tmp_path):
    module, _ = spark(idle=145, resident=False)
    command = module.command(tmp_path, tmp_path / "job-1", "trellis2", "beyond-canvas-media-job-1")
    assert command[0] == "docker" and "/runner/trellis_worker.py" in command


def test_a_3d_job_needs_far_less_room_when_the_model_is_already_loaded(spark):
    """Loaded, the weights are already counted against MemAvailable; only the job's own work is left."""
    module, box = spark(idle=100)
    assert module.room_for("trellis2") and box.stopped == []


def test_a_clip_asks_the_loaded_model_to_step_aside_before_the_safety_reader(spark):
    module, box = spark(idle=145)
    assert module.room_for("wan2.2-i2v-a14b")
    assert box.stopped == [TRELLIS], "the reader keeps looking as long as the memory allows"
    assert (module.RESIDENT / "trellis-paused").is_file()
    module.resume_resident()
    assert not (module.RESIDENT / "trellis-paused").exists()


def test_a_clip_that_needs_both_takes_both_and_gives_both_back(spark):
    """With 115 idle, the loaded model's 30 GiB is not enough on its own: the reader's 11 goes too."""
    module, box = spark(idle=115)
    assert module.room_for("wan2.2-i2v-a14b")
    assert box.stopped == [TRELLIS, READER]
    module.resume_resident()
    module.resume_reader()
    assert not (module.RESIDENT / "trellis-paused").exists() and not (module.RESIDENT / "paused").exists()


def test_a_job_lifts_only_the_pause_it_set_itself(spark):
    module, _ = spark(idle=145)
    module.RESIDENT.mkdir(parents=True)
    (module.RESIDENT / "trellis-paused").write_text("1")
    module.resume_resident()
    assert (module.RESIDENT / "trellis-paused").read_text() == "1"


def test_the_loaded_model_is_ready_only_once_its_socket_answers(monkeypatch, tmp_path):
    """The socket exists only after the weights are on the chip, so answering is what ready means."""
    monkeypatch.syspath_prepend(str(SPARK))
    module = importlib.import_module("media_spark")
    monkeypatch.setattr(module, "RESIDENT", tmp_path)
    assert not module.trellis_ready(), "no socket, not ready"
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
        server.bind(str(tmp_path / "trellis.sock"))
        server.listen(1)
        assert module.trellis_ready()
    sys.modules.pop("media_spark", None)


def test_a_job_the_loaded_model_dropped_is_run_again_in_its_own_container(spark):
    """Measured on the node: the loaded model was stopped under a running job (a pause left by
    a service that had been restarted) and the child's 3D model was simply lost. The job is worth one more
    attempt, which takes the container path because nothing is loaded any more."""
    module, box = spark(idle=145)
    tries = []

    def attempt():
        tries.append(module.trellis_ready())
        if len(tries) == 1:
            box.resident = False   # it went away under us
            raise OSError('worker failed')
        return 'made'

    assert module.once_more_without_the_resident(attempt, 'trellis2', lambda: False) == 'made'
    assert tries == [True, False], "the second attempt runs with nothing loaded"


def test_a_job_that_failed_on_its_own_is_not_run_twice(spark):
    """A drawing the model cannot build fails the same way twice; only a model that vanished earns a retry."""
    module, _box = spark(idle=145)
    tries = []

    def attempt():
        tries.append(1)
        raise OSError('worker failed')

    with pytest.raises(OSError):
        module.once_more_without_the_resident(attempt, 'trellis2', lambda: False)
    assert tries == [1]


def test_a_teacher_who_walked_away_does_not_get_a_second_attempt(spark):
    module, box = spark(idle=145)
    tries = []

    def attempt():
        tries.append(1)
        box.resident = False
        raise OSError('cancelled')

    with pytest.raises(OSError):
        module.once_more_without_the_resident(attempt, 'trellis2', lambda: True)
    assert tries == [1]


def test_a_job_reaches_the_media_servers_own_worker_exactly_once(spark, tmp_path):
    """The Spark's handler replaces media_server.Handler, so calling that name inside it calls itself for
    ever: every 3D job and every clip on the node once died of it, and the tests above did not
    notice because they never went through the handler."""
    module, _ = spark(idle=145)
    original = module.SparkHandler.__mro__[1]
    calls = []

    def base_generate(self, job, model):
        calls.append(model)
        return "made"

    kept, original.generate = original.generate, base_generate
    try:
        handler = object.__new__(module.SparkHandler)
        handler.disconnected = lambda: False
        assert module.SparkHandler.generate(handler, tmp_path, "trellis2") == "made"
        assert calls == ["trellis2"]
    finally:
        original.generate = kept


def test_the_three_places_that_name_the_loaded_models_container_agree(spark):
    module, _ = spark(idle=145)
    load = (SPARK / "trellis-resident-load.sh").read_text()
    loop = (SPARK / "trellis-resident.sh").read_text()
    assert module.TRELLIS_RESIDENT_NAME == TRELLIS
    assert f"NAME={TRELLIS}\n" in load and f"docker wait {TRELLIS} " in loop


def talk(socket_path, line):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(10)
        client.connect(str(socket_path))
        client.sendall(line)
        return client.makefile("rb").readline().decode().strip()


def test_the_resident_builds_one_model_per_connection_and_dies_on_a_failure(monkeypatch, tmp_path):
    """A job that fails ends the process: an error on the chip can leave the model unusable while the
    socket still accepts, and every later job would fail the same way, unseen."""
    monkeypatch.syspath_prepend(str(SPARK))
    resident = importlib.import_module("trellis_resident")
    jobs, built, ended = tmp_path / "jobs", [], []
    for name in ("good", "bad"):
        (jobs / name).mkdir(parents=True)
        (jobs / name / "input.png").write_bytes(b"PNG")

    def build(job):
        built.append(job.name)
        if job.name == "bad":
            raise RuntimeError("the chip said no")

    socket_path = tmp_path / "trellis.sock"
    server = threading.Thread(target=resident.serve, daemon=True,
                              args=(build, socket_path, jobs, lambda: ended.append(True)))
    server.start()
    for _ in range(100):
        if socket_path.exists():
            break
        time.sleep(.05)
    assert talk(socket_path, b"good\n") == "ok" and built == ["good"]
    assert talk(socket_path, b"nowhere\n") == "error bad-job", "a folder it was not given is refused"
    assert talk(socket_path, b"../escape\n") == "error bad-job", "and so is a path out of the jobs folder"
    assert talk(socket_path, b"bad\n") == "error RuntimeError"
    for _ in range(100):  # the answer is sent before the process is ended, so the end can trail the reply
        if ended:
            break
        time.sleep(.02)
    assert ended == [True] and built == ["good", "bad"]
    sys.modules.pop("trellis_resident", None)


class Worker:
    """A started worker as Popen reports it: what it was run with, and whether it is still going."""

    def __init__(self, argv, running):
        self.args, self._running = argv, running

    def poll(self):
        return None if self._running else 0


def resident_worker(running):
    """A job handed to the loaded model: a socket client, and no container of its own."""
    return Worker([sys.executable, str(SPARK / "trellis_client.py"), "/jobs/abc"], running)


def own_container_worker(running):
    return Worker(["docker", "run", "--rm", "--name", "beyond-canvas-media-1", "trellis2"], running)


def quiet_cleanup(module, monkeypatch, seen=None):
    """media_server's own cleanup, stubbed: it talks to a real Docker, which no test has."""
    monkeypatch.setattr(module, "_media_server_cleanup_job",
                        lambda name, process: seen.append(name) if seen is not None else None)


def test_a_3d_job_stopped_mid_run_takes_the_loaded_model_down_with_it(spark, monkeypatch):
    """An earlier finding: cancelling one of these stopped the socket client and nothing else.

    The building goes on inside the resident container, which media_server's cleanup never names, so a
    cancelled, timed-out or memory-stopped job kept generating after the GPU lock was released. The worst
    of it is the memory floor: this node freezes rather than failing one process when memory runs out, and
    the floor could no longer stop the work that was eating the memory.
    """
    module, box = spark(idle=145)
    quiet_cleanup(module, monkeypatch)
    module.cleanup_job("beyond-canvas-media-1", resident_worker(running=True))
    assert TRELLIS in box.stopped
    assert (module.RESIDENT / "trellis-paused").is_file(), "resume_resident must be able to lift it again"


def test_a_3d_job_that_finished_leaves_the_model_loaded(spark, monkeypatch):
    """Keeping it loaded is the whole point; only a job being stopped mid-run takes it down."""
    module, box = spark(idle=145)
    quiet_cleanup(module, monkeypatch)
    module.cleanup_job("beyond-canvas-media-1", resident_worker(running=False))
    assert box.stopped == []


def test_a_job_in_its_own_container_never_touches_the_loaded_model(spark, monkeypatch):
    module, box = spark(idle=145)
    quiet_cleanup(module, monkeypatch)
    module.cleanup_job("beyond-canvas-media-1", own_container_worker(running=True))
    assert box.stopped == []


def test_a_job_that_never_started_has_nothing_to_stop(spark, monkeypatch):
    module, box = spark(idle=145)
    quiet_cleanup(module, monkeypatch)
    module.cleanup_job("beyond-canvas-media-1", None)
    assert box.stopped == []


def test_the_media_servers_own_cleanup_still_runs(spark, monkeypatch):
    """Ours adds to that cleanup; it must not replace it, or the worker container is never removed."""
    module, box = spark(idle=145)
    seen = []
    quiet_cleanup(module, monkeypatch, seen)
    module.cleanup_job("beyond-canvas-media-1", resident_worker(running=True))
    assert seen == ["beyond-canvas-media-1"]


def test_the_model_is_stopped_even_when_the_workers_cleanup_raises(spark, monkeypatch):
    """media_server raises when it cannot prove the worker stopped. The memory must come back regardless:
    that path is the one where something is still running, which is exactly when this matters."""
    def unconfirmed(name, process):
        raise OSError("worker cleanup unconfirmed; legacy model stays paused")

    module, box = spark(idle=145)
    monkeypatch.setattr(module, "_media_server_cleanup_job", unconfirmed)
    with pytest.raises(OSError):
        module.cleanup_job("beyond-canvas-media-1", resident_worker(running=True))
    assert TRELLIS in box.stopped


def test_the_media_server_reaches_this_cleanup_and_this_one_does_not_call_itself(spark):
    """The same trap that once made every job recurse: media_server.Handler was replaced and then
    called by name. The original is captured before the override, so ours calls it and not itself."""
    module, _ = spark(idle=145)
    assert module.media_server.cleanup_job is module.cleanup_job
    assert module._media_server_cleanup_job is not module.cleanup_job
