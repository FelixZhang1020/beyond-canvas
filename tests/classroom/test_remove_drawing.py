"""A drawing the teacher removes is gone for good: from the class, the Portfolio and the file.

Asked for to take away a wrong photograph or a duplicate. Two refusals are part of it: nothing
is deleted while it is still being made from, and a drawing a book shares stays, because deleting
the book would take other children's drawings with it.
"""
import json
import threading
import urllib.error

import pytest

from studio.classroom.classroom import Classroom
from studio.classroom.portfolio import DrawingInUse, Portfolio
from studio.serve import make_server
from test_classroom import room, png, CLASS, ALLOW, GOOD, GROUNDED, CLEAN, run, Scripted  # noqa: F401
from tests.server.test_serve import add_drawing, call, open_class


def test_a_removed_drawing_leaves_the_class_the_portfolio_and_what_was_made_from_it(tmp_path, room, png):
    classroom = room([ALLOW, GOOD, GROUNDED, CLEAN])
    classroom.portfolio = Portfolio(tmp_path / "history.sqlite3")
    try:
        sid = classroom.begin(CLASS)
        kept, removed = classroom.add_drawing(sid, png), classroom.add_drawing(sid, png)
        run(classroom, sid, removed)
        classroom.save_drafts(sid, {kept: "stays", removed: "goes"})
        path = classroom.sessions[sid].drawings[removed]

        classroom.remove_drawing(sid, removed)

        session = classroom.sessions[sid]
        assert removed not in session.drawings and not path.exists()
        assert removed not in session.conversations and not session.request_ids
        course = classroom.portfolio.course(sid)
        assert [d["id"] for d in course["drawings"]] == [kept]
        assert course["activities"] == [] and course["drafts"] == {kept: "stays"}
        with pytest.raises(KeyError):
            classroom.portfolio.drawing(sid, removed)
        with pytest.raises(KeyError):
            classroom.drawing(sid, removed)
    finally:
        classroom.close()


def test_the_deleted_photograph_is_not_left_readable_inside_the_file(tmp_path, png):
    store = Portfolio(tmp_path / "history.sqlite3"); store.begin("one", "colour", "zh", "")
    marker = png + b"UNMISTAKABLE-CHILD-DRAWING" * 50
    store.add_drawing("one", "art", marker, "image/png")
    store.remove_drawing("one", "art")
    assert b"UNMISTAKABLE-CHILD-DRAWING" not in store.path.read_bytes()


def test_a_drawing_a_book_shares_is_refused_and_nothing_is_deleted(tmp_path, png):
    store = Portfolio(tmp_path / "history.sqlite3"); store.begin("one", "colour", "zh", "")
    for did in ("a", "b"):
        store.add_drawing("one", did, png, "image/png")
    store.record("one", "feedback", "art-feedback", ["a"], {"text": "Warm.", "question": "Why?"})
    store.record("one", "book", "drawings-to-storybook", ["a", "b"], {"pages": []})
    with pytest.raises(DrawingInUse) as refused:
        store.remove_drawing("one", "a")
    assert refused.value.code == "in_book"
    course = store.course("one")
    assert len(course["drawings"]) == 2 and len(course["activities"]) == 2


def test_a_drawing_still_being_made_from_is_refused(tmp_path, room, png):
    classroom = room([])
    classroom.portfolio = Portfolio(tmp_path / "history.sqlite3")
    try:
        sid = classroom.begin(CLASS); did = classroom.add_drawing(sid, png)
        classroom.request(sid, "art-feedback", [did], {})  # asked for, not yet finished
        with pytest.raises(DrawingInUse) as refused:
            classroom.remove_drawing(sid, did)
        assert refused.value.code == "drawing_busy"
        assert did in classroom.sessions[sid].drawings
        assert classroom.portfolio.drawing(sid, did)[0] == png
    finally:
        classroom.close()


def test_an_ended_course_keeps_its_drawings(tmp_path, room, png):
    classroom = room([])
    classroom.portfolio = Portfolio(tmp_path / "history.sqlite3")
    sid = classroom.begin(CLASS); did = classroom.add_drawing(sid, png)
    classroom.portfolio.end(sid)
    try:
        with pytest.raises(ValueError, match="ended"):
            classroom.remove_drawing(sid, did)
        assert classroom.portfolio.drawing(sid, did)[0] == png
    finally:
        classroom.close()


@pytest.fixture
def studio_with_portfolio(tmp_path):
    client = Scripted([])
    classroom = Classroom(tmp_path / "ledger.jsonl", clients={"vlm.studio": client, "vlm.director": client},
                          portfolio=Portfolio(tmp_path / "history.sqlite3"))
    page = tmp_path / "index.html"
    page.write_text("<title>Beyond Canvas</title>", encoding="utf-8")
    server = make_server(classroom, "127.0.0.1", 0, page)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}", classroom
    server.shutdown()
    classroom.close()


def test_the_page_deletes_a_drawing_and_hears_why_when_it_cannot(studio_with_portfolio):
    base, classroom = studio_with_portfolio
    sid = open_class(base)
    one, two = add_drawing(base, sid), add_drawing(base, sid)
    assert call(base, "DELETE", f"/api/session/{sid}/drawings/{one}") == (204, None)
    with pytest.raises(urllib.error.HTTPError) as gone:
        call(base, "GET", f"/api/courses/{sid}/drawings/{one}")
    assert gone.value.code == 404

    classroom.portfolio.record(sid, "book", "drawings-to-storybook", [two, "other"], {"pages": []})
    with pytest.raises(urllib.error.HTTPError) as refused:
        call(base, "DELETE", f"/api/session/{sid}/drawings/{two}")
    assert refused.value.code == 400
    assert json.loads(refused.value.read())["code"] == "in_book"


class Held(Scripted):
    """The safety look begun on upload, held in flight until the test lets it answer."""

    def __init__(self, replies):
        super().__init__(replies)
        self.gate = threading.Event()

    def chat(self, prompt, images=(), *, system=None, max_tokens=None):
        self.gate.wait(10)
        return super().chat(prompt, images, system=system, max_tokens=max_tokens)


def test_a_drawing_still_being_looked_at_on_upload_is_not_deleted_and_its_look_is_forgotten_after(tmp_path, png):
    """Code review: the look begun as the photo arrives runs outside any request, so deletion
    neither waited for it (the photo kept going to the model after it was gone) nor forgot its record."""
    looker = Held([ALLOW])
    classroom = Classroom(tmp_path / "ledger.jsonl", clients={"vlm.studio": looker, "vlm.director": looker})
    classroom.look_on_arrival = True
    try:
        sid = classroom.begin(CLASS)
        did = classroom.add_drawing(sid, png)
        with pytest.raises(DrawingInUse):
            classroom.remove_drawing(sid, did)
        looker.gate.set()
        arrival = classroom.sessions[sid].conversations[did]
        arrival.arrival.join(10)
        looked = arrival.arrival_id
        assert looked in (tmp_path / "ledger.jsonl").read_text(), "the look should have left its line"
        classroom.remove_drawing(sid, did)
        assert looked not in classroom.sessions[sid].request_ids
        assert looked not in (tmp_path / "ledger.jsonl").read_text(), "the look's line outlived the drawing"
    finally:
        classroom.close()
