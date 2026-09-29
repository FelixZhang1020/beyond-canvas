"""A storybook read in the studio's own voice is made once and kept with its book (operator).

No class had yet kept a child's voice, so every page was read by the studio's voice, made by StepFun at the
press of Read, about two seconds a sentence before anything was heard, and made again at every press: an ended
class kept nothing at all. Each sentence is now kept with the class's book and goes with it, and a book is read
ahead whenever it is opened, so a press waits only for the sound to travel.
"""
import hashlib
import threading
import types

import pytest

from studio.classroom.portfolio import Portfolio
from studio.providers.stepfun_voice import VoiceServiceError
from studio.voice import book_voice, child_voice
from tests.classroom.test_classroom import png, room  # noqa: F401
from tests.voice.test_child_voice import Reader, recording


class StudioVoice:
    """StepFun's storybook voice, as the studio sees it, counting what it was asked to read."""
    compressed, voice, sample_rate, model, base_url = True, "soft-child", 24000, "studio", "studio"

    def __init__(self, fail=False):
        self.read_for, self.fail = [], fail

    def validate_voice(self, voice_id):
        return voice_id

    def stream(self, text, voice_id, cancelled=lambda: False):
        raise AssertionError("a book's sentence is made whole with clip, never split again by stream")

    def clip(self, text, voice_id):
        self.read_for.append(text)
        if self.fail:
            raise VoiceServiceError("StepFun speech is unavailable; no automatic retry.")
        return b"ID3 studio " + text.encode()


@pytest.fixture
def book(tmp_path):
    """A class with a book of two pages: d1 talked about out loud, d2 only in typing."""
    portfolio = Portfolio(tmp_path / "history.sqlite3")
    portfolio.begin("c1", "colour", "en", "")
    for did in ("d1", "d2"):
        portfolio.add_drawing("c1", did, b"png", "image/png")
    portfolio.record("c1", "w1", "confirmed-words", ["d1"], {"text": "the fish swim home"})
    portfolio.keep_voice("c1", "d1", "w1", recording(2), "the fish swim home")
    portfolio.record("c1", "b1", "drawings-to-storybook", ["d1", "d2"],
                     {"pages": [{"drawing_id": "d1", "text": "Page one."}, {"drawing_id": "d2", "text": "Page two."}]})
    runtime = types.SimpleNamespace(voice=StudioVoice(), clients={child_voice.SLOT: Reader()})
    child_voice._failed.clear()
    return portfolio, runtime


def read(voice, text):
    return b"".join(voice.stream(text, book_voice.BOOK_VOICE))


def test_a_page_without_a_childs_voice_is_made_once_and_kept_with_the_book(book):
    portfolio, runtime = book
    for _ in range(2):
        voice, voice_id = child_voice.choose(portfolio, "c1", "child:d2", runtime)
        assert voice_id == book_voice.BOOK_VOICE
        page = read(voice, "三文鱼一家排着队游回家。最小的两条鱼在前面带路。")
        assert page == "ID3 studio 三文鱼一家排着队游回家。ID3 studio 最小的两条鱼在前面带路。".encode()
    assert sorted(runtime.voice.read_for) == sorted(["三文鱼一家排着队游回家。", "最小的两条鱼在前面带路。"]), \
        "each sentence was made once, the next while the one before played; the second press asked StepFun nothing"


def test_only_a_book_page_is_kept_never_the_chat_or_the_childs_own_words_read_back(book):
    """Code review: the review page and the class history read a child's answers in the storybook voice,
    and clearing the chat would have left them kept. Only the book asks for a page by its drawing (28-book.js)."""
    portfolio, runtime = book
    assert child_voice.choose(portfolio, "c1", "gentle-female", runtime) == (runtime.voice, "gentle-female")
    assert child_voice.choose(portfolio, "c1", book_voice.BOOK_VOICE, runtime) == (runtime.voice, book_voice.BOOK_VOICE)


def test_a_reading_made_at_another_bitrate_is_never_taken_for_this_one(book):
    """A voice now sent smaller must not be answered with the larger reading kept before it."""
    _, runtime = book
    smaller = StudioVoice()
    smaller.bitrate = "48k"
    assert book_voice.key(smaller, "Page two.") != book_voice.key(runtime.voice, "Page two.")


def test_a_long_sentence_is_kept_whole(book):
    portfolio, runtime = book
    voice, _ = child_voice.choose(portfolio, "c1", "child:d2", runtime)
    page = "三文鱼一家排着队游回家。小熊拿着一幅画走进教室，大家都围过来看他画的彩虹和太阳。"
    read(voice, page)
    assert portfolio.reading("c1", book_voice.key(runtime.voice, "小熊拿着一幅画走进教室，大家都围过来看他画的彩虹和太阳。"))


def test_an_ending_written_again_takes_the_readings_of_the_old_one_with_it(book):
    portfolio, runtime = book
    portfolio.ending("c1", "b1", "They all go to sleep.")
    voice, _ = child_voice.choose(portfolio, "c1", "child:d2", runtime)
    read(voice, "They all go to sleep.")
    portfolio.ending("c1", "b1", "They swim home.")
    assert portfolio.reading("c1", book_voice.key(runtime.voice, "They all go to sleep.")) is None


