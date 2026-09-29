"""A check run on a model that changed after its anatomy.json was made says so in one sentence.

anatomy.json is what the model held when inventory ran. The carpenter replaces a part each time it
places it again, so in design run 2 the builder took the roof from three purlin rings
to two and ran bearing on the old anatomy.json: it named a ring that was gone, bearing fell over on
the name with a Blender traceback, and the builder, which could not read it, lost several actions.
The same run placed its columns again, 36 of them and then 45: a check reading the old anatomy.json
would have left the nine new ones out and said nothing. Every check that looks the anatomy's pieces
up in the model now stops before it starts, says what changed and that inventory has to run again,
and exits non-zero because it did not run. What counts as a piece is what inventory counts, so a
camera or a hidden copy added since is no change.

The tools run through the driver's own `run_tool`, so what is asserted is what the builder reads:
the last line of what the tool printed, inside the 600 characters the driver shows it.
"""
import json

import pytest
from showpiece.blend import SKILLS, run_in_blender

from studio.showpiece.blender_bin import run_tool

INVENTORY = SKILLS / "model-anatomy/scripts/inventory.py"
SHOWN = 600       # what the driver shows the model of a tool's output (driver.py)
GONE, ADDED = ("Ridge beam", "Rafter back"), ("Column extra",)
AFTER = "it was made before the model last changed. Run model-anatomy inventory again, then {then}."
NAMES_GONE = "anatomy.json names 2 pieces the model no longer has (first: {first!r})"
HAS_ADDED = "the model has 1 piece anatomy.json does not name (first: 'Column extra')"

# The stack after a part was placed again: some pieces gone, some new. A new piece is a post on the
# slab in the columns' collection; `hidden` hides it and adds a camera, neither of which inventory counts.
CHANGE = '''
import bpy
for name in {gone!r}:
    bpy.data.objects.remove(bpy.data.objects[name])
for name in {added!r}:
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata([(2.7 + x * 0.1, y * 0.1, 0.3 + z * 2.4) for z in (0, 1) for y in (-1, 1) for x in (-1, 1)], [],
                     [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)])
    bpy.data.collections["02_Columns"].objects.link(bpy.data.objects.new(name, mesh))
if {hidden!r}:
    bpy.data.objects[{added!r}[0]].hide_set(True)
    bpy.data.objects[{added!r}[0]].hide_render = True
    bpy.context.scene.collection.objects.link(bpy.data.objects.new("Camera extra", bpy.data.cameras.new("Camera extra")))
bpy.ops.wm.save_as_mainfile(filepath=r"{out}")
'''
CHANGES = {"fewer": (GONE, (), NAMES_GONE), "more": ((), ADDED, HAS_ADDED),
           "both": (GONE, ADDED, NAMES_GONE + " and " + HAS_ADDED)}

CHECKS = [
    ("model-anatomy", "bearing", ()),
    ("load-path", "settle", ("--seconds", "1", "--fps", "12", "--width", "320", "--height", "180")),
    ("load-path", "shake", ("--width", "320", "--height", "180")),
]


def change_after_inventory(blender, stack_model, folder, gone, added, hidden=False):
    """anatomy.json made from the stack in `folder`, and the stack changed after it was made."""
    run_in_blender(blender, stack_model, INVENTORY, str(folder))
    script, model = folder / "change.py", folder / "changed.blend"
    script.write_text(CHANGE.format(gone=gone, added=added, hidden=hidden, out=model))
    run_in_blender(blender, stack_model, script)
    return model


def run_check(blender, model, folder, skill, tool, extra=()):
    anatomy = ("--anatomy", str(folder / "anatomy.json")) if skill == "load-path" else ()
    argv = [str(blender), "-b", str(model), "--python-exit-code", "1",
            "--python", str(SKILLS / skill / "scripts" / f"{tool}.py"), "--", str(folder), *anatomy, *extra]
    return run_tool(argv, 900)


@pytest.fixture(scope="module", params=list(CHANGES))
def changed(request, blender, stack_model, tmp_path_factory):
    gone, added, found = CHANGES[request.param]
    folder = tmp_path_factory.mktemp(request.param)
    return folder, change_after_inventory(blender, stack_model, folder, gone, added), found


@pytest.mark.parametrize(("skill", "tool", "extra"), CHECKS, ids=[c[1] for c in CHECKS])
def test_a_check_on_a_model_changed_since_inventory_stops_in_one_sentence_that_says_to_run_inventory(
        blender, changed, skill, tool, extra):
    folder, model, found = changed
    named = list(json.loads((folder / "anatomy.json").read_text())["pieces"])
    first = next(n for n in named if n in GONE)
    sentence = f"REFUSED {found}: {AFTER}".format(first=first, then=f"{skill} {tool}")
    code, tail = run_check(blender, model, folder, skill, tool, extra)
    assert code != 0, "the check did not run, so the driver shows a failed tool"
    assert "Traceback" not in tail
    assert tail.strip().splitlines()[-1] == sentence
    assert sentence in f"exit {code}: {tail}"[-SHOWN:]
    assert not (folder / f"{tool}.json").exists(), "nothing is written from the old anatomy"


def test_a_camera_or_a_hidden_piece_added_after_inventory_is_no_change(blender, stack_model, tmp_path):
    model = change_after_inventory(blender, stack_model, tmp_path, (), ADDED, hidden=True)
    code, tail = run_check(blender, model, tmp_path, "model-anatomy", "bearing")
    assert code == 0 and "REFUSED" not in tail
    assert "BEARING 9 pieces 0 floating" in tail
