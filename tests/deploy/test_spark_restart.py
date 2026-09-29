"""The script a standing permission points at, and the refusal that makes that safe.

restart.sh exists so that "an agent may restart Spark services without asking" can be written down
as one narrow rule instead of "an agent may run anything on the node". That is only true if the
script genuinely cannot be talked into running something else, so the tests that matter here are
the refusals: an unknown name must be turned away, and it must be turned away BEFORE a connection
is opened, or a typo would leave a service stopped.

`ssh` is a stub on PATH that records the command it was given. What reaches the node is the point;
whether the node answers is not, and there is no node in a test.
"""
import os
import re
import runpy
import subprocess
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
RESTART = ROOT / "deploy/spark/restart.sh"


@pytest.fixture
def spark(tmp_path):
    """A stub ssh on PATH that writes down what it was asked to run, and succeeds."""
    log = tmp_path / "ssh-calls.txt"
    stub = tmp_path / "ssh"
    stub.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$SSH_LOG"\nexit "${SSH_EXIT:-0}"\n')
    stub.chmod(0o755)

    def run(*args, busy=False):
        env = {**os.environ, "PATH": f"{tmp_path}:{os.environ['PATH']}", "SSH_LOG": str(log),
               "SSH_EXIT": "3" if busy else "0"}
        done = subprocess.run(["sh", str(RESTART), *args], capture_output=True, text=True, env=env)
        calls = log.read_text().splitlines() if log.exists() else []
        return done, calls

    return run


def test_a_name_it_does_not_know_is_refused_without_touching_the_node(spark):
    done, calls = spark("rm -rf /")
    assert done.returncode == 2
    assert "does not know a service called" in done.stderr
    assert calls == [], "a refused name must never reach the node"


def test_the_refusal_names_the_word_it_refused(spark):
    done, _ = spark("studioo")
    assert "'studioo'" in done.stderr, "the teacher should see which word was wrong"


def test_a_typo_in_the_second_name_stops_nothing_at_all(spark):
    """Every name is checked before any is stopped, so a half-done restart is impossible."""
    done, calls = spark("studio", "medai-video")
    assert done.returncode == 2
    assert calls == [], "the good name must not be acted on when a later one is bad"


def test_a_known_service_is_stopped_and_start_sh_is_asked_to_bring_it_back(spark):
    done, calls = spark("studio")
    assert done.returncode == 0, done.stderr
    assert len(calls) == 1
    assert "tmux kill-session -t studio" in calls[0]
    assert "start.sh" in calls[0]


def test_several_services_go_in_one_connection(spark):
    done, calls = spark("media-video", "media-trellis")
    assert done.returncode == 0, done.stderr
    assert len(calls) == 1, "one connection, not one per service"
    assert "tmux kill-session -t media-video" in calls[0]
    assert "tmux kill-session -t media-trellis" in calls[0]


def test_nothing_but_kill_session_and_start_sh_ever_reaches_the_node(spark):
    """The safety property spelled out: no other command can be made to travel."""
    _, calls = spark("door")
    sent = calls[0]
    body = re.split(r"\S+@\S+ ", sent, maxsplit=1)[1]   # after the ssh host, whatever its account
    # The one fixed wrapper around them: the lock the media service shares.
    wrapper = "mkdir -p ~/spark-media && flock ~/spark-media/restart.lock sh -c "
    assert body.startswith(wrapper), body
    body = body[len(wrapper):]
    for piece in body.split(";"):
        piece = piece.strip().strip("'\"").strip()
        if not piece or piece == "|| true":
            continue
        assert piece.startswith("tmux kill-session -t ") or piece.startswith("sh ~/beyond-canvas/"), \
            f"unexpected command sent to the node: {piece!r}"


def test_every_name_it_accepts_is_one_start_sh_knows_how_to_bring_back(spark):
    """A name this script stops but start.sh never starts would leave the node short a service."""
    listed = spark("--list")[0].stdout.split()
    start = (ROOT / "deploy/spark/start.sh").read_text()
    for name in listed:
        assert f"up {name} " in start or f'-t "{name}"' in start or name in start, \
            f"restart.sh offers {name}, but start.sh does not bring it up"


