"""Each skill declares the tools it may run, and a tool it has not declared is refused.

`allowed-tools` is the key NVIDIA's Skill format reserves for a skill saying what it may run, and
every skill here used to leave it empty. It is the skill's own statement rather than the
catalog's, which is what makes it worth having: the catalog says a tool exists, and the skill says
whether it is one of its own. A tool added to the catalog under a skill's name and never declared
is therefore unreachable rather than quietly available.

It is not the same thing as the driver's `withheld`, which refuses a tool for one kind of run and is
set by whoever starts it. This is standing, and belongs to the skill.

The test that matters most here is the last pair: a declaration nobody checks against the tools that
actually exist drifts, and both directions hurt. A tool left undeclared turns into a refusal the
first time a run reaches for it; a declared name with no tool behind it is a promise to a judge
reading SKILL.md that nothing keeps.
"""
import dataclasses
import json

from conftest import FakeClient
from studio.showpiece import catalog
from studio.showpiece import driver as drv

CLASSROOM = ("art-feedback", "drawings-to-storybook", "painting-to-animation",
             "painting-to-figure", "sketch-to-3d", "studio-safety")


def script(*replies):
    return FakeClient([json.dumps(r) for r in replies])


def declaring(driver, skill, *tools):
    """The skill as it would be if its own SKILL.md declared exactly these."""
    driver.skills[skill] = dataclasses.replace(driver.skills[skill], allowed=tuple(tools))


def asking_for(tmp_path, skill, tool, declared):
    """One run in which the model reaches for skill/tool, and the skill declares `declared`."""
    client = script({"think": "this one", "skill": skill, "tool": tool, "args": {"out_dir": "."}},
                    {"think": "oh", "final": "stopped"})
    driver = drv.Driver(client, None, tmp_path, cap=3)
    declaring(driver, skill, *declared)
    run = driver._new_run("do the thing")
    driver._loop(run)
    return run


def test_a_tool_the_skill_has_not_declared_is_refused(tmp_path):
    run = asking_for(tmp_path, "model-anatomy", "bearing", ["model-anatomy/inventory"])
    act = run.events[1]
    assert act["kind"] == "act"
    assert "REFUSED model-anatomy/bearing" in act["text"]


def test_a_refused_tool_never_runs(tmp_path):
    """Refused before anything starts, so it writes no file and costs no time: the point of
    declaring a limit is that the limit holds before the work, not after it."""
    run = asking_for(tmp_path, "model-anatomy", "bearing", ["model-anatomy/inventory"])
    assert not (run.dir / "bearing.json").exists()
    assert "bearing.py" not in str(run.events[1].get("command") or "")


def test_the_refusal_says_what_the_skill_does_allow(tmp_path):
    """A refusal that does not say what would have been allowed leaves the model guessing, and a
    model that guesses spends another turn on it."""
    run = asking_for(tmp_path, "model-anatomy", "bearing", ["model-anatomy/inventory"])
    assert "model-anatomy/inventory" in run.events[1]["text"]


def test_the_refusal_is_written_down_where_it_can_be_read_afterwards(tmp_path):
    """A refusal nobody can read later is indistinguishable from a tool nobody asked for, and the
    whole reason to declare a limit is to be able to show that it held."""
    run = asking_for(tmp_path, "model-anatomy", "bearing", ["model-anatomy/inventory"])
    receipts = json.loads((run.dir / "refusals.json").read_text(encoding="utf-8"))
    assert len(receipts) == 1
    assert receipts[0]["wanted"] == "model-anatomy/bearing"
    assert "SKILL.md" in receipts[0]["stopped_by"], "it must name the rule, not merely say no"
    assert receipts[0]["run"] == run.id


def test_a_declared_tool_is_not_refused(blender, stack_model, tmp_path):
    """The other half: a guard that refuses everything would pass every test above and be useless."""
    client = script({"think": "read it", "skill": "model-anatomy", "tool": "inventory", "args": {"out_dir": "."}},
                    {"think": "done", "final": "read"})
    driver = drv.Driver(client, stack_model, tmp_path, cap=5)
    run = driver.run_sync("what is in this model?")
    assert "REFUSED" not in run.events[1]["text"]
    assert (run.dir / "anatomy.json").is_file(), "a declared tool must still run"


def test_every_skill_declares_exactly_the_tools_the_catalog_gives_it():
    """Neither direction is allowed to drift: an undeclared tool becomes a refusal the first time a
    run reaches for it, and a declared name with no tool behind it is a promise SKILL.md cannot keep.
    """
    owners = {skill for skill, _ in catalog.TOOLS}
    skills = catalog.load_skills(names=sorted(owners))
    for name in sorted(owners):
        real = {f"{name}/{tool}" for skill, tool in catalog.TOOLS if skill == name}
        assert set(skills[name].allowed) == real, (
            f"{name}/SKILL.md declares {sorted(skills[name].allowed)}, the catalog gives it {sorted(real)}")


def test_a_skill_that_owns_no_script_declares_nothing():
    """Three classroom skills own no script -- the model does not make their mesh or their book. An
    empty declaration is the honest answer there, and a name invented for the sake of filling the key
    would be a claim nothing runs."""
    skills = catalog.load_skills(names=CLASSROOM)
    for name in CLASSROOM:
        scripts = sorted(p.stem for p in (catalog.SKILLS / name / "scripts").glob("*.py"))
        assert sorted(skills[name].allowed) == [f"{name}/{stem}" for stem in scripts], (
            f"{name} owns {scripts} and declares {sorted(skills[name].allowed)}")
