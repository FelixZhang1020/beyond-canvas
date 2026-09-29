"""A 3D toy figure inspired by a colour painting: parts in, checked figure out. No live model in these tests."""
import json
from pathlib import Path

import pytest
from PIL import ImageColor

from studio.making import figure
from studio.core.errors import ModelCancelled, ModelUnavailable
from studio.making.figure_render import render
from studio.providers.base import ChatResult


def part(shape="sphere", at=(0, .5, 0), size=(.5, .5, .5), colour="#aa5533", turn=(0, 0, 0)):
    return {"shape": shape, "at": list(at), "size": list(size), "turn": list(turn), "colour": colour}


DOG = {"subject": "a brown dog named after the child", "parts": [
    part("capsule", (0, .6, 0), (.5, .8, .4), "#f5f0e1"),          # body, resting on the base
    part("sphere", (0, 1.4, 0), (.4, .4, .4), "#f5f0e1"),          # head, floating .2 above the body
    part("sphere", (-.08, 1.45, .19), (.06, .06, .06), "#111111"),  # eyes on the head
    part("sphere", (.08, 1.45, .19), (.06, .06, .06), "#111111"),
]}


class Writer:
    """Answers in order; records the prompts and pictures it was shown."""

    def __init__(self, answers):
        self.answers, self.calls = list(answers), []

    def chat(self, prompt, images=(), *, system=None, max_tokens=None):
        self.calls.append({"prompt": prompt, "images": list(images), "max_tokens": max_tokens})
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        text = answer if isinstance(answer, str) else json.dumps(answer)
        return ChatResult(text, 1, 1, 0, 0, 0, "stepfun", "step-3.7-flash")


PASS = {"same_subject": True, "faces": "ok", "broken": False, "upsetting": False, "fix": ""}


def test_only_numbers_and_colours_reach_the_figure():
    fig = figure.parse(json.dumps(DOG))
    assert fig["version"] == 1 and len(fig["parts"]) == 4
    assert "subject" not in fig and "named after the child" not in json.dumps(fig)


@pytest.mark.parametrize("change", [
    {"shape": "person"}, {"colour": "sparkly"}, {"colour": "#12345"}, {"at": [0, 1]},
    {"at": [0, float("nan"), 0]}, {"size": [0, .5, .5]}, {"size": [9, .5, .5]}, {"turn": [0, 0, "x"]},
    {"size": [.5, .5]}, {"size": [9]},
])
def test_a_bad_part_refuses_the_whole_answer(change):
    doc = {"parts": [dict(part(), **change), part(), part()]}
    with pytest.raises(ValueError):
        figure.parse(json.dumps(doc))


def test_a_rewrite_that_loosens_the_format_still_reads():
    """In one run three second writings were thrown away for format alone: colour words ("orange", "white"),
    a few characters after the JSON, and a sphere's size as one number. A common colour word becomes its
    colour, trailing text is ignored, one size is the same every way; the prose still never reaches the figure."""
    doc = {"parts": [dict(part(), colour="orange"), dict(part(), colour="White"), dict(part(), size=[.4])]}
    fig = figure.parse(json.dumps(doc) + "\nDone!")
    assert [p["colour"] for p in fig["parts"]][:2] == ["#ffa500", "#ffffff"]
    assert fig["parts"][2]["size"] == [.4, .4, .4] and "Done" not in json.dumps(fig)


def test_an_answer_cut_off_mid_part_keeps_the_parts_that_arrived():
    """The commonest format loss of the overnight run: 14 of 41 unreadable answers were simply cut off,
    every one failing at its last character because the model ran out of room. The parts that did arrive are
    a toy; the half-written one is dropped, and the checks still decide whether it is shown."""
    whole = json.dumps({"parts": [part(), part(), part(), part()]})
    cut = whole[:whole.rindex("}, {") + 4] + '{"shape": "sphere", "at": [0, 0.5'
    fig = figure.parse(cut)
    assert len(fig["parts"]) == 3


