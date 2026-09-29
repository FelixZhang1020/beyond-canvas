"""Generative media through fal's queue: pictures, video and Splat's voice.

These are the slots no Step model can serve. `image.edit` turns a child's
drawing into a storybook page, `video.scene` gives a painting five seconds of
motion, `tts.studio` reads the story aloud. On the Spark they are local
processes; in Phase 0 they are rented, which is what this file is for.

fal is a queue, not a request. Submitting returns a handle immediately and the
work happens somewhere else, so every call here is submit, poll, fetch. That
matters for a product where a child is waiting: a video takes tens of seconds
and the page has to be told something in the meantime, which is why the wait is
bounded and the timeout message says the job is still alive rather than lost.

Contract verified against fal.ai/docs/model-apis/model-endpoints/queue:
submit to `queue.fal.run/{model}`, authenticate with `Key`, poll
`status_url` until `COMPLETED`, then read `response_url`.
"""

from __future__ import annotations

import os
import time
from typing import Any

import httpx

from studio.core.errors import ModelRefused, ModelUnavailable
from studio.providers.media import MediaResult, urls_in

QUEUE_URL = "https://queue.fal.run"
RETRYABLE = frozenset({408, 409, 425, 429, 500, 502, 503, 504})

# fal's three queue states. Only the last one has an answer behind it.
QUEUED, RUNNING, DONE = "IN_QUEUE", "IN_PROGRESS", "COMPLETED"

POLL_SECONDS = 1.5
TIMEOUT_SECONDS = 300.0


class FalClient:
    """One fal model, called through the queue and waited for.

    `price_usd` in the slot options is fal's published list price for one call.
    It is carried through to the result so a caller can add up what a storybook
    cost without asking fal, and it is a declared number rather than a measured
    one — see `studio/providers/media.py`.
    """

    # The clock, as an attribute rather than a constructor argument: a poll loop
    # has to be testable without a test spending real seconds, and a sixth
    # parameter would put this constructor over the five the craft limits allow.
    _sleep = staticmethod(time.sleep)

    def __init__(
        self,
        model: str,
        options: dict[str, Any] | None = None,
        api_key: str | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        key = api_key if api_key is not None else os.environ.get("FAL_KEY", "")
        if not key:
            raise ModelRefused(
                "FAL_KEY is not set; get one at https://fal.ai/dashboard/keys "
                "and put it in .env"
            )
        self.model = model
        self.options = dict(options or {})
        self.timeout_s = float(self.options.get("timeout_s", TIMEOUT_SECONDS))
        self._headers = {
            "Authorization": f"Key {key}",
            "Content-Type": "application/json",
        }
        self._client = client or httpx.Client(timeout=120.0)

    def make(self, inputs: dict[str, Any]) -> MediaResult:
        """Submit one job, wait for it, and return the files it produced."""
        started = time.monotonic()
        handle = self._call("POST", f"{QUEUE_URL}/{self.model}", inputs)
        payload = self._settle(handle, started)
        return MediaResult(
            urls=urls_in(payload),
            payload=payload,
            price_usd=float(self.options.get("price_usd", 0.0)),
            latency_s=time.monotonic() - started,
            provider="fal",
            model=self.model,
        )

    def _settle(self, handle: dict[str, Any], started: float) -> dict[str, Any]:
        """Poll until the job is done, then read its answer.

        A timeout here does not mean the work was lost. fal keeps the job and
        the result stays fetchable at its own URL, so the message says which
        one rather than only reporting that time ran out.
        """
        status_url = handle.get("status_url") or ""
        response_url = handle.get("response_url") or ""
        if not status_url or not response_url:
            raise ModelRefused(
                f"fal accepted the job for {self.model} but returned no queue handle: "
                f"{sorted(handle)}"
            )
        while True:
            state = self._call("GET", status_url)
            if state.get("status") == DONE:
                return self._call("GET", response_url)
            waited = time.monotonic() - started
            if waited > self.timeout_s:
                raise ModelUnavailable(
                    f"{self.model} was still {state.get('status', 'unknown')} after "
                    f"{waited:.0f}s. The job is not lost; fal holds the result at "
                    f"{response_url}. Raise timeout_s in the slot options to wait longer."
                )
            self._sleep(POLL_SECONDS)

    def _call(self, method: str, url: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        """One HTTP call, with fal's failures mapped onto the studio's vocabulary."""
        try:
            response = self._client.request(method, url, headers=self._headers, json=body)
        except httpx.RequestError as error:
            raise ModelUnavailable(f"fal unreachable: {error}") from error
        if response.status_code in RETRYABLE:
            raise ModelUnavailable(f"fal {response.status_code}: {response.text[:200]}")
        if response.status_code == 401:
            raise ModelRefused(
                "fal rejected FAL_KEY. Check the value in .env against "
                "https://fal.ai/dashboard/keys"
            )
        if response.status_code >= 400:
            raise ModelRefused(f"fal {response.status_code}: {response.text[:200]}")
        try:
            return response.json()
        except ValueError as error:
            raise ModelRefused(f"fal returned no JSON: {response.text[:200]}") from error
