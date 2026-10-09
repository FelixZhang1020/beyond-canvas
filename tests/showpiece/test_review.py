"""hall-carpenter review: an engineer from another company reads the hall's numbers and says what
does not make structural sense. Advice, never a verdict: it cannot pass a hall or fail one, it is
shown no picture, and when it cannot be reached or read the builder carries on."""
import json
from pathlib import Path

import pytest
from conftest import load_script

from studio.core.errors import ModelUnavailable
from studio.showpiece import catalog
from studio.core.slots import load_profile

SCRIPT = Path("skills/hall-carpenter/scripts/review.py")
NOTE = {"part": "ties", "number": "depth 0.10 m over a 5.10 m bay", "concern": "a tie beam a fiftieth of its span sags",
        "suggest": "make ties depth about 0.45"}


@pytest.fixture(scope="module")
def module():
    return load_script(SCRIPT, "review_script")


@pytest.fixture
def folder(tmp_path):
    def write(name, data):
        (tmp_path / name).write_text(json.dumps(data))
    write("survey.json", {"size": [41.39, 25.05, 14.65], "top": 16.02, "platform": {"top": 1.62, "size": [38.1, 24.8]},
                          "columns": {"count": 36, "xs": [-16.97, -12.49, -7.49, -2.55, 2.55, 7.49, 12.49, 16.97],
                                      "ys": [-8.81, -4.41, 0.0, 4.41, 8.81], "foot": 1.62, "top": 6.49, "diameter": 0.57},
                          "tie_beams": {"top": 6.29, "depth": 0.46, "width": 0.32}, "ridge": {"half_x": 8.5, "underside": 13.69},
                          "roof_rings": [{"ring": 1, "underside": 9.33, "size": 0.32}], "rafters": {"size": 0.36, "spacing": 0.05},
                          "tie_spans": {"spans": 36, "tied": 36}, "bracket_sets": {"columns": 36, "with_a_set": 36},
                          "column_places": [[0, 0]] * 36, "box": [[-20.7, -12.5, 1.37], [20.7, 12.5, 16.02]]})
    write("hall.json", {"parts": {"columns": {"told": {"height": 4.87, "diameter": 0.57}, "at": [{"x": 0, "y": 0}] * 36},
                                  "ties": {"told": {"top": 6.29, "depth": 0.10, "width": 0.32}, "underside": 6.19},
                                  "rafters": {"told": {"spacing": 0.5, "size": 0.36}}}})
    write("likeness.json", {"alike": True, "shared_outline": {"front": 0.944}, "size": {"temple": [41.39, 25.05, 14.65], "hall": [41.4, 25.0, 14.6]},
                            "columns": {"wanted": 36, "matched": 36, "built": 36},
                            "frame": {"hall": {"tie_spans": {"spans": 36, "tied": 36}, "roof_rings": 6, "ridge": {"underside": 13.69},
                                               "rafters": {"size": 0.36}, "bracket_sets": {"columns": 36, "with_a_set": 36}}, "short": []}})
    write("bearing.json", {"rests_on": {"a": [], "b": []}, "floating": {}, "stages": [1, 2, 3]})
    write("loads.json", {"summary": {"total_N": 10.157e6, "ground_N": 10.157e6, "not_carried_N": 0, "allowed_MPa": 10.0, "overloaded": [],
                                     "snow": {"per_m2_kN": 0.35, "total_kN": 363.1},
                                     "columns": [{"name": "Column a", "carries_kN": 529.7, "design_kN": 718.0, "diameter_m": 0.57,
                                                  "slenderness": 34.2, "design_MPa": 3.59},
                                                 {"name": "Column b", "carries_kN": 120.0, "design_kN": 170.0, "diameter_m": 0.57,
                                                  "slenderness": 34.2, "design_MPa": 0.85}]}})
    write("settle.json", {"pieces": {"private piece name": {"moved_m": 0}}, "summary": {"fell": 0, "shifted": 0, "frames": 30}})
    write("shake.json", {"summary": {"shake": {"peak_g": 0.2, "pull_g": 0.07, "came_down": 0, "drift_m": 0.04}}})
    return tmp_path


def test_the_sheet_puts_the_temple_and_the_hall_side_by_side_with_the_loads_and_both_tests(module, folder):
    sheet = module.sheet(folder)
    assert sheet["temple"]["tie_beams"] == {"top": 6.29, "depth": 0.46, "width": 0.32}
    assert sheet["hall_as_told"]["ties"] == {"top": 6.29, "depth": 0.10, "width": 0.32}
    assert sheet["temple"]["widest_bay_m"] == {"along_the_front": 5.1, "front_to_back": 4.41}, "an engineer thinks in spans"
    assert sheet["hall_as_measured"]["frame"]["tie_spans"] == {"spans": 36, "tied": 36}
    assert sheet["loads"]["hall"]["heaviest_column"]["design_MPa"] == 3.59 and sheet["loads"]["hall"]["columns"] == 2
    assert sheet["loads"]["hall"]["total_kN"] == 10157 and sheet["loads"]["hall"]["snow_kN"] == 363.1
    assert sheet["let_go"] == {"fell": 0, "shifted": 0} and sheet["shaken"]["came_down"] == 0
    assert "column_places" not in json.dumps(sheet) and "private piece name" not in json.dumps(sheet), "numbers, not piece lists"
    assert len(json.dumps(sheet)) < 6000, "one screen of numbers"


def test_a_check_that_never_ran_is_said_so_and_never_invented(module, folder):
    (folder / "shake.json").unlink()
    assert module.sheet(folder)["shaken"] == "not run"


