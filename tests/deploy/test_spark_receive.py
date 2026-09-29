"""The node's own refusal of a send that would put the class backwards.

This is the half of the rollback guard that the sending side cannot do. sync.sh
checks itself, but a session working from an old checkout runs the old sync.sh,
which has no check -- the guard lives in the file a stale copy replaces. Three
such sends once overwrote the class in one afternoon, each looking
like a success to whoever sent it.

What can only go wrong here: taking a send that lacks what the class runs, refusing one
that holds it, refusing the first send onto a machine that has never had one, and letting
anything but this script write the class's code.
"""

import subprocess
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
RECEIVE = ROOT / "deploy/spark/receive.sh"


@pytest.fixture
def node(tmp_path):
    """A stand-in for the node's home, with an archive ready to take."""
    home = tmp_path / "home"
    home.mkdir()
    payload = tmp_path / "payload"
    (payload / "studio").mkdir(parents=True)
    (payload / "studio" / "page.txt").write_text("the page this send carries\n")
    archive = tmp_path / "send.tgz"
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(payload / "studio", arcname="studio")
    return home, archive


def receive(node, count, rev="abc1234", anyway=False, ancestors=None):
    """Hand the node a send. `ancestors` is the sending checkout's commit list; None sends none at all."""
    home, archive = node
    import os

    env = dict(os.environ, HOME=str(home))
    if anyway:
        env["BEYOND_CANVAS_ANYWAY"] = "1"
    args = ["sh", str(RECEIVE), str(count), rev, str(archive)]
    if ancestors is not None:
        listed = home / "ancestors.txt"
        listed.write_text("".join(f"{commit}0000000000000000000000000000000000\n" for commit in ancestors))
        args.append(str(listed))
    return subprocess.run(args, capture_output=True, text=True, env=env, timeout=60)


def held(node):
    record = node[0] / ".beyond-canvas-version"
    return record.read_text().split() if record.is_file() else None


def test_a_machine_that_has_never_had_a_send_takes_the_first_one(node):
    """A fresh node has to start somewhere; refusing here means it never can."""
    done = receive(node, 500)
    assert done.returncode == 0, done.stderr
    assert held(node) == ["500", "abc1234"]
    assert (node[0] / "beyond-canvas" / "studio" / "page.txt").is_file()


def test_a_send_that_holds_what_the_class_runs_is_taken_and_recorded(node):
    assert receive(node, 500, "abc1234").returncode == 0
    done = receive(node, 501, "def5678", ancestors=["def5678", "abc1234"])
    assert done.returncode == 0, done.stderr
    assert held(node) == ["501", "def5678"]


def test_the_same_send_again_is_taken(node):
    """Two windows sending the same code is ordinary, not a rollback."""
    assert receive(node, 500).returncode == 0
    assert receive(node, 500, ancestors=["abc1234"]).returncode == 0
    assert held(node) == ["500", "abc1234"]


def test_a_send_that_lacks_what_the_class_runs_is_refused_and_names_both(node):
    """The shape those sends took: a stale checkout sending over newer work."""
    assert receive(node, 501, "eee0001").returncode == 0
    done = receive(node, 499, "ddd0002", ancestors=["ddd0002", "ccc0003"])
    assert done.returncode == 1, done.stdout
    assert "REFUSED" in done.stderr
    assert "eee0001" in done.stderr, "it did not say what the class runs"
    assert "ddd0002" in done.stderr, "it did not say what was sent"
    assert held(node) == ["501", "eee0001"], "the record moved despite the refusal"


def test_a_stale_branch_with_more_commits_is_still_refused(node):
    """Code review: counting commits took a stale branch whose own commits outnumbered main's."""
    assert receive(node, 501, "eee0001").returncode == 0
    done = receive(node, 900, "bbb0009", ancestors=["bbb0009", "ccc0003"])
    assert done.returncode == 1 and "does not hold what the class is running" in done.stderr


def test_a_send_from_a_sync_that_sends_no_commit_list_is_refused(node):
    """A sync.sh older than the ancestry check: the node cannot tell, so it does not guess."""
    assert receive(node, 501, "eee0001").returncode == 0
    done = receive(node, 600, "fff0006")
    assert done.returncode == 1 and "from an older sync.sh" in done.stderr
    assert held(node) == ["501", "eee0001"]


