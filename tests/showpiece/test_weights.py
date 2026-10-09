"""load-path weights: every piece's weight goes down the carrying graph to the ground."""
import json
import subprocess
import sys

import pytest
from showpiece.blend import SKILLS, run_in_blender

ANATOMY = SKILLS / "model-anatomy/scripts/inventory.py"
BEARING = SKILLS / "model-anatomy/scripts/bearing.py"
WEIGHTS = SKILLS / "load-path/scripts/weights.py"


def test_the_stack_balances_and_the_columns_share_the_roof(blender, stack_model, tmp_path):
    run_in_blender(blender, stack_model, ANATOMY, str(tmp_path))
    run_in_blender(blender, stack_model, BEARING, str(tmp_path))
    done = subprocess.run([sys.executable, str(WEIGHTS), str(tmp_path / "anatomy.json"), str(tmp_path / "bearing.json"),
                           str(tmp_path)], capture_output=True, text=True, check=True)
    assert done.stdout.startswith("LOADS 11 pieces")
    loads = json.loads((tmp_path / "loads.json").read_text())
    s = loads["summary"]
    assert s["ground_N"] == pytest.approx(s["total_N"], rel=1e-6) and s["not_carried_N"] == 0
    pieces = loads["pieces"]
    sheet = pieces["Tile sheet"]
    # The roof weighs 7 kN per square metre of footprint, tiles, boarding and clay bed together.
    assert sheet["weight_N"] == pytest.approx(4.6 * 3.0 * 7000, rel=1e-3)
    # Nine points over the sheet: six land on the rafters, one in the gap on the ridge, two on nothing
    # and are shared out among the seven that found something, so each rafter takes three sevenths.
    assert set(sheet["passes_to"]) == {"Rafter front", "Rafter back", "Ridge beam"}
    assert sheet["passes_to"]["Rafter front"] == pytest.approx(sheet["weight_N"] * 3 / 7, rel=1e-6)
    columns = sorted(c["carries_N"] for c in s["columns"])
    # Shares follow sampled contact areas, and the bearing tool's samples on a 30 cm seat are few,
    # so symmetric columns come out within about 15 %, not equal.
    assert len(columns) == 4 and columns[-1] == pytest.approx(columns[0], rel=0.15)
    assert pieces["Ridge beam"]["carries_N"] > pieces["Rafter front"]["carries_N"] > sheet["weight_N"] / 3


def test_a_column_too_thin_for_its_load_is_named_and_a_thick_one_is_not(tmp_path):
    """Stress is the load over the cross-section; timber is allowed 10 MPa in compression, the design
    value of the lowest softwood grade. The Foguang hall's heaviest column works at about 2.3 MPa."""
    def piece(role, kind, lo, hi):
        size = [hi[i] - lo[i] for i in range(3)]
        return {"role": role, "kind": kind, "box": [lo, hi], "extents": size, "zmin": lo[2],
                "volume": size[0] * size[1] * size[2]}
    pieces = {"Ground": piece("ground", "sheet", [-5, -5, -1], [5, 5, 0]),
              "Column thick": piece("timber", "column", [-2.25, -0.25, 0], [-1.75, 0.25, 3]),
              "Column thin": piece("timber", "column", [1.975, -0.025, 0], [2.025, 0.025, 3]),
              "Beam": piece("timber", "beam", [-2.5, -1.0, 3], [2.5, 1.0, 4])}
    bearing = {"order": ["Beam", "Column thick", "Column thin", "Ground"], "ground": ["Ground"],
               "rests_on": {"Beam": [{"on": "Column thick", "area": 1.0}, {"on": "Column thin", "area": 1.0}],
                            "Column thick": [{"on": "Ground", "area": 1.0}], "Column thin": [{"on": "Ground", "area": 1.0}]},
               "near": {}, "carried_by": {"Beam": ["Column thick", "Column thin"]}}
    (tmp_path / "anatomy.json").write_text(json.dumps({"pieces": pieces}))
    (tmp_path / "bearing.json").write_text(json.dumps(bearing))
    done = subprocess.run([sys.executable, str(WEIGHTS), str(tmp_path / "anatomy.json"), str(tmp_path / "bearing.json"),
                           str(tmp_path)], capture_output=True, text=True, check=True)
    s = json.loads((tmp_path / "loads.json").read_text())["summary"]
    beam_half_kN = 5 * 2 * 1 * 500 * 9.81 / 2 / 1000          # 49 kN of beam, half on each column
    thin = next(c for c in s["columns"] if c["name"] == "Column thin")
    assert thin["diameter_m"] == pytest.approx(0.05) and thin["carries_kN"] == pytest.approx(beam_half_kN, rel=0.01)
    assert s["allowed_MPa"] == 10.0 and [c["name"] for c in s["overloaded"]] == ["Column thin"]
    assert thin["stress_MPa"] > 10 > next(c for c in s["columns"] if c["name"] == "Column thick")["stress_MPa"]
    assert "1 column too weak" in done.stdout


