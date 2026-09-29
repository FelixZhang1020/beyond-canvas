"""A storybook's pages redrawn in a picture-book style (studio/making/book_pictures.py, operator).

The teacher sees page 1 in every style, picks one, and the rest of the book is drawn in it; or she makes the book
of the originals, choosing a drawing or its clip on each page. The models here are scripted: one vision client
answers the safety screen, the must-keep list and the comparison by what it is asked, and a fake painter stands
in for FLUX on the Spark and writes the seed and the style into each picture it returns.
"""
import base64
import json
import threading

import pytest

from studio.making import book_pictures
from studio.classroom.classroom import Classroom
from studio.classroom.portfolio import DrawingInUse
from studio.providers.base import ChatResult
from studio.providers.media import MediaResult, MediaSlot
from tests.classroom.test_classroom import ALLOW, CLASS, outputs_of, png  # noqa: F401  (png is a fixture)

STYLES = list(book_pictures.styles())
KEEP = "A red bird on a blue sky."
UNSAFE = '{"verdict": "unsafe", "reason": "not for a child", "text_found": []}'


class Eyes:
    """The class's vision model, answering by what it is asked. `kept` and `safe` rule on a redraw's bytes;
    `outline` is the story it writes, when a test asks for one."""

    def __init__(self, kept=lambda picture: True, safe=lambda picture: True):
        self.kept, self.safe, self.prompts, self.lock, self.outline = kept, safe, [], threading.Lock(), []

    def chat(self, prompt, images=(), *, system=None, max_tokens=None):
        with self.lock:
            self.prompts.append(prompt)
        drawn = [base64.b64decode(i.partition(",")[2]) for i in images if i.startswith("data:image/jpeg")]
        redraw = next((b for b in drawn if b.startswith(b"\xff\xd8\xffpainted")), None)
        if "Compose a coherent children's story" in prompt:
            text = json.dumps(self.outline)
        elif "must stay" in prompt:
            text = KEEP
        elif "repainted in a picture-book style" in prompt:
            text = json.dumps({"kept": True} if self.kept(redraw) else {"kept": False, "missing": ["the bird"]})
        else:   # the safety screen, of an original or of a redraw
            text = UNSAFE if redraw is not None and not self.safe(redraw) else ALLOW
        return ChatResult(text, 1, 1, 0, 0.0, 0.0, "scripted", "scripted")


class Painter:
    """FLUX on the Spark: one job, every picture of it back in order, each marked with its style and seed.
    Given `hold`, its first job waits for it, as a load on the Spark takes its ~23 s."""

    def __init__(self, hold=None):
        self.jobs, self.hold, self.started = [], hold, threading.Event()

    def make(self, inputs):
        self.jobs.append(inputs["pictures"])
        if self.hold is not None and len(self.jobs) == 1:
            self.started.set()
            assert self.hold.wait(5)
        styles = {word: style for style in STYLES for word in (book_pictures._table()["styles"][style],)}
        marked = [b"\xff\xd8\xffpainted " + f"{next((s for w, s in styles.items() if w in p['instruction']), 'blank')} "
                  f"{p['seed']}".encode() for p in inputs["pictures"]]
        return MediaResult([], payload={"pictures": ["data:image/jpeg;base64," + base64.b64encode(m).decode()
                                                     for m in marked]})


def studio(tmp_path, eyes, painter=None):
    clients = {"vlm.studio": eyes, "vlm.director": eyes}
    if painter is not None:
        clients["image.book"] = MediaSlot(painter, "restyle_pictures", {}, {})
    room = Classroom(tmp_path / "ledger.jsonl", clients=clients)
    room.ceiling_gb = float("inf")
    return room


def ask(room, sid, skill, ids, options):
    started = room.request(sid, skill, ids, options)
    room.run_request(started["request_id"])
    return list(room.follow(started["request_id"]))


def marks(result):
    return [base64.b64decode(p["url"].partition(",")[2]).split(b" ", 1)[1].decode() for p in result["pictures"]]


