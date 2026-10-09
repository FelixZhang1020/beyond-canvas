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
import re
import subprocess
import sys
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
    "evalkit/rubric/loop.py": "rule 12\n",
    "skills/art-feedback/scripts/feedback.py": "the feedback skill\n",
    "skills/art-feedback/assets/prompts/opening.txt": "the opening prompt\n",
    "skills/load-path/scripts/collapse.py": "a Blender script, run per job\n",
    "skills/drawings-to-storybook/assets/picture-styles.json": "{}\n",
    "skills/drawings-to-storybook/assets/picture-talk.json": "{}\n",
    "studio/conversation/strings.json": "{}\n",
    "studio/profiles/stepfun.yaml": "slots: {}\n",
}

# Data the studio reads once and keeps, one file of each kind: the storybook's styles and picture talk,
# a showpiece skill's SKILL.md (its allowed-tools are enforced from the copy read), the words the
# harness says to a child, and the profile the class was built from.
KEPT_DATA = [
    "skills/drawings-to-storybook/assets/picture-styles.json",
    "skills/drawings-to-storybook/assets/picture-talk.json",
    "skills/load-path/SKILL.md",
    "studio/conversation/strings.json",
    "studio/profiles/stepfun.yaml",
]

# The studio's code, gathered in a fresh interpreter so nothing another test imported is counted:
# imported, then the loads it makes later -- every skill script conversation.py loads (once, and
# kept), the safety skill's second-look rule safety.py loads the same way, and the monitor's file the
# console loads and keeps, which sits in no module table and is asked for by name -- then every import
# written in any of that, inside functions too, followed until nothing new loads. That is how an import
# a request handler makes lazily is caught without running the handler. Data the studio reads once and
# keeps is not code and is not seen; the script names those files. Prints every file of ours it holds
# outside studio/.
TRACE = r"""
import ast, importlib, importlib.util, re, sys
from pathlib import Path
root = Path.cwd().resolve()
import studio.serve
from studio.conversation import conversation
from studio.ops import spark_monitor
for source in sorted((root / 'studio').rglob('*.py')):
    text = source.read_text(encoding='utf-8')
    calls = re.findall(r'_load_skill\(\s*"([^"]+)",\s*"([^"]+)"', text)
    if len(calls) != len(re.findall(r'(?<!def )_load_skill\(', text)):
        sys.exit(f'{source}: a _load_skill call this trace cannot read; name its script as a literal')
    for name, relative in calls:
        conversation._load_skill(name, relative)
conversation._SKILLS['safety_skill'].second_look_rule()
monitor_file = Path(spark_monitor.monitor().__file__).resolve()


def ours():
    files = {Path(m.__file__).resolve() for m in list(sys.modules.values()) if getattr(m, '__file__', None)}
    return {p for p in files if p.is_relative_to(root) and p.relative_to(root).parts[0] != '.venv'}


def submodule(name):
    try:
        return importlib.util.find_spec(name) is not None
    except ModuleNotFoundError:        # `from a.b import c` where a.b is a module and c a name in it
        return False


read = set()
while unread := sorted(ours() - read):
    for path in unread:
        read.add(path)
        for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
            if isinstance(node, ast.Import):
                modules, maybe = [a.name for a in node.names], []
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                modules, maybe = [node.module], [f'{node.module}.{a.name}' for a in node.names]
            else:
                continue
            for name in modules + [m for m in maybe if submodule(m)]:
                if name.split('.')[0] in ('studio', 'evalkit'):
                    importlib.import_module(name)
for path in sorted(ours() | {monitor_file}):
    if path.relative_to(root).parts[0] != 'studio':
        print(path.relative_to(root))
"""


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
        (work / name).parent.mkdir(parents=True, exist_ok=True)
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


def test_a_change_to_the_rules_the_studio_grades_by_sends_someone_to_restart_it(node):
    """The studio imports evalkit's rubric once, at start. Once rule 12 changed in
    evalkit/rubric/loop.py, this check said nothing was stale, and the studio would have gone on
    grading colour openings by the old rule until someone restarted it by hand."""
    done = node({"studio": 100}, touch="evalkit/rubric/loop.py", at=500)
    assert "running code older" in done.stdout and "studio" in done.stdout