def test_an_answer_cut_off_before_three_parts_is_still_refused():
    whole = json.dumps({"parts": [part(), part(), part()]})
    with pytest.raises(ValueError):
        figure.parse(whole[:whole.index("}, {") + 4] + '{"shape": "sph')


@pytest.mark.parametrize("word,colour", [
    ("lavender", "#e6e6fa"), ("peach", "#ffcba4"), ("light blue", "#add8e6"), ("dark_brown", "#631919"),
    ("darkred", "#8b0000"), ("lightgray", "#d3d3d3"), ("medium blue", "#0000cd"), ("light brown", "#c97f7f"),
])
def test_the_reader_takes_the_colour_names_the_model_actually_writes(word, colour):
    """Measured in the overnight run: answers were thrown away whole for naming a colour this way.

    A name is still a closed list. "light X" and "dark X" are a known word in front of a known name: light
    mixes 40% white into it, dark keeps 60% of it, so "dark_brown" is brown's #a52a2a scaled to #631919.
    """
    fig = figure.parse(json.dumps({"parts": [dict(part(), colour=word), part(), part()]}))
    assert fig["parts"][0]["colour"] == colour


@pytest.mark.parametrize("word", ["burnt umber", "dark charcoal grey", "sparkly", "the colour of the sea"])
def test_a_colour_that_is_not_a_known_name_is_still_refused(word):
    with pytest.raises(ValueError):
        figure.parse(json.dumps({"parts": [dict(part(), colour=word), part(), part()]}))


def test_the_toy_is_written_by_one_model_and_looked_at_by_another():
    """Writing a toy and judging it are different jobs with different settings, and one slot used to serve
    both: the overnight speed trial could not tell which half its speed came from. A deployment
    that names no checker keeps using the writer, as every deployment did before."""
    writer = Writer([{"parts": [part(), part(), part()]}])
    checker = Writer([PASS, PASS])
    made = figure.make("data:image/png;base64,AA", writer, looker=checker)
    assert made["held_back"] is False
    assert len(writer.calls) == 1 and len(checker.calls) == 2
    alone = Writer([{"parts": [part(), part(), part()]}, PASS, PASS])
    assert figure.make("data:image/png;base64,AA", alone)["held_back"] is False
    assert len(alone.calls) == 3


def test_a_colour_name_still_reads_after_pillow_has_looked_it_up():
    """Pillow rewrites its own table as it goes: the first getrgb("white") replaces "#ffffff" with
    (255, 255, 255). Reading only the written form passed this file alone and failed the whole suite,
    because by then something had drawn in a named colour."""
    ImageColor.getrgb("white")
    fig = figure.parse(json.dumps({"parts": [dict(part(), colour="White"), dict(part(), colour="light blue"), part()]}))
    assert [p["colour"] for p in fig["parts"]][:2] == ["#ffffff", "#add8e6"]


@pytest.mark.parametrize("given,colour", [
    ([0.45, 0.25, 0.1], "#73401a"), ([0, 0, 0], "#000000"), ([1.0, 1.0, 1.0], "#ffffff"),
])
def test_a_colour_written_as_three_numbers_is_read(given, colour):
    """The second commonest loss of the overnight run: the model wrote colours as red, green, blue from
    0 to 1 for a whole answer. They are numbers, like everything else kept from a figure."""
    fig = figure.parse(json.dumps({"parts": [dict(part(), colour=given), part(), part()]}))
    assert fig["parts"][0]["colour"] == colour


@pytest.mark.parametrize("given", [[1.5, 0, 0], [255, 0, 0], [-0.1, 0, 0], [0.5, 0.5], ["a", "b", "c"]])
def test_numbers_that_are_not_a_colour_from_zero_to_one_are_refused(given):
    with pytest.raises(ValueError):
        figure.parse(json.dumps({"parts": [dict(part(), colour=given), part(), part()]}))


