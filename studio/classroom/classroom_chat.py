"""Taking back what was said about one drawing: the whole conversation, or its last round.

Operator. A stuck or wrong conversation could only be walked past; now the teacher
can clear it for good or take back the child's last answer and give it again. Both erase the
child's words from the Portfolio, which is the point, and neither can be undone.

A round is the child's words and everything the companion said after them. The companion
writes each reply from its opening, recent dialogue and the child's latest words, so what the class keeps
in memory -- the running dialogue a story is drafted from, the latest confirmed words, and the
opening -- is all that has to follow the Portfolio. Kept apart from classroom.py, which is over
the 500-line limit and cannot be written to.
"""

from __future__ import annotations

from studio.classroom.classroom_model import MAKING
from studio.classroom.portfolio import DrawingInUse

CHILD = "Child: "
# What a clip, a 3D model or a figure is made from is the picture and the words sent with the request,
# never the conversation; a book reads the conversation. Clearing it waits only for what reads it,
# so a conversation can be cleared while its drawing's clip is being made.
WORDLESS = tuple(skill for skill in MAKING if skill != "drawings-to-storybook")


class ChatEdits:
    def forget_chat(self, session_id, drawing_id, last_round=False):
        """Erase a drawing's conversation, or its last round. Refused while the companion is answering."""
        with self.lock:
            session = self._editable_session(session_id)
            if drawing_id not in session.drawings:
                raise KeyError(f"no such drawing: {drawing_id}")
            if any(not self.requests[r].stream.finished for r in session.request_ids
                   if r in self.requests and drawing_id in self.requests[r].drawing_ids
                   and self.requests[r].skill not in WORDLESS):
                raise DrawingInUse("The companion is still answering about this drawing.", "drawing_busy")
            dialogue = session.dialogue.get(drawing_id, [])
            said = [at for at, line in enumerate(dialogue) if line.startswith(CHILD)]
            if self.portfolio:
                self.portfolio.forget_chat(session.course_id, drawing_id, last_round)
            elif last_round and not said:
                raise DrawingInUse("There is no answer to take back.", "nothing_to_undo")
            # A reply asked for before now belongs to what was just erased (classroom_requests.py).
            session.chat_cleared[drawing_id] = session.chat_cleared.get(drawing_id, 0) + 1
            session.unanswered.pop(drawing_id, None)
            if not last_round:
                for kept in (session.dialogue, session.transcripts, session.openings):
                    kept.pop(drawing_id, None)
                if drawing_id in session.conversations:
                    session.conversations[drawing_id].opening = ""
                return
            if said:
                del dialogue[said[-1]:]
            earlier = [line[len(CHILD):] for line in dialogue if line.startswith(CHILD)]
            if earlier:
                session.transcripts[drawing_id] = earlier[-1]
            else:
                session.transcripts.pop(drawing_id, None)
