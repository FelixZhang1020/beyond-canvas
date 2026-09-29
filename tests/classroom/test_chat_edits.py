"""A drawing's conversation can be cleared for good, or its last round taken back.

Asked for when a conversation stuck on two unanswered rounds had no way out. A round
is the child's words and everything the companion said after them. Both erase from the Portfolio
and from what the class remembers, so a reopened course and the next story draft agree with the
screen; neither touches the drawing or anything else made from it.
"""
import json
import urllib.error

import pytest

from studio.classroom.portfolio import DrawingInUse, Portfolio
from test_classroom import room, png, CLASS  # noqa: F401
from test_remove_drawing import studio_with_portfolio  # noqa: F401
from tests.server.test_serve import add_drawing, call, open_class


def said(classroom, sid, did, rid, skill, output):
    """What a finished request leaves behind: a Portfolio record and the class's memory of it."""
    classroom.portfolio.record(sid, rid, skill, [did], output)
    session = classroom.sessions[sid]
    classroom._remember_creation(session, did, skill, output)
    if skill == "confirmed-words":
        session.transcripts[did] = output["text"]


@pytest.fixture
def chat(tmp_path, room, png):
    classroom = room([])
    classroom.portfolio = Portfolio(tmp_path / "history.sqlite3")
    sid = classroom.begin(CLASS)
    did, other = classroom.add_drawing(sid, png), classroom.add_drawing(sid, png)
    said(classroom, sid, did, "r1", "art-feedback", {"text": "Snow on the trees.", "question": "Falling or still?", "beat": "opening"})
    classroom.sessions[sid].openings[did] = "Snow on the trees.\nFalling or still?"
    said(classroom, sid, did, "r2-words", "confirmed-words", {"text": "Still falling"})
    said(classroom, sid, did, "r2", "art-feedback", {"text": "Still falling, softly.", "beat": "reply"})
    said(classroom, sid, did, "r3-words", "confirmed-words", {"text": "UNMISTAKABLE-LAST-ANSWER"})
    said(classroom, sid, did, "r3", "art-feedback", {"status": "stopped", "message": "No answer."})
    said(classroom, sid, other, "o1", "art-feedback", {"text": "A red house.", "beat": "opening"})
    classroom.portfolio.record(sid, "t1", "teacher-review", [did], {"text": "For the teacher."})
    yield classroom, sid, did, other
    classroom.close()


def ids(classroom, sid):
    return [a["id"] for a in classroom.portfolio.course(sid)["activities"]]


def test_taking_back_the_last_round_leaves_every_earlier_one(chat):
    classroom, sid, did, other = chat
    classroom.forget_chat(sid, did, last_round=True)
    assert ids(classroom, sid) == ["r1", "r2-words", "r2", "o1", "t1"]
    session = classroom.sessions[sid]
    assert session.transcripts[did] == "Still falling"
    assert session.dialogue[did][-1] == "Companion: Still falling, softly."
    assert session.openings[did] == "Snow on the trees.\nFalling or still?"


def test_taken_back_words_are_not_left_readable_inside_the_file(chat):
    classroom, sid, did, _ = chat
    classroom.forget_chat(sid, did, last_round=True)
    assert b"UNMISTAKABLE-LAST-ANSWER" not in classroom.portfolio.path.read_bytes()


def test_clearing_erases_the_whole_conversation_and_nothing_else(chat):
    classroom, sid, did, other = chat
    classroom._conversation(classroom.sessions[sid], did).opening = "Snow on the trees."
    classroom.forget_chat(sid, did)
    assert ids(classroom, sid) == ["o1", "t1"]
    session = classroom.sessions[sid]
    assert did not in session.dialogue and did not in session.transcripts and did not in session.openings
    assert session.conversations[did].opening == ""
    assert session.dialogue[other] == ["Companion: A red house."]
    assert did in session.drawings


