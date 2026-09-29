"""A storybook read in the child's own voice (operator): what is kept, what goes with it, who reads.

Every page is read in one voice: the voice of the first answer said out loud about its drawing in the chat,
copied on the Spark, or the studio's own where the answers were typed or there were none. Only that first
recording is kept, cut to ten seconds from the first word, and it goes whenever its answer goes.
"""
import hashlib
import io
import random
import threading
import types
import wave

import pytest

from studio.voice import child_voice
from studio.classroom.portfolio import Portfolio
from studio.providers.stepfun_voice import VoiceServiceError
from studio.voice.transcribe import Heard
from tests.classroom.test_classroom import CLASS, GOOD, png, routed, run  # noqa: F401


def recording(seconds, speaking_from=0.0, rate=16000, seed=7):
    """A WAV as the class hears it: quiet, then speech, here noise no other recording shares."""
    noise = random.Random(seed)
    quiet, loud = int(speaking_from * rate), int((seconds - speaking_from) * rate)
    samples = [0] * quiet + [noise.randint(-9000, 9000) for _ in range(loud)]
    out = io.BytesIO()
    with wave.open(out, "wb") as clip:
        clip.setnchannels(1)
        clip.setsampwidth(2)
        clip.setframerate(rate)
        clip.writeframes(b"".join(v.to_bytes(2, "little", signed=True) for v in samples))
    return out.getvalue()


def seconds_of(wav):
    with wave.open(io.BytesIO(wav)) as clip:
        return clip.getnframes() / clip.getframerate()


class Ears:
    def hear(self, wav, language):
        return Heard("the fish swim home", language)


class Reader:
    """VoxCPM2 on the Spark, as the studio sees it."""

    def __init__(self, fail=False):
        self.read_for, self.said, self.fail = [], [], fail

    def read(self, reference, text, cancelled=lambda: False, said=""):
        self.read_for.append(text)
        self.said.append(said)
        if self.fail:
            raise VoiceServiceError("the Spark could not copy it")
        return b"ID3 child " + text.encode()


class StudioVoice:
    compressed, voice, sample_rate, model, base_url = True, "soft-child", 24000, "studio", "studio"

    def validate_voice(self, voice_id):
        return voice_id

    def stream(self, text, voice_id, cancelled=lambda: False):
        yield b"ID3 studio " + text.encode()


@pytest.fixture
def voiced(tmp_path, routed, png):
    classroom = routed([GOOD, "So the fish swim home. Who leads them?", "So the smallest lead. Where is home?",
                        "So home is up the river. What do they see?"])
    classroom.portfolio = Portfolio(tmp_path / "history.sqlite3")
    classroom.ears = Ears()
    sid = classroom.begin(CLASS)
    did, other = classroom.add_drawing(sid, png), classroom.add_drawing(sid, png)
    run(classroom, sid, did)
    yield classroom, sid, did, other
    classroom.close()


def answer(classroom, sid, did, said, wav=None):
    """The child answers, out loud when there is a recording, and the teacher sends it."""
    options = {"transcript": said}
    if wav is not None:
        options["sample"] = classroom.hear(sid, wav).sample
    return run(classroom, sid, did, options)


def course(classroom, sid):
    return classroom.sessions[sid].course_id


def test_only_the_first_answer_said_out_loud_about_a_drawing_is_kept(voiced):
    classroom, sid, did, _ = voiced
    first = recording(3, speaking_from=1.0)
    answer(classroom, sid, did, "the fish swim home", first)
    answer(classroom, sid, did, "the smallest lead", recording(2, seed=8))
    kept, said, _ = classroom.portfolio.voice(course(classroom, sid), did)
    assert kept == child_voice.reference(first)[0], "the second child's voice does not replace the first"
    assert said == "the fish swim home", "with the words heard in it, which VoxCPM2 needs to follow the voice"
    assert not classroom.sessions[sid].heard, "both recordings left the class's memory once sent"


def test_a_typed_answer_keeps_no_voice_and_a_later_spoken_one_is_the_first(voiced):
    classroom, sid, did, _ = voiced
    answer(classroom, sid, did, "the fish swim home")
    assert classroom.portfolio.voice(course(classroom, sid), did) is None
    spoken = recording(2)
    answer(classroom, sid, did, "the smallest lead", spoken)
    assert classroom.portfolio.voice(course(classroom, sid), did)[0] == child_voice.reference(spoken)[0]


def test_a_recording_heard_and_never_sent_is_not_kept(voiced):
    classroom, sid, did, _ = voiced
    heard = classroom.hear(sid, recording(2))
    assert heard.sample and heard.text == "the fish swim home"
    answer(classroom, sid, did, "typed instead")
    assert classroom.portfolio.voice(course(classroom, sid), did) is None
    for _ in range(child_voice.HELD + 2):
        classroom.hear(sid, recording(1))
    assert len(classroom.sessions[sid].heard) == child_voice.HELD, "a class holds only its last few, unsent"


