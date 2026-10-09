"""The child's own voice for their storybook: which recording is kept, and which voice reads a page.

Operator: every page of a book is read in one voice. A drawing a child talked about out loud in the
chat is read in that child's voice, copied from the first answer said about it; one talked about only in typing,
or not at all, is read by the studio's voice. Several voices on one drawing (two children, a teacher helping) all
come down to the first recording sent. The recording comes only from the chat's microphone: never a file the
teacher adds, never the spoken ending. The ending page is read in the voice of the page before it. The same voice
reads the child's own answers about that drawing when the chat is played back (operator), typed ones too, so a child
is never heard in two voices; a drawing without one keeps the studio's voice for them.

A recording is held here, in the class's memory, from the moment it is heard until its answer is sent. Sending
keeps it in the Portfolio only if it is the first for that drawing (Portfolio.keep_voice), cut to its first ten
seconds of speech, with the words heard in it, and tied to that answer, so taking the answer back, clearing the
chat, deleting the drawing or the class deletes it, and every page read from it. A recording whose answer is never
sent is forgotten with the class.

The voice is copied on the Spark by VoxCPM2 (the `tts.child` slot, RemoteChildVoice), never by a company: StepFun's
copy reads one sentence per voice, and its lasting copy is sold per voice and kept on its servers. It is copied from
the recording and its words: from the recording alone, the sentences of a page in a 148 Hz voice came out anywhere
between 119 and 207 Hz; with its words, at 148 (docs/measured/child-voice.md). Each sentence read is
kept with the recording, so a book is read at once the next time; a new book is read ahead in the background
(read_ahead), so the teacher's first press is quick too.

The two protection rules the design record set for this feature, that a copied voice says only the child's own
words and needs its own parental consent, were set aside by the operator when this was decided, knowing that pages are
the studio's story and that parents may hear it as the child's.
"""

from __future__ import annotations

import dataclasses
import hashlib
import io
import secrets
import sqlite3
import threading
import time
import wave

from studio.voice import book_voice
from studio.voice.audio_in import say
from studio.voice.book_voice import BOOK_VOICE, BookVoice
from studio.providers.stepfun_voice import VoiceServiceError, sentences

SLOT = "tts.child"
PREFIX = "child:"   # how a book asks for the voice of a page's drawing: "child:<drawing id>"
WORDS = "child-words:"   # how the chat asks for a child's own answer read back: "child-words:<drawing id>"
HELD = 4   # recordings heard in a class and not yet sent; older ones are forgotten
REFERENCE_S = 10   # VoxCPM2 copies a voice from a few seconds; more is only more of a child's voice kept
_lock = threading.Lock()
_making: dict = {}   # one lock per sentence being read, so a read-ahead and a press share one making
_spark = threading.Lock()   # one sentence at a time to the Spark's voice, which takes one job at a time
# Recordings the Spark could not copy lately, and when: the rest of that reading goes to the studio's voice without
# asking again, and a reading after FAILED_S asks again, since a busy or restarting Spark fails the same way.
_failed: dict = {}
FAILED_S = 600
_ahead: set = set()   # the books being read ahead now, by course and pages


def hold(session, wav: bytes, heard):
    """Keep a recording from the chat's microphone until its answer is sent; the answer carries its `sample`."""
    if not heard.is_something:
        return heard
    token = secrets.token_urlsafe(12)
    with _lock:
        session.heard[token] = (wav, heard.text)
        while len(session.heard) > HELD:
            session.heard.popitem(last=False)
    return dataclasses.replace(heard, sample=token)


def keep_first(portfolio, session, drawing_id: str, activity_id: str, token) -> None:
    """The answer just saved was sent with a recording: keep it if it is the drawing's first."""
    with _lock:
        held = session.heard.pop(token, None) if isinstance(token, str) else None
    if held is None or portfolio is None:
        return
    wav, said = held
    clip, whole = reference(wav)
    try:   # the words go with it only while they are all in it: a cut recording is copied from its sound alone
        portfolio.keep_voice(session.course_id, drawing_id, activity_id, clip, said if whole else "")
    except sqlite3.Error:   # the answer is saved and answered either way; only the voice is lost
        say("child voice: a first recording could not be kept")


def reference(wav: bytes) -> tuple[bytes, bool]:
    """The recording from where the child starts speaking, at most REFERENCE_S seconds of it, and whether
    that is all of it."""
    try:
        with wave.open(io.BytesIO(wav)) as source:
            channels, width, rate = source.getnchannels(), source.getsampwidth(), source.getframerate()
            frames = source.readframes(source.getnframes())
    except (wave.Error, EOFError):
        return wav, True   # not a plain WAV: kept as it came, and the Spark says whether it can use it
    if (channels, width) != (1, 2):
        return wav, True
    step = rate // 50 * 2   # 20 ms windows of 16-bit samples
    loud = (at for at in range(0, len(frames) - 1, step)
            if max(memoryview(frames[at:at + step]).cast("h"), key=abs, default=0) not in range(-1000, 1001))
    start = max(0, next(loud, 0) - step * 5)   # from the breath before the first word (about -30 dB and up)
    out = io.BytesIO()
    with wave.open(out, "wb") as clip:
        clip.setnchannels(1)
        clip.setsampwidth(2)
        clip.setframerate(rate)
        clip.writeframes(frames[start:start + rate * 2 * REFERENCE_S])
    return out.getvalue(), start + rate * 2 * REFERENCE_S >= len(frames)