def test_with_no_answer_given_there_is_nothing_to_take_back(tmp_path, room, png):
    classroom = room([])
    classroom.portfolio = Portfolio(tmp_path / "history.sqlite3")
    try:
        sid = classroom.begin(CLASS); did = classroom.add_drawing(sid, png)
        said(classroom, sid, did, "r1", "art-feedback", {"text": "Hello.", "beat": "opening"})
        with pytest.raises(DrawingInUse) as refused:
            classroom.forget_chat(sid, did, last_round=True)
        assert refused.value.code == "nothing_to_undo"
        assert ids(classroom, sid) == ["r1"]
    finally:
        classroom.close()


def test_nothing_is_taken_back_while_the_companion_is_answering(tmp_path, room, png):
    classroom = room([])
    classroom.portfolio = Portfolio(tmp_path / "history.sqlite3")
    try:
        sid = classroom.begin(CLASS); did = classroom.add_drawing(sid, png)
        said(classroom, sid, did, "r1-words", "confirmed-words", {"text": "A bear."})
        classroom.request(sid, "art-feedback", [did], {})  # asked for, not yet finished
        for last_round in (True, False):
            with pytest.raises(DrawingInUse) as refused:
                classroom.forget_chat(sid, did, last_round=last_round)
            assert refused.value.code == "drawing_busy"
        assert ids(classroom, sid) == ["r1-words"]
    finally:
        classroom.close()


def test_the_page_takes_back_a_round_and_clears_a_conversation(studio_with_portfolio):
    base, classroom = studio_with_portfolio
    sid = open_class(base)
    did = add_drawing(base, sid)
    with pytest.raises(urllib.error.HTTPError) as refused:
        call(base, "DELETE", f"/api/session/{sid}/drawings/{did}/last-round")
    assert refused.value.code == 400
    assert json.loads(refused.value.read())["code"] == "nothing_to_undo"
    classroom.portfolio.record(sid, "w", "confirmed-words", [did], {"text": "A bear."})
    assert call(base, "DELETE", f"/api/session/{sid}/drawings/{did}/last-round") == (204, None)
    classroom.portfolio.record(sid, "o", "art-feedback", [did], {"text": "Hello.", "beat": "opening"})
    assert call(base, "DELETE", f"/api/session/{sid}/drawings/{did}/conversation") == (204, None)
    assert classroom.portfolio.course(sid)["activities"] == []


def _no_answer(*args, **kwargs):
    from studio.core.errors import ModelUnavailable
    raise ModelUnavailable("the model did not answer")


def test_words_sent_again_after_an_unanswered_round_are_not_saved_twice(tmp_path, room, png):
    """After a stop the page puts the child's words back in the field, so Send
    retries that round. Saving them again would show the child saying it twice."""
    from test_classroom import ALLOW, GOOD, GROUNDED, CLEAN, FOLLOWS, NOTHING_INVENTED, run
    reply = "So the dog ran away from your house. Where was he going?"
    classroom = room([ALLOW, GOOD, GROUNDED, CLEAN, reply, CLEAN, NOTHING_INVENTED, FOLLOWS])
    classroom.portfolio = Portfolio(tmp_path / "history.sqlite3")
    try:
        sid = classroom.begin(CLASS); did = classroom.add_drawing(sid, png)
        run(classroom, sid, did)
        # A real round nobody answered (review: set by hand, nothing held the line that marks it).
        answering, classroom.client.chat = classroom.client.chat, _no_answer
        run(classroom, sid, did, {"transcript": "the dog ran away"})
        classroom.client.chat = answering
        run(classroom, sid, did, {"transcript": "the dog ran away"})
        words = [a for a in classroom.portfolio.course(sid)["activities"] if a["skill"] == "confirmed-words"]
        assert [a["summary"]["text"] for a in words] == ["the dog ran away"]
        assert classroom.sessions[sid].dialogue[did][-1].startswith("Companion: ")
    finally:
        classroom.close()


