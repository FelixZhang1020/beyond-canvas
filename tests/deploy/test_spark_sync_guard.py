"""The check that stops a send from putting the node back to older code.

Once, a send from a checkout behind main reverted two commits on the
node. Nothing failed: the studio kept the reverted server code in memory and
reads the page from disk each request, so the class simply served the old page
until someone noticed by chance. This is the thing that now notices.

The repositories here are real ones made in a temp folder, with a real remote,
because the check is `git merge-base --is-ancestor` against a real fetch and a
stand-in for git would only prove the stand-in. `ssh` and `rsync` are stubs on
PATH: the point is which sends are refused, not what reaches the node.
"""
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SYNC = ROOT / "deploy/spark/sync.sh"


def git(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True).stdout


@pytest.fixture
def checkout(tmp_path):
    """A clone whose origin has one commit more than it, and stubs for the network."""
    origin = tmp_path / "origin"
    origin.mkdir()
    git(origin, "init", "--quiet", "--initial-branch=main")
    git(origin, "config", "user.email", "t@example.com")
    git(origin, "config", "user.name", "Test")
    (origin / "studio").mkdir()
    (origin / "studio" / "page.txt").write_text("the page as main has it\n")
    git(origin, "add", "-A")
    git(origin, "commit", "--quiet", "-m", "first")

    work = tmp_path / "work"
    git(tmp_path, "clone", "--quiet", str(origin), str(work))
    git(work, "config", "user.email", "t@example.com")
    git(work, "config", "user.name", "Test")
    (work / "deploy" / "spark").mkdir(parents=True)
    (work / "deploy" / "spark" / "sync.sh").write_text(SYNC.read_text(encoding="utf-8"), encoding="utf-8")
    (work / ".env").write_text("STEPFUN_API_KEY=not-a-real-key\n", encoding="utf-8")

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name in ("ssh", "rsync"):
        stub = bin_dir / name
        # rsync can run a script first, so a test can make main move mid-upload; ssh writes down what it
        # was asked to run, so a test can read what actually reaches the node rather than assuming.
        stub.write_text("#!/bin/sh\n[ -z \"${SYNC_TEST_DURING:-}\" ] || sh \"$SYNC_TEST_DURING\"\n"
                        "[ -z \"${SYNC_TEST_RSYNC_LOG:-}\" ] || printf '%s\\n' \"$*\" >> \"$SYNC_TEST_RSYNC_LOG\"\nexit 0\n"
                        if name == "rsync" else
                        "#!/bin/sh\n[ -z \"${SYNC_TEST_SSH_LOG:-}\" ] || printf '%s\\n' \"$*\" "
                        ">> \"$SYNC_TEST_SSH_LOG\"\nexit 0\n", encoding="utf-8")
        stub.chmod(0o755)
    return work, origin, bin_dir


def run(checkout, *args):
    work, _, bin_dir = checkout
    import os

    env = dict(os.environ, PATH=f"{bin_dir}:{os.environ['PATH']}", BEYOND_CANVAS_ENV=str(work / ".env"))
    env.update(getattr(run, "extra", {}))
    return subprocess.run(["sh", "deploy/spark/sync.sh", *args], cwd=work,
                          capture_output=True, text=True, env=env, timeout=120)


def fall_behind(checkout):
    """main gains a commit this checkout does not have -- the shape of that revert."""
    work, origin, _ = checkout
    (origin / "studio" / "page.txt").write_text("the page after the fix\n")
    git(origin, "add", "-A")
    git(origin, "commit", "--quiet", "-m", "the fix a send must not undo")


def test_a_checkout_behind_main_is_refused_and_told_what_it_would_undo(checkout):
    fall_behind(checkout)
    done = run(checkout)
    assert done.returncode == 1, done.stdout
    assert "behind main" in done.stderr
    assert "the fix a send must not undo" in done.stderr, "it did not say what would be lost"
    assert "--anyway" in done.stderr, "it refused without saying how to proceed"


