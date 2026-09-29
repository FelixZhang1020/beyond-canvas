"""Nothing an agent asks for may write over the model it was handed.

Found by a code review: the driver took any tool in the catalogue, whichever skills the
run had, and a hall-placing tool is told to save the hall at the run's model. In an exhibition run that
model is the standing temple itself, so one guessed action would have saved a platform over it.
"""
import json
from pathlib import Path

from conftest import FakeClient
from studio.showpiece import catalog
from studio.showpiece import driver as drv

PLATFORM = {"think": "lay the platform", "skill": "hall-carpenter", "tool": "platform",
            "args": {"size": "10,8", "top": 1.0, "thickness": 1.0}}
DONE = {"think": "done", "final": "done"}


def ran(monkeypatch):
    """Every command the driver would have run, instead of running it."""
    calls = []
    monkeypatch.setattr(drv, "run_tool", lambda argv, timeout, cwd=None: calls.append(argv) or (0, "placed"))
    monkeypatch.setattr(catalog, "find_blender", lambda: "/Applications/Blender.app/Contents/MacOS/Blender")
    return calls


def temple(tmp_path):
    path = tmp_path / "temple.blend"
    path.write_bytes(b"the standing temple")
    return path


def test_an_exhibition_run_cannot_reach_a_tool_of_a_skill_it_was_not_given(tmp_path, monkeypatch):
    calls, model = ran(monkeypatch), temple(tmp_path)
    run = drv.Driver(FakeClient([json.dumps(PLATFORM), json.dumps(DONE)]), model, tmp_path / "runs").run_sync("show it")
    act = next(e for e in run.events if e["kind"] == "act")
    assert act["text"].startswith("no such tool hall-carpenter/platform")
    assert "hall-carpenter" not in act["text"].split("the tools are ")[1], "it lists only this run's tools"
    assert calls == [] and model.read_bytes() == b"the standing temple"


def test_a_run_with_the_carpentry_skills_still_cannot_save_over_the_model_it_was_handed(tmp_path, monkeypatch):
    calls, model = ran(monkeypatch), temple(tmp_path)
    driver = drv.Driver(FakeClient([json.dumps(PLATFORM), json.dumps(DONE)]), model, tmp_path / "runs",
                        skills=catalog.load_skills(names=catalog.CARPENTRY))
    run = driver.run_sync("rebuild it")                   # not from nothing: the run's model is the temple
    act = next(e for e in run.events if e["kind"] == "act")
    assert act["text"].startswith("REFUSED hall-carpenter/platform writes a hall")
    assert calls == [] and model.read_bytes() == b"the standing temple"


def test_a_from_nothing_run_writes_only_the_hall_in_its_own_folder(tmp_path, monkeypatch):
    calls, model = ran(monkeypatch), temple(tmp_path)
    driver = drv.Driver(FakeClient([json.dumps(PLATFORM), json.dumps(DONE)]), model, tmp_path / "runs",
                        skills=catalog.load_skills(names=catalog.CARPENTRY))
    run = driver.run_sync("rebuild it", from_nothing=True)
    assert len(calls) == 1
    hall = calls[0][calls[0].index("--hall") + 1]
    assert hall == str(run.dir / "hall.blend") and str(model) not in calls[0]
    assert model.read_bytes() == b"the standing temple"


def test_a_tool_given_the_joints_works_on_the_copy_they_were_cut_into(tmp_path, monkeypatch):
    """The joints tool cuts them into a copy it saves in the run folder, never into the hall. A live run
    gave every tool the hall, so its close-ups of the joints could only film pieces that were not there;
    a tool given joints.json now works on the copy that file names."""
    calls, model = ran(monkeypatch), temple(tmp_path)

    def blender(argv, timeout, cwd=None):
        calls.append(argv)
        out = Path(argv[argv.index("--") + 1])
        if argv[argv.index("--python") + 1].endswith("inventory.py"):
            (out / "anatomy.json").write_text("{}")
        if argv[argv.index("--python") + 1].endswith("joints.py"):
            (out / "temple-joints.blend").write_bytes(b"the copy with its joints cut")
            (out / "joints.json").write_text(json.dumps({"model": str(out / "temple-joints.blend"), "joints": []}))
        return 0, "done"

    monkeypatch.setattr(drv, "run_tool", blender)
    steps = [{"think": "read it", "skill": "model-anatomy", "tool": "inventory", "args": {"out_dir": "."}},
             {"think": "cut", "skill": "joint-reveal", "tool": "joints",
              "args": {"out_dir": ".", "tenon": [["Post", "Block"]]}},
             {"think": "film", "skill": "joint-reveal", "tool": "explode",
              "args": {"out_dir": ".", "pieces": "Post,Block", "joints": "joints.json", "closeups": True}}, DONE]
    driver = drv.Driver(FakeClient([json.dumps(s) for s in steps]), model, tmp_path / "runs")
    run = driver.run_sync("how do the joints lock")
    assert [argv[2] for argv in calls] == [str(model), str(model), str((run.dir / "temple-joints.blend").resolve())]
    assert "--closeups" in calls[2] and model.read_bytes() == b"the standing temple"