def test_the_engineer_reads_numbers_and_is_never_shown_a_picture(module, folder, fake_client):
    client = fake_client([json.dumps({"notes": [NOTE], "overall": "concerns"})])
    found = module.review(folder, client)
    call = client.calls[0]
    assert call["images"] == [], "the eyes look at pictures; the engineer must not share their mistake"
    assert '"depth": 0.1' in call["prompt"] and "structural engineer" in call["prompt"] and ".png" not in call["prompt"]
    assert found["available"] and found["read"] and found["notes"] == [NOTE] and found["overall"] == "concerns"
    assert json.loads((folder / "review.json").read_text())["notes"] == [NOTE]


def test_notes_name_a_part_the_builder_can_change_and_stay_short(module, folder, fake_client):
    wild = {"part": "the foundations of the mountain", "number": "x" * 900, "concern": "c", "suggest": "s"}
    client = fake_client([json.dumps({"notes": [wild] + [NOTE] * 9, "overall": "concerns"})])
    notes = module.review(folder, client)["notes"]
    assert len(notes) == module.MOST_NOTES == 5
    assert notes[0]["part"] == "other" and len(notes[0]["number"]) <= module.LONGEST and notes[1]["part"] == "ties"


def test_thinking_out_loud_and_prose_around_the_answer_are_tolerated(module, folder, fake_client):
    reply = '<think>The ties {look} thin. {"notes": []}</think>\nHere is my review: ' + json.dumps({"notes": [NOTE], "overall": "concerns"})
    assert module.review(folder, fake_client([reply]))["notes"] == [NOTE]


def test_an_answer_that_cannot_be_read_is_said_so_and_is_no_verdict_on_the_hall(module, folder, fake_client):
    found = module.review(folder, fake_client(["The hall looks fine to me, broadly."]))
    assert found["available"] and not found["read"] and found["notes"] == []
    assert "could not be read" in module.told(found)


def test_an_engineer_who_cannot_be_reached_never_stops_the_builder(module, folder):
    class Away:
        def chat(self, *args, **kwargs):
            raise ModelUnavailable("llama-server at http://127.0.0.1:7330 did not answer")

    found = module.review(folder, Away())
    assert not found["available"] and found["notes"] == []
    assert module.told(found).startswith("REVIEW not available") and "advice" in module.told(found)


def test_the_line_the_builder_reads_says_it_is_advice(module, folder, fake_client):
    line = module.told(module.review(folder, fake_client([json.dumps({"notes": [NOTE], "overall": "concerns"})])))
    assert line.startswith("REVIEW 1 note") and "advice, not a check" in line and "ties: depth 0.10 m over a 5.10 m bay" in line
    quiet = module.told(module.review(folder, fake_client([json.dumps({"notes": [], "overall": "sound"})])))
    assert quiet.startswith("REVIEW 0 notes")


def test_the_operator_can_ask_for_a_review_and_the_engineer_lives_on_the_spark():
    spec = catalog.TOOLS[("hall-carpenter", "review")]
    assert spec.kind == "python" and not spec.needs_model and not spec.work and "review.json" in spec.outputs
    slot = load_profile("spark")["llm.engineer"]
    assert slot.provider == "llamacpp" and slot.options["base_url"] == "http://127.0.0.1:7330"
    assert "Nemotron" in slot.model and slot.options.get("rotating_slot") is True


def test_column_heights_are_given_the_same_way_for_both_and_the_sheet_says_how_to_read_itself(module, folder):
    """The first live review read the hall's columns as 4.87 m tall against a seat at 6.49 m: the sheet gave
    the temple's as foot and top and the hall's as foot and length. It also took the temple's own inner
    rings, which stand inside the outer columns as any roof's do, for the hall's."""
    hall = json.loads((folder / "hall.json").read_text())
    hall["parts"]["columns"].update({"foot": 1.62, "top": 6.49, "diameter": 0.57})
    (folder / "hall.json").write_text(json.dumps(hall))
    sheet = module.sheet(folder)
    assert sheet["columns_compared"] == {"temple": {"foot": 1.62, "top": 6.49, "length": 4.87, "diameter": 0.57},
                                         "hall": {"foot": 1.62, "top": 6.49, "length": 4.87, "diameter": 0.57}}
    assert list(sheet)[0] == "how_to_read", "the conventions come before the numbers"
    read = " ".join(sheet["how_to_read"])
    assert "above the ground" in read and "top minus foot" in read and "negative" in read
    assert "the standing temple" in read and "never the hall" in read


def test_the_temples_column_loads_sit_beside_the_halls_when_they_were_measured(module, folder):
    """The review could never say "your heaviest column carries twice the temple's": the sheet had no
    temple loads. They are measured by the same three tools as the hall's and put beside them."""
    assert module.sheet(folder)["loads"]["temple"] == "not measured"
    (folder / "temple-loads.json").write_text(json.dumps({"summary": {
        "total_N": 13.9e6, "ground_N": 13.9e6, "not_carried_N": 0, "allowed_MPa": 10.0, "overloaded": [],
        "snow": {"total_kN": 360.0}, "posts": [{"name": "Hip end purlin", "carries_kN": 3.0, "design_MPa": 0.4}],
        "columns": [{"name": "Inner timber column", "carries_kN": 518.0, "design_kN": 705.0, "diameter_m": 0.54,
                     "slenderness": 36.2, "design_MPa": 4.03}]}}))
    loads = module.sheet(folder)["loads"]
    assert loads["temple"]["heaviest_column"]["carries_kN"] == 518.0 and loads["hall"]["heaviest_column"]["carries_kN"] == 529.7
    assert loads["temple"]["columns"] == 1 and loads["temple"]["posts_on_the_frame"] == 1
