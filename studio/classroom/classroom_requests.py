"""Accepting a request, running it on its own thread, and publishing what it produced.

The Classroom mixes this in. Split out of classroom.py, unchanged, for the size limit.
"""

from __future__ import annotations

import sqlite3
import threading
import traceback
import uuid
from contextvars import ContextVar
from typing import Any

from studio.conversation import creation
from studio.classroom.classroom_model import (BUILT, FEEDBACK_PLAN, ONE_DRAWING, RUNGS, SKILLS, ClassSession, Request,
                                    RequestCancelled)
from studio.classroom.classroom_chat import ChatEdits
from studio.classroom.classroom_delete import CourseDeletion
from studio.classroom.portfolio import CourseClosed
from studio.server import media_links
from studio.server.stream import ledger_line
from studio.core.metering import counting_for, stop_counting
from studio.providers.choices import clip_makers
from studio.conversation.words import say


# The watcher of the request running on this thread. A drawing has one Conversation, and its `observe`
# used to be the request's own watcher; with a clip and a conversation able to run on the
# same drawing at once, the second would take over the first's progress and its cancel check. Every
# run sets its watcher here and hands the Conversation the one router below, which asks the thread.
_WATCHING: ContextVar = ContextVar("watching", default=None)


class _Routed:
    """Passes a transition to whichever request is running on the calling thread."""

    def __call__(self, transition):
        watch = _WATCHING.get()
        if watch is not None:
            watch(transition)

    def __getattr__(self, name):
        return getattr(_WATCHING.get(), name)


ROUTED = _Routed()


