"""model-anatomy reads any building model: what is in it, and what rests on what."""
import json

import pytest
from showpiece.blend import SKILLS, run_in_blender

TOOLS = SKILLS / "model-anatomy/scripts"


@pytest.fixture(scope="module")
def anatomy(blender, stack_model, tmp_path_factory):
    out = tmp_path_factory.mktemp("anatomy")
    run_in_blender(blender, stack_model, TOOLS / "inventory.py", str(out))
    return json.loads((out / "anatomy.json").read_text()), out


def test_every_piece_gets_a_role_from_its_collection_name(anatomy):
    data, _ = anatomy
    roles = {name: piece["role"] for name, piece in data["pieces"].items()}
    assert len(roles) == 11
    assert roles["Slab"] == "ground" and roles["Tile sheet"] == "covering"
    assert roles["Rafter front"] == "rafter" and roles["Ridge beam"] == "timber"
    assert data["model"]["by_role"] == {"ground": 1, "timber": 7, "rafter": 2, "covering": 1}


def test_kinds_and_sizes_come_from_the_geometry(anatomy):
    data, _ = anatomy
    pieces = data["pieces"]
    assert pieces["Column NE"]["kind"] == "column"
    assert pieces["Lintel front"]["kind"] == "beam"
    assert pieces["Lintel front"]["extents"][0] == pytest.approx(4.6, abs=0.01)
    assert pieces["Tile sheet"]["kind"] == "sheet"
    assert pieces["Slab"]["kind"] == "sheet"
    lo, hi = data["model"]["box"]
    assert lo == pytest.approx([-2.3, -1.5, 0.3], abs=0.01) and hi == pytest.approx([2.3, 1.5, 3.4], abs=0.01)
    assert data["model"]["ground_box"][1] == pytest.approx([3, 2, 0.3], abs=0.01)
    assert pieces["Slab"]["tags"] == {} and data["model"]["assemblies"] == {}


def test_landmarks_are_camera_positions_around_the_building(anatomy):
    data, _ = anatomy
    marks = data["landmarks"]
    assert {"centre", "front", "back", "left", "right", "above", "inside"} <= set(marks)
    assert marks["front"]["at"][1] < -2 and marks["front"]["look"] == pytest.approx([0, 0, 1.85], abs=0.01)
    assert marks["above"]["at"][2] > 3.4
    assert data["cameras"] == {}


@pytest.fixture(scope="module")
def bearing(blender, stack_model, anatomy):
    _, out = anatomy
    run_in_blender(blender, stack_model, TOOLS / "bearing.py", str(out))
    return json.loads((out / "bearing.json").read_text())


def test_each_piece_rests_on_what_is_under_it(bearing):
    on = {name: {c["on"] for c in contacts} for name, contacts in bearing["rests_on"].items()}
    assert on["Column NE"] == {"Slab"}
    assert on["Lintel front"] == {"Column SW", "Column SE"}
    assert on["Ridge beam"] == {"Lintel front", "Lintel back"}
    assert on["Rafter back"] == {"Ridge beam"}
    assert bearing["floating"] == {} and bearing["ground"] == ["Slab"]


def test_the_order_puts_every_piece_before_what_carries_it(bearing):
    order = bearing["order"]
    assert order.index("Rafter front") < order.index("Ridge beam") < order.index("Lintel back")
    assert order.index("Lintel back") < order.index("Column NW")
    assert "Tile sheet" not in order and "Slab" not in order


def test_stages_are_the_construction_sequence(bearing):
    stages = [sorted(s) for s in bearing["stages"]]
    assert stages == [
        ["Column NE", "Column NW", "Column SE", "Column SW"],
        ["Lintel back", "Lintel front"],
        ["Ridge beam"],
        ["Rafter back", "Rafter front"],
        ["Tile sheet"],
    ]
