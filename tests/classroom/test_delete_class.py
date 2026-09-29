"""A class the teacher deletes from Lesson settings is gone for good (operator).

The course, every drawing, everything made from them and any editor open on it. Whatever is still
being made is stopped, not waited for. Other classes are untouched.
"""
import threading
import urllib.error

import pytest

from studio.classroom.classroom import Classroom
from studio.classroom.portfolio import Portfolio
from studio.serve import make_server
from test_classroom import room, png, CLASS, ALLOW, GOOD, GROUNDED, CLEAN, run, Scripted  # noqa: F401
from tests.server.test_serve import add_drawing, call, open_class


def test_a_deleted_class_leaves_the_portfolio_and_its_editor_closes(tmp_path, room, png):
    classroom = room([ALLOW, GOOD, GROUNDED, CLEAN])
    classroom.portfolio = Portfolio(tmp_path / "history.sqlite3")
    try:
        sid, other = classroom.begin(CLASS), classroom.begin(CLASS)
        did = classroom.add_drawing(sid, png); kept = classroom.add_drawing(other, png)
        run(classroom, sid, did)
        classroom.save_drafts(sid, {did: "goes"})
        folder = classroom.sessions[sid].folder

        classroom.delete_course(sid)

        assert sid not in classroom.sessions and not folder.exists()
        with pytest.raises(KeyError):
            classroom.portfolio.course(sid)
        with pytest.raises(KeyError):
            classroom.portfolio.drawing(sid, did)
        assert [c["id"] for c in classroom.portfolio.courses()["items"]] == [other]
        assert classroom.portfolio.drawing(other, kept)[0] == png
    finally:
        classroom.close()


def test_nothing_of_the_class_is_left_in_the_file(tmp_path, png):
    store = Portfolio(tmp_path / "history.sqlite3"); store.begin("one", "colour", "zh", "")
    store.add_drawing("one", "art", png + b"UNMISTAKABLE-CHILD-DRAWING" * 50, "image/png")
    store.record("one", "feedback", "art-feedback", ["art"], {"text": "UNMISTAKABLE-FEEDBACK " * 20})
    store.save_drafts("one", {"art": "UNMISTAKABLE-DRAFT " * 20})
    store.drawing("one", "art", thumbnail=True)
    store.delete_course("one")
    kept = store.path.read_bytes()
    assert b"UNMISTAKABLE-CHILD-DRAWING" not in kept and b"UNMISTAKABLE-FEEDBACK" not in kept
    assert b"UNMISTAKABLE-DRAFT" not in kept and not store._thumbnails


def test_an_ended_class_can_be_deleted_and_an_unknown_one_is_refused(tmp_path, png):
    store = Portfolio(tmp_path / "history.sqlite3"); store.begin("one", "colour", "zh", "")
    store.add_drawing("one", "art", png, "image/png"); store.end("one")
    store.delete_course("one")
    assert store.courses()["total"] == 0
    with pytest.raises(KeyError):
        store.delete_course("one")


def test_work_still_being_made_is_stopped_and_never_saved(tmp_path, room, png):
    classroom = room([])
    classroom.portfolio = Portfolio(tmp_path / "history.sqlite3")
    try:
        sid = classroom.begin(CLASS); did = classroom.add_drawing(sid, png)
        rid = classroom.request(sid, "art-feedback", [did], {})["request_id"]  # asked for, not yet finished
        request = classroom.requests[rid]
        classroom.delete_course(sid)
        assert request.cancelled.is_set() and rid not in classroom.requests
        assert classroom.portfolio.courses()["total"] == 0
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


def test_the_page_deletes_a_class_and_its_drawings_no_longer_open(studio_with_portfolio):
    base, _ = studio_with_portfolio
    sid = open_class(base)
    did = add_drawing(base, sid)
    assert call(base, "DELETE", f"/api/courses/{sid}") == (204, None)
    for path in (f"/api/courses/{sid}", f"/api/courses/{sid}/drawings/{did}"):
        with pytest.raises(urllib.error.HTTPError) as gone:
            call(base, "GET", path)
        assert gone.value.code == 404
    with pytest.raises(urllib.error.HTTPError) as again:
        call(base, "DELETE", f"/api/courses/{sid}")
    assert again.value.code == 404