def test_a_part_as_small_as_an_eyelash_is_kept():
    """Whiskers, eyelashes and pupils came as 0.005 and were thrown away with the whole answer; a part that
    small cannot break anything, and the floor is there only to refuse nothing-sized parts."""
    fig = figure.parse(json.dumps({"parts": [dict(part(), size=[.005, .005, .1]), part(), part()]}))
    assert fig["parts"][0]["size"] == [.005, .005, .1]


@pytest.mark.parametrize("parts", [[], [part()] * 2, [part()] * 141])
def test_a_figure_has_three_to_one_hundred_and_forty_parts(parts):
    with pytest.raises(ValueError):
        figure.parse(json.dumps({"parts": parts}))


def test_a_floating_head_settles_onto_its_body_and_keeps_its_eyes():
    settled = figure.settle(figure.parse(json.dumps(DOG)))
    body, head, eye = settled["parts"][0], settled["parts"][1], settled["parts"][2]
    assert head["at"][1] - head["size"][1] / 2 == pytest.approx(body["at"][1] + body["size"][1] / 2, abs=1e-6)
    assert eye["at"][1] - head["at"][1] == pytest.approx(1.45 - 1.4)   # the eyes travelled with the head


def test_settling_only_ever_moves_parts_down_onto_the_base():
    lifted = {"parts": [part("box", (0, 2, 0), (1, .4, 1)), part(at=(0, 2.4, 0)), part(at=(.3, 2.4, 0))]}
    settled = figure.settle(figure.parse(json.dumps(lifted)))
    lowest = min(p["at"][1] - p["size"][1] / 2 for p in settled["parts"])
    assert lowest == pytest.approx(0, abs=1e-6)
    assert all(s["at"][1] <= p["at"][1] for s, p in zip(settled["parts"], lifted["parts"]))


def test_a_ground_slab_keeps_its_colour_and_lies_flat_on_the_base():
    doc = {"parts": [part("cylinder", (0, .3, 0), (2, .08, 2), "#6a3fa0"), part(at=(0, .6, 0)), part(at=(.2, .6, 0))]}
    settled = figure.settle(figure.parse(json.dumps(doc)))
    assert settled["parts"][0]["colour"] == "#6a3fa0"
    assert settled["parts"][0]["at"][1] == pytest.approx(.04)


def test_the_preview_is_a_picture_of_the_figure_not_an_empty_base():
    image = render(figure.settle(figure.parse(json.dumps(DOG))), 30, 320, 240)
    assert image.size == (320, 240)
    colours = {c for _, c in image.getcolors(320 * 240)}
    assert (0xf5 * .36 <= max(c[0] for c in colours))   # lit body colour present, not just background and base


def test_a_figure_that_passes_the_look_is_returned_after_one_writing():
    painting = "data:image/png;base64,iVBORw0KGgo="
    writer = Writer([DOG, PASS, PASS])
    made = figure.make(painting, writer)
    assert made["held_back"] is False and made["figure"]["version"] == 1
    assert len(writer.calls) == 3 and writer.calls[1]["images"][0] == painting   # the look sees the painting too


def test_a_failed_look_writes_again_with_the_reason_twice_then_holds_back():
    """Three writings, not two: the third kept about six more toys a class (docs/measured/figure-three-writings.md)."""
    fail = dict(PASS, faces="missing", fix="Give the shark its teeth.")
    writer = Writer([DOG, fail, DOG, dict(fail, fix="Open the shark's mouth."), DOG, fail])
    made = figure.make("data:image/png;base64,iVBORw0KGgo=", writer)
    assert made["held_back"] is True and "figure" not in made and made["reason_code"] == "figure_held_back"
    assert made["writings"] == 3 and len(writer.calls) == 6
    assert "Give the shark its teeth." in writer.calls[2]["prompt"]
    assert "Open the shark's mouth." in writer.calls[4]["prompt"], "the third writing hears what the second got wrong"