def test_asking_for_nothing_explains_itself_instead_of_restarting_everything(spark):
    done, calls = spark()
    assert done.returncode == 2
    assert "usage:" in done.stderr
    assert calls == [], "no argument must not be read as 'all of them'"


def test_a_restart_that_would_lose_a_clip_being_made_is_refused(spark):
    """A studio restart once cut off a clip 6 1/2 minutes into its 12."""
    done, calls = spark("studio", busy=True)
    assert done.returncode == 3 and "still running" in done.stderr and "--while-busy" in done.stderr
    assert len(calls) == 1, "a refusal is an answer, not a dropped connection to retry"


def test_the_count_and_the_restart_happen_in_one_step_under_the_shared_lock(spark):
    """Code review: counted in one connection and restarted in another, a job could start between."""
    _, calls = spark("studio")
    sent = calls[0]
    assert "flock ~/spark-media/restart.lock" in sent
    assert sent.index("media-extra/jobs") < sent.index("tmux kill-session -t studio") < sent.index("start.sh")
    assert sent.index("studio_idle.py") < sent.index("tmux kill-session -t studio")


def test_studio_restart_guard_requires_zero_finished_requests():
    idle = runpy.run_path(str(ROOT / "deploy/spark/studio_idle.py"))["idle"]
    assert idle({"active_requests": 0})
    assert not idle({"active_requests": 1})
    assert not idle({"active_requests": True})
    assert not idle({"ok": True}), "a studio without the guard field must fail closed"


def test_start_sh_is_told_what_was_stopped_so_its_log_can_say_who_restarted_it(spark):
    """The studio was once down four minutes mid-class and nothing in its log said why."""
    _, calls = spark("studio", "door")
    assert "start.sh studio door'" in calls[0]


@pytest.mark.parametrize("told, why", [("studio", "restarted by restart.sh"), ("", "it was not running")])
def test_every_start_leaves_a_dated_line_saying_why(tmp_path, told, why):
    """start.sh's own `up`, run with a stand-in tmux that has no sessions."""
    import re
    text = (ROOT / "deploy/spark/start.sh").read_text()
    up = re.search(r'^STOPPED=.*?^}\n', text, re.S | re.M).group(0)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "tmux").write_text('#!/bin/sh\n[ "$1" = has-session ] && exit 1\nexit 0\n')
    (bin_dir / "tmux").chmod(0o755)
    (tmp_path / "logs").mkdir()
    env = {**os.environ, "HOME": str(tmp_path), "PATH": f"{bin_dir}:{os.environ['PATH']}"}
    script = f'set -eu\n{up}up studio "true"\n'
    subprocess.run(["sh", "-c", script, "start.sh", *told.split()], env=env, check=True)
    line = (tmp_path / "logs" / "studio.log").read_text().strip()
    assert re.fullmatch(rf"\d\d/\w+/\d{{4}} \d\d:\d\d:\d\d start\.sh: starting studio \({why}\)", line), line


def remote(calls):
    """The command as it reaches the node, without ssh's own options and host."""
    return re.split(r"\S+@\S+ ", calls[0], maxsplit=1)[1]


@pytest.mark.parametrize("jobs, left, class_busy, restarted",
                         [(1, 0, False, False), (0, 0, True, False), (0, 0, False, True), (0, 1, False, True)])
