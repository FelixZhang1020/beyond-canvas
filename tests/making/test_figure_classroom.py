"""painting-to-figure inside a class: colour entrance only, checked, cached, recorded without prose."""
import json

import pytest

from studio.core.errors import ModelUnavailable
from studio.classroom.portfolio import Portfolio
from tests.making.test_figure import DOG, PASS
from tests.making.test_sketch import ALLOW, classroom


def figure_run(room, sid, did):
    request = room.request(sid, "painting-to-figure", [did], {})
    room.run_request(request["request_id"])
    return list(room.follow(request["request_id"]))


def done(events):
    return next(data for name, data in events if name == "done")


def test_the_figure_is_offered_only_on_the_colour_entrance(tmp_path):
    room, sid, did, _, _ = classroom(tmp_path, [], entrance="sketch")
    try:
        with pytest.raises(ValueError, match="colour entrance"):
            room.request(sid, "painting-to-figure", [did], {})
    finally:
        room.close()


def test_a_colour_painting_gets_a_checked_figure_and_no_model_prose(tmp_path):
    room, sid, did, writer, screener = classroom(tmp_path, [json.dumps(DOG), json.dumps(PASS), json.dumps(PASS)],
                                                 entrance="colour")
    screener.replies.append(ALLOW)   # the preview is screened too, after the painting
    try:
        assert "painting-to-figure" in room.health()["skills"]
        data = done(figure_run(room, sid, did))
        assert data["stage"] == "painting-to-figure" and data.get("status") != "stopped"
        figure = data["outputs"]["figure"]
        assert figure["version"] == 1 and len(figure["parts"]) == len(DOG["parts"])
        assert "named after the child" not in json.dumps(data)
        assert len(screener.calls) == 2 and len(writer.calls) == 3   # painting + preview; writing + two looks
        stages = {row["stage"] for row in room.ledger_lines(sid)}
        assert stages == {"studio-safety", "painting-to-figure"}
    finally:
        room.close()


def test_a_class_with_a_figure_writer_of_its_own_writes_the_figure_there(tmp_path):
    """StepFun First gives the figure its own slot (vlm.figure) so it can wait longer than a draft."""
    from tests.conftest import FakeClient
    room, sid, did, studio_writer, screener = classroom(tmp_path, [], entrance="colour")
    screener.replies.append(ALLOW)
    figure_writer = FakeClient([json.dumps(DOG), json.dumps(PASS), json.dumps(PASS)])
    room.clients["vlm.figure"] = figure_writer
    try:
        assert "figure" in done(figure_run(room, sid, did))["outputs"]
        assert len(figure_writer.calls) == 3 and studio_writer.calls == []
    finally:
        room.close()


def test_a_class_that_names_a_checker_looks_at_the_toy_there(tmp_path):
    """The toy's check has its own slot (vlm.figure.look): the writer lists parts, the
    checker judges a picture, and one setting used to move both."""
    from tests.conftest import FakeClient
    room, sid, did, studio_writer, screener = classroom(tmp_path, [], entrance="colour")
    screener.replies.append(ALLOW)
    figure_writer = FakeClient([json.dumps(DOG)])
    figure_checker = FakeClient([json.dumps(PASS), json.dumps(PASS)])
    room.clients["vlm.figure"] = figure_writer
    room.clients["vlm.figure.look"] = figure_checker
    try:
        assert "figure" in done(figure_run(room, sid, did))["outputs"]
        assert len(figure_writer.calls) == 1 and len(figure_checker.calls) == 2 and studio_writer.calls == []
    finally:
        room.close()


def test_a_figure_is_made_once_per_painting(tmp_path):
    room, sid, did, writer, screener = classroom(tmp_path, [json.dumps(DOG), json.dumps(PASS), json.dumps(PASS)],
                                                 entrance="colour")
    screener.replies.append(ALLOW)
    try:
        first, second = done(figure_run(room, sid, did)), done(figure_run(room, sid, did))
        assert first["outputs"]["figure"] == second["outputs"]["figure"] and len(writer.calls) == 3
    finally:
        room.close()