def test_a_third_writing_that_passes_is_used():
    fail = dict(PASS, broken=True, fix="Attach the head.")
    made = figure.make("data:image/png;base64,iVBORw0KGgo=", Writer([DOG, fail, DOG, fail, DOG, PASS, PASS]))
    assert made["held_back"] is False and made["writings"] == 3


def test_a_second_writing_that_passes_is_used():
    writer = Writer([DOG, dict(PASS, broken=True, fix="Attach the head."), DOG, PASS, PASS])
    assert figure.make("data:image/png;base64,iVBORw0KGgo=", writer)["held_back"] is False


@pytest.mark.parametrize("look", ["not json", {"same_subject": "yes"}, dict(PASS, upsetting=True),
                                  dict(PASS, same_subject=False), dict(PASS, faces="missing")])
def test_anything_but_a_clear_pass_is_not_shown(look):
    writer = Writer([DOG, look, DOG, look, DOG, look])
    assert figure.make("data:image/png;base64,iVBORw0KGgo=", writer)["held_back"] is True


def test_an_unusable_answer_is_written_again_and_an_outage_is_not_hidden():
    writer = Writer(["not a figure", DOG, PASS, PASS])
    assert figure.make("data:image/png;base64,iVBORw0KGgo=", writer)["held_back"] is False
    with pytest.raises(ModelUnavailable):
        figure.make("data:image/png;base64,iVBORw0KGgo=", Writer([ModelUnavailable("offline")]))


def test_a_stopped_request_pays_for_no_further_call():
    """The teacher's stop is read before every call: a figure is up to twelve calls and minutes long, and the
    class stays locked while it runs (a stopped teacher report once paid for a second draft the same way)."""
    writer = Writer([DOG, PASS])
    with pytest.raises(ModelCancelled):
        figure.make("data:image/png;base64,iVBORw0KGgo=", writer, cancelled=lambda: True)
    assert writer.calls == []
    writer = Writer([DOG, PASS])
    with pytest.raises(ModelCancelled):
        figure.make("data:image/png;base64,iVBORw0KGgo=", writer, cancelled=lambda: len(writer.calls) == 1)
    assert len(writer.calls) == 1   # the look check after the writing was not paid for


def test_every_unit_shape_spans_one_on_each_axis_in_the_preview_and_the_viewer():
    """"size" is a part's full extent, which settling relies on. The ring was a quarter as thick as its
    size said (tube .125 either side), so it was drawn thin and settled a gap below and above it."""
    from pathlib import Path
    from studio.making.figure_render import UNITS
    for shape, triangles in UNITS.items():
        points = [p for t in triangles for p in t]
        spans = [max(p[k] for p in points) - min(p[k] for p in points) for k in range(3)]
        assert all(abs(s - 1) < .02 for s in spans), (shape, spans)
    viewer = Path("studio/showcase_3d/figure.js").read_text()
    assert "TorusGeometry(.375, .125, 12, 32).rotateX(Math.PI / 2).scale(1, 4, 1)" in viewer


def test_the_writer_gets_room_to_think():
    writer = Writer([DOG, PASS, PASS])
    figure.make("data:image/png;base64,iVBORw0KGgo=", writer)
    assert writer.calls[0]["max_tokens"] >= 32000   # 16000 ran out on the savanna painting


IMG = "data:image/png;base64,iVBORw0KGgo="


def test_a_figure_is_shown_only_when_two_looks_both_pass():
    """Operator: the check gave different answers on the same toy on repeat, so a figure is shown
    only when two independent looks agree it is the painting's subject and fit to show."""
    writer = Writer([DOG, PASS, PASS])
    made = figure.make(IMG, writer)
    assert not made["held_back"] and len(writer.calls) == 3