def test_one_sloped_roof_sheet_rests_on_the_rafters_under_it_and_its_weight_reaches_the_ground(tmp_path):
    """The rebuilt hall's roof is four big sloped sheets. Measured from the sheet's lowest edge, the eave,
    nothing is under it, and 3,534 kN of the run-3 hall's 10,157 kN never reached a column. A sheet
    that finds nothing under its lowest edge rests on the highest timber below its top instead."""
    def piece(role, kind, lo, hi):
        size = [hi[i] - lo[i] for i in range(3)]
        return {"role": role, "kind": kind, "box": [lo, hi], "extents": size, "zmin": lo[2],
                "volume": size[0] * size[1] * size[2]}
    pieces = {"Ground": piece("ground", "sheet", [-5, -5, -1], [5, 5, 0]),
              "Column a": piece("timber", "column", [-2.2, -0.2, 0], [-1.8, 0.2, 3]),
              "Column b": piece("timber", "column", [1.8, -0.2, 0], [2.2, 0.2, 3]),
              "Rafter": piece("rafter", "beam", [-2.5, -2.0, 3.0], [2.5, 2.0, 5.0]),
              "Roof sheet front": piece("covering", "sheet", [-2.5, -2.0, 3.0], [2.5, 2.0, 5.2])}
    bearing = {"order": ["Rafter", "Column a", "Column b", "Ground"], "ground": ["Ground"],
               "rests_on": {"Rafter": [{"on": "Column a", "area": 1.0}, {"on": "Column b", "area": 1.0}],
                            "Column a": [{"on": "Ground", "area": 1.0}], "Column b": [{"on": "Ground", "area": 1.0}]},
               "near": {}, "carried_by": {"Rafter": ["Column a", "Column b"]}}
    (tmp_path / "anatomy.json").write_text(json.dumps({"pieces": pieces}))
    (tmp_path / "bearing.json").write_text(json.dumps(bearing))
    subprocess.run([sys.executable, str(WEIGHTS), str(tmp_path / "anatomy.json"), str(tmp_path / "bearing.json"),
                    str(tmp_path)], capture_output=True, text=True, check=True)
    loads = json.loads((tmp_path / "loads.json").read_text())
    s = loads["summary"]
    assert loads["pieces"]["Roof sheet front"]["passes_to"] == {"Rafter": pytest.approx(5 * 4 * 7000)}
    assert s["not_carried_N"] == 0 and s["ground_N"] == pytest.approx(s["total_N"], rel=1e-6)


def _piece(role, kind, lo, hi):
    size = [hi[i] - lo[i] for i in range(3)]
    return {"role": role, "kind": kind, "box": [lo, hi], "extents": size, "zmin": lo[2],
            "volume": size[0] * size[1] * size[2]}


def _weigh(tmp_path, pieces, bearing):
    (tmp_path / "anatomy.json").write_text(json.dumps({"pieces": pieces}))
    (tmp_path / "bearing.json").write_text(json.dumps(bearing))
    done = subprocess.run([sys.executable, str(WEIGHTS), str(tmp_path / "anatomy.json"), str(tmp_path / "bearing.json"),
                           str(tmp_path)], capture_output=True, text=True, check=True)
    return json.loads((tmp_path / "loads.json").read_text())["summary"], done.stdout


def test_snow_on_the_roof_reaches_the_columns_and_is_added_the_way_the_standard_adds_it(tmp_path):
    """A heavier roof changes nothing in a let-go test, where pieces cannot bend or crush; it matters to
    the columns' strength. 0.35 kN of snow on every square metre of the roof's footprint, and the
    design load is 1.3 times the hall's own weight plus 1.5 times the snow."""
    pieces = {"Ground": _piece("ground", "sheet", [-6, -6, -1], [6, 6, 0]),
              "Column west": _piece("timber", "column", [-2.25, -0.25, 0], [-1.75, 0.25, 3]),
              "Column east": _piece("timber", "column", [1.75, -0.25, 0], [2.25, 0.25, 3]),
              "Beam": _piece("timber", "beam", [-5, -5, 3], [5, 5, 3.2]),
              "Tile sheet": _piece("covering", "sheet", [-5, -5, 3.2], [5, 5, 3.3])}
    bearing = {"order": ["Beam", "Column west", "Column east", "Ground"], "ground": ["Ground"],
               "rests_on": {"Beam": [{"on": "Column west", "area": 1.0}, {"on": "Column east", "area": 1.0}],
                            "Column west": [{"on": "Ground", "area": 1.0}], "Column east": [{"on": "Ground", "area": 1.0}]},
               "near": {}, "carried_by": {"Beam": ["Column west", "Column east"]}}
    s, printed = _weigh(tmp_path, pieces, bearing)
    assert s["snow"]["per_m2_kN"] == 0.35 and s["snow"]["total_kN"] == pytest.approx(35.0) and "GB 50009" in s["snow"]["source"]
    west = next(c for c in s["columns"] if c["name"] == "Column west")
    assert west["snow_kN"] == pytest.approx(17.5, rel=1e-3), "half the snow each"
    assert west["design_kN"] == pytest.approx(1.3 * west["carries_kN"] + 1.5 * 17.5, rel=1e-3)
    assert s["total_N"] == pytest.approx(s["ground_N"]), "the hall's own weight is still reported without the snow"
    assert "snow" in printed


