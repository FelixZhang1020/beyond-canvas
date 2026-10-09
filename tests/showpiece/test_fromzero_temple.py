"""The rebuild runner weighs the standing temple once, by the same three tools that weigh the hall,
and puts the result in every run folder, so the engineer's review can set the two side by side."""
import json

from conftest import FakeClient
from evalkit import fromzero
from studio.showpiece import catalog
from studio.showpiece import driver as drv


def test_a_file_seeded_into_a_run_is_in_its_folder_before_the_first_turn(tmp_path):
    seed = tmp_path / "made-earlier.json"
    seed.write_text('{"summary": {}}')
    client = FakeClient(['{"think": "done", "final": "nothing to do"}'])
    run = drv.Driver(client, None, tmp_path / "runs", cap=2).run_sync("rebuild", from_nothing=True,
                                                                       seed={"temple-loads.json": seed})
    assert json.loads((run.dir / "temple-loads.json").read_text()) == {"summary": {}}


def test_the_temple_is_weighed_by_the_halls_own_tools_once_per_temple_file(blender, stack_model, tmp_path):
    made = fromzero.temple_loads(stack_model, tmp_path / "cache")
    summary = json.loads(made.read_text())["summary"]
    assert summary["columns"] and summary["ground_N"] > 0, "the stack's four columns carry it to the ground"
    first = made.stat().st_mtime_ns
    assert fromzero.temple_loads(stack_model, tmp_path / "cache") == made and made.stat().st_mtime_ns == first, \
        "the same temple file is not weighed twice"


def test_a_builder_asking_for_the_engineers_review_during_a_rebuild_is_refused_and_loses_no_lap(tmp_path):
    """Operator's decision: of eleven notes in two rounds of reviews, eight misread the sheet, and
    each named a part and a number, which the builder was told to act on. Acted on, they would have cost laps
    or broken a hall that passes. The review is the operator's, after hand-over; during a rebuild the harness
    refuses it in a sentence, runs nothing, and the builder carries on."""
    client = FakeClient(['{"think": "all passed", "skill": "hall-carpenter", "tool": "review", "args": {}}',
                         '{"think": "then I am done", "final": "done"}'])
    driver = fromzero.carpenter(client, tmp_path / "temple.blend", tmp_path / "runs", cap=4)
    driver.gate = None
    run = driver.run_sync("rebuild", from_nothing=True)
    asked = next(e for e in run.events if e.get("tool") == "review")
    assert "command" not in asked, "nothing ran"
    assert "after the hall is handed over" in asked["text"] and not (run.dir / "review.json").exists()
    assert run.events[-1]["kind"] == "final", "and the builder carried on"


def test_the_builder_is_not_offered_the_review_and_the_skill_says_whose_it_is():
    told = (catalog.ROOT / "studio/showpiece/prompts/carpenter.txt").read_text()
    assert "review" not in told
    skill = (catalog.SKILLS / "hall-carpenter/SKILL.md").read_text()
    assert "the operator asks for it after the hall is handed over" in skill


def test_the_temple_is_weighed_when_the_runner_is_given_relative_folders(blender, stack_model, tmp_path, monkeypatch):
    """The usage line gives --runs as .studio/showpiece/rebuilds, relative. Each tool ran inside the cache
    folder with paths relative to the project, so it wrote into a nested copy and the run crashed."""
    import shutil
    from pathlib import Path
    shutil.copyfile(stack_model, tmp_path / "temple.blend")
    monkeypatch.chdir(tmp_path)
    made = fromzero.temple_loads(Path("temple.blend"), Path("runs/.temple"))
    assert made.is_absolute() and made.is_file() and made.parent.parent == (tmp_path / "runs/.temple").resolve()


def test_a_rebuild_can_be_driven_by_a_builder_that_reads_only_text():
    """Move 5 of the score plan: the builder thinking on the Spark is text-only."""
    from pathlib import Path

    assert fromzero.carpenter(FakeClient([]), fromzero.TEMPLE, Path("."), pictures=False).pictures is False
    assert fromzero.carpenter(FakeClient([]), fromzero.TEMPLE, Path(".")).pictures is True
