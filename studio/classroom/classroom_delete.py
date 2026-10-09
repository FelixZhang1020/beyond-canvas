"""Deleting a drawing, or a whole class, for good (operator).

Gone for good, by the operator's choice over a class that could be brought back: the Portfolio's
course, every drawing and everything made from them, and any editor open on it. Whatever is still
being made for the class is stopped rather than waited for. The Portfolio is erased first, so a
failure there leaves the class exactly as it was; the editors are closed after, inside the same
lock `_record_request` takes, so no result can land in between. The Spark's nightly copy and the
copies pulled back to the Mac still hold it until they age out, and that was said when it was chosen.

Kept apart from classroom.py, which is over the 500-line limit and cannot be written to.
"""

from __future__ import annotations

from studio.classroom.portfolio import DrawingInUse


class CourseDeletion:
    def delete_course(self, course_id):
        if self.portfolio is None:
            raise KeyError("No course portfolio is configured.")
        with self.lock:
            self.portfolio.delete_course(course_id)
            for sid, session in list(self.sessions.items()):
                if session.course_id == course_id:
                    self.end(sid)

    def remove_drawing(self, session_id, drawing_id):
        """Delete a drawing for good: this copy, the Portfolio's, and everything made from it alone.

        Refused while anything is still being made from it, so no request finishes into a deleted
        drawing; the Portfolio refuses one a book shares. Nothing is kept to undo it with.

        That includes the safety look begun as the photo arrived (classroom._look_on_arrival), which
        runs outside any request: until a review caught it, a drawing deleted in its first seconds
        was still being sent to the model after it was gone, and the look's record outlived it.
        """
        with self.lock:
            session = self._editable_session(session_id)
            if drawing_id not in session.drawings:
                raise KeyError(f"no such drawing: {drawing_id}")
            made = [self.requests[r] for r in session.request_ids
                    if r in self.requests and drawing_id in self.requests[r].drawing_ids]
            looked = session.conversations.get(drawing_id)
            arrival = getattr(looked, "arrival", None)
            looking = arrival is not None and arrival.is_alive()
            # Nor while its picture book gets ready after the story (classroom_runs._ready_book_pictures).
            ready = session.book_ready
            readying = ready is not None and ready.is_alive() and drawing_id in session.book_ready_ids
            if looking or readying or any(not request.stream.finished for request in made):
                raise DrawingInUse("Something is still being made from this drawing.", "drawing_busy")
            if self.portfolio:
                self.portfolio.remove_drawing(session.course_id, drawing_id)
            elif any(len(request.drawing_ids) > 1 for request in made):
                raise DrawingInUse("This drawing is part of a book.", "in_book")
            session.drawings.pop(drawing_id).unlink(missing_ok=True)
            for kept in (session.conversations, session.transcripts, session.openings, session.dialogue, session.scenes,
                         session.keep_lists):
                kept.pop(drawing_id, None)
            for pair in [pair for pair in session.book_pictures if pair[0] == drawing_id]:
                del session.book_pictures[pair]
            for request in made:
                session.request_ids.remove(request.request_id)
                self.requests.pop(request.request_id, None)
                self.ledger.forget(request.request_id)
            looked_id = getattr(looked, "arrival_id", None)
            if looked_id in session.request_ids:
                session.request_ids.remove(looked_id)
                self.ledger.forget(looked_id)
