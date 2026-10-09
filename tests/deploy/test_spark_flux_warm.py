"""A storybook's FLUX stays loaded between the jobs of a book on the Spark (operator).

Every picture-book job used to load FLUX.2 Klein again, ~22 s each time: of the 81 s the rest of a five-page book
took, about 45 were two loads. The book's first job now starts a warm container (flux_client.py), later jobs are
handed to it (flux_book_worker.serve), it leaves ~3 minutes after the book's last job, and any other media job
that needs its ~22 GiB sends it away before anything else is asked to step aside.
"""
import importlib
import json
import sys
import threading
import time
from pathlib import Path

import pytest

SPARK = Path("deploy/spark").resolve()


@pytest.fixture
def spark(monkeypatch):
    monkeypatch.syspath_prepend(str(SPARK))
    modules = {name: importlib.import_module(name) for name in ("flux_book_worker", "flux_client", "media_spark")}
    yield modules
    for name in modules:
        sys.modules.pop(name, None)


def serving(worker, tmp_path, work, idle_s):
    jobs, sock = tmp_path / "jobs", tmp_path / "flux-book.sock"
    jobs.mkdir()
    thread = threading.Thread(target=worker.serve, args=(work,), daemon=True,
                              kwargs={"socket_path": sock, "jobs": jobs, "idle_s": idle_s, "after_failure": lambda: None})
    thread.start()
    for _ in range(100):
        if sock.exists():
            break
        time.sleep(0.02)
    return jobs, sock, thread


def job(jobs, name="one"):
    folder = jobs / name
    folder.mkdir()
    (folder / "request.json").write_text(json.dumps({"pictures": [{"image": "data:image/jpeg;base64,AAAA",
                                                                    "instruction": "watercolour", "seed": 42}]}))
    return folder


def test_a_job_handed_over_is_drawn_by_the_loaded_model_and_answered(spark, tmp_path):
    worker, client = spark["flux_book_worker"], spark["flux_client"]
    drawn = []
    jobs, sock, thread = serving(worker, tmp_path, lambda folder: (drawn.append(folder.name),
                                 (folder / "output.json").write_text('{"pictures": ["x"]}')), idle_s=5)
    started = []
    assert client.main(job(jobs), path=sock, begin=lambda: started.append(1) or True) == 0
    assert drawn == ["one"] and started == [], "already loaded: nothing started"
    assert client.main(jobs / "missing", path=sock, begin=lambda: True) == 1, "a folder with no job is refused"


def test_the_loaded_model_leaves_after_the_books_last_job_and_a_look_does_not_keep_it(spark, tmp_path):
    worker, client = spark["flux_book_worker"], spark["flux_client"]
    jobs, sock, thread = serving(worker, tmp_path, lambda folder: (folder / "output.json").write_text("{}"), idle_s=1.0)
    client.main(job(jobs), path=sock, begin=lambda: True)
    done = time.monotonic()
    time.sleep(0.6)
    assert client.answers(sock), "still loaded within its idle time"
    thread.join(timeout=3)
    assert not thread.is_alive() and time.monotonic() - done < 1.5, "the look at 0.6 s did not add another second"
    assert not sock.exists() and not client.answers(sock), "gone, and says so"


def test_a_failed_job_says_so_and_ends_the_loaded_model(spark, tmp_path):
    worker, client = spark["flux_book_worker"], spark["flux_client"]
    ended = []
    jobs, sock = tmp_path / "jobs", tmp_path / "flux-book.sock"
    jobs.mkdir()

    def fail(folder):
        raise RuntimeError("the chip said no")
    threading.Thread(target=worker.serve, args=(fail,), daemon=True, kwargs={
        "socket_path": sock, "jobs": jobs, "idle_s": 2, "after_failure": lambda: ended.append(1)}).start()
    while not sock.exists():
        time.sleep(0.02)
    assert client.main(job(jobs), path=sock, begin=lambda: True) == 1
    for _ in range(100):  # the answer is sent before the model is ended, so the end can trail the reply
        if ended:
            break
        time.sleep(0.02)
    assert ended == [1]