class RequestFlow(ChatEdits, CourseDeletion):
    """The request half of the Classroom: validation, the run loop, publishing, the ledger read-back.

    Carries ChatEdits (taking a conversation back) and CourseDeletion because classroom.py is full.
    """

    def request(
        self, session_id: str, skill: str, drawing_ids: list[str], options: dict[str, Any]
    ) -> dict[str, Any]:
        session = self._editable_session(session_id)
        cleared = {drawing: session.chat_cleared.get(drawing, 0) for drawing in drawing_ids}
        if skill == "painting-to-animation" and options.get("media_kind") == "figure":
            # The colour planner's one "make" action has two outputs; a figure is its own skill underneath,
            # and needs no description.
            skill, options = "painting-to-figure", {}
        # The FLUX still picture, the third output, was retired (operator): Wan 2.2
        # makes the real animation. An old page asking for one is told so.
        if options.get("media_kind") == "image":
            raise ValueError("The still picture was retired; ask for the clip or the figure")
        if options.get("media_kind", "video") != "video":
            raise ValueError("Unknown media kind")
        # The teacher's choice of clip maker (operator): only one this class's studio offers.
        if skill == "painting-to-animation" and "clip_maker" in options:
            offered = clip_makers(self._session_runtime(session).editor)
            if options["clip_maker"] not in offered:
                raise ValueError(f"clip_maker must be one of {offered}")
        if skill not in SKILLS:
            raise ValueError(f"skill must be one of {SKILLS}")
        if skill == "sketch-to-3d" and session.entrance != "sketch":
            raise ValueError("sketch-to-3d requires the sketch entrance")
        if skill == "painting-to-figure" and session.entrance != "colour":
            raise ValueError("painting-to-figure requires the colour entrance")
        missing = [drawing for drawing in drawing_ids if drawing not in session.drawings]
        if not drawing_ids or missing:
            raise KeyError(f"no such drawing: {missing or 'none given'}")
        # Pixal3D, the second 3D choice, was archived (operator); an old page asking for it
        # is told so. Its models already in the Portfolio still open.
        if skill == "sketch-to-3d" and options.get("model_choice") == "pixal":
            raise ValueError("Pixal3D was archived; TRELLIS.2 makes the 3D model")
        if skill == "sketch-to-3d" and options.get("model_choice", "auto") not in ("auto", "trellis2"):
            raise ValueError("Unknown 3D model choice")
        if skill == "sketch-to-3d":
            if not isinstance(options.get("regenerate", False), bool):
                raise ValueError("regenerate must be a boolean")
            models = self.session_capabilities(session_id)["mesh_models"]
            choice = options.get("model_choice", "auto")
            if models:
                selected = next((m for m in models if m["id"] == ("trellis2" if choice == "auto" else choice)), None)
                if selected is None or selected["status"] == "unavailable":
                    raise ValueError("Selected 3D model is unavailable")
                options = dict(options, model_choice=choice)
        rung = options.get("rung")
        if rung is not None and rung not in RUNGS:
            raise ValueError(f"rung must be one of {RUNGS}, not {rung!r}")
        if not isinstance(options.get("sample", ""), str):   # a held recording's handle (studio/voice/child_voice.py)
            raise ValueError("sample must be the handle hearing returned")
        if skill in ONE_DRAWING and len(drawing_ids) > 1:
            # Silently using the first and dropping the rest looked like it had
            # worked on all of them.
            raise ValueError(f"{skill} takes one drawing, not {len(drawing_ids)}")
        if skill in ("drawings-to-storybook", "story-outline") and not 2 <= len(set(drawing_ids)) == len(drawing_ids) <= 8:
            raise ValueError("A book takes 2–8 distinct drawings.")
        if "pages" in options:
            options = dict(options, pages=creation.pages(options["pages"], drawing_ids))
        if skill in ("book-pictures", "drawings-to-storybook"):
            options = self._book_look(session, skill, drawing_ids, options)
        if skill in ("scene-description", "story-outline"):
            previous = options.get("previous", "")
            if not isinstance(previous, str) or len(previous) > 20000:
                raise ValueError("Invalid previous draft.")
            scenes = options.get("scenes", {})
            if (not isinstance(scenes, dict) or any(did not in drawing_ids or not isinstance(text, str)
                    or len(text) > 600 for did, text in scenes.items())):
                raise ValueError("Invalid scene descriptions.")
        request = Request(
            uuid.uuid4().hex[:12], session_id, skill, list(drawing_ids), dict(options)
        )
        with self.lock:
            self._editable_session(session_id)
            gone = [drawing for drawing in drawing_ids if drawing not in session.drawings]
            if gone:  # deleted by the teacher since the check above
                raise KeyError(f"no such drawing: {gone}")
            if skill == "art-feedback" and any(session.chat_cleared.get(d, 0) != n for d, n in cleared.items()):
                # Cleared or taken back while this was on its way: it belongs to the erased round
                # and would bring it back (found by review).
                raise ValueError("The conversation was cleared while this was being sent.")
            self.requests[request.request_id] = request
            session.request_ids.append(request.request_id)
        return {"request_id": request.request_id, "plan": self._plan(session, skill, drawing_ids)}

    def _book_look(self, session, skill, drawing_ids, options):
        """A picture book's options: which styles to draw, or which look and which clips the bound book uses."""
        from studio.making import book_pictures
        looks = book_pictures.styles()
        if session.entrance != "colour" and (skill == "book-pictures" or options.get("look", "original") != "original"):
            raise ValueError("A picture book is made in a colour class.")
        if skill == "book-pictures":
            chosen = options.get("styles")
            if (self._session_runtime(session).clients.get("image.book") is None or not isinstance(chosen, list)
                    or not chosen or any(not isinstance(s, str) or s not in looks for s in chosen)
                    or len(set(chosen)) != len(chosen)):
                raise ValueError(f"styles must be some of {list(looks)}")
            if len(set(drawing_ids)) != len(drawing_ids) or len(drawing_ids) * len(chosen) > book_pictures.MOST:
                raise ValueError(f"At most {book_pictures.MOST} distinct pictures in one job.")
            return {"styles": chosen}
        look, motion = options.get("look", "original"), options.get("motion")
        if look not in ("original", *looks):
            raise ValueError(f"look must be original or one of {list(looks)}")
        # Which pages play their clip, in a book of the originals; left out, every clip made so far, as before.
        if motion is not None and (not isinstance(motion, list) or any(did not in drawing_ids for did in motion)):
            raise ValueError("motion must list drawings of this book")
        return dict(options, look=look)

    def _plan(self, session: ClassSession, skill: str, drawing_ids: list[str]) -> list[dict]:
        """What will actually happen, not what happens the first time.

        A drawing is screened once and the verdict is remembered, so announcing
        the safety step on every request drew a step that never ran. The
        contract's closing promise is that the screen shows the sequence the
        record holds.
        """
        screened = all(
            # A look started on arrival will have run by the time this request's work begins.
            drawing in session.conversations and (session.conversations[drawing].verdict is not None
                                                  or getattr(session.conversations[drawing], "arrival", None))
            for drawing in drawing_ids
        )
        steps = [] if screened else [{"stage": "studio-safety", "skill": "studio-safety"}]
        if skill == "art-feedback":
            return steps + FEEDBACK_PLAN[1:]
        return steps + [{"stage": skill, "skill": skill}]

    def start(self, request_id: str) -> threading.Thread:
        thread = threading.Thread(target=self.run_request, args=(request_id,), daemon=True)
        thread.start()
        return thread

    def follow(self, request_id: str, quiet_after: float | None = None):
        return self.requests[request_id].stream.follow(quiet_after)

    def cancel(self, session_id, request_id):
        self._session(session_id)
        request = self.requests[request_id]
        if request.session_id != session_id:
            raise KeyError("No such request in this class.")
        request.cancelled.set()
        request.stream.stop(request.skill, say(self.sessions[session_id].language, "cancelled"), "cancelled")
        request.stream.finish()

    def _observer(self, request):
        observe = request.stream.observer(request.request_id)
        def update(transition):
            if request.cancelled.is_set() or request.session_id not in self.sessions:
                raise RequestCancelled()
            observe(transition)
        update.wants_text = observe.wants_text   # which stages stream their words (studio/server/textstream.py)
        _WATCHING.set(update)
        return ROUTED

    def run_request(self, request_id: str) -> None:
        """Do the work of one request, whatever happens, and always finish the run."""
        request = self.requests.get(request_id)
        if request is None:
            return
        session = self.sessions.get(request.session_id)
        language = session.language if session else "en"
        lane = session.lane(request.skill) if session is not None else None
        acquired = lane is not None and lane.acquire(blocking=False)
        from studio.providers.gpu_job import cancelled_request
        cancel_token = cancelled_request.set(request.cancelled.is_set)
        counted = counting_for(request_id)   # this request's meter totals, apart from another lane's
        try:
            if request.cancelled.is_set():
                return
            for drawing_id in (request.drawing_ids if acquired else ()):
                arrival = getattr(session.conversations.get(drawing_id), "arrival", None)
                if arrival is not None:
                    arrival.join()   # the safety look begun on upload; never a second one
            if session is not None and not acquired:
                request.stream.stop(request.skill, say(language, "busy"), "busy")
            elif self._too_full():
                # Section 7's whole point: out of memory freezes the box, and a
                # freeze during a class is the end of the class. Refusing one
                # request is recoverable; a frozen machine in front of twenty
                # children is not. Until now the ceiling was arithmetic with a
                # unit test and nothing consulted it.
                request.stream.stop(request.skill, say(language, "busy"), "out_of_memory")
            elif session is None:
                request.stream.stop(request.skill, say(language, "hiccup"), "model_unavailable")
            elif request.skill not in BUILT:
                request.stream.stop(request.skill, say(language, "not_open"), "not_built")
            elif request.skill == "teacher-review":
                self._teacher_review(request, session)
            elif request.skill in ("scene-description", "story-outline"):
                self._creation_draft(request, session)
            elif request.skill == "painting-to-animation":
                if not self.animation_slot.acquire(blocking=False):
                    request.stream.stop(request.skill, say(language, "busy"), "busy")
                else:
                    try:
                        self._animate(request, session)
                    finally:
                        self.animation_slot.release()
            elif request.skill == "sketch-to-3d":
                if not self.sketch_slot.acquire(blocking=False):
                    request.stream.stop(request.skill, say(language, "busy"), "busy")
                else:
                    try:
                        self._reconstruct(request, session)
                    finally:
                        self.sketch_slot.release()
            elif request.skill == "painting-to-figure":
                if not self.figure_slot.acquire(blocking=False):
                    request.stream.stop(request.skill, say(language, "busy"), "busy")
                else:
                    try:
                        self._figure(request, session)
                    finally:
                        self.figure_slot.release()
            elif request.skill == "drawings-to-storybook":
                self._storybook(request, session)
            elif request.skill == "book-pictures":
                self._book_pictures(request, session)
            else:
                self._feedback(request, session)
        except (RequestCancelled, CourseClosed):
            pass
        except sqlite3.Error:
            request.stream.stop(request.skill, say(language, "storage_failed"), "storage_unavailable")
        except Exception:
            traceback.print_exc()
            request.stream.stop(request.skill, say(language, "hiccup"), "model_unavailable")
        finally:
            cancelled_request.reset(cancel_token)
            stop_counting(counted)
            _WATCHING.set(None)
            if self.portfolio and session is not None and request.session_id in self.sessions:
                stopped = next((data for name, data in reversed(request.stream.updates)
                                if name == "done" and data.get("status") == "stopped"), None)
                if stopped:
                    try:
                        self._record_request(request, request_id, request.skill, stopped)
                    except (CourseClosed, RequestCancelled):
                        pass
                    except Exception:
                        traceback.print_exc()
            request.stream.finish()
            if acquired:
                lane.release()
            if request.session_id not in self.sessions:
                # Its updates stay: the page may not yet have read the reason its class ended, and
                # Classroom.end already let go of the request, so they go when the page's stream does.
                self.ledger.forget(request_id)

    def _publish(self, request, event, data):
        with self.lock:
            self._record_request(request, request.request_id, request.skill, data["outputs"])
            if self.portfolio:
                data["outputs"]["artifact_id"] = request.request_id
                # Clips, book pictures and 3D models go as files of their own, as a saved result's do: sent inside the
                # "done", a book's seven pictures made it 2.2 MB, and over the class's link the page waited minutes
                # after the studio had finished (operator). The result was just saved, so its addresses answer.
                course = self._session(request.session_id).course_id
                data = {**data, "outputs": media_links.detach(
                    data["outputs"], f"/api/courses/{course}/activities/{request.request_id}")}
            request.stream.emit(event, data)

    def _record_request(self, request, activity_id, skill, output):
        # A result from a previous editor stays invalid even after the course
        # has been reopened. Serialize this check with completion/reopening.
        with self.lock:
            if request.cancelled.is_set() or request.session_id not in self.sessions:
                raise RequestCancelled()
            session = self._session(request.session_id)
            if self.portfolio:
                self.portfolio.record(self._session(request.session_id).course_id, activity_id, skill,
                                      request.drawing_ids, output)
            for did in request.drawing_ids:
                self._remember_creation(session, did, skill, output)

    def ledger_lines(self, session_id: str) -> list[dict[str, Any]]:
        """What this class did, read back from the file rather than from memory."""
        wanted = set(self._session(session_id).request_ids)
        return [
            ledger_line(entry, entry.session)
            for entry in self.ledger.entries()
            if entry.session in wanted
        ]
