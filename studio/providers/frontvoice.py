"""The class's first voice: Qwen3.6 on the Spark writes the chat lines, Step 3.7 Flash whenever it cannot.

Operator decision, on docs/measured/chat-speed-and-front-voice.md: Step 3.7 Flash
thinks before every answer and a first comment took about forty seconds; Qwen3.6 with its thinking off
writes the same lines in about one, and they pass the rubric about as often. Step still judges every
line, so only the writing moves.

Qwen holds ~50 GiB and steps aside while the Spark makes a clip, so for minutes at a time it is not
there. `FrontFirst` then hands the very same call to the studio's own writer, and the class carries on
at the old speed instead of stopping. A line Qwen cannot write for any other reason goes the same way,
and each such hand-over is one line in the studio's log.

`WithFrontVoice` is how the first voice reaches a conversation. `studio/classroom/classroom.py` hands every
conversation the studio client and cannot grow (the size guard refuses it), so the first voice rides
on that client, as NVIDIA's safety reader rides on the screener: to everything else it is the studio
client unchanged, and the conversation looks for `.front` on it for the lines a child waits for.
"""

from __future__ import annotations

import sys
import time
from collections.abc import Sequence
from contextlib import contextmanager
from contextvars import ContextVar

from studio.core.errors import ModelError
from studio.providers.base import ChatResult, VisionChatClient


# The most the first voice is asked to write at once. The creation drafts ask Step for 12000 because Step
# spends most of it thinking; Qwen writes with its thinking off, and its window is 16384 tokens with the
# picture and the prompt inside it, so the full 12000 would be refused before a word was written.
FRONT_MOST_TOKENS = 4000


# Set while a draft Qwen already got wrong is written again: the studio's writer then writes it directly.
_front_off: ContextVar[bool] = ContextVar("front_off", default=False)


@contextmanager
def without_front():
    """Write with the studio's writer alone for the calls inside (drafting.py, after a rejected Qwen draft)."""
    token = _front_off.set(True)
    try:
        yield
    finally:
        _front_off.reset(token)


class FrontFirst:
    """Ask the first voice; if it gives no line, ask the studio's writer the same thing.

    It also stands in front of the teacher review and the creation drafts
    (studio/core/deployments.py). To anything that reads the slot's settings it is the writer behind.
    """

    def __init__(self, front: VisionChatClient, behind: VisionChatClient) -> None:
        self.front = front
        self.behind = behind

    def __getattr__(self, name):
        return getattr(self.behind, name)

    def chat(self, prompt: str, images: Sequence[str] = (), *, system: str | None = None,
             max_tokens: int | None = None) -> ChatResult:
        if _front_off.get():
            return self.behind.chat(prompt, images, system=system, max_tokens=max_tokens)
        try:
            asked = min(max_tokens, FRONT_MOST_TOKENS) if max_tokens else None
            return self.front.chat(prompt, images, system=system, max_tokens=asked)
        except ModelError as error:
            # Said in the studio's log, by kind only (never the prompt): without it a first voice that
            # quietly stopped answering looks exactly like a slow class, and the reason for Qwen is speed.
            print(f"{time.strftime('%F %T')} first voice gave no line ({type(error).__name__}); "
                  "Step 3.7 Flash writes it", file=sys.stderr)
            return self.behind.chat(prompt, images, system=system, max_tokens=max_tokens)


class WithFrontVoice:
    """The studio client, carrying the first voice for the conversation to find."""

    def __init__(self, studio: VisionChatClient, front: VisionChatClient) -> None:
        self.studio = studio
        self.front = FrontFirst(front, studio)

    def chat(self, prompt: str, images: Sequence[str] = (), *, system: str | None = None,
             max_tokens: int | None = None) -> ChatResult:
        return self.studio.chat(prompt, images, system=system, max_tokens=max_tokens)

    def __getattr__(self, name):
        return getattr(self.studio, name)