def choose(portfolio, course_id: str, voice_id, runtime):
    """The voice a page is read in and its id: the child's for "child:<drawing>" when one is kept, else the studio's
    storybook voice, kept with the book (studio/voice/book_voice.py). "child-words:<drawing>", a child's own answer
    played back in the chat or on the review page, is read in the same kept voice, else in the storybook voice and
    never kept, since clearing the chat must take it away. Anything else, the companion's voices, is passed through."""
    studio = runtime.voice
    words = isinstance(voice_id, str) and voice_id.startswith(WORDS)
    if not (words or isinstance(voice_id, str) and voice_id.startswith(PREFIX)):
        return studio, voice_id
    # The class voice speaks MP3; a studio without one (an older profile) could not fall back mid-book.
    mp3 = portfolio is not None and getattr(studio, "compressed", False)
    fallback = BookVoice(portfolio, course_id, studio) if mp3 and not words else studio
    maker, drawing = runtime.clients.get(SLOT), voice_id.split(":", 1)[1]
    kept = portfolio.voice(course_id, drawing) if maker is not None and mp3 else None
    if kept is None:
        return fallback, BOOK_VOICE
    return ChildVoice(portfolio, course_id, drawing, maker, fallback, kept[2]), ChildVoice.voice


def narration(portfolio, course_id, drawing_id, text, maker, cancelled=lambda: False):
    """A sentence read in the drawing's kept voice, as MP3: kept from before, or made now and kept; None if not.

    A sentence at a time, because VoxCPM2 on the Spark makes speech a little faster than it is heard (5 s for
    5.6 s, measured): the first is heard after a few seconds, and the rest keep ahead of the reading.
    """
    text = text.strip() if isinstance(text, str) else ""
    kept = portfolio.voice(course_id, drawing_id) if text else None
    if kept is None or time.monotonic() - _failed.get((course_id, drawing_id, kept[2]), -FAILED_S) < FAILED_S:
        return None
    key = hashlib.sha256(text.encode()).hexdigest()
    with _lock:
        page = _making.setdefault((course_id, drawing_id, key), threading.Lock())
    with page:
        made = portfolio.narration(course_id, drawing_id, key)
        if made is not None:
            return made
        try:
            with _spark:
                made = maker.read(kept[0], text, cancelled, said=kept[1])
        except VoiceServiceError:
            _failed[(course_id, drawing_id, kept[2])] = time.monotonic()
            say("child voice: the Spark could not copy this recording; the studio's voice reads its pages")
            return None
        if made:
            try:
                portfolio.keep_narration(course_id, drawing_id, key, made)
            except sqlite3.Error:
                pass   # the recording went while the page was read (a turn taken back): play it, keep nothing
        return made


def read_ahead(portfolio, course_id, pages, runtime) -> None:
    """Read a book in the background, in page order, so the teacher's press plays at once.

    `pages` is [(drawing_id, text)]. A page is read in its drawing's kept voice, or, with none kept or one the
    Spark cannot copy, in the studio's storybook voice (studio/voice/book_voice.py). Never raises: a page not read
    ahead is read when it is asked for. A book already being read ahead is not started twice.
    """
    maker, studio = runtime.clients.get(SLOT), runtime.voice
    wanted = [(d, t.strip()) for d, t in pages if d and isinstance(t, str) and t.strip()]
    if portfolio is None or not wanted:
        return
    job = (course_id, hash(tuple(wanted)))
    with _lock:
        if job in _ahead:
            return
        _ahead.add(job)

    def page(drawing_id, text):
        parts = sentences(text)
        first = narration(portfolio, course_id, drawing_id, parts[0], maker) if maker is not None else None
        if first is not None:
            for sentence in parts[1:]:
                if narration(portfolio, course_id, drawing_id, sentence, maker) is None:
                    return   # the Spark stopped partway: the page is read when it is asked for
        elif getattr(studio, "compressed", False):
            for sentence in parts:
                book_voice.reading(portfolio, course_id, studio, sentence)

    def work():
        try:
            for drawing_id, text in wanted:
                page(drawing_id, text)
        except (VoiceServiceError, sqlite3.Error, KeyError, OSError):
            pass   # StepFun unreachable, or a course deleted meanwhile: a press asks again
        finally:
            with _lock:
                _ahead.discard(job)
    threading.Thread(target=work, daemon=True, name="book-voice-ahead").start()


class ChildVoice:
    """A page in the child's voice for studio/voice/speech.py, an MP3 a sentence; the studio's voice if it cannot be made.

    Decided at the first sentence, so a page is never read in two voices: one the Spark cannot copy is read by the
    studio from its start, and one that fails halfway stops, as the class voice does.
    """

    compressed = True
    voice = "child"
    sample_rate = 24000
    model = "VoxCPM2"
    base_url = ""

    def __init__(self, portfolio, course_id, drawing_id, maker, studio, kept_at=""):
        self.portfolio, self.course_id, self.drawing_id = portfolio, course_id, drawing_id
        self.maker, self.studio = maker, studio
        # studio/voice/speech.py keeps what it read by this: the recording's own time, so one said again is never
        # answered with the reading of the one taken back.
        self.base_url = f"child:{course_id}:{drawing_id}:{kept_at}"

    def validate_voice(self, voice_id) -> str:
        return self.voice

    def stream(self, text, voice_id=voice, cancelled=lambda: False):
        for n, sentence in enumerate(sentences(text.strip())):
            if cancelled():
                return
            made = narration(self.portfolio, self.course_id, self.drawing_id, sentence, self.maker, cancelled)
            if made:
                yield made
            elif n == 0 and not cancelled():
                yield from self.studio.stream(text, BOOK_VOICE, cancelled)
                return
            elif not cancelled():
                raise VoiceServiceError("The child's voice stopped partway through the page.")
