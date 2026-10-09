"""The course-history routes: what the Portfolio screen asks the server for.

These were part of `studio/serve.py` until that file passed the
500-line limit and the size guard stopped accepting writes to it. They are the
natural first piece to leave, because the portfolio is already its own store
(`studio/classroom/portfolio.py`) and its routes touch a live class only to ask whether one
happens to be open on the same course.

A mixin rather than a separate handler: the route table stays in `serve.py`, so
the question "what does this server answer?" still has one place to look, and
only the bodies moved. `_course_speech` reaches `_speech_events`, which lives in
`serve_speech.py`; both are mixed into the same handler, so the call resolves.
"""

from __future__ import annotations

import json
import sys
import time
from studio.voice import child_voice
from studio.making.figure_card import card
from studio.server import media_links
from studio.server.page_transfer import send_bytes
from urllib.parse import urlsplit, parse_qs

from studio.providers.stepfun_voice import VoiceServiceError


class PortfolioRoutes:
    """Course history, mixed into `StudioHandler`."""

    def _portfolio(self):
        portfolio = self.server.classroom.portfolio
        if portfolio is None:
            raise KeyError("This classroom does not have a portfolio store.")
        return portfolio

    def _remove_drawing(self, session_id, drawing_id):
        # A class route kept here because serve.py is full: deleting a drawing is a Portfolio deletion.
        self.server.classroom.remove_drawing(session_id, drawing_id)
        self._bytes(204, b"", "application/json")

    def _forget_chat(self, session_id, drawing_id, which):
        # Also a Portfolio deletion kept here because serve.py is full: `conversation` clears
        # the drawing's chat for good, `last-round` takes back the child's last answer.
        self.server.classroom.forget_chat(session_id, drawing_id, last_round=which == "last-round")
        self._bytes(204, b"", "application/json")

    def _courses(self):
        params = parse_qs(urlsplit(self.path).query)
        result = self._portfolio().courses(params.get("q", [""])[0], params.get("entrance", [""])[0],
                                           int(params.get("offset", ["0"])[0]))
        for item in result["items"]:
            item["active"] = self.server.classroom.course_session(item["id"]) is not None
        self._json(200, result)

    def _course(self, sid):
        result = self._portfolio().course(sid)
        result["active_session_id"] = self.server.classroom.course_session(sid)
        result["active"] = result["active_session_id"] is not None
        self._json(200, result)

    def _rename_course(self, sid):
        self._portfolio().rename(sid, self._json_body().get("title"))
        self._bytes(204, b"", "application/json")

    def _complete_course(self, sid):
        self._json_body()
        self.server.classroom.complete_course(sid)
        self._bytes(204, b"", "application/json")

    def _delete_course(self, sid):
        # Said in the studio's log once it is gone: two classes were once deleted seconds after they were made
        # and nothing recorded what, or by whom. Every browser reaches the studio through the door from one address,
        # so the browser's own name is what tells a person's Chrome from an automated one.
        portfolio = self.server.classroom.portfolio
        try:
            course = portfolio.course(sid) if portfolio else {}
        except KeyError:
            course = {}
        self.server.classroom.delete_course(sid)
        print(f"{time.strftime('%d/%b/%Y %H:%M:%S')} class deleted: {sid} "
              f"{json.dumps(course.get('title') or '', ensure_ascii=False)} with {len(course.get('drawings', []))} "
              f"drawing(s), by {self.headers.get('User-Agent') or 'a client that gave no name'}", file=sys.stderr)
        self._bytes(204, b"", "application/json")

    def _reopen_course(self, sid):
        self._json_body()
        self._json(200, self.server.classroom.edit_course(sid, reopen=True))

    def _edit_course(self, sid):
        self._json_body()
        self._json(200, self.server.classroom.edit_course(sid))

    def _course_drawing(self, sid, did):
        # Tagged rather than sent again: a drawing does not change once it is
        # saved, and the home screen asks for every tile on every visit.
        thumbnail = parse_qs(urlsplit(self.path).query).get("thumbnail") == ["1"]
        send_bytes(self, *self._portfolio().drawing(sid, did, thumbnail))

    def _course_activity(self, sid, aid):
        activity = self._portfolio().activity(sid, aid)
        if parse_qs(urlsplit(self.path).query).get("preview") == ["1"]:
            # A saved 3D figure as the picture on its card, on this row because serve.py is full.
            figure = activity["outputs"].get("figure")
            if not isinstance(figure, dict):
                raise KeyError("This result has no 3D figure.")
            send_bytes(self, card(figure), "image/png", private=True)
            return
        pages = activity["outputs"].get("pages")
        if isinstance(pages, list) and pages:
            # A book opened is read ahead, ending included, so Read plays at once (studio/voice/book_voice.py).
            wanted = [(page.get("drawing_id"), page.get("text")) for page in pages if isinstance(page, dict)]
            if activity["ending"] and wanted:
                wanted.append((wanted[-1][0], activity["ending"]))
            child_voice.read_ahead(self._portfolio(), sid, wanted, self._course_runtime(sid))
        # Clips, book pictures and 3D models go as files of their own (studio/server/media_links.py); the rest is
        # sent compressed, and revalidated on repeat visits.
        activity["outputs"] = media_links.detach(activity["outputs"], f"/api/courses/{sid}/activities/{aid}")
        body = json.dumps(activity, ensure_ascii=False).encode("utf-8")
        send_bytes(self, body, "application/json; charset=utf-8", compress=True, private=True)

    def _course_media(self, sid, aid, address):
        media_links.send(self, *media_links.media(self._portfolio().activity(sid, aid)["outputs"], address))

    def _course_result(self, sid, aid, part):
        # A storybook's ending and a 3D result's angle share one route row: serve.py is at its size limit.
        body = self._json_body()
        if part == "view":
            self._portfolio().view(sid, aid, body.get("camera_base"))
        else:
            self._portfolio().ending(sid, aid, body.get("text"))
            # The whole book again, since a new ending takes the book's kept readings with it; the ending in the voice
            # of the page before it, as the book reads it (studio/voice/child_voice.py).
            pages = [p for p in self._portfolio().activity(sid, aid)["outputs"].get("pages") or [] if isinstance(p, dict)]
            wanted = [(p.get("drawing_id"), p.get("text")) for p in pages]
            ending = (wanted[-1][0] if wanted else None, body.get("text"))
            child_voice.read_ahead(self._portfolio(), sid, wanted + [ending], self._course_runtime(sid))
        self._bytes(204, b"", "application/json")

    def _course_runtime(self, sid):
        """The runtime a saved course is read with: its open class's, or the studio's own."""
        classroom = self.server.classroom
        with classroom.lock:
            active = classroom.course_session(sid)
            return classroom._session_runtime(classroom._session(active)) if active else classroom._runtime()

    def _course_speech(self, sid):
        from studio.voice.speech import SpeechSession
        self._portfolio().course(sid)  # Only an existing saved course can use this route.
        payload = self._json_body()
        try:
            voice, voice_id = child_voice.choose(self._portfolio(), sid, payload.get("voice"), self._course_runtime(sid))
            events = SpeechSession().stream(voice, payload.get("text"), voice_id)
        except VoiceServiceError as error:
            print(f"course speech unavailable before streaming: {error}", flush=True)
            self._json(503, {"error": "Classroom speech is unavailable."})
            return
        self._speech_events(events)
