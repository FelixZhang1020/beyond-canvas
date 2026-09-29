"""The studio's own storybook voice, each sentence made once and kept with the class's book.

A page with no child's voice kept for its drawing is read by the studio's voice, StepFun's `soft-child` preset. At
one point that was every page of every book: no class had a spoken answer kept. Each press of Read asked StepFun
afresh, about two seconds a sentence before anything was heard, over a link to the classroom that measured 7 to
67 KB/s, and an ended class kept nothing between presses (operator: "voice loading ... still slow").

Each sentence is kept in the Portfolio with the class's book (Portfolio.keep_reading), so it goes when the book
goes: made again, a drawing deleted with it, or the class deleted. What is kept is the studio's voice reading the
story, as the book's own text is kept. Only a page the book asks for by its drawing is kept (28-book.js asks
"child:<drawing>"): the chat's voices, and a child's own answers read back on the review page in this same voice,
never are, since clearing the chat must take them away (code review). A book is read ahead whenever it
is made or opened (child_voice.read_ahead), so a press waits only for the sound to travel.
"""

from __future__ import annotations

import hashlib
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor

from studio.providers.stepfun_voice import sentences

BOOK_VOICE = "soft-child"   # the studio's storybook voice, for every page without a child's recording
_lock = threading.Lock()
_making: dict = {}   # one lock per sentence being made, so a read-ahead and a press share one making


def key(studio, sentence: str) -> str:
    """What a sentence is kept under: its words, and the voice that read them, at the size it is sent."""
    voice = f"{getattr(studio, 'model', '')}|{getattr(studio, 'bitrate', '')}|{BOOK_VOICE}"
    return hashlib.sha256(f"{voice}|{sentence}".encode()).hexdigest()


def reading(portfolio, course_id, studio, sentence, cancelled=lambda: False) -> bytes:
    """One sentence in the studio's storybook voice, as MP3: kept from before, or made now and kept; b"" if cancelled."""
    kept_as = key(studio, sentence)
    with _lock:
        making = _making.setdefault((course_id, kept_as), threading.Lock())
    with making:
        kept = portfolio.reading(course_id, kept_as)
        if kept is not None:
            return kept
        # Made whole: through `stream` a long sentence is split at its comma again, and two pieces were never kept.
        make = getattr(studio, "clip", None)
        pieces = [make(sentence, BOOK_VOICE)] if make else [p for p in studio.stream(sentence, BOOK_VOICE, cancelled) if p]
        if cancelled() or not pieces:
            return b""
        if len(pieces) == 1:   # one sentence is one MP3; anything else is played but not kept
            try:
                portfolio.keep_reading(course_id, kept_as, pieces[0])
            except sqlite3.Error:
                pass   # the class or its book went while the sentence was made: play it, keep nothing
        return b"".join(pieces)


class BookVoice:
    """The studio's storybook voice for studio/voice/speech.py, an MP3 a sentence, each kept with the book."""

    compressed = True
    voice = BOOK_VOICE
    sample_rate = 24000

    def __init__(self, portfolio, course_id, studio):
        self.portfolio, self.course_id, self.studio = portfolio, course_id, studio
        self.model = getattr(studio, "model", "")
        self.base_url = f"book:{course_id}"

    def validate_voice(self, voice_id) -> str:
        return self.studio.validate_voice(BOOK_VOICE)

    def stream(self, text, voice_id=BOOK_VOICE, cancelled=lambda: False):
        """Sentence by sentence, the next made while the one before is heard, as the class voice does."""
        pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="book-voice")
        try:
            pending = [pool.submit(reading, self.portfolio, self.course_id, self.studio, part, cancelled)
                       for part in sentences(text.strip())]
            for job in pending:
                if cancelled():
                    return
                made = job.result()
                if made:
                    yield made
        finally:
            pool.shutdown(wait=False, cancel_futures=True)
