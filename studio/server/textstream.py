"""Words a model is still writing, passed to whoever is showing them.

Operator: the teacher watched "model working, 6 seconds" over every
report and reply, then got the whole text at once. Now a text model's words go
to the page as they are written, and are replaced if a check sends them back.

Nothing between the harness and the model had to learn about the page. The
harness opens a listener around the one call whose words are wanted, and a
provider that finds one asks its model to stream and hands it the text so far
after every piece. A call with no listener is made exactly as before, which is
every judge (they run on their own threads, where the listener is not set), the
safety look, and every call outside a class.

The listener gets the WHOLE text of the current call each time, never a piece:
a second call (a retry, or the first voice handing over to Step) starts again
from nothing, and whoever is showing it replaces what it showed.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar

Listener = Callable[[str], None]

_listener: ContextVar[Listener | None] = ContextVar("textstream_listener", default=None)


def current() -> Listener | None:
    """The listener for this thread's call, or None when nobody is watching."""
    return _listener.get()


@contextmanager
def listening(listener: Listener) -> Iterator[None]:
    token = _listener.set(listener)
    try:
        yield
    finally:
        _listener.reset(token)


def unfinished_cut(text: str, found) -> str:
    """The words so far without an ending that could be the start of something written on the drawing.

    Code review: the redaction removes a name only once it is whole, so while the model
    was still writing "Alice Smith" the page was shown "Alice S", and the event stream kept it for
    replay. The ending is held back until it is either the whole name, which the redaction then
    removes, or no longer the start of one. Cut with the redaction's own rule: pieces as written,
    stripped, longer than one character. Cut AFTER the redaction (code review, same day): cutting first
    broke a whole match when two found strings overlapped ("Alice Smith" and "Smithson": "Hello Alice
    Smith" was cut to "Hello Alice", which the redaction then left standing).
    """
    for written in found:
        piece = written.strip()
        if len(piece) > 1:
            for size in range(min(len(piece) - 1, len(text)), 0, -1):
                if text.endswith(piece[:size]):
                    text = text[: len(text) - size]
                    break
    return text


@contextmanager
def shown_as(change: Callable[[str], str]) -> Iterator[None]:
    """Pass the words through `change` before they are shown; nothing at all when nobody listens.

    The redaction of anything written on the drawing is applied here, so a name the
    safety look found is taken out of the words as they arrive, not only at the end.
    """
    outer = _listener.get()
    if outer is None:
        yield
        return
    token = _listener.set(lambda text: outer(change(text)))
    try:
        yield
    finally:
        _listener.reset(token)