def test_a_figure_that_fails_its_checks_is_held_back_in_plain_words(tmp_path):
    fail = json.dumps(dict(PASS, broken=True, fix="Attach the head."))
    room, sid, did, _, screener = classroom(tmp_path, [json.dumps(DOG), fail] * 3, entrance="colour")
    screener.replies += [ALLOW] * 3
    try:
        data = done(figure_run(room, sid, did))
        assert data["status"] == "stopped" and data["reason_code"] == "figure_held_back"
        assert data["message"] and "figure" not in data.get("outputs", {})
    finally:
        room.close()


BLOCK = '{"verdict":"block","reason":"a computer picture, not a child drawing","text_found":[]}'
UNSAFE = '{"verdict":"unsafe","reason":"","text_found":[]}'


def test_a_toy_the_screen_calls_not_artwork_is_still_shown(tmp_path):
    """Operator: Qwen screens the preview with its thinking off, and called harmless toys (a teddy
    bear, a Christmas tree) "block", the verdict for a photograph or a screenshot. The studio drew the toy and it
    can never be a photograph, so "not artwork" does not hold it back; harm still does (the next test)."""
    room, sid, did, writer, screener = classroom(tmp_path, [json.dumps(DOG), json.dumps(PASS), json.dumps(PASS)],
                                                 entrance="colour")
    screener.replies += [BLOCK, BLOCK]   # a stop is asked twice before it stands
    try:
        data = done(figure_run(room, sid, did))
        assert data.get("status") != "stopped" and "figure" in data["outputs"]
    finally:
        room.close()


def test_a_toy_the_screen_calls_unsafe_is_still_held_back(tmp_path):
    room, sid, did, writer, screener = classroom(tmp_path, [json.dumps(DOG)] * 3, entrance="colour")
    screener.replies += [UNSAFE] * 6   # three writings, each preview asked twice
    try:
        data = done(figure_run(room, sid, did))
        assert data["status"] == "stopped" and data["reason_code"] == "figure_held_back"
        assert len(writer.calls) == 3   # written three times and never looked at
    finally:
        room.close()


def test_a_screening_outage_is_reported_as_one_not_as_a_poor_figure(tmp_path):
    room, sid, did, writer, screener = classroom(tmp_path, [json.dumps(DOG)], entrance="colour")
    answer = screener.chat
    def down_after_the_painting(*args, **kwargs):
        if screener.replies:
            return answer(*args, **kwargs)   # the painting itself is screened
        raise ModelUnavailable("the screener is down")
    screener.chat = down_after_the_painting
    try:
        data = done(figure_run(room, sid, did))
        assert data["status"] == "stopped" and data["reason_code"] == "model_unavailable"
        assert len(writer.calls) == 1   # no second writing paid for a screen that never ran
    finally:
        room.close()


def test_stop_ends_the_figure_between_calls_and_frees_the_class(tmp_path):
    room, sid, did, writer, screener = classroom(tmp_path, [json.dumps(DOG), json.dumps(PASS)], entrance="colour")
    screener.replies.append(ALLOW)
    request = room.request(sid, "painting-to-figure", [did], {})
    write = writer.chat
    def stopped_while_writing(*args, **kwargs):
        room.cancel(sid, request["request_id"])
        return write(*args, **kwargs)
    writer.chat = stopped_while_writing
    try:
        room.run_request(request["request_id"])
        assert len(writer.calls) == 1 and len(screener.calls) == 1   # no preview screen, no look check
        assert room.figure_slot.acquire(blocking=False)
        room.figure_slot.release()
    finally:
        room.close()


