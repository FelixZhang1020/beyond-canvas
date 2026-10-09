"""A class makes one thing and holds one conversation at the same time (operator).

One lock used to hold the whole class while a clip was made, about twelve minutes on the Spark, and
the teacher could neither talk with the next child nor ask for a teacher review. The skills' own work is
stood in for here, because a scripted model answers in order and two runs at once would take each
other's answers; what is real is the request runner, its two locks and where each run's progress goes.
"""

from __future__ import annotations

import threading
import types
from pathlib import Path

import pytest

from studio.classroom.classroom import Classroom
from studio.core.harness import Stage, Transition
from studio.classroom.portfolio import DrawingInUse
from tests.classroom.test_classroom import CLASS, DRAWING, Scripted


def steps(request):
    return [data.get("stage") for name, data in request.stream.updates if name == "stage"]


def reason(request):
    return next((data.get("reason_code") for name, data in request.stream.updates if name == "done"), None)


@pytest.fixture
def lanes(tmp_path):
    """A class with a clip that waits to be let go, and a conversation that answers at once."""
    # vlm.teacher named, so the teacher review below asks a script and never reaches StepFun.
    room = Classroom(tmp_path / "ledger", clients={"vlm.studio": Scripted([]), "vlm.director": Scripted([]),
                                                   "vlm.teacher": Scripted([])})
    sid = room.begin(CLASS)
    did = room.add_drawing(sid, Path(DRAWING).read_bytes())
    making, release = threading.Event(), threading.Event()

    def report(self, request, session, skill):
        conversation = self._conversation(session, request.drawing_ids[0])
        conversation.observe = self._observer(request)
        return lambda: conversation.observe(Transition(Stage(skill, skill, lambda _: None), "running"))

    def animate(self, request, session):
        progress = report(self, request, session, "painting-to-animation")
        making.set()
        assert release.wait(5), "the test never let the clip go"
        progress()   # after the conversation below took the same drawing's Conversation
        request.stream.emit("done", {"stage": request.skill, "outputs": {"video_url": "clip.mp4"}})

    def feedback(self, request, session):
        report(self, request, session, "art-feedback")()
        request.stream.emit("done", {"stage": request.skill, "outputs": {"text": "A sun.", "beat": "opening"}})

    room._animate = types.MethodType(animate, room)
    room._feedback = types.MethodType(feedback, room)
    yield types.SimpleNamespace(room=room, sid=sid, did=did, making=making, release=release)
    release.set()
    room.close()


def start_clip(lanes):
    rid = lanes.room.request(lanes.sid, "painting-to-animation", [lanes.did], {})["request_id"]
    thread = lanes.room.start(rid)
    assert lanes.making.wait(5), "the clip never started"
    return lanes.room.requests[rid], thread


def test_a_conversation_about_the_same_drawing_runs_while_its_clip_is_made(lanes):
    clip, thread = start_clip(lanes)
    rid = lanes.room.request(lanes.sid, "art-feedback", [lanes.did], {})["request_id"]
    lanes.room.run_request(rid)
    talk = lanes.room.requests[rid]
    assert reason(talk) is None, "the conversation was refused while a clip was being made"
    assert steps(talk) == ["art-feedback"]
    lanes.release.set()
    thread.join(5)
    assert not thread.is_alive()
    # The clip's progress stays the clip's, although the conversation took the drawing after it began;
    # it used to go to the conversation's finished stream, and be lost.
    assert "painting-to-animation" in steps(clip)
    assert "painting-to-animation" not in steps(talk)
    assert any(name == "done" and data.get("outputs") for name, data in clip.stream.updates)


def test_a_second_clip_still_waits_for_the_first(lanes):
    start_clip(lanes)
    rid = lanes.room.request(lanes.sid, "painting-to-animation", [lanes.did], {"hint": "again"})["request_id"]
    lanes.room.run_request(rid)
    assert reason(lanes.room.requests[rid]) == "busy"


def test_a_teacher_review_is_not_refused_as_busy_while_a_clip_is_made(lanes):
    start_clip(lanes)
    rid = lanes.room.request(lanes.sid, "teacher-review", [lanes.did], {})["request_id"]
    lanes.room.run_request(rid)
    # The scripted model has no review to give, so it stops; what matters is why it stopped.
    assert reason(lanes.room.requests[rid]) != "busy"


def test_settings_still_wait_for_a_clip(lanes):
    start_clip(lanes)
    with pytest.raises(ValueError):
        lanes.room.update_settings(lanes.sid, {"language": "zh"})


def test_a_conversation_can_be_cleared_while_its_drawing_is_being_animated(lanes):
    lanes.room.request(lanes.sid, "painting-to-animation", [lanes.did], {})   # accepted, not yet finished
    lanes.room.forget_chat(lanes.sid, lanes.did)
    lanes.room.request(lanes.sid, "art-feedback", [lanes.did], {})
    with pytest.raises(DrawingInUse):
        lanes.room.forget_chat(lanes.sid, lanes.did)
