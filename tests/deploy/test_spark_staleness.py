"""The check that a service is RUNNING the code the node holds, not merely storing it.

A service reads its code once, when it starts. Twice in one day that gap cost something: the fix
for a recursion that killed every 3D job and every clip sat on the node's disk while the old code
ran on in memory, and a skill's declared tools were deployed and enforced by nothing because the
studio had started before they arrived. Both times `compare-with-spark.sh` said the Spark matched,
and both times it was right -- the files did match. Nothing compared them to what was running.

What "changed" means here is git's last commit touching a service's files, not their mtime on the
node: every send unpacks the whole archive, so mtime there is the time of the last send whatever
the content, and reading it calls a service stale whenever anyone deploys anything.

`ssh` is a stub that answers the one question this part asks -- which services are up and when each
started -- and gives the file comparison nothing, because that half is not what is under test here.
"""
import subprocess
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
COMPARE = ROOT / "deploy/spark/compare-with-spark.sh"

# Files the temp repository needs for the pathspecs in the script to match something.
FILES = {
    "deploy/spark/door.py": "the door\n",
    "deploy/spark/spark_recorder.py": "the recorder\n",
    "deploy/spark/media_spark.py": "the media service\n",
    "deploy/spark/memory_guard.py": "the floor\n",
    "deploy/spark/safety-reader.sh": "the reader\n",
    "deploy/spark/trellis-resident.sh": "the resident\n",
    "deploy/spark/trellis_resident.py": "the resident's server\n",
    "deploy/gpu-media/extra/media_server.py": "the 4090's media server\n",
    "studio/serve.py": "the studio\n",
    "studio/page/index.html": "<html lang=zh></html>\n",
}


def git(repo, *args, when=None):
    env = None
    if when is not None:
        stamp = f"{when} +0000"
        import os
        env = {**os.environ, "GIT_AUTHOR_DATE": stamp, "GIT_COMMITTER_DATE": stamp}
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True, env=env).stdout


@pytest.fixture
def node(tmp_path):
    """A checkout of the script with its service files, and a stub node whose services I can time."""
    work = tmp_path / "work"
    (work / "deploy" / "spark").mkdir(parents=True)
    (work / "deploy" / "gpu-media" / "extra").mkdir(parents=True)
    (work / "studio" / "page").mkdir(parents=True)
    git(work.parent, "init", "--quiet", "--initial-branch=main", str(work))
    git(work, "config", "user.email", "t@example.com")
    git(work, "config", "user.name", "Test")
    (work / "deploy" / "spark" / "compare-with-spark.sh").write_text(COMPARE.read_text(encoding="utf-8"),
                                                                    encoding="utf-8")
    for name, text in FILES.items():
        (work / name).write_text(text, encoding="utf-8")
    base = int(time.time()) - 10_000
    git(work, "add", "-A")
    git(work, "commit", "--quiet", "-m", "everything as it stands", when=base)

    listing = tmp_path / "tmux.txt"
    stub = tmp_path / "bin"
    stub.mkdir()
    ssh = stub / "ssh"
    # The tmux question is answered from a file a test writes; the file comparison is given nothing,
    # so it reports differences and the part under test still runs.
    ssh.write_text('#!/bin/sh\ncase "$*" in *"tmux list-sessions"*) cat "$SPARK_TMUX"; exit 0;; esac\n'
                   'echo "=== holds"\nexit 0\n', encoding="utf-8")
    ssh.chmod(0o755)
    (stub / "scp").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    (stub / "scp").chmod(0o755)

    def run(services, touch=None, at=None):
        """services: {name: seconds-after-base it started}. touch: a file changed `at` seconds after base."""
        if touch:
            (work / touch).write_text("changed\n", encoding="utf-8")
            git(work, "add", "-A")
            git(work, "commit", "--quiet", "-m", f"change {touch}", when=base + at)
        listing.write_text("".join(f"{n} {base + s}\n" for n, s in services.items()), encoding="utf-8")
        import os
        env = {**os.environ, "PATH": f"{stub}:{os.environ['PATH']}", "SPARK_TMUX": str(listing)}
        return subprocess.run(["sh", "deploy/spark/compare-with-spark.sh"], cwd=work,
                              capture_output=True, text=True, env=env, timeout=120)

    return run


def test_a_service_older_than_its_own_code_is_named(node):
    done = node({"door": 100}, touch="deploy/spark/door.py", at=500)
    assert "running code older than the node holds" in done.stdout
    assert "door" in done.stdout


def test_the_report_names_the_commit_the_service_has_not_got(node):
    """A name alone leaves the reader to find out what they are missing; the commit says it."""
    done = node({"door": 100}, touch="deploy/spark/door.py", at=500)
    assert "change deploy/spark/door.py" in done.stdout


def test_the_report_names_the_command_that_fixes_it(node):
    done = node({"door": 100}, touch="deploy/spark/door.py", at=500)
    assert "restart.sh door" in done.stdout


def test_a_service_started_after_its_code_changed_is_not_named(node):
    done = node({"door": 900}, touch="deploy/spark/door.py", at=500)
    assert "running code older" not in done.stdout


def test_a_service_that_is_not_running_is_not_stale(node):
    """Nothing is running old code if nothing is running; start.sh is the answer to that, not this."""
    done = node({"studio": 900}, touch="deploy/spark/door.py", at=500)
    assert "door" not in done.stdout.replace("deploy/spark/door.py", "")


def test_a_new_page_does_not_send_anyone_to_restart_the_studio(node):
    """The studio reads its html, css and js from disk on each request, so a new page is live at
    once. Only what it imports at start counts, or every page change would ask for a restart."""
    done = node({"studio": 100}, touch="studio/page/index.html", at=500)
    assert "running code older" not in done.stdout


def test_a_new_python_file_does_send_someone_to_restart_the_studio(node):
    done = node({"studio": 100}, touch="studio/serve.py", at=500)
    assert "running code older" in done.stdout and "studio" in done.stdout


def test_the_script_still_finishes_when_every_service_is_current(node):
    """It ran under `set -e` as `test && printf`, so the loop -- and the whole pipeline -- ended with
    status 1 whenever the last service checked was current, which is the ordinary case. The script
    was taken out before it could say anything at all."""
    done = node({"door": 900, "studio": 900})
    assert "this checkout:" in done.stdout, "the summary after the check never printed"