def test_page_one_comes_in_every_style_from_one_job_told_what_the_drawing_must_keep(tmp_path, png):
    painter = Painter()
    room = studio(tmp_path, Eyes(), painter)
    try:
        sid = room.begin(CLASS)
        ids = [room.add_drawing(sid, png) for _ in range(2)]
        result = outputs_of(ask(room, sid, "book-pictures", ids[:1], {"styles": STYLES}))
        assert [(p["drawing_id"], p["style"]) for p in result["pictures"]] == [(ids[0], s) for s in STYLES]
        assert marks(result) == [f"{s} 42" for s in STYLES] and not any(p["changed"] for p in result["pictures"])
        assert len(painter.jobs) == 1 and len(painter.jobs[0]) == len(STYLES) == 7, "one job, so the Spark loads FLUX once"
        assert all(KEEP in job["instruction"] for job in painter.jobs[0]), "each told what the drawing must keep"
        ask(room, sid, "book-pictures", ids[:1], {"styles": ["clay"]})
        assert len(painter.jobs) == 1, "a page already drawn in a style is not drawn again"
    finally:
        room.close()


def test_a_page_of_the_book_that_lost_something_is_drawn_once_more_and_marked_only_if_it_still_has(tmp_path, png):
    for kept, marked in ((lambda picture: b"42" not in picture, []), (lambda picture: False, ["clay", "clay"])):
        painter = Painter()
        room = studio(tmp_path, Eyes(kept=kept), painter)
        try:
            sid = room.begin(CLASS)
            ids = [room.add_drawing(sid, png) for _ in range(2)]
            result = outputs_of(ask(room, sid, "book-pictures", ids, {"styles": ["clay"]}))
            assert [len(job) for job in painter.jobs] == [2, 2] and {p["seed"] for p in painter.jobs[1]} == {43}
            assert marks(result) == ["clay 43", "clay 43"] and all(p["again"] for p in result["pictures"])
            assert [p["style"] for p in result["pictures"] if p["changed"]] == marked, "the teacher sees which"
        finally:
            room.close()


def test_page_one_in_every_style_is_drawn_once_and_what_changed_is_only_marked(tmp_path, png):
    # Operator: faster books. Six of seven samples were flagged and drawn again for a choice that keeps one, and
    # the second draw fixed none of them; the sample she picks gets its try with the rest of the book instead.
    painter = Painter()
    room = studio(tmp_path, Eyes(kept=lambda picture: b"clay" not in picture and b"gouache" not in picture), painter)
    try:
        sid = room.begin(CLASS)
        ids = [room.add_drawing(sid, png) for _ in range(2)]
        result = outputs_of(ask(room, sid, "book-pictures", ids[:1], {"styles": STYLES}))
        assert [len(job) for job in painter.jobs] == [len(STYLES)], "one job, no second draw of a sample"
        assert marks(result) == [f"{s} 42" for s in STYLES] and not any(p["again"] for p in result["pictures"])
        assert [p["style"] for p in result["pictures"] if p["changed"]] == ["gouache", "clay"]
    finally:
        room.close()


def test_the_chosen_sample_that_changed_gets_one_more_try_beside_the_rest_of_the_book_and_never_a_third(tmp_path, png):
    # Every drawing here is the same picture, so each "clay 42" is flagged the same way: page 2's first draw too.
    for kept, fixed in ((lambda picture: picture != b"\xff\xd8\xffpainted clay 42", True),
                        (lambda picture: False, False)):
        painter = Painter()
        room = studio(tmp_path, Eyes(kept=kept), painter)
        try:
            sid = room.begin(CLASS)
            ids = [room.add_drawing(sid, png) for _ in range(2)]
            sample = outputs_of(ask(room, sid, "book-pictures", ids[:1], {"styles": ["clay", "paper"]}))
            assert [p["changed"] for p in sample["pictures"]] == [True, not fixed]
            book = outputs_of(ask(room, sid, "book-pictures", ids, {"styles": ["clay"]}))
            assert sorted(p["seed"] for p in painter.jobs[1]) == [42, 43], "page 1 again, in the same job as page 2"
            assert [len(job) for job in painter.jobs] == [2, 2, 1], "then page 2's second try, and no third for page 1"
            assert [p["changed"] for p in book["pictures"]] == [not fixed, not fixed]
            assert marks(book) == ["clay 43", "clay 43"] and all(p["again"] for p in book["pictures"])
            again = outputs_of(ask(room, sid, "book-pictures", ids, {"styles": ["clay"]}))
            assert again["pictures"] == book["pictures"] and len(painter.jobs) == 3, "asked again, nothing is redrawn"
        finally:
            room.close()


