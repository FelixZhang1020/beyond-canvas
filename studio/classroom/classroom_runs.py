"""Each skill's run inside a class: feedback, animation, 3D, the storybook and the creation drafts.

The Classroom mixes this in. Split out of classroom.py, unchanged, for the size limit.
"""

from __future__ import annotations

import threading
import time

from studio.voice import child_voice

from studio.conversation import creation
from studio.classroom.classroom_model import RUNGS, SAFETY_REASONS, ClassSession, Request, RequestCancelled
from studio.providers.choices import clip_makers
from studio.conversation.words import say, split_question
from studio.server import media_links


class SkillRuns:
    """The per-skill half of the Classroom. Each run reports through request.stream and self._publish."""

    def _feedback(self, request: Request, session: ClassSession) -> None:
        conversation = self._conversation(session, request.drawing_ids[0])
        conversation.observe = self._observer(request)
        # A rung outside the ladder was refused when the request was accepted.
        rung = request.options.get("rung")
        said = str(request.options.get("transcript", "") or "").strip()
        # A child can only answer something that was asked. Before the studio has opened,
        # the words in that field are the teacher's own — once a teacher's question
        # went into a course as the child's answer, and was answered with another question,
        # because a reply with no opening quietly wrote one nobody ever saw. Refused here,
        # before anything is recorded and before any model is asked.
        if said and rung not in RUNGS and not conversation.opening:
            request.stream.stop("art-feedback", say(session.language, "no_opening"), "no_opening")
            return
        # The same words sent again after a round nobody answered are that round retried, not a
        # second answer: the page puts them back in the field after a stop, and saving
        # them twice would show the child saying it twice. Only words left unanswered in this sitting
        # count: after a course is reopened the same words are a new answer (review).
        again = bool(said) and session.unanswered.get(request.drawing_ids[0]) == said
        if said and not again:
            self._record_request(request, request.request_id + "-words", "confirmed-words", {"text": said})
            child_voice.keep_first(self.portfolio, session, request.drawing_ids[0], request.request_id + "-words",
                                   request.options.get("sample"))
        if said:
            session.transcripts[request.drawing_ids[0]] = said
            session.unanswered[request.drawing_ids[0]] = said
        # The conversation so far, oldest first; the answer being replied to is supplied on its own.
        history = list(session.dialogue.get(request.drawing_ids[0], []))
        if said and history and history[-1] == f"Child: {said}":
            history = history[:-1]
        if rung in RUNGS:
            beat = conversation.climb(int(rung), request.request_id, history=tuple(history))
        elif said:
            self._bridge(request, session, said)
            beat = conversation.reply(said, request.request_id, history=tuple(history))
        else:
            beat = conversation.open(request.request_id)

        if not beat.ok:
            stage = "studio-safety" if beat.reason_code in SAFETY_REASONS else "art-feedback"
            if conversation.verdict is None:
                stage = "studio-safety"
            request.stream.stop(stage, beat.refused, beat.reason_code)
            return
        text, question = split_question(beat.text)
        self._publish(request,
            "done",
            {
                "stage": "art-feedback",
                "request_id": request.request_id,
                "outputs": {
                    "text": text,
                    "question": question,
                    "language": session.language,
                    "rubric": {"passed": not beat.failed_rules, "failed": beat.failed_rules},
                    "beat": beat.kind,
                },
            },
        )

    def _bridge(self, request: Request, session: ClassSession, said: str) -> None:
        """Say the child's words back at once, before the real reply is written (studio/conversation/bridge.py)."""
        from studio.conversation import bridge
        text, written = bridge.line(self._session_runtime(session).clients.get("chat.bridge"), said, session.language)
        request.stream.emit("stage", {"stage": "art-feedback", "status": "running", "request_id": request.request_id,
                                      "partial": {"bridge": text, "written": written}})

    def _animate(self, request: Request, session: ClassSession) -> None:
        """One short Wan preview, returned separately from the original drawing.

        The safety verdict is the conversation's, so a drawing already refused
        for feedback is refused here too without asking a model a second time.
        """
        conversation = self._conversation(session, request.drawing_ids[0])
        conversation.observe = self._observer(request)
        said = str(request.options.get("hint", "") or "").strip()
        # Which clip maker makes it: the teacher's choice (validated in classroom_requests), else the one the
        # studio would pick (ClipChoices: the Spark's while it is open, online once it is closed). Resolved once,
        # so the saved clip names the maker that made it (code review: it said "spark" for clips
        # made online).
        offered = clip_makers(self._session_runtime(session).editor)
        maker = request.options.get("clip_maker") or ("spark" if "spark" in offered or not offered else offered[0])
        conversation.clip_maker = maker if offered else None
        beat = conversation.animate(said, request.request_id)
        if not beat.ok:
            stage = "studio-safety" if conversation.verdict is None else request.skill
            if beat.reason_code in SAFETY_REASONS:
                stage = "studio-safety"
            request.stream.stop(stage, beat.refused, beat.reason_code)
            return
        self._publish(request,
            "done",
            {
                "stage": request.skill,
                "request_id": request.request_id,
                "outputs": {"video_url": beat.plan["video_url"], "language": session.language,
                            "scene_description": said, "deployment": self._session_runtime(session).name,
                            "clip_maker": maker},
            },
        )

    def _reconstruct(self, request: Request, session: ClassSession) -> None:
        conversation = self._conversation(session, request.drawing_ids[0])
        conversation.observe = self._observer(request)
        beat = conversation.reconstruct(request.request_id, request.options.get("model_choice", "auto"),
                                        regenerate=request.options.get("regenerate", False))
        if not beat.ok:
            stage = "studio-safety" if conversation.verdict is None or beat.reason_code in SAFETY_REASONS else request.skill
            request.stream.stop(stage, beat.refused, beat.reason_code)
            return
        self._publish(request, "done", {"stage": request.skill, "request_id": request.request_id,
                                    "outputs": {"scene": beat.plan, "language": session.language, "deployment": self._session_runtime(session).name, "model_choice": request.options.get("model_choice", "auto")}})

    def _figure(self, request: Request, session: ClassSession) -> None:
        """A 3D toy figure inspired by the painting; shown only if its checks passed (painting-to-figure)."""
        conversation = self._conversation(session, request.drawing_ids[0])
        conversation.observe = self._observer(request)
        beat = conversation.figure(request.request_id, request.cancelled.is_set)
        if not beat.ok:
            stage = "studio-safety" if conversation.verdict is None or beat.reason_code in SAFETY_REASONS else request.skill
            request.stream.stop(stage, beat.refused, beat.reason_code)
            return
        self._publish(request, "done", {"stage": request.skill, "request_id": request.request_id,
                                        "outputs": {"figure": beat.plan, "language": session.language,
                                                    "deployment": self._session_runtime(session).name}})

    def _book_pictures(self, request, session):
        """A storybook's pages redrawn in the chosen styles (studio/making/book_pictures.py). A page already drawn in a
        style, in this sitting or saved with the course, is not drawn again, except a sample she chose that the check
        flagged: in her one style, that gets its second try beside the rest of the book."""
        from studio.making import book_pictures
        from studio.core.deployments import BOOK_SLOT
        self._await_book_ready(request, session)
        choosing = len(request.options["styles"]) > 1
        wanted = [(did, style) for did in request.drawing_ids for style in request.options["styles"]]
        known, conversations, again = {}, {}, []
        for did, style in wanted:
            picture = session.book_pictures.get((did, style)) or (
                self.portfolio.latest_picture(session.course_id, did, style) if self.portfolio else None)
            if picture:
                known[(did, style)] = picture   # still shown if its second try is not safe to show
                if choosing or not picture.get("changed") or picture.get("again"):
                    continue
                again.append((did, style))
            if did not in conversations:
                conversation = conversations[did] = self._conversation(session, did)
                conversation.observe = self._observer(request)
                beat = conversation.story_page("", request.request_id)   # screened before any model sees it
                if not beat.ok:
                    request.stream.stop("studio-safety", beat.refused, beat.reason_code)
                    return
        missing = [pair for pair in wanted if pair not in known]
        try:
            drawn = book_pictures.make(conversations, missing, self._session_runtime(session).clients[BOOK_SLOT],
                                       session.keep_lists, request.request_id, again=again,
                                       choosing=choosing) if missing or again else []
        except book_pictures.Busy:
            request.stream.stop(request.skill, say(session.language, "busy"), "busy")
            return
        except book_pictures.Failed as failed:
            held = failed.code == "book_picture_held_back"
            request.stream.stop(request.skill, say(session.language, failed.code if held else "hiccup"), failed.code)
            return
        for picture in drawn:
            known[(picture["drawing_id"], picture["style"])] = picture
        for pair in again:   # a second try not safe to show leaves the first, and it is not tried a third time
            if not any((p["drawing_id"], p["style"]) == pair for p in drawn):
                known[pair] = {**known[pair], "again": True}
        session.book_pictures.update(known)
        outputs = {"pictures": [known[pair] for pair in wanted if pair in known], "language": session.language}
        # The course keeps each picture once: only the ones drawn now are saved, the page gets them all.
        with self.lock:
            if drawn:
                saved = {"pictures": drawn, "language": session.language}
                self._record_request(request, request.request_id, request.skill, saved)
                if self.portfolio:   # saved first, so each goes as a file of its own, as a clip does (_publish)
                    base = f"/api/courses/{session.course_id}/activities/{request.request_id}"
                    address = {(p["drawing_id"], p["style"]): p for p in media_links.detach(saved, base)["pictures"]}
                    outputs["pictures"] = [address.get((p["drawing_id"], p["style"]), p) for p in outputs["pictures"]]
            request.stream.emit("done", {"stage": request.skill, "request_id": request.request_id, "outputs": outputs})

    def _storybook(self, request, session):
        pages = []
        confirmed = {p["drawing_id"]: p["text"] for p in request.options.get("pages", [])}
        # The look the teacher chose (classroom_requests._book_look): the originals, or a picture-book style whose
        # pages were drawn before binding. `motion` lists the originals that play their clip.
        look, motion = request.options.get("look", "original"), request.options.get("motion")
        for drawing_id in request.drawing_ids:
            conversation = self._conversation(session, drawing_id)
            conversation.observe = self._observer(request)
            text = confirmed.get(drawing_id, session.transcripts.get(drawing_id, ""))
            beat = conversation.story_page(text, request.request_id)
            if not beat.ok:
                request.stream.stop("studio-safety", beat.refused, beat.reason_code)
                return
            page = {"drawing_id": drawing_id, "text": text}
            if look != "original":
                picture = session.book_pictures.get((drawing_id, look)) or (
                    self.portfolio.latest_picture(session.course_id, drawing_id, look) if self.portfolio else None)
                if not picture:
                    request.stream.stop(request.skill, say(session.language, "book_pictures_missing"), "pictures_missing")
                    return
                page["picture_url"] = picture["url"]
                pages.append(page)
                continue
            if motion is not None and drawing_id not in motion:
                video = None
            elif self.portfolio:
                video = self.portfolio.latest_video(session.course_id, drawing_id)
            else:
                cached = conversation._animation
                video = cached[1].as_dict().get("video_url") if cached else None
            if video:
                page["video_url"] = video
            pages.append(page)
        self._publish(request, "done", {"stage": request.skill, "request_id": request.request_id,
                                   "outputs": {"pages": pages, "language": session.language, "look": look}})
        # The pages a child talked about out loud, read in that child's voice while the teacher looks at the book.
        child_voice.read_ahead(self.portfolio, session.course_id, [(p["drawing_id"], p["text"]) for p in pages],
                               self._session_runtime(session))

    @staticmethod
    def _remember_creation(session, did, skill, output):
        if output.get("status"):
            return
        if skill in ("confirmed-words", "art-feedback"):
            text = "\n".join(str(output[k]) for k in ("text", "question") if output.get(k))
            if text:
                session.dialogue.setdefault(did, []).append(("Child: " if skill == "confirmed-words" else "Companion: ") + text)
            if skill == "art-feedback":
                session.unanswered.pop(did, None)   # answered: the same words again are a new answer
        scene = output.get("scene_description") or (output.get("text") if skill == "scene-description" else None)
        if scene:
            session.scenes[did] = scene
        if skill == "story-outline":
            for item in output.get("scenes", []):
                if item.get("drawing_id") == did:
                    session.scenes[did] = item["text"]

    def _creation_draft(self, request, session):
        added = []
        try:
            self._run_creation_draft(request, session, added)
        finally:
            # Stop never leaves an unpublished page available to a later press.
            if request.cancelled.is_set():
                for did, cached in added:
                    if session.accepted_scene_drafts.get(did) is cached:
                        session.accepted_scene_drafts.pop(did, None)

    def _run_creation_draft(self, request, session, added):
        scenes, supplied = [], request.options.get("scenes", {})
        for did in request.drawing_ids:
            if request.cancelled.is_set():
                raise RequestCancelled()
            fingerprint = (tuple(session.dialogue.get(did, [])), session.language, session.entrance,
                           session.lesson_intent)
            cached = session.accepted_scene_drafts.get(did)
            text = supplied.get(did) or session.scenes.get(did)
            if text:
                session.accepted_scene_drafts.pop(did, None)
            supplemented = request.skill == "story-outline" and not text
            if supplemented and cached and cached[0] == fingerprint:
                text = cached[1]
            conversation = self._conversation(session, did)
            conversation.observe = self._observer(request)
            needs_write = request.skill == "scene-description" or not text
            if needs_write:
                beat = conversation.creation_draft("scene", {
                    "dialogue": session.dialogue.get(did, []),
                    "previous": request.options.get("previous", "") if request.skill == "scene-description" else "",
                }, request.request_id,
                    independent_review=request.skill != "story-outline",
                    stopped=request.cancelled.is_set if request.skill == "story-outline" else None)
                text = beat.text
            else:
                beat = conversation.story_page(text, request.request_id)
            if not beat.ok:
                candidate = ({"skill": "scene-description", "text": beat.draft, "drawing_id": did}
                             if beat.draft is not None else None)
                self._stop_draft(request, beat, candidate)
                return
            scenes.append({"drawing_id": did, "text": text, "supplemented": supplemented})
            if needs_write and request.skill == "story-outline":
                saved = (fingerprint, text)
                session.accepted_scene_drafts[did] = saved
                added.append((did, saved))
        if request.skill == "scene-description":
            output = {"text": scenes[0]["text"], "language": session.language}
        else:
            conversation = self._conversation(session, request.drawing_ids[0])

            beat = conversation.creation_draft("story", {"scenes": [dict(scene, dialogue=session.dialogue.get(scene["drawing_id"], [])) for scene in scenes], "previous": request.options.get("previous", "")},
                                               request.request_id, request.drawing_ids,
                                               source_images=[self._conversation(session, did).image for did in request.drawing_ids],
                                               independent_review=False, stopped=request.cancelled.is_set)
            if not beat.ok:
                candidate = ({"skill": "story-outline", "outline": creation.parse_outline(beat.draft, request.drawing_ids),
                              "scenes": scenes} if beat.draft is not None else None)
                self._stop_draft(request, beat, candidate)
                return
            output = {"outline": creation.told(creation.parse_outline(beat.text, request.drawing_ids), session.language),
                      "scenes": scenes, "language": session.language}
        self._publish(request, "done", {"stage": request.skill, "request_id": request.request_id, "outputs": output})
        if request.skill == "story-outline":
            for did in request.drawing_ids:
                session.accepted_scene_drafts.pop(did, None)
            self._ready_book_pictures(request, session)

    def _ready_book_pictures(self, request, session):
        """While she reads the story, a picture book gets ready (book_pictures.prepare), after any earlier story's:
        only in a colour class on a studio with FLUX, as nothing else makes one."""
        from studio.making import book_pictures
        from studio.core.deployments import BOOK_SLOT
        painter = self._session_runtime(session).clients.get(BOOK_SLOT)
        if session.entrance != "colour" or painter is None:
            return
        conversations = {did: self._conversation(session, did) for did in request.drawing_ids}
        before = session.book_ready
        # Its drawings cannot be deleted until it is done (classroom_delete), as with the look on arrival.
        earlier = session.book_ready_ids if before is not None and before.is_alive() else set()
        session.book_ready_ids = earlier | set(conversations)

        def ready():
            try:
                if before is not None:
                    before.join()
                book_pictures.prepare(conversations, painter, session.keep_lists, request.request_id)
            finally:   # a class ended or a drawing deleted meanwhile takes what was written for it
                with self.lock:
                    if self.sessions.get(session.session_id) is not session:
                        self.ledger.forget(request.request_id)
                    for did in [did for did in session.keep_lists if did not in session.drawings]:
                        session.keep_lists.pop(did, None)
        session.book_ready = threading.Thread(target=ready, name="book-ready", daemon=True)
        session.book_ready.start()

    def _await_book_ready(self, request, session):
        """Page 1 asked for while FLUX is still loading waits for it, instead of being told the studio is busy."""
        from studio.making.book_pictures import READY_WAIT_S
        ready, deadline = session.book_ready, time.monotonic() + READY_WAIT_S
        while ready is not None and ready.is_alive() and time.monotonic() < deadline:
            if request.cancelled.is_set():
                break
            ready.join(0.5)
        if request.cancelled.is_set():
            raise RequestCancelled()

    def _stop_draft(self, request, beat, candidate):
        if candidate is None:
            request.stream.stop(request.skill, beat.refused, beat.reason_code)
            return
        # Rejected candidates remain separate from success outputs and never
        # enter _publish or the session's confirmed scenes/story pages.
        with self.lock:
            if request.cancelled.is_set() or request.session_id not in self.sessions:
                raise RequestCancelled()
            data = {"stage": request.skill, "request_id": request.request_id, "status": "stopped",
                    "message": beat.refused, "reason_code": beat.reason_code, "review_failed": True,
                    "candidate": candidate, "issues": list(beat.issues)}
            request.stream.emit("stage", data)
            request.stream.emit("done", data)
