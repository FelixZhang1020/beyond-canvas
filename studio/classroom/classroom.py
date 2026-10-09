"""One class, held in memory for as long as the teacher keeps it open.

This is the state the page contract describes: sessions, the drawings in them,
the requests made against them, and the events each request produced. It knows
nothing about HTTP — `serve.py` is the transport — so all of it is testable
with a fake model and no port.

Working drawings live in a private folder released at class end. The optional
Portfolio stores durable course originals, confirmed words and completed outputs,
as requested. Of the recordings only one per drawing is kept (the storybook voice); speech caches are
temporary. The
diagnostic ledger is still the harness's own record translated for the page.
"""

from __future__ import annotations

import io
import shutil
import tempfile
import threading
import time
import traceback
import uuid
from pathlib import Path
from typing import Any

from PIL import Image

from evalkit.rubric import ENTRANCES
from studio.conversation.conversation import Conversation, _screen_gate
from studio.core.errors import ModelError
from studio.core.harness import Harness, Stage
from studio.core.ledger import Ledger
from studio.providers import build_client, build_media_slot
from studio.providers.choices import clip_makers, closed_clip_makers
from studio.providers.media import MediaSlot
from studio.providers.base import VisionChatClient
from studio.core.slots import load_profile, resolve
from studio.core.watchdog import CLASSROOM_CEILING_GB
from studio.core.metering import used_memory_gb
from studio.voice import audio_in, child_voice
from studio.voice.transcribe import Heard, WhisperCppClient, hearing_for
from studio.classroom.portfolio import CourseClosed
from studio.conversation.words import say

from studio.classroom.classroom_model import (  # noqa: F401  (re-exported: callers import these from here)
    BUILT, FEEDBACK_PLAN, GEOMETRY_SLOT, LANGUAGES, ONE_DRAWING, RUNGS, SAFETY_REASONS, SAFETY_SLOT, built_here,
    SKILLS, SLOTS, ClassSession, Request, RequestCancelled, SessionGone,
)
from studio.classroom.classroom_requests import RequestFlow
from studio.classroom.classroom_runs import SkillRuns