def test_an_older_send_asked_for_deliberately_is_taken(node):
    assert receive(node, 501, "eee0001").returncode == 0
    done = receive(node, 499, "ddd0002", anyway=True, ancestors=["ddd0002"])
    assert done.returncode == 0, done.stderr
    assert "deliberately" in done.stdout
    assert held(node) == ["499", "ddd0002"]


def test_something_that_is_not_a_count_or_a_revision_is_refused_rather_than_guessed(node):
    done = receive(node, "not-a-number")
    assert done.returncode == 2 and "not a count" in done.stderr
    done = receive(node, 500, "no;such rev")
    assert done.returncode == 2 and "not a revision" in done.stderr


def test_a_send_whose_archive_never_arrived_is_refused(node):
    home, archive = node
    archive.unlink()
    done = receive((home, archive), 500)
    assert done.returncode == 2
    assert "no archive" in done.stderr


def test_the_class_code_is_locked_between_sends_so_nothing_else_can_write_it(node):
    """Code review: an old sync.sh unpacked straight into the tree without asking the receiver."""
    import os
    import tarfile as tf
    if os.geteuid() == 0:
        pytest.skip("root writes through any lock; the node runs as its own user")
    home, archive = node
    assert receive(node, 500).returncode == 0
    page = home / "beyond-canvas" / "studio" / "page.txt"
    with pytest.raises(PermissionError):
        page.write_text("an old sync.sh writing past the receiver\n")
    old_style = subprocess.run(["tar", "-xzf", str(archive), "-C", str(home / "beyond-canvas")],
                               capture_output=True, text=True)
    assert old_style.returncode != 0, "a direct unpack went through the lock"
    assert page.read_text() == "the page this send carries\n"
    again = receive(node, 501, "def5678", ancestors=["def5678", "abc1234"])
    assert again.returncode == 0, "the receiver itself must still get through: " + again.stderr
    with pytest.raises(PermissionError):
        page.write_text("still locked afterwards\n")


def test_a_folder_send_goes_through_the_lock_and_records_no_version(node):
    home, archive = node
    import os
    env = dict(os.environ, HOME=str(home))
    done = subprocess.run(["sh", str(RECEIVE), "--folder", str(archive)], capture_output=True, text=True, env=env)
    assert done.returncode == 0, done.stderr
    assert (home / "beyond-canvas" / "studio" / "page.txt").is_file() and held(node) is None


def remove(home, paths):
    """Hand the node a list of left-over files, as compare-with-spark.sh --mend does."""
    import os

    env = dict(os.environ, HOME=str(home))
    return subprocess.run(["sh", str(RECEIVE), "--remove"], input="".join(f"{path}\n" for path in paths),
                          capture_output=True, text=True, env=env, timeout=60)


def left_over(node, *names):
    """A node that took a send and still holds files from an older one, locked in with it."""
    home, _ = node
    studio = home / "beyond-canvas" / "studio"
    studio.mkdir(parents=True)
    for name in names:
        (studio / name).write_text("from an older send\n")
    assert receive(node, 5).returncode == 0
    return studio


def test_left_over_files_are_removed_through_the_lock_and_the_folder_is_locked_again(node):
    """compare-with-spark.sh --mend's own rm failed on the lock from the day it came in, so 63 old files
    had to be removed by hand after the code was moved."""
    import os

    studio = left_over(node, "classroom.py", "an old name.py")
    done = remove(node[0], ["studio/classroom.py", "studio/an old name.py"])
    assert done.returncode == 0, done.stderr
    assert sorted(path.name for path in studio.iterdir()) == ["page.txt"]
    assert not os.access(studio, os.W_OK), "nothing else may write the class's code afterwards"


@pytest.mark.parametrize("stray", ["../.env", "studio/../../.env", ".studio/portfolio.sqlite3", "/etc/hosts"])
def test_one_path_outside_the_code_folders_and_nothing_is_removed(node, stray):
    studio = left_over(node, "classroom.py")
    done = remove(node[0], ["studio/classroom.py", stray])
    assert done.returncode == 2 and "nothing removed" in done.stderr
    assert (studio / "classroom.py").is_file()