def test_a_change_to_a_skill_script_the_studio_keeps_loaded_sends_someone_to_restart_it(node):
    """conversation.py loads a skill's script on the first drawing and keeps it for good."""
    done = node({"studio": 100}, touch="skills/art-feedback/scripts/feedback.py", at=500)
    assert "running code older" in done.stdout and "studio" in done.stdout


def test_a_new_skill_prompt_does_not_send_anyone_to_restart_the_studio(node):
    """art-feedback reads its prompts from disk on every call, so a new prompt is live at once."""
    done = node({"studio": 100}, touch="skills/art-feedback/assets/prompts/opening.txt", at=500)
    assert "running code older" not in done.stdout


@pytest.mark.parametrize("data", KEPT_DATA)
def test_a_change_to_data_the_studio_reads_once_sends_someone_to_restart_it(node, data):
    """Data is not code, and this check once watched code only. A picture-book style's instruction
    changed several times in a few days and each change sat on the node's disk, not in the class, until
    someone remembered to restart the studio by hand. An occasional restart nobody needed (a SKILL.md
    change when nobody has opened /showpiece since the start) is the price, chosen (operator)."""
    done = node({"studio": 100}, touch=data, at=500)
    assert "running code older" in done.stdout and "studio" in done.stdout


def test_every_showpiece_skill_the_studio_reads_is_watched():
    """The showpiece reads one SKILL.md for each skill in its catalog. A seventh added there and not
    here would be read once and kept, and a change to it would not mark the studio stale."""
    from studio.showpiece.catalog import SIX
    script = COMPARE.read_text(encoding="utf-8").replace("\\\n", "")
    paths = re.search(r'^SERVICES="studio:(.*)$', script, re.M).group(1).split()
    assert sorted(f"skills/{name}/SKILL.md" for name in SIX) == sorted(p for p in paths if p.endswith("SKILL.md"))


def test_a_skill_script_run_in_its_own_process_does_not_send_anyone_to_restart_the_studio(node):
    """The showpiece's skill scripts run per job in Blender; the studio never holds them."""
    done = node({"studio": 100}, touch="skills/load-path/scripts/collapse.py", at=500)
    assert "running code older" not in done.stdout


def test_the_studio_entry_names_every_file_outside_studio_that_the_studio_keeps_loaded():
    """The studio's list is written by hand and its imports are not, and the two drifted apart once
    without a sound. This gathers the studio's code as TRACE says and asks, of every file of ours it
    holds outside studio/, whether the script would see a commit to it. The patterns go through `sh`,
    as in the script: there they are unquoted, so the shell expands them before git reads them. A
    backslash at a line's end inside the quotes joins the next line on, as the shell does."""
    script = COMPARE.read_text(encoding="utf-8").replace("\\\n", "")
    paths = re.search(r'^SERVICES="studio:(.*)$', script, re.M).group(1)
    named = set(subprocess.run(["sh", "-c", "git ls-files -- $1", "sh", paths], cwd=ROOT,
                               capture_output=True, text=True, check=True).stdout.split())
    traced = subprocess.run([sys.executable, "-c", TRACE], cwd=ROOT, capture_output=True, text=True,
                            timeout=300)
    assert traced.returncode == 0, traced.stderr[-3000:]
    loaded = traced.stdout.split()
    assert "evalkit/rubric/loop.py" in loaded, f"the trace never reached outside studio/: {loaded}"
    unseen = sorted(set(loaded) - named)
    assert not unseen, f"the studio keeps these loaded and a change to them would not mark it stale: {unseen}"


def test_the_script_still_finishes_when_every_service_is_current(node):
    """It ran under `set -e` as `test && printf`, so the loop -- and the whole pipeline -- ended with
    status 1 whenever the last service checked was current, which is the ordinary case. The script
    was taken out before it could say anything at all."""
    done = node({"door": 900, "studio": 900})
    assert "this checkout:" in done.stdout, "the summary after the check never printed"