class Classroom(RequestFlow, SkillRuns):
    """Sessions, drawings and requests, and one thread per request to run them."""

    def __init__(
        self,
        ledger_path: str | Path,
        *,
        profile: str = "cloud",
        clients: dict[str, VisionChatClient] | None = None,
        ears: WhisperCppClient | None = None,
        editor: MediaSlot | None = None,
        portrait: MediaSlot | None = None,
        voice=None,
        portfolio=None,
    ) -> None:
        self.profile = profile
        self.deployment = profile if profile == "stepfun" else "current"
        self._deployments = {}
        self.deployment_path = None
        self.ledger = Ledger(ledger_path)
        self.ceiling_gb = CLASSROOM_CEILING_GB
        # Optional on purpose: a studio with no transcription model still works,
        # because the teacher can always type what the child said. Listening is
        # a convenience on top of that, never a dependency of the loop.
        self.ears = ears or hearing_for(profile)
        runtime = None
        if clients is None and profile == 'stepfun':
            from studio.core.deployments import build_runtime
            runtime = build_runtime(profile)
            clients = runtime.clients
            editor = editor if editor is not None else runtime.editor
            portrait = portrait if portrait is not None else runtime.portrait
            voice = voice if voice is not None else runtime.voice
        if clients is None:
            resolved = load_profile(profile)
            clients = {slot: build_client(resolve(slot, resolved)) for slot in SLOTS}
            if SAFETY_SLOT in resolved:
                clients[SAFETY_SLOT] = build_client(resolved[SAFETY_SLOT])
            if GEOMETRY_SLOT in resolved:
                clients[GEOMETRY_SLOT] = build_client(resolved[GEOMETRY_SLOT])
            if editor is None and "video.animation" in resolved:
                try:
                    editor = build_media_slot(resolved["video.animation"])
                except ModelError:
                    # An unavailable optional image editor must not prevent a
                    # teacher from opening the existing feedback classroom.
                    editor = None
            if portrait is None and "mesh.portrait" in resolved:
                portrait = build_media_slot(resolved["mesh.portrait"])
        self.clients = clients
        self.editor = editor
        self.deployed = runtime is not None
        self.portrait = portrait
        self.voice = voice
        self.portfolio = portfolio
        self.sessions: dict[str, ClassSession] = {}
        self.requests: dict[str, Request] = {}
        self.lock = threading.RLock()
        # Bound simultaneous reconstruction requests across all connected tablets.
        self.sketch_slot = threading.BoundedSemaphore(1)
        self.animation_slot = threading.BoundedSemaphore(1)
        self.figure_slot = threading.BoundedSemaphore(1)
        # Off unless the server turns it on: tests script the safety answer after an upload.
        self.look_on_arrival = False

    def _runtime(self):
        from studio.core.deployments import Runtime
        with self.lock:
            return Runtime(self.deployment, self.profile, self.clients, self.editor,
                           self.portrait, self.voice, self.deployed)

    def _session_runtime(self, session):
        with self.lock:
            return session.runtime or self._runtime()

    def deployment_status(self):
        from studio.core.deployments import describe
        with self.lock:
            return describe(self)

    def switch_deployment(self, name):
        from studio.core.deployments import build_stepfun, build_runtime, DEPLOYMENTS, save_selection
        if name not in (*DEPLOYMENTS, "current"):
            raise ValueError("Unknown deployment")
        with self.lock:
            if name == self.deployment:
                if self.deployment_path:
                    save_selection(self.deployment_path, name)
                return self.deployment_status()
            self._deployments[self.deployment] = self._runtime()
            target = self._deployments.get(name)
            if target is None:
                if name == "current":
                    raise ValueError("Legacy deployment is not configured")
                target = build_stepfun() if name == "stepfun" else build_runtime(name)
            # Persist before changing live defaults. A failed save leaves the old runtime intact.
            if self.deployment_path:
                save_selection(self.deployment_path, name)
            for session in self.sessions.values():
                if session.runtime is None:
                    session.runtime = self._runtime()
            self._deployments[name] = target
            self.deployment, self.profile = target.name, target.profile
            self.clients, self.editor = target.clients, target.editor
            self.portrait, self.voice, self.deployed = target.portrait, target.voice, target.deployed
            return self.deployment_status()

    def session_capabilities(self, session_id):
        session = self._session(session_id)
        runtime = self._session_runtime(session)
        from studio.core.deployments import model_options
        with self.lock:
            checked_at, report = getattr(self, '_component_checks', {}).get(runtime.profile, (0, None))
        if report is None and runtime.deployed:
            # Nothing has been checked since this studio started, and nothing
            # used to be until someone opened the system screen —
            # so every class opened after a restart read every model as
            # "unverified". The first class to ask pays for one check; the cache
            # serves the rest. A check that cannot run reads as unknown, which is
            # the truth of it.
            from studio.core.deployment_checks import check_deployment
            try:
                report = check_deployment(self, runtime.profile)
                checked_at = time.monotonic()
            except Exception:
                report = None
        if report is not None and time.monotonic() - checked_at > 60:
            # The minute-old cut-off exists so a stale REFUSAL stops blocking a
            # model the teacher could try again. It was also turning a stale PASS
            # into "unverified" — a warning on a working route, in a teacher's
            # face, every time a minute had gone by. A stale pass stays ready and
            # says it was checked earlier; a stale refusal still falls back to
            # unknown.
            report = dict(report, components=[
                dict(c, reason='stale') if c.get('status') == 'ready'
                else dict(c, status='unknown', reason='not_checked')
                for c in report.get('components', [])])
        meshes = model_options(runtime.profile, "mesh", report) if runtime.deployed else []
        return {"deployment": runtime.name, "mesh_models": meshes,
                "video": runtime.editor is not None, "video_makers": clip_makers(runtime.editor), "video_makers_closed": closed_clip_makers(runtime.editor),
                "speech": {"available": runtime.voice is not None}}

    def health(self) -> dict[str, Any]:
        """What this studio is, and what it can actually do.

        `skills` is what runs here. The page hides the controls for everything
        else rather than offering a button that always answers "not open yet".
        """
        skills = built_here(self.editor, self.clients)
        with self.lock:
            active_requests = sum(not request.stream.finished for request in self.requests.values())
        return {
            "ok": True,
            "profile": self.profile,
            "mode": "studio",
            "skills": skills,
            "listening": self.ears is not None,
            "portfolio": self.portfolio is not None,
            "course_lifecycle": self.portfolio is not None,
            "active_requests": active_requests,
            "speech": {"available": self.voice is not None,
                       "local": bool(getattr(self.voice, "local", False)),
                       "model": getattr(self.voice, "model", None),
                       "voices": getattr(self.voice, "voices", {}),
                       "default_voice": getattr(self.voice, "voice", None)},
        }

    # Sessions ----------------------------------------------------------------

    def begin(self, settings: dict[str, Any]) -> str:
        """Start a class. The entrance has no default; the teacher picks it."""
        language = str(settings.get("language", ""))
        entrance = str(settings.get("entrance", ""))
        if language not in LANGUAGES:
            raise ValueError(f"language must be one of {LANGUAGES}")
        if entrance not in ENTRANCES:
            raise ValueError(f"entrance must be one of {ENTRANCES}; the teacher picks it by hand")
        session = ClassSession(
            session_id=uuid.uuid4().hex[:12],
            language=language,
            entrance=entrance,
            lesson_intent=str(settings.get("lesson_intent", "") or ""),
            folder=Path(tempfile.mkdtemp(prefix="beyond-canvas-")),
        )
        if self.portfolio:
            try:
                self.portfolio.begin(session.session_id, entrance, language, session.lesson_intent, settings.get("title"))
            except Exception:
                shutil.rmtree(session.folder, ignore_errors=True)
                raise
        session.course_id = session.session_id
        with self.lock:
            self.sessions[session.session_id] = session
        return session.session_id

    def end(self, session_id: str, reason: str = "") -> bool:
        """Release an editing session; only complete_course marks it ended. A `reason` is said to its running
        requests first: a stream that just closes reads on the page as a lost connection."""
        with self.lock:
            session = self.sessions.pop(session_id, None)
        if session is None:
            return False
        session.speech.stop(close=True)
        shutil.rmtree(session.folder, ignore_errors=True)
        for request_id in session.request_ids:
            request = self.requests.get(request_id)
            if request is not None:
                request.cancelled.set()
                if reason:
                    request.stream.stop(request.skill, say(session.language, reason), reason)
                request.stream.finish()
            self.ledger.forget(request_id)
            # Media responses contain embedded pictures; release them when the
            # class ends instead of keeping completed streams for the process.
            self.requests.pop(request_id, None)
        return True

    def save_drafts(self, session_id, drafts):
        with self.lock:
            session = self._editable_session(session_id)
            if self.portfolio is None:
                raise ValueError("Course storage is unavailable.")
            self.portfolio.save_drafts(session.course_id, drafts)

    def course_session(self, course_id):
        with self.lock:
            return next((s.session_id for s in self.sessions.values() if s.course_id == course_id), None)

    def complete_course(self, course_id):
        """The teacher explicitly makes the course read-only, then closes editors."""
        if self.portfolio is None:
            raise KeyError("No course portfolio is configured.")
        with self.lock:
            self.portfolio.end(course_id)  # A failed save leaves editing available.
            for sid, session in list(self.sessions.items()):
                if session.course_id == course_id:
                    self.end(sid)

    def edit_course(self, course_id, *, reopen=False):
        """Restore saved content into a fresh editor without changing its course ID."""
        if self.portfolio is None:
            raise KeyError("No course portfolio is configured.")
        with self.lock:
            course = self.portfolio.course(course_id)
            if course["ended_at"] and not reopen:
                raise CourseClosed("This course has ended. Reopen it before editing.")
            existing = self.course_session(course_id)
            session = ClassSession(uuid.uuid4().hex[:12], course["language"], course["entrance"],
                                   course["lesson_intent"], Path(tempfile.mkdtemp(prefix="beyond-canvas-")),
                                   course_id=course_id)
            try:
                for drawing in course["drawings"]:
                    data, mime = self.portfolio.drawing(course_id, drawing["id"])
                    path = session.folder / (drawing["id"] + "." + mime.split("/")[-1])
                    path.write_bytes(data)
                    session.drawings[drawing["id"]] = path
                for activity in course["activities"]:
                    summary = activity["summary"]
                    for did in activity["drawings"]:
                        self._remember_creation(session, did, activity["skill"], summary)
                        if activity["skill"] == "confirmed-words":
                            session.transcripts[did] = summary.get("text", "")
                        elif activity["skill"] == "art-feedback" and not summary.get("status") and did not in session.openings:
                            # The first thing the studio said about this drawing is what the
                            # child heard first. Usually that is the opening; a course saved
                            # by an older studio can hold replies and no opening record at all,
                            # and reading it as an unopened conversation would refuse the next
                            # answer the teacher sends and invent a fresh opening nobody saw.
                            session.openings[did] = "\n".join(filter(None, (summary.get("text"), summary.get("question"))))
                if reopen:
                    self.portfolio.reopen(course_id)
                else:
                    self.portfolio.require_open(course_id)
            except Exception:
                shutil.rmtree(session.folder, ignore_errors=True)
                raise
            if existing:
                self.end(existing, "session_gone")
            self.sessions[session.session_id] = session
            return {"session_id": session.session_id, "course": self.portfolio.course(course_id),
                    "deployment": self.deployment, "capabilities": self.session_capabilities(session.session_id)}

    def close(self) -> None:
        for session_id in list(self.sessions):
            self.end(session_id)

    # Drawings ----------------------------------------------------------------

    def add_drawing(self, session_id: str, data: bytes) -> str:
        session = self._editable_session(session_id)
        try:
            with Image.open(io.BytesIO(data)) as opened:
                opened.verify()
                kind = (opened.format or "png").lower()
        except Exception as error:
            raise ValueError(f"not an image: {error}") from error
        drawing_id = uuid.uuid4().hex[:12]
        with self.lock:
            session = self._editable_session(session_id)
            if self.portfolio:
                self.portfolio.add_drawing(session.course_id, drawing_id, data, f"image/{kind}")
            path = session.folder / f"{drawing_id}.{kind}"
            path.write_bytes(data)
            session.drawings[drawing_id] = path
        if self.look_on_arrival:
            self._look_on_arrival(session, drawing_id)
        return drawing_id

    def _look_on_arrival(self, session: ClassSession, drawing_id: str) -> None:
        """The safety look, once, as the photo arrives (operator).

        It used to run inside whatever the teacher pressed first and cost that
        step 4-7 s. Every later step reuses the verdict, and a request for this
        drawing waits for a look still in flight rather than paying for a second.
        A look that errors leaves no verdict, so the first request looks again.
        """
        conversation = self._conversation(session, drawing_id)
        stage = Stage("screen", "studio-safety", conversation._screen, gate=_screen_gate, retries=0)
        harness = Harness(self.ledger, meters=(conversation.screener,))
        # Filed under the class like any request, so its line shows in the class's
        # record and is forgotten with the rest when the class ends.
        with self.lock:
            session.request_ids.append(harness.session)
            conversation.arrival_id = harness.session   # forgotten with the drawing (classroom_delete.py)

        def look() -> None:
            try:
                harness.run([stage], {"drawing": conversation.drawing, "beat": "arrival"})
            except Exception:
                traceback.print_exc()
            # A class that ended while this look was out has already forgotten its
            # lines, and this one was written after. Checked after the write, so
            # whichever of the two finishes last removes it.
            with self.lock:
                ended = self.sessions.get(session.session_id) is not session
            if ended:
                self.ledger.forget(harness.session)

        conversation.arrival = threading.Thread(target=look, name="safety-on-arrival", daemon=True)
        conversation.arrival.start()

    def drawing(self, session_id: str, drawing_id: str) -> tuple[bytes, str]:
        path = self._session(session_id).drawings[drawing_id]
        return path.read_bytes(), f"image/{path.suffix.lstrip('.') or 'png'}"

    def hear(self, session_id: str, audio: bytes) -> Heard:
        """Turn one recording into a sentence the teacher can read and correct.

        What comes back is text, which is what section 5a asks for: the teacher sees what was heard
        before any of it reaches a skill. The recording is held until its answer is sent, and only the
        first about a drawing is kept, for its storybook page's voice (studio/voice/child_voice.py).
        """
        session = self._session(session_id)
        if not audio:
            raise ValueError("no audio was sent")
        return child_voice.hold(session, *audio_in.listen(self.ears, audio, session.language))

    def speak(self, session_id, text, voice_id=None):
        session = self._session(session_id)
        runtime = self._session_runtime(session)
        voice, voice_id = child_voice.choose(self.portfolio, session.course_id, voice_id, runtime)
        return session.speech.stream(voice, text, voice_id)

    def update_settings(self, session_id, settings):
        session = self._editable_session(session_id)
        language = settings.get("language", session.language)
        if language not in LANGUAGES:
            raise ValueError("Unsupported classroom language.")
        intent = settings.get("lesson_intent", session.lesson_intent)
        if not isinstance(intent, str) or len(intent) > 2000:
            raise ValueError("Lesson intent must be at most 2000 characters.")
        with session.idle(), self.lock:
            session = self._editable_session(session_id)
            if self.portfolio:
                self.portfolio.settings(session.course_id, language, intent)
            session.language, session.lesson_intent = language, intent
            for conversation in session.conversations.values():
                conversation.language, conversation.lesson_intent = language, intent
                conversation.settings = conversation.feedback.ClassSettings(session.entrance, language, intent)

    def _too_full(self) -> bool:
        """Whether the box has room to do one more thing.

        The ceiling is section 7's, and it is generous on purpose: it already
        contains the allowance for a model load's transient. On a laptop with
        less memory than the ceiling this never fires, which is correct — nothing
        here is loading a 24 GB model.
        """
        return used_memory_gb() >= self.ceiling_gb

    def _teacher_review(self, request, session):
        conversation = self._conversation(session, request.drawing_ids[0])
        conversation.observe = self._observer(request)
        client = self._session_runtime(session).clients.get("vlm.teacher")
        if client is None:
            # Every deployment profile names vlm.teacher, so a runtime built by
            # build_runtime always carries it. This path is only reached by a
            # classroom assembled from a bare client map, and resolves the slot
            # from StepFun First (API First until it was archived).
            client = build_client(resolve("vlm.teacher", load_profile("stepfun")))
        beat = conversation.teacher_review(client, request.request_id, request.cancelled.is_set)
        if not beat.ok:
            request.stream.stop("studio-safety" if beat.reason_code in SAFETY_REASONS else request.skill,
                                beat.refused, beat.reason_code)
            return
        self._publish(request, "done", {"stage": request.skill, "request_id": request.request_id,
            "outputs": {"text": beat.text, "language": session.language,
                        "model": getattr(client, "model", "") or "unknown", "beat": "teacher-review"}})

    def _conversation(self, session: ClassSession, drawing_id: str) -> Conversation:
        """One conversation per drawing, so the opening survives into the reply."""
        runtime = self._session_runtime(session)
        with self.lock:   # a clip and a conversation can ask for the same drawing's at once
            if drawing_id not in session.conversations:
                session.conversations[drawing_id] = Conversation(
                    session.drawings[drawing_id],
                    self.ledger,
                    entrance=session.entrance,  # type: ignore[arg-type]
                    studio=runtime.clients["vlm.studio"],
                    director=runtime.clients["vlm.director"],
                    screener=runtime.clients.get(SAFETY_SLOT),
                    geometry=runtime.clients.get(GEOMETRY_SLOT),
                    editor=runtime.editor,
                    creation=runtime.clients.get("vlm.creation"),
                    figure=runtime.clients.get("vlm.figure"),
                    figure_look=runtime.clients.get("vlm.figure.look"),
                    portrait=runtime.portrait,
                    language=session.language,
                    lesson_intent=session.lesson_intent,
                )
                session.conversations[drawing_id].opening = session.openings.get(drawing_id, "")
            return session.conversations[drawing_id]

    def _session(self, session_id: str) -> ClassSession:
        session = self.sessions.get(session_id)
        if session is None:
            raise SessionGone(f"no such session: {session_id}")
        return session

    def _editable_session(self, session_id):
        session = self._session(session_id)
        if self.portfolio:
            self.portfolio.require_open(session.course_id)
        return session