def test_a_chosen_sample_whose_second_try_is_not_safe_to_show_keeps_the_first_and_is_not_tried_again(tmp_path, png):
    painter = Painter()
    room = studio(tmp_path, Eyes(kept=lambda picture: b"42" not in picture,
                                 safe=lambda picture: picture != b"\xff\xd8\xffpainted clay 43"), painter)
    try:
        sid = room.begin(CLASS)
        ids = [room.add_drawing(sid, png) for _ in range(2)]
        sample = outputs_of(ask(room, sid, "book-pictures", ids[:1], {"styles": ["clay", "paper"]}))
        book = outputs_of(ask(room, sid, "book-pictures", ids[:1], {"styles": ["clay"]}))
        assert [p["url"] for p in book["pictures"]] == [sample["pictures"][0]["url"]], "the flagged sample, not nothing"
        assert book["pictures"][0]["again"] and len(painter.jobs) == 2
        ask(room, sid, "book-pictures", ids[:1], {"styles": ["clay"]})
        assert len(painter.jobs) == 2, "not a third time (code review)"
    finally:
        room.close()


def story(room, eyes, sid, ids):
    """The teacher's story, written; then what the studio got ready for its pictures while she read it."""
    eyes.outline = [{"drawing_id": did, "text": f"Page {n}."} for n, did in enumerate(ids, 1)]
    outputs_of(ask(room, sid, "story-outline", ids, {"scenes": {did: "A red bird." for did in ids}}))
    ready = room.sessions[sid].book_ready
    if ready is not None:
        ready.join(5)
    return ready


def test_while_the_teacher_reads_the_story_flux_is_loaded_and_every_drawing_listed(tmp_path, png):
    # Operator: faster books. The first press waited ~23 s for FLUX to load and ~3 s a page for its list.
    painter, eyes = Painter(), Eyes()
    room = studio(tmp_path, eyes, painter)
    try:
        sid = room.begin(CLASS)
        ids = [room.add_drawing(sid, png) for _ in range(3)]
        assert story(room, eyes, sid, ids) is not None
        assert [len(job) for job in painter.jobs] == [1], "one picture, so FLUX loads"
        warm = base64.b64decode(painter.jobs[0][0]["image"].partition(",")[2])
        assert len(warm) < 2048 and warm.startswith(b"\xff\xd8\xff"), "a blank page, never a child's drawing"
        assert set(room.sessions[sid].keep_lists) == set(ids)
        listed = sum("must stay" in prompt for prompt in eyes.prompts)
        ask(room, sid, "book-pictures", ids[:1], {"styles": STYLES})
        assert sum("must stay" in prompt for prompt in eyes.prompts) == listed, "page 1 writes no list of its own"
        assert [len(job) for job in painter.jobs] == [1, len(STYLES)]
    finally:
        room.close()
    (tmp_path / "bare").mkdir()
    plain = Eyes()
    bare = studio(tmp_path / "bare", plain)
    try:
        sid = bare.begin(CLASS)
        assert story(bare, plain, sid, [bare.add_drawing(sid, png) for _ in range(2)]) is None
        assert not bare.sessions[sid].keep_lists, "no FLUX, no picture book: nothing to get ready"
    finally:
        bare.close()


