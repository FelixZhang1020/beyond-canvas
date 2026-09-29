"""A dedicated safety model that answers about one picture: neither a chat model nor a media model.

NVIDIA's Nemotron 3.5 Content Safety takes a picture and a question and answers in three fixed
lines. It is served by the safety skill's own small server (`skills/studio-safety/scripts/
nemotron_server.py`) on the machine that holds the weights, and this is the client for it. What the
answer means, and what the studio does about it, is the skill's business and not this file's.

`WithSecondLook` is how the reader reaches a conversation. `studio/classroom/classroom.py` hands every
conversation one screener and cannot be written until it is split (the size guard refuses it), so
the reader rides on that screener: to anything that chats it is the four-verdict client unchanged,
and the conversation looks for `.second` on it.
"""

from __future__ import annotations

import ipaddress
import time
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import urlsplit

import httpx

from studio.core.errors import ModelRefused, ModelUnavailable
from studio.providers.base import ChatResult, VisionChatClient

DEFAULT_BASE_URL = "http://127.0.0.1:7140"


class SafetyReader(Protocol):
    """What the safety skill asks of a second reader. The picture is a data URI, never a path."""

    def look(self, image_data_uri: str, question: str) -> str: ...


class SafetyReaderClient:
    def __init__(self, model: str, options: dict[str, Any] | None = None, client: httpx.Client | None = None) -> None:
        self.model = model
        self.options = dict(options or {})
        self.base_url = str(self.options.get("base_url", DEFAULT_BASE_URL)).rstrip("/")
        host = urlsplit(self.base_url).hostname or ""
        try:
            loopback = ipaddress.ip_address(host).is_loopback
        except ValueError:
            loopback = host.lower() == "localhost"
        # As in llamacpp.py: a desktop proxy must not stand between the studio and its own machine.
        self._client = client or httpx.Client(timeout=float(self.options.get("timeout_s", 60)), trust_env=not loopback)
        self.answered = False     # seen answering in this process: then an absence is a pause, worth waiting out

    def look(self, image_data_uri: str, question: str) -> str:
        try:
            response = self._client.post(f"{self.base_url}/look", json={"image": image_data_uri, "question": question})
        except httpx.RequestError as error:
            raise ModelUnavailable(f"the safety reader at {self.base_url} did not answer: {error}") from error
        if response.status_code >= 500:
            raise ModelUnavailable(f"the safety reader answered {response.status_code}")
        if response.status_code >= 400:
            raise ModelRefused(f"the safety reader refused the request: {response.status_code}")
        # A 200 that is not our server's answer (a stale process, a proxy's page) is the same to the
        # studio as no answer: unavailable, which stops nothing, and never an error in the class.
        try:
            answer = response.json()["answer"]
        except (ValueError, TypeError, KeyError) as error:
            raise ModelUnavailable(f"whatever answers at {self.base_url} is not the safety reader") from error
        if not isinstance(answer, str):
            raise ModelUnavailable(f"whatever answers at {self.base_url} is not the safety reader")
        self.answered = True
        return answer

    def wait_ready(self, seconds: float, pause: float = 2.0) -> bool:
        """Whether the reader answers, waiting up to `seconds` for one that has answered before. On the
        Spark it steps aside while a clip needs its memory and loads again after (~12 s); a reader never
        seen in this process (a Mac with no reader) is asked once and not waited for."""
        deadline = time.monotonic() + (seconds if self.answered else 0)
        while True:
            try:
                if self._client.get(f"{self.base_url}/health", timeout=2.0).status_code == 200:
                    return True
            except httpx.RequestError:
                pass
            if time.monotonic() >= deadline:
                return False
            time.sleep(pause)


@dataclass(frozen=True)
class WithSecondLook:
    """The four-verdict client, carrying the second reader to the conversation that will ask it."""

    first: VisionChatClient
    second: SafetyReader

    def chat(self, prompt: str, images: Sequence[str] = (), *, system: str | None = None,
             max_tokens: int | None = None) -> ChatResult:
        return self.first.chat(prompt, images, system=system, max_tokens=max_tokens)

    def __getattr__(self, name: str):
        """In every other way it is the four-verdict client (its model, its options): a class that
        switched the second look on found a runtime check reading `.model` off the screener. Python's
        own hooks (a copy's, a pickle's) are never passed on, or a copy would lose the second reader."""
        if name in ("first", "second") or name.startswith("__"):
            raise AttributeError(name)
        return getattr(self.first, name)