def test_the_figure_preview_is_screened_on_the_way_out_like_any_picture_the_studio_makes(tmp_path):
    """NVIDIA's second reader asks the way-out question of a machine-made picture; a flagged preview is
    written twice more and then held back, and only its code is kept."""
    from studio.conversation.conversation import Conversation
    from studio.core.ledger import Ledger
    from studio.providers.safetyreader import WithSecondLook
    from tests.classroom.test_classroom import DRAWING, Scripted
    from tests.skills.test_safety_reader_wiring import VIOLENCE, Reader
    reader = Reader(["User Safety: safe", VIOLENCE, VIOLENCE, VIOLENCE])
    conversation = Conversation(DRAWING, Ledger(tmp_path / "ledger.jsonl"), entrance="colour", studio=Scripted([]),
                                director=Scripted([]), creation=Scripted([json.dumps(DOG)] * 3),
                                screener=WithSecondLook(Scripted([ALLOW]), reader))
    beat = conversation.figure("flagged-figure")
    assert not beat.ok and beat.reason_code == "figure_held_back"
    assert len(reader.asked) == 4 and reader.asked[1] != reader.asked[0], "the door, then the way out three times"
    assert "Violence" not in (tmp_path / "ledger.jsonl").read_text()
    from studio.server.stream import ledger_line
    held = [e for e in Ledger(tmp_path / "ledger.jsonl").entries() if e.stage == "figure"][-1]
    assert ledger_line(held, "r")["second_look"] == "violence", "the record names what stopped it, never 'clear'"


def test_a_figure_shown_after_a_flagged_first_writing_is_recorded_by_the_look_it_passed(tmp_path):
    """The first writing was flagged and written again; the teacher's view must not show that flag
    beside the figure that was shown (review)."""
    from studio.conversation.conversation import Conversation
    from studio.core.ledger import Ledger
    from studio.providers.safetyreader import WithSecondLook
    from studio.server.stream import ledger_line
    from tests.classroom.test_classroom import DRAWING, Scripted
    from tests.skills.test_safety_reader_wiring import VIOLENCE, Reader
    reader = Reader(["User Safety: safe", VIOLENCE] + ["User Safety: safe"] * 6)
    conversation = Conversation(DRAWING, Ledger(tmp_path / "ledger.jsonl"), entrance="colour", studio=Scripted([]),
                                director=Scripted([]), creation=Scripted([json.dumps(DOG)] * 2 + [json.dumps(PASS)] * 4),
                                screener=WithSecondLook(Scripted([ALLOW] * 8), reader))
    assert conversation.figure("second-writing-shown").ok
    shown = [e for e in Ledger(tmp_path / "ledger.jsonl").entries() if e.stage == "figure"][-1]
    assert ledger_line(shown, "r")["second_look"] == "clear"


def test_the_colour_planners_figure_output_is_filed_as_painting_to_figure(tmp_path):
    # The page's planner has one "make" action with two outputs: the clip and the figure.
    room, sid, did, writer, screener = classroom(tmp_path, [json.dumps(DOG), json.dumps(PASS), json.dumps(PASS)],
                                                 entrance="colour")
    screener.replies.append(ALLOW)
    try:
        request = room.request(sid, "painting-to-animation", [did], {"media_kind": "figure", "hint": "ignored"})
        assert request["plan"][-1] == {"stage": "painting-to-figure", "skill": "painting-to-figure"}
        room.run_request(request["request_id"])
        data = done(list(room.follow(request["request_id"])))
        assert data["stage"] == "painting-to-figure" and data["outputs"]["figure"]["version"] == 1
    finally:
        room.close()
    room, sid, did, _, _ = classroom(tmp_path / "sketch", [], entrance="sketch")
    try:
        with pytest.raises(ValueError, match="colour entrance"):
            room.request(sid, "painting-to-animation", [did], {"media_kind": "figure"})
    finally:
        room.close()


def test_the_saved_course_lists_a_figure_as_a_figure(tmp_path):
    store = Portfolio(tmp_path / "courses.db")
    store.begin("course", "colour", "zh", "")
    store.record("course", "made", "painting-to-figure", ["d"], {"figure": {"version": 1, "parts": []}, "language": "zh"})
    kinds = [item["summary"]["kind"] for item in store.course("course")["activities"]]
    assert kinds == ["figure"]