def test_a_checkout_that_has_everything_main_has_goes_through(checkout):
    done = run(checkout)
    assert "this checkout holds everything main holds" in done.stdout
    assert "behind main" not in done.stderr


def test_a_checkout_ahead_of_main_still_sends(checkout):
    """A branch in a worktree is how the Spark work is tested; that was never the problem."""
    work, _, _ = checkout
    (work / "studio" / "new.txt").write_text("work not yet on main\n")
    git(work, "add", "-A")
    git(work, "commit", "--quiet", "-m", "not on main yet")
    done = run(checkout)
    assert "this checkout holds everything main holds" in done.stdout
    assert "behind main" not in done.stderr


def test_anyway_sends_from_a_checkout_that_is_behind(checkout):
    fall_behind(checkout)
    done = run(checkout, "--anyway")
    assert "behind main" not in done.stderr
    assert done.returncode == 0, done.stderr


def test_an_origin_it_cannot_reach_is_refused_rather_than_guessed(checkout):
    """Not knowing is the case the check exists for."""
    work, _, _ = checkout
    git(work, "remote", "set-url", "origin", str(work / "no-such-repository"))
    done = run(checkout)
    assert done.returncode == 1
    assert "cannot reach origin" in done.stderr
    assert "--anyway" in done.stderr


def test_a_folder_git_knows_nothing_about_still_sends(checkout):
    """The vendor tree folder mode exists for holds no tracked file, so it can put nothing back."""
    work, _, _ = checkout
    (work / ".gitignore").write_text("vendor/\n", encoding="utf-8")
    git(work, "add", ".gitignore")
    git(work, "commit", "--quiet", "-m", "ignore the vendor tree")
    (work / "vendor").mkdir()
    (work / "vendor" / "big.bin").write_text("weights\n")
    fall_behind(checkout)
    done = run(checkout, "vendor")
    assert "behind main" not in done.stderr, "the one folder send this mode exists for was blocked"
    assert done.returncode == 0, done.stderr


def test_a_folder_send_of_tracked_code_is_checked_like_any_other(checkout):
    """The hole an adversarial review found.

    The exemption was written as a comment saying folder mode carries only
    gitignored vendor files. Nothing enforced it, so `sync.sh studio` from a
    stale tree walked past the guard and would have overwritten the class with
    older code -- the very rollback the guard exists to stop.
    """
    fall_behind(checkout)
    done = run(checkout, "studio")
    assert done.returncode == 1, f"a folder of tracked code was sent from a stale tree: {done.stdout}"
    assert "behind main" in done.stderr
    assert "studio" in done.stderr, "it did not say which folder it was refusing"
    assert "the fix a send must not undo" in done.stderr


def test_a_folder_of_tracked_code_sends_when_the_checkout_is_not_behind(checkout):
    """Being checked is not being blocked: only a stale tree is refused."""
    done = run(checkout, "studio")
    assert done.returncode == 0, done.stderr
    assert "behind main" not in done.stderr


def test_main_moving_during_the_upload_stops_the_unpack(checkout):
    """The window the first check cannot see.

    A send takes about four minutes and this script's own notes record six-minute
    stalls. In that time someone else can land work and finish their own send, so
    a send that passed the first check arrives last and puts their work back. The
    check runs again once the upload is done, leaving about a second instead.
    """
    work, origin, _ = checkout
    during = work / "during.sh"
    during.write_text(
        f"cd {origin}\n"
        "printf 'landed while the upload ran\\n' > studio/page.txt\n"
        "git add -A\n"
        "git -c user.email=t@example.com -c user.name=Test commit --quiet -m 'landed mid-upload' || true\n",
        encoding="utf-8")
    run.extra = {"SYNC_TEST_DURING": str(during)}
    try:
        done = run(checkout)
    finally:
        run.extra = {}
    assert "this checkout holds everything main holds" in done.stdout, "the first check should have passed"
    assert done.returncode == 1, f"it unpacked over newer work: {done.stdout}"
    assert "main moved on while this was uploading" in done.stderr
    assert "landed mid-upload" in done.stderr, "it did not name the work it would have undone"