def test_a_long_answer_is_kept_from_the_first_word_for_ten_seconds_without_its_words(voiced):
    kept, whole = child_voice.reference(recording(25, speaking_from=3.0))
    assert seconds_of(kept) == child_voice.REFERENCE_S and not whole
    with wave.open(io.BytesIO(kept)) as clip:
        opening = clip.readframes(int(clip.getframerate() * 0.2))
    assert any(opening[2 * n:2 * n + 2] != b"\0\0" for n in range(len(opening) // 2)), "the silence before is gone"
    assert child_voice.reference(recording(4))[1] and seconds_of(child_voice.reference(recording(4))[0]) == 4
    assert child_voice.reference(b"not a wav") == (b"not a wav", True)
    classroom, sid, did, _ = voiced
    answer(classroom, sid, did, "the fish swim home and then they swim on", recording(12, speaking_from=1.0))
    assert classroom.portfolio.voice(course(classroom, sid), did)[1] == "", "cut off, its words no longer match it"


def test_taking_the_answer_back_erases_the_voice_and_every_page_read_in_it(voiced):
    classroom, sid, did, _ = voiced
    spoken = recording(2, seed=31)
    answer(classroom, sid, did, "the fish swim home", spoken)
    cid = course(classroom, sid)
    classroom.portfolio.keep_narration(cid, did, "page-1", b"ID3 UNMISTAKABLE-PAGE-READ")
    classroom.forget_chat(sid, did, last_round=True)
    assert classroom.portfolio.voice(cid, did) is None
    assert classroom.portfolio.narration(cid, did, "page-1") is None
    file = classroom.portfolio.path.read_bytes()
    assert child_voice.reference(spoken)[0][1000:1400] not in file and b"UNMISTAKABLE-PAGE-READ" not in file


def test_deleting_the_drawing_or_the_class_erases_the_voice(voiced):
    classroom, sid, did, other = voiced
    answer(classroom, sid, did, "the fish swim home", recording(2))
    cid = course(classroom, sid)
    classroom.remove_drawing(sid, did)
    assert classroom.portfolio.voice(cid, did) is None
    classroom.portfolio.record(cid, "o-words", "confirmed-words", [other], {"text": "a red house"})
    classroom.portfolio.keep_voice(cid, other, "o-words", recording(2, seed=9))
    classroom.portfolio.keep_narration(cid, other, "page-1", b"ID3 page")
    classroom.portfolio.delete_course(cid)
    with classroom.portfolio.connect() as db:
        assert db.execute("SELECT count(*) FROM voices").fetchone()[0] == 0
        assert db.execute("SELECT count(*) FROM narrations").fetchone()[0] == 0


@pytest.fixture
def kept(tmp_path):
    """A Portfolio holding one drawing's first spoken answer, and a runtime with the Spark's reader."""
    portfolio = Portfolio(tmp_path / "history.sqlite3")
    portfolio.begin("c1", "colour", "en", "")
    portfolio.add_drawing("c1", "d1", b"png", "image/png")
    portfolio.add_drawing("c1", "d2", b"png", "image/png")
    portfolio.record("c1", "r1-words", "confirmed-words", ["d1"], {"text": "the fish swim home"})
    portfolio.keep_voice("c1", "d1", "r1-words", recording(2), "the fish swim home")
    reader = Reader()
    runtime = types.SimpleNamespace(voice=StudioVoice(), clients={child_voice.SLOT: reader})
    child_voice._failed.clear()
    return portfolio, reader, runtime


def test_a_page_is_read_in_its_drawings_voice_and_a_page_without_one_by_the_studio(kept):
    portfolio, reader, runtime = kept
    voice, voice_id = child_voice.choose(portfolio, "c1", "child:d1", runtime)
    assert voice_id == "child" and b"".join(voice.stream("The fish swim home.")) == b"ID3 child The fish swim home."
    voice, voice_id = child_voice.choose(portfolio, "c1", "child:d2", runtime)
    assert (voice.studio, voice_id) == (runtime.voice, child_voice.BOOK_VOICE), "typed, or never talked about"
    assert child_voice.choose(portfolio, "c1", "gentle-female", runtime) == (runtime.voice, "gentle-female")
    alone = types.SimpleNamespace(voice=runtime.voice, clients={})
    voice, voice_id = child_voice.choose(portfolio, "c1", "child:d1", alone)
    assert (voice.studio, voice_id) == (runtime.voice, child_voice.BOOK_VOICE)


def test_a_recording_said_again_is_never_answered_with_the_reading_of_the_one_taken_back(kept, tmp_path):
    """studio/voice/speech.py keeps what it read by the voice's address, so that address names the recording."""
    portfolio, _, runtime = kept
    first, _ = child_voice.choose(portfolio, "c1", "child:d1", runtime)
    with portfolio.connect() as db:
        db.execute("DELETE FROM activities WHERE id='r1-words'")
    portfolio.record("c1", "r2-words", "confirmed-words", ["d1"], {"text": "the smallest lead"})
    portfolio.keep_voice("c1", "d1", "r2-words", recording(2, seed=12), "the smallest lead")
    again, _ = child_voice.choose(portfolio, "c1", "child:d1", runtime)
    assert first.base_url != again.base_url


def test_a_page_is_read_once_and_kept_so_the_next_reading_is_at_once(kept):
    portfolio, reader, runtime = kept
    for _ in range(2):
        voice, _ = child_voice.choose(portfolio, "c1", "child:d1", runtime)
        assert b"".join(voice.stream("The fish swim home.")) == b"ID3 child The fish swim home."
    assert reader.read_for == ["The fish swim home."]
    assert reader.said == ["the fish swim home"], "the Spark is given the recording's words with it"


def test_a_page_is_read_a_sentence_at_a_time_so_the_first_is_heard_soon(kept):
    portfolio, reader, runtime = kept
    voice, _ = child_voice.choose(portfolio, "c1", "child:d1", runtime)
    page = "三文鱼一家排着队游回家。最小的两条鱼在前面带路。"
    assert len(list(voice.stream(page))) == 2
    assert reader.read_for == ["三文鱼一家排着队游回家。", "最小的两条鱼在前面带路。"]


def test_a_recording_the_spark_cannot_copy_leaves_its_pages_to_the_studio_voice_for_a_while(kept, monkeypatch):
    portfolio, _, runtime = kept
    runtime.clients[child_voice.SLOT] = failing = Reader(fail=True)
    for page in ("The fish swim home.", "They reach the river."):
        voice, _ = child_voice.choose(portfolio, "c1", "child:d1", runtime)
        assert b"".join(voice.stream(page)) == b"ID3 studio " + page.encode()
    assert failing.read_for == ["The fish swim home."], "not asked again for the rest of that reading"
    runtime.clients[child_voice.SLOT] = recovered = Reader()
    later = child_voice.time.monotonic() + child_voice.FAILED_S
    monkeypatch.setattr(child_voice.time, "monotonic", lambda: later)
    voice, _ = child_voice.choose(portfolio, "c1", "child:d1", runtime)
    assert b"".join(voice.stream("The fish swim home.")) == b"ID3 child The fish swim home.", "a busy Spark is asked again"
    assert recovered.read_for == ["The fish swim home."]


def test_a_new_book_is_read_ahead_in_page_order_and_only_where_a_voice_is_kept(kept):
    portfolio, reader, runtime = kept
    done = threading.Event()
    original = child_voice.narration

    def counted(*args, **kwargs):
        made = original(*args, **kwargs)
        if len(reader.read_for) == 2:
            done.set()
        return made
    child_voice.narration = counted
    try:
        child_voice.read_ahead(portfolio, "c1", [("d1", "Page one."), ("d2", "Page two."), ("d1", "The end.")], runtime)
        assert done.wait(5)
    finally:
        child_voice.narration = original
    assert reader.read_for == ["Page one.", "The end."]
    key = hashlib.sha256(b"The end.").hexdigest()
    assert portfolio.narration("c1", "d1", key) == b"ID3 child The end."


def test_the_hearing_route_hands_the_page_the_recordings_handle(tmp_path, routed):
    from tests.server.test_serve import call, multipart
    from studio.serve import make_server
    classroom = routed([GOOD])
    classroom.portfolio = Portfolio(tmp_path / "history.sqlite3")
    classroom.ears = Ears()
    page = tmp_path / "index.html"
    page.write_text("<title>Beyond Canvas</title>", encoding="utf-8")
    server = make_server(classroom, "127.0.0.1", 0, page)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        sid = classroom.begin(CLASS)
        body, content_type = multipart("audio", "said.wav", recording(1))
        status, heard = call(f"http://127.0.0.1:{server.server_address[1]}", "POST", f"/api/session/{sid}/heard",
                             body, content_type)
        assert status == 200 and heard["text"] == "the fish swim home"
        assert heard["sample"] in classroom.sessions[sid].heard
    finally:
        server.shutdown()
        server.server_close()
        classroom.close()


def test_a_sample_that_is_not_a_handle_is_refused(voiced):
    classroom, sid, did, _ = voiced
    with pytest.raises(ValueError):
        classroom.request(sid, "art-feedback", [did], {"transcript": "hi", "sample": 42})