def test_the_same_words_after_an_answer_are_a_new_answer(tmp_path, room, png):
    from test_classroom import ALLOW, GOOD, GROUNDED, CLEAN, FOLLOWS, NOTHING_INVENTED, run
    reply = "So the dog ran away from your house. Where was he going?"
    classroom = room([ALLOW, GOOD, GROUNDED, CLEAN, reply, CLEAN, NOTHING_INVENTED, FOLLOWS,
                      reply, CLEAN, NOTHING_INVENTED, FOLLOWS])
    classroom.portfolio = Portfolio(tmp_path / "history.sqlite3")
    try:
        sid = classroom.begin(CLASS); did = classroom.add_drawing(sid, png)
        run(classroom, sid, did)
        for _ in range(2):
            run(classroom, sid, did, {"transcript": "the dog ran away"})
        words = [a for a in classroom.portfolio.course(sid)["activities"] if a["skill"] == "confirmed-words"]
        assert len(words) == 2
    finally:
        classroom.close()


def test_the_same_words_after_the_course_is_reopened_are_a_new_answer(tmp_path, room, png):
    """Review: matching the text alone would drop a child's real answer given again later.
    Only words left unanswered in this sitting are a retry; a reopened course starts with none."""
    from test_classroom import ALLOW, GOOD, GROUNDED, CLEAN, FOLLOWS, NOTHING_INVENTED, run
    reply = "So the dog ran away from your house. Where was he going?"
    classroom = room([ALLOW, GOOD, GROUNDED, CLEAN, reply, CLEAN, NOTHING_INVENTED, FOLLOWS])
    classroom.portfolio = Portfolio(tmp_path / "history.sqlite3")
    try:
        sid = classroom.begin(CLASS); did = classroom.add_drawing(sid, png)
        run(classroom, sid, did)
        said(classroom, sid, did, "earlier-words", "confirmed-words", {"text": "the dog ran away"})
        run(classroom, sid, did, {"transcript": "the dog ran away"})
        words = [a for a in classroom.portfolio.course(sid)["activities"] if a["skill"] == "confirmed-words"]
        assert len(words) == 2
    finally:
        classroom.close()


def test_a_reply_asked_for_before_a_clear_cannot_bring_the_round_back(chat, monkeypatch):
    """Review: a request is checked before it takes the class lock, so a clear could slip in
    between and the reply would land on the erased conversation. It is refused instead."""
    import studio.classroom.classroom_requests as flow
    classroom, sid, did, _ = chat
    made = flow.Request
    def cleared_meanwhile(*args, **kwargs):
        classroom.forget_chat(sid, did)          # the teacher clears it while this request is on its way
        return made(*args, **kwargs)
    monkeypatch.setattr(flow, "Request", cleared_meanwhile)
    with pytest.raises(ValueError, match="cleared"):
        classroom.request(sid, "art-feedback", [did], {"transcript": "still falling"})
    assert not [r for r in classroom.sessions[sid].request_ids if did in classroom.requests[r].drawing_ids]


def test_undo_takes_the_last_round_in_the_order_the_page_shows_it(tmp_path, png):
    """Review: two records with the same timestamp are shown in id order; undo followed
    insertion order and could take back a different answer from the one on screen."""
    store = Portfolio(tmp_path / "history.sqlite3"); store.begin("one", "colour", "zh", "")
    store.add_drawing("one", "art", png, "image/png")
    store.record("one", "z-words", "confirmed-words", ["art"], {"text": "shown last"})
    store.record("one", "a-words", "confirmed-words", ["art"], {"text": "shown first"})
    with store.connect() as db:
        db.execute("UPDATE activities SET created_at='2026-09-24T00:00:00+00:00' WHERE course_id='one'")
    assert [a["id"] for a in store.course("one")["activities"]] == ["a-words", "z-words"]
    store.forget_chat("one", "art", last_round=True)
    assert [a["id"] for a in store.course("one")["activities"]] == ["a-words"]