def test_a_slender_column_gives_way_where_a_stocky_one_of_the_same_section_holds(tmp_path):
    """A thin column does not crush, it bows. Two 15 cm columns under the same 49 kN: one a metre tall,
    one six. Over its section each works at under 3 MPa of the 10 allowed; the tall one is so slender
    that the standard lets it carry only about a tenth of that."""
    pieces = {"Ground": _piece("ground", "sheet", [-6, -6, -1], [6, 6, 0]),
              "Column short": _piece("timber", "column", [-2.075, -0.075, 0], [-1.925, 0.075, 1]),
              "Column tall": _piece("timber", "column", [1.925, -0.075, 0], [2.075, 0.075, 6]),
              "Beam low": _piece("timber", "beam", [-4.5, -1.0, 1], [0.5, 1.0, 2]),
              "Beam high": _piece("timber", "beam", [-0.5, -1.0, 6], [4.5, 1.0, 7])}
    bearing = {"order": ["Beam high", "Beam low", "Column tall", "Column short", "Ground"], "ground": ["Ground"],
               "rests_on": {"Beam low": [{"on": "Column short", "area": 1.0}], "Beam high": [{"on": "Column tall", "area": 1.0}],
                            "Column short": [{"on": "Ground", "area": 1.0}], "Column tall": [{"on": "Ground", "area": 1.0}]},
               "near": {}, "carried_by": {"Beam low": ["Column short"], "Beam high": ["Column tall"]}}
    s, printed = _weigh(tmp_path, pieces, bearing)
    short, tall = (next(c for c in s["columns"] if c["name"] == n) for n in ("Column short", "Column tall"))
    assert short["stress_MPa"] < 3 and tall["stress_MPa"] < 3, "neither would crush"
    assert short["slenderness"] == pytest.approx(1 / 0.0375, rel=0.01) and tall["slenderness"] == pytest.approx(160, rel=0.01)
    assert tall["holds"] == pytest.approx(2800 / 160 ** 2, rel=0.01) and short["holds"] > 0.8
    assert [c["name"] for c in s["overloaded"]] == ["Column tall"] and tall["design_MPa"] > 10 > short["design_MPa"]
    assert "Column tall" in printed and "too weak" in printed


def test_a_post_standing_on_the_frame_is_judged_as_a_post_and_never_counted_as_a_column(tmp_path):
    """The rebuilt hall's four king posts stand on its roof beams and were counted as columns, 40 of 36,
    and the sheet showed a 0.30 m "lightest column" that sent NVIDIA's reviewer the wrong way. The temple's
    own figures counted two hip purlins the same way. A column is an upright that stands on the ground; an
    upright on timber still carries load and is still judged, as a post."""
    pieces = {"Ground": _piece("ground", "sheet", [-6, -6, -1], [6, 6, 0]),
              "Column west": _piece("timber", "column", [-2.25, -0.25, 0], [-1.75, 0.25, 3]),
              "Column east": _piece("timber", "column", [1.75, -0.25, 0], [2.25, 0.25, 3]),
              "Beam": _piece("timber", "beam", [-2.5, -0.5, 3], [2.5, 0.5, 3.5]),
              "Frame 0.00 | king post": _piece("timber", "column", [-0.025, -0.025, 3.5], [0.025, 0.025, 4.5]),
              "Ridge": _piece("timber", "beam", [-2.5, -1.0, 4.5], [2.5, 1.0, 5.5]),
              "Column hanging": _piece("timber", "column", [4.75, -0.25, 1], [5.25, 0.25, 4])}
    post = "Frame 0.00 | king post"
    bearing = {"order": ["Ridge", post, "Beam", "Column west", "Column east", "Ground"], "ground": ["Ground"],
               "rests_on": {"Ridge": [{"on": post, "area": 1.0}], post: [{"on": "Beam", "area": 1.0}],
                            "Beam": [{"on": "Column west", "area": 1.0}, {"on": "Column east", "area": 1.0}],
                            "Column west": [{"on": "Ground", "area": 1.0}], "Column east": [{"on": "Ground", "area": 1.0}]},
               "near": {}, "carried_by": {"Ridge": [post], post: ["Beam"], "Beam": ["Column west", "Column east"]}}
    s, printed = _weigh(tmp_path, pieces, bearing)
    assert sorted(c["name"] for c in s["columns"]) == ["Column east", "Column hanging", "Column west"], \
        "an upright resting on nothing stays a column: hanging is never a way off the strength check"
    assert [p["name"] for p in s["posts"]] == [post]
    assert [(c["name"], c["what"]) for c in s["overloaded"]] == [(post, "post")], "a post too thin still fails the hall"
    assert "1 post too weak" in printed and post in printed