def test_the_first_job_of_a_book_starts_the_warm_container_and_waits_for_it_to_load(spark, monkeypatch, tmp_path):
    client = spark["flux_client"]
    monkeypatch.setattr(client, "RESIDENT", tmp_path)
    ran, looks = [], iter([False, False, True])
    ok = type("Done", (), {"returncode": 0})()
    assert client.start(run=lambda argv, **_: ran.append(argv) or ok, ready=lambda: next(looks), sleep=lambda s: None)
    assert ran[0] == ["docker", "rm", "-f", client.NAME], "one that stopped answering goes first"
    command = ran[1]
    assert command[:3] == ["docker", "run", "-d"] and "--rm" in command and command[command.index("-u") + 1].count(":") == 1
    assert f"{client.HOME}/models/flux2-klein-4b:/models/flux:ro" in command
    assert f"{client.HOME}/spark-media/media-extra/jobs:/jobs" in command and f"{tmp_path}:/resident" in command
    assert command[-3:] == ["/spark/flux_book_worker.py", "--idle", "180"], "leaves three minutes after the last job"
    never = iter([False] * 1000)
    assert not client.start(run=lambda argv, **_: ran.append(argv) or ok, ready=lambda: next(never), sleep=lambda s: None,
                            load_s=0), "a model that never loads is given up"
    assert ran[-1] == ["docker", "rm", "-f", client.NAME], "and removed, so its memory comes back"


def test_the_media_service_hands_book_jobs_over_and_sends_the_warm_model_away_for_others(spark, monkeypatch, tmp_path):
    media = spark["media_spark"]
    assert media.command(Path("/root"), Path("/job"), "flux", "worker")[1:] == [str(SPARK / "flux_client.py"), "/job"]
    warm, removed = [True], []

    def docker(argv, **_):
        if argv[:3] == ["docker", "rm", "-f"] and argv[-1] == media.FLUX_WARM_NAME:
            removed.append(argv[-1]); warm[0] = False
        return type("Done", (), {"returncode": 0, "stdout": "", "stderr": ""})()
    monkeypatch.setattr(media, "flux_warm", lambda: warm[0])
    monkeypatch.setattr(media, "trellis_ready", lambda: False)
    monkeypatch.setattr(media, "front_up", lambda: True)
    monkeypatch.setattr(media.subprocess, "run", docker)
    monkeypatch.setattr(media.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(media, "RESIDENT", tmp_path)
    monkeypatch.setattr(media.memory_guard, "available_gib", lambda: 40 if warm[0] else 62)
    monkeypatch.setattr(media.memory_guard, "total_gib", lambda: 121.69)
    assert media.peak_of("flux") == media.FLUX_JOB_GIB, "a job on the loaded model needs little"
    assert media.room_for("trellis2") and removed == [media.FLUX_WARM_NAME], "the warm FLUX went first, and alone"


def test_a_book_job_on_the_loaded_model_fits_beside_the_safety_reader_at_what_the_node_has_left(spark, monkeypatch):
    # Measured on a book: a loaded FLUX left ~27 GiB available, and a job on it adds ~2. Counted at 4 under the
    # old 24 GiB floor, every job of the book paused the safety reader and its check waited ~23 s for it.
    media = spark["media_spark"]
    stopped = []
    monkeypatch.setattr(media, "flux_warm", lambda: True)
    monkeypatch.setattr(media.memory_guard, "available_gib", lambda: 27.0)
    monkeypatch.setattr(media.memory_guard, "total_gib", lambda: 121.69)
    monkeypatch.setattr(media, "_step_aside", lambda flag, container, model: stopped.append(container) or True)
    assert media.room_for("flux") and stopped == [], "the reader stays loaded for the check that follows"


def test_a_book_job_stopped_mid_run_takes_the_warm_model_with_it(spark, monkeypatch):
    media = spark["media_spark"]
    removed = []
    monkeypatch.setattr(media, "_media_server_cleanup_job", lambda name, process: None)
    monkeypatch.setattr(media.subprocess, "run", lambda argv, **_: removed.append(argv))
    running = type("Client", (), {"args": ["python3", "/spark/flux_client.py", "/job"], "poll": lambda self: None})()
    media.cleanup_job("worker", running)
    assert removed == [["docker", "rm", "-f", media.FLUX_WARM_NAME]]
    removed.clear()
    finished = type("Client", (), {"args": ["python3", "/spark/flux_client.py", "/job"], "poll": lambda self: 0})()
    media.cleanup_job("worker", finished)
    assert removed == [], "a finished job leaves the model warm for the book's next page"