def test_page_one_asked_for_while_flux_is_loading_waits_for_it_instead_of_saying_busy(tmp_path, png):
    hold = threading.Event()
    painter, eyes = Painter(hold=hold), Eyes()
    room = studio(tmp_path, eyes, painter)
    try:
        sid = room.begin(CLASS)
        ids = [room.add_drawing(sid, png) for _ in range(2)]
        eyes.outline = [{"drawing_id": did, "text": f"Page {n}."} for n, did in enumerate(ids, 1)]
        outputs_of(ask(room, sid, "story-outline", ids, {"scenes": {did: "A red bird." for did in ids}}))
        assert painter.started.wait(5)
        with pytest.raises(DrawingInUse) as refused:   # not sent to a model after it is gone (code review)
            room.remove_drawing(sid, ids[1])
        assert refused.value.code == "drawing_busy"
        started = room.request(sid, "book-pictures", ids[:1], {"styles": ["clay"]})
        worker = threading.Thread(target=room.run_request, args=(started["request_id"],))
        worker.start()
        hold.set()
        worker.join(5)
        assert marks(outputs_of(list(room.follow(started["request_id"])))) == ["clay 42"]
        with pytest.raises(DrawingInUse) as refused:
            room.remove_drawing(sid, ids[1])
        assert refused.value.code == "in_book", "ready now: refused only as any book's drawing is, without a Portfolio"
    finally:
        hold.set()
        room.close()


def test_a_redraw_that_fails_its_safety_screen_twice_is_never_shown(tmp_path, png):
    room = studio(tmp_path, Eyes(safe=lambda picture: b"clay" not in picture), Painter())
    try:
        sid = room.begin(CLASS)
        ids = [room.add_drawing(sid, png) for _ in range(2)]
        page_one = outputs_of(ask(room, sid, "book-pictures", ids[:1], {"styles": STYLES}))
        assert [p["style"] for p in page_one["pictures"]] == [s for s in STYLES if s != "clay"], "every other style"
        events = ask(room, sid, "book-pictures", ids[1:], {"styles": ["clay"]})
        stopped = next(data for name, data in events if name == "done")
        assert stopped["status"] == "stopped" and stopped["reason_code"] == "book_picture_held_back"
        assert not any("pictures" in (data.get("outputs") or {}) for _, data in events)
        assert all(style != "clay" for _, style in room.sessions[sid].book_pictures), "no clay page to bind"
    finally:
        room.close()


def test_a_redrawn_page_that_fails_its_safety_screen_keeps_its_first_picture(tmp_path, png):
    """Review: the first picture was safe and only flagged as changed, the second not safe to show. The book keeps
    the first, marked as changed and as tried twice; until then the whole style was refused for that one page."""
    room = studio(tmp_path, Eyes(kept=lambda picture: False, safe=lambda picture: b" 43" not in picture), Painter())
    try:
        sid = room.begin(CLASS)
        ids = [room.add_drawing(sid, png) for _ in range(2)]
        result = outputs_of(ask(room, sid, "book-pictures", ids, {"styles": ["clay"]}))
        assert marks(result) == ["clay 42", "clay 42"]
        assert all(p["changed"] and p["again"] for p in result["pictures"]), "marked, and never tried a third time"
    finally:
        room.close()


def test_page_one_comes_as_a_file_for_each_style_once_the_course_has_kept_it(tmp_path, png, monkeypatch):
    """Review: page 1's seven pictures still travelled inside its "done", the 2.2 MB the slow link waited minutes
    for (the clip's fix had not reached them). They go as files of their own now, saved before they are sent."""
    from studio.classroom.portfolio import Portfolio
    from studio.server import media_links
    monkeypatch.setattr(media_links, "SMALL", 0)   # the fake painter's pictures are a few bytes
    room = studio(tmp_path, Eyes(), Painter())
    room.portfolio = Portfolio(tmp_path / "history.sqlite3")
    try:
        sid = room.begin(CLASS)
        did = room.add_drawing(sid, png)
        started = room.request(sid, "book-pictures", [did], {"styles": STYLES})
        room.run_request(started["request_id"])
        result = outputs_of(list(room.follow(started["request_id"])))
        course, rid = room.sessions[sid].course_id, started["request_id"]
        saved = room.portfolio.activity(course, rid)["outputs"]
        assert [p["style"] for p in result["pictures"]] == STYLES
        for picture in result["pictures"]:
            assert picture["url"].startswith(f"/api/courses/{course}/activities/{rid}/media/pictures.")
            data, kind = media_links.media(saved, picture["url"].split("/media/")[1].split("?")[0])
            assert kind == "image/jpeg" and data.startswith(b"\xff\xd8\xffpainted " + picture["style"].encode())
        assert room.sessions[sid].book_pictures[(did, STYLES[0])]["url"].startswith("data:"), "kept whole"
    finally:
        room.close()


