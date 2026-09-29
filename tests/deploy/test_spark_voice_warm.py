"""A storybook's child's voice on the Spark: VoxCPM2 kept loaded while a book is read (operator).

The first page of a book starts a warm container (voice_client.py, reusing flux_client.py's starting), later pages
are handed to it (voice_book_worker.py, serving as flux_book_worker.py does), and any other job that needs its
memory sends it away first; a page stopped mid-read takes it down with it.
"""
import importlib
import sys
from pathlib import Path

import pytest

SPARK = Path("deploy/spark").resolve()


@pytest.fixture
def spark(monkeypatch):
    monkeypatch.syspath_prepend(str(SPARK))
    modules = {name: importlib.import_module(name)
               for name in ("flux_client", "voice_client", "voice_book_worker", "media_spark")}
    yield modules
    for name in modules:
        sys.modules.pop(name, None)


def test_a_page_is_handed_to_the_warm_voice_and_its_container_is_the_voices_own(spark, monkeypatch, tmp_path):
    media, client = spark["media_spark"], spark["voice_client"]
    assert media.command(Path("/root"), Path("/job"), "VoxCPM2", "worker")[1:] == [str(SPARK / "voice_client.py"), "/job"]
    command = client.start_command()
    assert command[:3] == ["docker", "run", "-d"] and client.NAME in command and client.IMAGE == "beyond-canvas/voice:1"
    assert f"{client.warm.HOME}/models/voxcpm2:/models/voice:ro" in command
    assert command[-3:] == ["/spark/voice_book_worker.py", "--idle", "600"], "leaves ten minutes after the last page"
    assert client.socket_path(tmp_path) == tmp_path / "voice-book.sock"


def test_a_page_counts_as_read_once_its_recording_is_written_not_a_pictures_file(spark, monkeypatch, tmp_path):
    """First run on the node: the worker read the sentence and said ok, and the hand-over, which waited
    for the picture book's output.json, called it failed."""
    client = spark["voice_client"]
    asked = {}
    monkeypatch.setattr(client.warm, "main", lambda job, **kwargs: asked.update(kwargs) or 0)
    client.main(tmp_path)
    assert asked["output"] == "output.wav"


def test_the_shared_starter_starts_the_container_it_is_given(spark):
    warm = spark["flux_client"]
    ran = []
    ok = type("Done", (), {"returncode": 0})()
    assert warm.start(run=lambda argv, **_: ran.append(argv) or ok, ready=lambda: True, sleep=lambda s: None,
                      name="beyond-canvas-voice-warm", command=["docker", "run", "voice"])
    assert ran == [["docker", "rm", "-f", "beyond-canvas-voice-warm"], ["docker", "run", "voice"]]


def test_a_page_is_read_a_sentence_at_a_time(spark):
    sentences = spark["voice_book_worker"].sentences
    assert sentences("小鱼回家了。它们很开心！天黑了") == [
        "小鱼回家了。", "它们很开心！", "天黑了"]
    long = "鱼" * 70 + "，" + "鱼" * 10 + "。"
    assert [len(s) for s in sentences(long, most=60)] == [71, 11], "a long one breaks at its next comma"


def test_other_jobs_send_the_warm_voice_away_and_a_voice_page_never_pauses_the_chat(spark, monkeypatch, tmp_path):
    media = spark["media_spark"]
    warm, removed, stopped = [True], [], []

    def docker(argv, **_):
        if argv[:3] == ["docker", "rm", "-f"] and argv[-1] == media.VOICE_WARM_NAME:
            removed.append(argv[-1]); warm[0] = False
        if argv[:2] == ["docker", "stop"]:
            stopped.append(argv[-1])
        return type("Done", (), {"returncode": 0, "stdout": "", "stderr": ""})()
    monkeypatch.setattr(media, "voice_warm", lambda: warm[0])
    monkeypatch.setattr(media, "flux_warm", lambda: False)
    monkeypatch.setattr(media, "trellis_ready", lambda: False)
    monkeypatch.setattr(media, "front_up", lambda: True)
    monkeypatch.setattr(media, "reader_up", lambda: False)
    monkeypatch.setattr(media.subprocess, "run", docker)
    monkeypatch.setattr(media.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(media, "RESIDENT", tmp_path)
    monkeypatch.setattr(media.memory_guard, "available_gib", lambda: 40 if warm[0] else 62)
    assert media.peak_of("VoxCPM2") == media.VOICE_JOB_GIB, "a page on the loaded model needs little"
    assert media.room_for("trellis2") and removed == [media.VOICE_WARM_NAME]
    monkeypatch.setattr(media.memory_guard, "available_gib", lambda: 30)
    assert not media.room_for("VoxCPM2") and stopped == [], "short of room, a page waits; the chat voice stays"


def test_a_page_stopped_mid_read_takes_the_warm_voice_with_it(spark, monkeypatch):
    media = spark["media_spark"]
    removed = []
    monkeypatch.setattr(media, "_media_server_cleanup_job", lambda name, process: None)
    monkeypatch.setattr(media.subprocess, "run", lambda argv, **_: removed.append(argv))
    running = type("Client", (), {"args": ["python3", "/spark/voice_client.py", "/job"], "poll": lambda self: None})()
    media.cleanup_job("worker", running)
    assert removed == [["docker", "rm", "-f", media.VOICE_WARM_NAME]]
    removed.clear()
    finished = type("Client", (), {"args": ["python3", "/spark/voice_client.py", "/job"], "poll": lambda self: 0})()
    media.cleanup_job("worker", finished)
    assert removed == [], "a finished page leaves the voice warm for the next"


def test_the_voice_service_is_one_the_scripts_start_restart_and_compare(spark):
    start, restart, compare = ((SPARK / name).read_text() for name in ("start.sh", "restart.sh", "compare-with-spark.sh"))
    assert "up media-voice" in start and "--kind voice" in start and "7280" in start
    assert 'ready VoxCPM2 "$HOME/models/voxcpm2/.complete" beyond-canvas/voice:1' in start
    assert " media-voice " in restart.split("KNOWN=")[1].split("\n")[0].replace('"', " ")
    assert "\nmedia-voice:deploy/spark/media_spark.py" in compare
