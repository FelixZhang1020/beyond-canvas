"""What a class is made of: the skills it knows, the slots it needs, and one session and one request.

Split out of classroom.py (the file was 909 lines against the 500-line limit) so the request
and run halves can share these names without importing the Classroom itself. classroom.py re-exports them.
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from studio.conversation.conversation import Conversation
from studio.voice.speech import SpeechSession
from studio.server.stream import Stream

# Skills that run. The rest answer that they are not open yet, which is better
# than a stack trace dressed as a model outage.
BUILT = ("teacher-review", "art-feedback", "painting-to-animation", "painting-to-figure", "sketch-to-3d",
         "drawings-to-storybook", "scene-description", "story-outline", "book-pictures")

SKILLS = (
    "teacher-review",
    "art-feedback",
    "sketch-to-3d",
    "painting-to-animation",
    "painting-to-figure",
    "painting-to-scene",
    "drawings-to-storybook",
    "scene-description", "story-outline",
    # A storybook's pages redrawn in a picture-book style (studio/making/book_pictures.py).
    "book-pictures",
)
# Skills that speak about a single drawing. The storybook is the only one that
# takes a stack.
ONE_DRAWING = ("teacher-review", "art-feedback", "painting-to-animation", "painting-to-figure", "painting-to-scene",
               "sketch-to-3d", "scene-description")

# Skills that make something over minutes: a clip, a 3D model, a figure, a book. A class runs one of
# these beside one conversation, so the teacher can talk and write a teacher review while a clip is
# made (operator); one lock used to hold the whole class for the clip's ~12 minutes.
# Everything else is the talk lane.
MAKING = ("painting-to-animation", "painting-to-figure", "painting-to-scene", "sketch-to-3d",
          "drawings-to-storybook", "book-pictures")


def built_here(editor, clients) -> list[str]:
    """BUILT, less what this studio has no model for: no clip without a video slot, no picture book without
    FLUX on image.book (studio/core/deployments.py BOOK_SLOT). The page hides what is not here."""
    return [skill for skill in BUILT if not (skill == "painting-to-animation" and editor is None)
            and not (skill == "book-pictures" and "image.book" not in (clients or {}))]

LANGUAGES = ("zh", "en")

# The slots a class needs. `safety.image` is optional: the cloud profile has no
# such model and the director stands in. On the box it is not optional and it is
# not the director — section 7 loads the director alone, with the studio
# unloaded, and never while a child is waiting. Screening every drawing at the
# director would mean loading a 109 GB model for every photograph.
SLOTS = ("vlm.studio", "vlm.director")
SAFETY_SLOT = "safety.image"
GEOMETRY_SLOT = "vlm.sketch"
RUNGS = (2, 3)

# Reason codes that describe the drawing rather than the machine. The page
# attributes these to the safety step; everything else belongs to the skill.
SAFETY_REASONS = ("blank_page", "photo_not_drawing", "unsafe_image")

# The page names its steps by skill; the harness names its stages by beat. The
# rubric is listed as its own step because that is how a judge reads it.
FEEDBACK_PLAN = [
    {"stage": "studio-safety", "skill": "studio-safety"},
    {"stage": "art-feedback", "skill": "art-feedback"},
    {"stage": "rubric", "skill": "art-feedback"},
]


@dataclass
class ClassSession:
    """One class: its settings, its drawings, and the conversations open on them."""

    session_id: str
    language: str
    entrance: str
    lesson_intent: str
    folder: Path
    course_id: str = ""
    drawings: dict[str, Path] = field(default_factory=dict)
    conversations: dict[str, Conversation] = field(default_factory=dict)
    request_ids: list[str] = field(default_factory=list)
    transcripts: dict[str, str] = field(default_factory=dict)
    openings: dict[str, str] = field(default_factory=dict)
    dialogue: dict[str, list[str]] = field(default_factory=dict)
    # How often a drawing's conversation was cleared or taken back (studio/classroom/classroom_chat.py), so a
    # reply asked for before that cannot bring the erased round back; and the child's words still
    # waiting for an answer in this sitting, so only a real retry of them is not saved twice.
    chat_cleared: dict[str, int] = field(default_factory=dict)
    unanswered: dict[str, str] = field(default_factory=dict)
    scenes: dict[str, str] = field(default_factory=dict)
    # Accepted auto-filled scenes from an unfinished outline. They are not published scenes;
    # the dialogue/settings fingerprint prevents a retry from using stale words.
    accepted_scene_drafts: dict[str, tuple[tuple, str]] = field(default_factory=dict)
    # A picture book's must-keep lists, by drawing, and its redrawn pages, by (drawing, style): made once in a
    # sitting, and read back from the Portfolio after a reopen (studio/making/book_pictures.py).
    keep_lists: dict[str, str] = field(default_factory=dict)
    book_pictures: dict[tuple[str, str], dict] = field(default_factory=dict)
    # What gets a picture book ready while the teacher reads its story (book_pictures.prepare), for page 1 to wait on.
    book_ready: threading.Thread | None = None
    book_ready_ids: set[str] = field(default_factory=set)
    speech: SpeechSession = field(default_factory=SpeechSession)
    # Recordings heard and not yet sent as an answer, by the handle the page sends back (studio/voice/child_voice.py).
    heard: OrderedDict = field(default_factory=OrderedDict)
    talk_lock: threading.Lock = field(default_factory=threading.Lock)
    make_lock: threading.Lock = field(default_factory=threading.Lock)
    runtime: Any = None

    def lane(self, skill: str) -> threading.Lock:
        """The lock a skill's run holds: one making job and one conversation at a time, side by side."""
        return self.make_lock if skill in MAKING else self.talk_lock

    @contextmanager
    def idle(self):
        """Both lanes held, for a change no running job may see half made; refused while either works."""
        held = [lock for lock in (self.talk_lock, self.make_lock) if lock.acquire(blocking=False)]
        try:
            if len(held) < 2:
                raise ValueError("Wait for the current activity before changing settings.")
            yield
        finally:
            for lock in held:
                lock.release()


@dataclass
class Request:
    request_id: str
    session_id: str
    skill: str
    drawing_ids: list[str]
    options: dict[str, Any]
    stream: Stream = field(default_factory=Stream)
    cancelled: threading.Event = field(default_factory=threading.Event)


class RequestCancelled(Exception):
    pass


class SessionGone(KeyError):
    """This editing session is not open here any more.

    Almost always because the same course was opened again somewhere else: `edit_course` keeps
    one editor per course and ends the one it replaces, and the page that lost it has no way to
    hear about it. Told apart from every other 404 by its `code`, so that page can rejoin the
    course instead of repeating an id the server has already forgotten — which is what it used
    to do, three times in a row, while the message told the teacher to try again.
    """

    code = "session_gone"