def test_on_the_node_a_job_folder_stops_the_restart_and_none_lets_it_through(spark, tmp_path, jobs, left, class_busy,
                                                                               restarted):
    """The node's half, run for real: flock, the count and the stop, with start.sh and tmux standing in.

    The studio's own answer stands in as well (deploy/spark/studio_idle.py asks the live studio whether a
    class request is still running): the real one here would ask the class beside this test. The
    pretend node used to have none, the question always failed, and a restart with nothing running
    was refused as busy, so the test that the guard lets an idle node through was red for two days.

    tmux stands in too, and gets a server folder of its own. tmux finds its server through
    /tmp/tmux-UID, not HOME, and this test runs on the Spark beside the class: before this, a
    real `tmux kill-session -t studio` here closed the live studio, twice in one evening.

    `left` is a folder a crashed service left four hours ago: counted as a job, it refused every restart
    until someone removed it by hand (code review).
    """
    import shutil
    if not shutil.which("flock"):
        pytest.skip("flock is the node's (util-linux); the Mac has none")
    _, calls = spark("studio")
    home = tmp_path / "node"
    (home / "spark-media" / "media-extra" / "jobs").mkdir(parents=True)
    for n in range(jobs):
        (home / "spark-media" / "media-extra" / "jobs" / f"media-{n}").mkdir()
    for n in range(left):
        stale = home / "spark-media" / "media-extra" / "jobs" / f"media-left-{n}"
        stale.mkdir()
        os.utime(stale, (time.time() - 4 * 3600,) * 2)
    start = home / "beyond-canvas" / "deploy" / "spark" / "start.sh"
    start.parent.mkdir(parents=True)
    start.write_text("touch ~/started\n")
    (start.parent / "studio_idle.py").write_text(f"import sys\nsys.exit({3 if class_busy else 0})\n")
    bin_dir, tmux_log = tmp_path / "node-bin", tmp_path / "tmux-calls.txt"
    bin_dir.mkdir()
    (bin_dir / "tmux").write_text(f'#!/bin/sh\nprintf "%s\\n" "$*" >> "{tmux_log}"\n')
    (bin_dir / "tmux").chmod(0o755)
    (tmp_path / "tmux-server").mkdir()
    env = {**os.environ, "HOME": str(home), "PATH": f"{bin_dir}:{os.environ['PATH']}",
           "TMUX_TMPDIR": str(tmp_path / "tmux-server")}
    env.pop("TMUX", None)
    ran = subprocess.run(["sh", "-c", remote(calls)], env=env, capture_output=True, text=True)
    assert (ran.returncode == 0) is restarted and (home / "started").exists() is restarted
    stopped = tmux_log.read_text().splitlines() if tmux_log.exists() else []
    assert stopped == (["kill-session -t studio"] if restarted else []), "only the stand-in tmux may be asked"


def test_with_no_job_running_the_restart_goes_ahead(spark):
    done, calls = spark("studio")
    assert done.returncode == 0 and any("kill-session -t studio" in call for call in calls)


def test_a_deliberate_restart_skips_the_count(spark):
    done, calls = spark("--while-busy", "media-video")
    assert done.returncode == 0 and "media-extra/jobs" not in calls[0]


def test_a_keeper_restart_needs_no_busy_check(spark):
    """Restarting a keeper leaves its loaded model and any job alone (keeper-common.sh adopts it)."""
    done, calls = spark("qwen-front")
    assert done.returncode == 0 and "media-extra/jobs" not in calls[0]


def test_every_start_removes_the_job_folders_a_crash_left_and_keeps_the_live_ones(tmp_path):
    """The line start.sh runs, run for real on a pretend media folder: a folder four hours old holds a
    child's drawing that no job will ever clear, and one made a minute ago is a job still running."""
    line = next(text for text in (ROOT / "deploy/spark/start.sh").read_text().splitlines()
                if text.startswith('find "$MEDIA/media-extra/jobs"'))
    jobs = tmp_path / "media-extra" / "jobs"
    live, left = jobs / "media-live", jobs / "media-left"
    for folder in (live, left):
        folder.mkdir(parents=True)
        (folder / "input.png").write_bytes(b"PNG")
    os.utime(left, (time.time() - 4 * 3600,) * 2)
    subprocess.run(["sh", "-c", line], env={**os.environ, "MEDIA": str(tmp_path)}, check=True)
    assert live.exists() and not left.exists()
    assert "-mmin -180" in RESTART.read_text() and "-mmin +180" in line, "the count and the clean-up agree"
