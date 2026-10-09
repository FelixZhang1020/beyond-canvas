"""NVIDIA's safety model beside the four-verdict check: what each of them may decide.

The rule is the operator's. At the door only sexual content stops a drawing, and only
when the model says so twice; any other flag lets the drawing in, answered warmly, with codes for
the teacher and never the model's words. On the way out any flag refuses the machine-made picture.
A model that cannot be reached, or whose answer cannot be read, stops nothing: the check the studio
has always had still decides, and the record says the second look was not there.
"""

from pathlib import Path

import pytest
from conftest import load_script

from studio.core.errors import ModelUnavailable

SCRIPT = Path("skills/studio-safety/scripts/safety.py")
IMAGE = "data:image/png;base64,AAAA"
ALLOW = '{"verdict": "allow", "reason": "a crayon house", "text_found": []}'
SOFTEN = '{"verdict": "soften", "reason": "a monster with teeth", "text_found": []}'
PHOTO = '{"verdict": "block", "reason": "a photograph of a room", "text_found": []}'
SAFE = "User Safety: safe"
VIOLENCE = "User Safety: unsafe\nSafety Categories: Violence, Threat"
SEXUAL = "User Safety: unsafe\nSafety Categories: Sexual"
PROSE = "<think>The child has drawn someone being stabbed, which worries me.</think>\n" + VIOLENCE


class Reader:
    """NVIDIA's model, replaying canned answers and remembering what it was asked."""

    def __init__(self, answers):
        self.answers, self.asked = list(answers), []

    def look(self, image, question):
        self.asked.append((image, question))
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


@pytest.fixture(scope="module")
def module():
    return load_script(SCRIPT, "safety_script_second_look")


def test_without_a_second_reader_nothing_changes(module, fake_client):
    result = module.screen(IMAGE, fake_client([ALLOW]))
    assert result.verdict == "allow" and result.second_look == "" and result.ledger_note == "allow"


def test_a_clean_second_look_leaves_the_verdict_alone_and_is_written_down(module, fake_client):
    reader = Reader([SAFE])
    result = module.screen(IMAGE, fake_client([ALLOW]), second=reader)
    assert result.verdict == "allow" and result.teacher_codes == ()
    assert result.second_look == "clear" and result.ledger_note == "allow second-look:clear"
    assert reader.asked == [(IMAGE, module.second_look_rule().QUESTIONS["door"])]


def test_a_drawing_flagged_for_violence_comes_in_answered_warmly_with_codes_only(module, fake_client):
    result = module.screen(IMAGE, fake_client([ALLOW]), second=Reader([PROSE]))
    assert result.may_proceed and result.verdict == "soften", "a flag that is not sexual never stops a child"
    assert result.teacher_codes == ("violence", "threat")
    assert result.ledger_note == "soften second-look:violence,threat"
    assert "stabbed" not in repr(result), "the model's words about a child's drawing go no further than the reader"


def test_sexual_content_stops_the_drawing_before_any_other_model_sees_it(module, fake_client):
    first = fake_client([])
    result = module.screen(IMAGE, first, second=Reader([SEXUAL, SEXUAL]))
    assert not result.may_proceed and result.verdict == "unsafe"
    assert result.reason == "nemotron_sexual" and result.ledger_note == "unsafe second-look:sexual"
    assert first.calls == [], "a picture stopped at the door is not sent on to a company"


def test_one_unstable_stop_does_not_turn_a_child_away(module, fake_client):
    reader = Reader([SEXUAL, SAFE])
    result = module.screen(IMAGE, fake_client([ALLOW]), second=reader)
    assert result.may_proceed and result.verdict == "allow" and len(reader.asked) == 2


def test_a_photo_and_a_blank_page_stay_the_four_verdict_checks_business(module, fake_client):
    result = module.screen(IMAGE, fake_client([PHOTO, PHOTO]), second=Reader([SAFE]))
    assert result.verdict == "block" and not result.may_proceed and result.second_look == "clear"


@pytest.mark.parametrize("trouble", [ModelUnavailable("connection refused"), "I cannot help with that."])
def test_a_second_reader_that_is_down_or_unreadable_stops_nothing_and_is_written_down(module, fake_client, trouble):
    result = module.screen(IMAGE, fake_client([SOFTEN]), second=Reader([trouble]))
    assert result.verdict == "soften" and result.may_proceed
    assert result.second_look == "unavailable" and result.ledger_note == "soften second-look:unavailable"


def test_on_the_way_out_any_flag_refuses_the_picture_on_one_look(module, fake_client):
    first, reader = fake_client([]), Reader([VIOLENCE])
    result = module.screen(IMAGE, first, second=reader, point="out")
    assert not result.may_proceed and result.verdict == "unsafe" and result.reason == "nemotron_flagged"
    assert first.calls == [] and len(reader.asked) == 1, "a machine-made picture refused costs one retry, not two looks"
    assert reader.asked[0][1] == module.second_look_rule().QUESTIONS["out"]


def test_on_the_way_out_a_clean_look_still_leaves_the_old_check_to_decide(module, fake_client):
    unsafe = '{"verdict": "unsafe", "reason": "private", "text_found": []}'
    assert module.screen(IMAGE, fake_client([ALLOW]), second=Reader([SAFE]), point="out").may_proceed
    assert not module.screen(IMAGE, fake_client([unsafe, unsafe]), second=Reader([SAFE]), point="out").may_proceed


def test_on_the_way_out_a_reader_that_is_down_leaves_the_old_check_to_decide(module, fake_client):
    result = module.screen(IMAGE, fake_client([ALLOW]), second=Reader([ModelUnavailable("down")]), point="out")
    assert result.may_proceed and result.second_look == "unavailable"


def test_only_the_two_points_the_studio_has_can_be_asked_about(module, fake_client):
    with pytest.raises(ValueError):
        module.screen(IMAGE, fake_client([ALLOW]), second=Reader([SAFE]), point="sideways")


def test_the_command_line_can_ask_the_second_reader_alone_and_never_builds_the_other_model(module, monkeypatch, capsys):
    """A run on the Spark names one model to the operator, so it must be able to ask that one only."""
    def no_chat_model(config):
        raise AssertionError("the four-verdict model was not named for this run")
    monkeypatch.setattr(module, "build_client", no_chat_model)
    monkeypatch.setattr(module, "build_safety_reader", lambda config: Reader([VIOLENCE]))
    module.main(["skills/art-feedback/evals/files/dog-sun.png", "--profile", "spark", "--second-slot", "safety.reader",
                 "--second-only", "--point", "out"])
    printed = capsys.readouterr().out
    assert printed.startswith("unsafe second-look:violence,threat: nemotron_flagged") and printed.rstrip().endswith("s)")


def test_asking_the_second_reader_alone_needs_its_slot(module):
    with pytest.raises(SystemExit):
        module.main(["skills/art-feedback/evals/files/dog-sun.png", "--second-only"])