def test_a_second_look_that_disagrees_sends_the_toy_back_with_its_reason():
    fail = dict(PASS, same_subject=False, fix="Make it the shark.")
    writer = Writer([DOG, PASS, fail, DOG, PASS, PASS])
    made = figure.make(IMG, writer)
    assert not made["held_back"] and made["writings"] == 2 and "Make it the shark." in writer.calls[3]["prompt"]


def test_a_first_look_that_fails_is_not_asked_again():
    """Both must pass, so a first fail already decides; the second look is not paid for."""
    writer = Writer([DOG, dict(PASS, broken=True, fix="Attach the head."), DOG, PASS, PASS])
    made = figure.make(IMG, writer)
    assert made["writings"] == 2 and len(writer.calls) == 5


def test_the_look_check_gets_room_to_think():
    """8000 ran out: Step 3.7 Flash spent it all on hidden reasoning and answered nothing, which a
    class would have read as the model being unavailable."""
    writer = Writer([DOG, PASS, PASS])
    figure.make("data:image/png;base64,iVBORw0KGgo=", writer)
    assert writer.calls[1]["max_tokens"] >= 16000


def test_a_painted_floor_is_drawn_over_the_base_not_cut_into_wedges():
    """Nothing sits below the base, so the base is drawn first. Sorted with the parts, its top was cut
    into light and dark wedges over a painted floor, and that is the picture the checks were shown."""
    floor = {"version": 1, "parts": [{"shape": "cylinder", "at": [0, .02, 0], "size": [2, .04, 2],
                                      "turn": [0, 0, 0], "colour": "#c00000"}]}
    image = render(floor, 0, 480, 360)
    band = [image.getpixel((x, 180)) for x in range(170, 311, 5)]
    assert all(r > 50 and g < 20 and b < 20 for r, g, b in band), band


def test_the_look_check_never_asks_for_writing_and_wants_eyes_only_on_the_main_characters():
    """Operator: a zoo toy showing the giraffes, lion, building and birds was held back for not
    spelling "ZOO" and for eyeless tiny birds. A toy of shapes cannot spell, and a background speck needs no
    face; the main characters still keep their eyes."""
    look = (Path("skills/painting-to-figure/assets/prompts/look.txt")).read_text()
    assert "never ask for writing" in look.lower()
    assert "main character" in look and "every face in the painting" not in look
    assert "main character" in figure.FIX_INSTRUCTION["unclear"]


def test_a_busy_scene_becomes_a_toy_of_its_one_main_subject_and_the_look_accepts_it():
    """Operator: every Christmas-castle painting was held back one day, the look finding the
    princess, soldiers and mice missing their eyes. A toy of simple shapes cannot carry a dozen faces, so a
    busy scene makes its one main thing alone, and the look does not count the characters left out."""
    write = Path("skills/painting-to-figure/assets/prompts/figure.txt").read_text()
    look = Path("skills/painting-to-figure/assets/prompts/look.txt").read_text()
    assert "busy scene" in write and "one main subject" in write
    assert "busy scene" in look and "left out are not missing" in look
    assert "busy scene" in figure.FIX_INSTRUCTION["unclear"]


def test_the_figure_writer_has_time_for_its_slowest_measured_writing_and_drafts_keep_three_minutes(monkeypatch):
    """vlm.figure writes the figure; its slowest writing measured 151 s with two running. The
    scene and story drafts on vlm.creation keep the default: a hung draft locks the class until it ends."""
    from studio.core.slots import load_profile
    profile = load_profile("stepfun")
    assert profile["vlm.figure"].options["timeout_s"] >= 300
    assert profile["vlm.creation"].options["timeout_s"] == 180
    from studio.core.deployments import build_runtime
    monkeypatch.setenv("STEPFUN_API_KEY", "test-key")
    clients = build_runtime("stepfun").clients   # what start-up hands the classroom
    assert clients["vlm.figure"]._client.timeout.read >= 300
    assert clients["vlm.creation"].behind._client.timeout.read == 180   # Qwen on the Spark