def test_the_send_looks_at_what_it_left_behind(checkout):
    """A send that only reports success is how that revert went unnoticed.

    Written first as `[ -x ... ]`, which was always false because the comparison
    script is checked in without the executable bit: the send said nothing and
    looked at nothing, which is the silent pass the check exists to stop.
    """
    work, _, _ = checkout
    compare = work / "deploy" / "spark" / "compare-with-spark.sh"
    compare.write_text("#!/bin/sh\necho 'the Spark matches this checkout'\n", encoding="utf-8")
    done = run(checkout)
    assert done.returncode == 0, done.stderr
    assert "the Spark matches this checkout" in done.stdout, "the send never looked"


def test_a_send_with_no_way_to_check_says_so_rather_than_staying_quiet(checkout):
    _, _, _ = checkout
    done = run(checkout)
    assert done.returncode == 0, done.stderr
    assert "the send was not checked" in done.stderr


def sent_to_the_node(checkout, tmp_path, *args):
    """Run a send and return what the node was actually asked to run."""
    log = tmp_path / "ssh-calls.txt"
    run.extra = {"SYNC_TEST_SSH_LOG": str(log)}
    try:
        done = run(checkout, *args)
    finally:
        run.extra = {}
    return done, (log.read_text(encoding="utf-8") if log.exists() else "")


def test_a_deliberate_rollback_reaches_the_node_and_not_only_this_script(checkout, tmp_path):
    """`--anyway` used to clear this script's checks and stop there.

    The receiver keeps its own guard on purpose, because a stale checkout runs a stale sync.sh whose
    guard cannot be trusted. Nothing carried the decision across, so the one documented way to put the
    class back to older code was refused on the node every time, however exactly it was followed.
    """
    fall_behind(checkout)
    done, sent = sent_to_the_node(checkout, tmp_path, "--anyway")
    assert done.returncode == 0, done.stderr
    assert "BEYOND_CANVAS_ANYWAY=1" in sent, "the node never heard that the rollback was meant"


def test_an_ordinary_send_carries_no_override(checkout, tmp_path):
    """The receiver's guard is the thing protecting the class; only an explicit --anyway lifts it."""
    done, sent = sent_to_the_node(checkout, tmp_path)
    assert done.returncode == 0, done.stderr
    assert "BEYOND_CANVAS_ANYWAY" not in sent


def test_the_nodes_refusal_names_a_way_out_this_script_understands():
    """The receiver printed `BEYOND_CANVAS_ANYWAY=1 sh deploy/spark/sync.sh`, which sync.sh never read:
    following the instruction exactly left the sender stuck with no way past their own refusal."""
    receive = (SYNC.parent / "receive.sh").read_text(encoding="utf-8")
    offered = [line for line in receive.splitlines() if "echo" in line and "deploy/spark/sync.sh" in line]
    assert offered, "a refusal must name a way out"
    for line in offered:
        assert "--anyway" in line, f"names a route sync.sh does not read: {line.strip()}"


def test_only_the_files_travel_and_the_node_packs_the_send(checkout, tmp_path):
    """Operator: build everything on the Spark. The Mac packed ~8 MB and sent it whole every time,
    an hour a send over a 5 KB/s relay; now rsync sends the checkout's files and the node packs."""
    rsync_log, ssh_log = tmp_path / "rsync-calls.txt", tmp_path / "ssh-calls.txt"
    run.extra = {"SYNC_TEST_RSYNC_LOG": str(rsync_log), "SYNC_TEST_SSH_LOG": str(ssh_log)}
    try:
        done = run(checkout)
    finally:
        run.extra = {}
    assert done.returncode == 0, done.stderr
    calls, sent = rsync_log.read_text(encoding="utf-8"), ssh_log.read_text(encoding="utf-8")
    assert "--files-from=" in calls and "beyond-canvas-sync-mirror-" in calls
    assert "tar --null -T ../beyond-canvas-send-" in sent and "-czf" in sent, "the node did not pack it"