def test_a_reading_is_kept_only_while_the_class_has_a_book_and_goes_with_it(book):
    portfolio, runtime = book
    voice, _ = child_voice.choose(portfolio, "c1", "child:d2", runtime)
    read(voice, "Page two.")
    key = book_voice.key(runtime.voice, "Page two.")
    assert portfolio.reading("c1", key) == b"ID3 studio Page two."
    portfolio.record("c1", "b2", "drawings-to-storybook", ["d2"], {"pages": [{"drawing_id": "d2", "text": "Other."}]})
    assert portfolio.reading("c1", key) is None, "a book made again takes the old one's readings with it"
    with portfolio.connect() as db:
        db.execute("DELETE FROM activities WHERE id='b2'")
    read(voice, "Page two.")
    assert portfolio.reading("c1", key) is None, "with no book there is nothing to keep it with"
    portfolio.record("c1", "b3", "drawings-to-storybook", ["d2"], {"pages": [{"drawing_id": "d2", "text": "Two."}]})
    read(voice, "Two.")
    portfolio.delete_course("c1")
    with portfolio.connect() as db:
        assert db.execute("SELECT count(*) FROM readings").fetchone()[0] == 0


def test_a_book_is_read_ahead_in_the_childs_voice_where_one_is_kept_and_the_studios_elsewhere(book):
    portfolio, runtime = book
    done = threading.Event()
    original = book_voice.reading

    def counted(*args, **kwargs):
        made = original(*args, **kwargs)
        done.set()
        return made
    book_voice.reading = counted
    try:
        child_voice.read_ahead(portfolio, "c1", [("d1", "Page one."), ("d2", "Page two.")], runtime)
        assert done.wait(5)
    finally:
        book_voice.reading = original
    assert runtime.clients[child_voice.SLOT].read_for == ["Page one."]
    assert runtime.voice.read_for == ["Page two."]
    assert portfolio.reading("c1", book_voice.key(runtime.voice, "Page two.")) == b"ID3 studio Page two."
    assert portfolio.narration("c1", "d1", hashlib.sha256(b"Page one.").hexdigest()) == b"ID3 child Page one."


def test_a_page_whose_child_voice_the_spark_cannot_copy_is_read_ahead_by_the_studio(book):
    portfolio, runtime = book
    runtime.clients[child_voice.SLOT] = Reader(fail=True)
    done = threading.Event()
    original = book_voice.reading

    def counted(*args, **kwargs):
        made = original(*args, **kwargs)
        done.set()
        return made
    book_voice.reading = counted
    try:
        child_voice.read_ahead(portfolio, "c1", [("d1", "Page one.")], runtime)
        assert done.wait(5)
    finally:
        book_voice.reading = original
    assert runtime.voice.read_for == ["Page one."]


def test_a_studio_voice_that_fails_keeps_nothing_and_says_so(book):
    portfolio, runtime = book
    runtime.voice.fail = True
    voice, _ = child_voice.choose(portfolio, "c1", "child:d2", runtime)
    with pytest.raises(VoiceServiceError):
        read(voice, "Page two.")
    assert portfolio.reading("c1", book_voice.key(runtime.voice, "Page two.")) is None
    runtime.voice.fail = False
    child_voice.read_ahead(portfolio, "c1", [("d2", "Page two.")], types.SimpleNamespace(voice=None, clients={}))


def test_a_reading_that_breaks_partway_ends_with_the_retry_line_never_a_read_that_spins(tmp_path, room, png):
    """Code review: only StepFun's own failure ended a reading; anything else (a process the node
    could not start, a store that was busy) left the page waiting on keep-alives for ever."""
    import json
    import urllib.request
    from studio.serve import make_server
    from tests.server.test_serve import open_class

    class Breaks:
        compressed, voice, sample_rate, model, base_url = True, "gentle-female", 24000, "breaks", "breaks"

        def validate_voice(self, voice_id):
            return voice_id

        def stream(self, text, voice_id, cancelled=lambda: False):
            yield b"ID3 first sentence"
            raise BlockingIOError("the node could not start a process")
    classroom = room([]); classroom.portfolio = Portfolio(tmp_path / "history.sqlite3"); classroom.voice = Breaks()
    server = make_server(classroom, "127.0.0.1", 0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        sid = open_class(base)
        request = urllib.request.Request(base + f"/api/courses/{sid}/speech", method="POST",
                                         data=json.dumps({"text": "Hello there.", "voice": "gentle-female"}).encode(),
                                         headers={"Content-Type": "application/json"})
        kinds = []
        with urllib.request.urlopen(request, timeout=10) as reply:
            for line in reply:
                kinds.append(json.loads(line)["type"])
                if kinds[-1] in ("error", "done") or kinds.count("heartbeat") >= 3:
                    break
        assert kinds == ["format", "mp3", "error"], kinds
    finally:
        server.shutdown(); server.server_close(); classroom.close()


def test_a_press_and_the_read_ahead_make_a_sentence_once(book):
    portfolio, runtime = book
    started, release = threading.Event(), threading.Event()
    slow = runtime.voice.clip

    def waiting(text, voice_id):
        started.set()
        release.wait(5)
        return slow(text, voice_id)
    runtime.voice.clip = waiting
    ahead = threading.Thread(target=book_voice.reading, args=(portfolio, "c1", runtime.voice, "Page two."))
    ahead.start()
    assert started.wait(5)
    voice, _ = child_voice.choose(portfolio, "c1", "child:d2", runtime)
    pressed = []
    press = threading.Thread(target=lambda: pressed.append(read(voice, "Page two.")))
    press.start()
    release.set()
    ahead.join(5); press.join(5)
    assert pressed == [b"ID3 studio Page two."] and runtime.voice.read_for == ["Page two."]
