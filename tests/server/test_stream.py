"""A follower can be asked to say when nothing is happening.

A route that keeps a browser's connection alive through a silent stage needs
to know the stream has been quiet, and the stream already wakes every tick to
look for news. Reporting that quiet as a `None` item, only when asked, lets
the route write its keep-alive on its own thread; a follower that did not ask
sees exactly what it always saw.
"""
import threading
import time

import pytest

from studio.server import stream as stream_module
from studio.server.stream import Stream


@pytest.fixture
def quick(monkeypatch):
    monkeypatch.setattr(stream_module, "TICK_S", 0.01)


def test_a_plain_follower_never_hears_about_quiet(quick):
    stream = Stream()
    stream.emit("stage", {"n": 1})
    threading.Timer(0.08, stream.finish).start()
    assert list(stream.follow()) == [("stage", {"n": 1})]


def test_a_follower_that_asked_hears_none_while_nothing_happens_and_the_updates_when_they_come(quick):
    stream = Stream()
    seen = []

    def watch():
        seen.extend(stream.follow(quiet_after=0.03))

    thread = threading.Thread(target=watch, daemon=True)
    thread.start()
    time.sleep(0.15)
    stream.emit("stage", {"n": 1})
    stream.finish()
    thread.join(2)
    assert not thread.is_alive(), "the follower ends when the request ends"
    assert None in seen, "quiet was reported while nothing happened"
    assert [item for item in seen if item is not None] == [("stage", {"n": 1})]
    assert seen[-1] == ("stage", {"n": 1}), "quiet is never reported after the last update"


def _transition(skill, status, draft=""):
    from studio.core.harness import Stage, Transition
    return Transition(Stage("opening", skill, lambda inputs: None), status, draft=draft)


def test_the_childs_feedback_reaches_the_page_as_a_draft_under_review():
    stream = Stream()
    stream.observer("r1")(_transition("art-feedback", "checking", "我看见一只熊。"))
    stream.finish()
    assert list(stream.follow()) == [("stage", {"stage": "art-feedback", "status": "running", "request_id": "r1",
                                                "partial": {"text": "我看见一只熊。", "question": "",
                                                            "checking": True, "revised": False}})]


def test_no_other_skill_sends_its_words_again_while_they_are_judged():
    stream = Stream()
    for skill in ("teacher-review", "scene-description", "studio-safety"):
        stream.observer("r1")(_transition(skill, "checking", "words"))
    stream.finish()
    assert list(stream.follow()) == []
