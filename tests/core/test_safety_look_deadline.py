"""A look at the door that gives no answer is given up on, not waited out; a made thing's look is not.

One look spent all 12,000 tokens thinking and returned nothing; with the retries a
drawing could wait about five minutes. A look normally takes 3-7 s, so past LOOK_DEADLINE_S it is
a model that did not answer, and the harness already asks once more.
"""
import threading
import time
from pathlib import Path

import pytest
from conftest import load_script

from studio.core.errors import ModelError
from studio.providers.base import ChatResult

SCRIPT = Path(__file__).parents[2] / "skills" / "studio-safety" / "scripts" / "safety.py"
ALLOW = '{"verdict":"allow","reason":"a drawing","text_found":[]}'


@pytest.fixture
def safety():
    return load_script(SCRIPT, "safety_script_deadline")


class Silent:
    """A model that thinks and thinks and never answers."""
    def __init__(self): self.released = threading.Event()
    def chat(self, prompt, images=(), **kwargs):
        self.released.wait(5)
        return ChatResult(ALLOW, 1, 1, 0, 0, 0, "t", "t")


class Quick:
    def chat(self, prompt, images=(), **kwargs):
        return ChatResult(ALLOW, 1, 1, 0, 0, 0, "t", "t")


def test_a_look_with_no_answer_stops_at_the_deadline(safety, monkeypatch):
    monkeypatch.setattr(safety, "LOOK_DEADLINE_S", 0.2)
    silent = Silent()
    started = time.monotonic()
    with pytest.raises(ModelError, match="no answer within"):
        safety.screen("data:image/png;base64,x", silent)
    silent.released.set()
    assert time.monotonic() - started < 2, "the drawing is not kept waiting for a look that never ends"


def test_a_look_that_answers_in_time_is_taken(safety, monkeypatch):
    monkeypatch.setattr(safety, "LOOK_DEADLINE_S", 0.2)
    assert safety.screen("data:image/png;base64,x", Quick()).verdict == "allow"


def test_the_deadline_is_well_above_a_normal_look():
    text = SCRIPT.read_text(encoding="utf-8")
    assert "LOOK_DEADLINE_S = 45.0" in text   # a look takes 3-7 s on the Spark (ledger)


class Slow:
    """A look that answers, but only after the door's limit has passed."""
    def chat(self, prompt, images=(), **kwargs):
        time.sleep(0.5)
        return ChatResult(ALLOW, 1, 1, 0, 0, 0, "t", "t")


def test_a_finished_clips_look_is_waited_for_past_the_doors_limit(safety, monkeypatch):
    """A clip takes twelve minutes to make and is thrown away when its look fails, with no second try."""
    monkeypatch.setattr(safety, "LOOK_DEADLINE_S", 0.2)
    assert safety.screen("data:image/png;base64,x", Slow(), point="out").verdict == "allow"
    with pytest.raises(ModelError, match="no answer within"):
        safety.screen("data:image/png;base64,x", Slow(), point="door")