def test_the_book_binds_in_the_chosen_style_or_of_the_originals_with_the_clips_she_picked(tmp_path, png):
    room = studio(tmp_path, Eyes(), Painter())
    try:
        sid = room.begin(CLASS)
        ids = [room.add_drawing(sid, png) for _ in range(2)]
        drawn = outputs_of(ask(room, sid, "book-pictures", ids, {"styles": ["clay"]}))["pictures"]
        pages = [{"drawing_id": did, "text": f"Page {n}."} for n, did in enumerate(ids, 1)]
        clay = outputs_of(ask(room, sid, "drawings-to-storybook", ids, {"pages": pages, "look": "clay"}))
        assert clay["look"] == "clay" and [p["picture_url"] for p in clay["pages"]] == [p["url"] for p in drawn]
        assert [p["text"] for p in clay["pages"]] == ["Page 1.", "Page 2."], "the confirmed words, unchanged"
        original = outputs_of(ask(room, sid, "drawings-to-storybook", ids, {"pages": pages, "look": "original",
                                                                             "motion": []}))
        assert not any("picture_url" in p or "video_url" in p for p in original["pages"])
        events = ask(room, sid, "drawings-to-storybook", ids, {"pages": pages, "look": "watercolour"})
        assert next(data for name, data in events if name == "done")["reason_code"] == "pictures_missing"
    finally:
        room.close()


def test_a_picture_book_is_refused_where_it_cannot_be_made(tmp_path, png):
    room = studio(tmp_path, Eyes(), Painter())
    (tmp_path / "bare").mkdir()
    bare = studio(tmp_path / "bare", Eyes())
    try:
        sid = room.begin(CLASS)
        ids = [room.add_drawing(sid, png) for _ in range(3)]
        for options in ({"styles": ["oil"]}, {"styles": []}, {"styles": ["clay", "clay"]}, {}, {"styles": [[1]]},
                        {"styles": [{}]}, {"styles": "clay"}):
            with pytest.raises(ValueError):
                room.request(sid, "book-pictures", ids[:1], options)
        with pytest.raises(ValueError):   # three pages in four styles is twelve pictures, past one job's eight
            room.request(sid, "book-pictures", ids, {"styles": STYLES})
        with pytest.raises(ValueError):
            room.request(sid, "drawings-to-storybook", ids[:2], {"look": "oil"})
        sketch = room.begin({**CLASS, "entrance": "sketch"})
        drawing = room.add_drawing(sketch, png)
        with pytest.raises(ValueError):
            room.request(sketch, "book-pictures", [drawing], {"styles": ["clay"]})
        assert "book-pictures" in room.health()["skills"] and "book-pictures" not in bare.health()["skills"]
        plain = bare.begin(CLASS)
        with pytest.raises(ValueError):
            bare.request(plain, "book-pictures", [bare.add_drawing(plain, png)], {"styles": ["clay"]})
    finally:
        room.close()
        bare.close()


def test_another_classs_pages_being_drawn_is_said_at_once(tmp_path, png):
    painter = Painter()
    room = studio(tmp_path, Eyes(), painter)
    try:
        sid = room.begin(CLASS)
        ids = [room.add_drawing(sid, png) for _ in range(2)]
        with book_pictures._DRAWING:
            events = ask(room, sid, "book-pictures", ids[:1], {"styles": ["clay"]})
        assert next(data for name, data in events if name == "done")["reason_code"] == "busy"
        assert painter.jobs == []
    finally:
        room.close()


def test_the_record_keeps_counts_and_never_what_the_drawing_shows(tmp_path, png):
    room = studio(tmp_path, Eyes(kept=lambda picture: b"42" not in picture), Painter())
    try:
        sid = room.begin(CLASS)
        ids = [room.add_drawing(sid, png) for _ in range(2)]
        ask(room, sid, "book-pictures", ids[:1], {"styles": ["clay"]})
        ask(room, sid, "book-pictures", ids[1:], {"styles": ["clay"]})
        ledger = (tmp_path / "ledger.jsonl").read_text()
        lines = [json.loads(line) for line in ledger.splitlines()]
        stages = [line["stage"] for line in lines]
        assert {"picture-keep", "picture-book", "picture-check", "picture-book-again", "picture-check-again"} <= set(stages)
        assert "red bird" not in ledger and "the bird" not in ledger
        kept = [line for line in lines if line["stage"] == "picture-keep"]
        assert all(line["tokens"] > 0 for line in kept), "the lists written on other threads are counted"
        assert all(line["tokens"] > 0 for line in lines if line["stage"] == "picture-check"), "and the checks"
        assert kept[0]["inputs_hash"] != kept[1]["inputs_hash"], "each job's line has its own fingerprint"
    finally:
        room.close()


def test_a_deleted_drawing_takes_its_list_and_its_redraws_with_it(tmp_path, png):
    room = studio(tmp_path, Eyes(), Painter())
    try:
        sid = room.begin(CLASS)
        ids = [room.add_drawing(sid, png) for _ in range(2)]
        ask(room, sid, "book-pictures", ids[:1], {"styles": ["clay", "paper"]})
        session = room.sessions[sid]
        assert session.keep_lists[ids[0]] and (ids[0], "clay") in session.book_pictures
        room.remove_drawing(sid, ids[0])
        assert ids[0] not in session.keep_lists
        assert not [pair for pair in session.book_pictures if pair[0] == ids[0]]
    finally:
        room.close()


def test_asking_again_for_pictures_already_drawn_draws_and_saves_nothing_new(tmp_path, png):
    painter = Painter()
    room = studio(tmp_path, Eyes(), painter)
    saved = []
    try:
        sid = room.begin(CLASS)
        ids = [room.add_drawing(sid, png) for _ in range(2)]
        room._record_request = lambda request, activity, skill, output: saved.append((skill, len(output.get("pictures", []))))
        first = outputs_of(ask(room, sid, "book-pictures", ids[:1], {"styles": ["clay"]}))
        again = outputs_of(ask(room, sid, "book-pictures", ids[:1], {"styles": ["clay", "paper"]}))
        assert [p["style"] for p in again["pictures"]] == ["clay", "paper"] and again["pictures"][0] == first["pictures"][0]
        assert [n for skill, n in saved if skill == "book-pictures"] == [1, 1], "each picture saved once"
        assert [len(job) for job in painter.jobs] == [1, 1]
    finally:
        room.close()


def test_a_comparison_cut_off_at_its_word_limit_still_says_whether_it_kept_the_picture():
    assert book_pictures.kept('{\n  "kept": false,\n  "why": ["lost princess", "changed mouse col') is False
    assert book_pictures.kept('```json\n{"kept": true}\n```') is True
    assert book_pictures.kept("The picture looks lovely.") is None, "no answer is not a finding"


def test_the_page_offers_exactly_the_styles_the_skill_draws_in_its_order():
    import re
    from pathlib import Path
    page = (Path(__file__).parents[2] / "studio/page/src/29l-book-look.js").read_text(encoding="utf-8")
    offered = re.findall(r"'([a-z]+)'", re.search(r"const STYLES = \[([^\]]+)\]", page).group(1))
    assert offered == STYLES and len(STYLES) == 7, "operator: all seven styles tried"
