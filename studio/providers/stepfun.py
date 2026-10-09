"""StepFun's own platform, the sponsor's models bought from the sponsor.

Step 3.7 Flash used to be reached through OpenRouter, which
is a reseller of the same weights: same model, an extra hop, and a bill from
somebody else. This is the direct route, and it also opens the audio line, which
OpenRouter does not carry at all.

Two clients, because StepFun sells two shapes and this product buys both:

    StepFunClient       /v1/chat/completions   sentences, the director slot
    StepFunMediaClient  /v1/audio/speech       a recording, the voice slots

THREE THINGS MEASURED AGAINST THE LIVE API, none of them guesses:

1. `reasoning_effort` is a TOP-LEVEL field here. OpenRouter nests it as
   `{"reasoning": {"effort": ...}}`; sending that shape to StepFun silently
   does nothing, which is the worst of the three ways this could fail.

2. The response carries NO cost. OpenRouter reports `usage.cost` and this
   platform reports nothing, because it bills in CNY against an account
   balance. So `cost_usd` below is computed from list prices written in the
   profile — the same honest fiction `media.py` documents for its own price
   field, and named the same way. A slot may instead say
   `included_in_plan`, which stops that arithmetic: under a subscription the
   call is paid for before it is made, and a computed dollar figure would be a
   bill nobody receives.

3. The hidden-reasoning trap is identical to OpenRouter's, and worse than it
   looks: `completion_tokens_details.reasoning_tokens` comes back as **0**
   while the thinking is billed as ordinary completion tokens. Measured: one
   word of answer for 355 completion tokens, and at `max_tokens: 200` an empty
   string with `finish_reason: length`. That field cannot warn anyone, so the
   empty answer is turned into an error that names the budget instead.
"""

from __future__ import annotations

import os
import time
from collections.abc import Sequence
from typing import Any

import httpx

from studio.core.errors import EmptyCompletion, ModelRefused, ModelUnavailable
from studio.server import textstream
from studio.providers import streaming
from studio.providers.base import ChatResult
from studio.providers.media import MediaResult, urls_in

API_URL = "https://api.stepfun.com/v1"

# The subscription's own address, read off the plan page. It is not
# the default: only the `stepfun` profile asks for it, through provider_options,
# and that file carries the reasoning. Named here so the one place that knows
# StepFun's addresses knows both of them.
PLAN_URL = "https://api.stepfun.com/step_plan/v1"

RETRYABLE = frozenset({408, 409, 425, 429, 500, 502, 503, 504})

# api.stepfun.ai answers, and rejects a key minted on api.stepfun.com with
# "Incorrect API key provided" — which reads as a bad key rather than as the
# wrong region. Measured, the same trap SiliconFlow sets.
MISSING_KEY = (
    "STEPFUN_API_KEY is not set; get one at https://platform.stepfun.com and put "
    "it in .env. A key from platform.stepfun.com works on api.stepfun.com only."
)


def _require_key(api_key: str | None) -> str:
    key = api_key if api_key is not None else os.environ.get("STEPFUN_API_KEY", "")
    if not key:
        raise ModelRefused(MISSING_KEY)
    return key


def _raise_for_status(response: httpx.Response) -> None:
    """One mapping of HTTP to this project's two error types, for both clients."""
    if response.status_code in RETRYABLE:
        raise ModelUnavailable(f"stepfun {response.status_code}: {response.text[:200]}")
    if response.status_code == 401:
        raise ModelRefused(f"StepFun rejected STEPFUN_API_KEY. {MISSING_KEY}")
    if response.status_code == 402:
        raise ModelRefused(
            "StepFun has no balance on this account, so the model never ran. Top up "
            "at https://platform.stepfun.com — the key is fine, or this would be a 401."
        )
    if response.status_code >= 400:
        raise ModelRefused(f"stepfun {response.status_code}: {response.text[:200]}")


class StepFunClient:
    """Step models bought directly, through an OpenAI-compatible endpoint."""

    def __init__(
        self,
        model: str,
        options: dict[str, Any] | None = None,
        api_key: str | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        key = _require_key(api_key)
        self.model = model
        self.options = dict(options or {})
        self.base_url = str(self.options.get("base_url") or API_URL).rstrip("/")
        self._headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }
        # Three minutes unless the slot says otherwise: the 3D figure's writing measured up to 151 s.
        self._client = client or httpx.Client(timeout=float(self.options.get("timeout_s", 180)))

    def chat(
        self,
        prompt: str,
        images: Sequence[str] = (),
        *,
        system: str | None = None,
        max_tokens: int | None = None,
    ) -> ChatResult:
        body = self._body(prompt, images, system, max_tokens)
        started = time.monotonic()
        listener = textstream.current()
        payload = self._post(body) if listener is None else self._stream(body, listener)
        return self._result(payload, time.monotonic() - started)

    def _body(
        self,
        prompt: str,
        images: Sequence[str],
        system: str | None,
        max_tokens: int | None,
    ) -> dict[str, Any]:
        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        content += [{"type": "image_url", "image_url": {"url": uri}} for uri in images]
        messages: list[dict[str, Any]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": content})
        body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens or self.options.get("max_tokens", 1200),
        }
        # Top level, NOT nested under "reasoning" the way OpenRouter takes it.
        if effort := self.options.get("reasoning_effort"):
            body["reasoning_effort"] = effort
        return body

    def _post(self, body: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}/chat/completions"
        try:
            response = self._client.post(url, headers=self._headers, json=body)
        except httpx.RequestError as error:
            raise ModelUnavailable(f"stepfun unreachable: {error}") from error
        _raise_for_status(response)
        return response.json()

    def _stream(self, body: dict[str, Any], listener: textstream.Listener) -> dict[str, Any]:
        """The same call, streamed, so the page can show the words as they are written (studio/server/textstream.py)."""
        url = f"{self.base_url}/chat/completions"
        body = {**body, "stream": True, "stream_options": {"include_usage": True}}
        try:
            with self._client.stream("POST", url, headers=self._headers, json=body) as response:
                if response.status_code >= 400:
                    response.read()
                _raise_for_status(response)
                return streaming.read(response.iter_lines(), listener, self.model)
        except httpx.RequestError as error:
            raise ModelUnavailable(f"stepfun unreachable: {error}") from error

    def _cost(self, usage: dict[str, Any]) -> float:
        """List price from the profile, never a figure StepFun reported.

        StepFun publishes CNY per million tokens and returns no cost at all, so
        the profile carries the USD conversion and states which CNY figure and
        which rate produced it. Absent prices give 0.0, which means "the profile
        did not say" rather than "free".
        """
        if self.options.get("included_in_plan"):
            # A subscription is paid before the call, so per-token arithmetic
            # here would invent a bill nobody receives. 0.0 is the true marginal
            # cost; what it must not be read as is "free", and the ledger view
            # says which of the two a zero means.
            return 0.0
        per_m_in = float(self.options.get("price_usd_per_m_in", 0.0))
        per_m_out = float(self.options.get("price_usd_per_m_out", 0.0))
        return (
            usage.get("prompt_tokens", 0) * per_m_in
            + usage.get("completion_tokens", 0) * per_m_out
        ) / 1_000_000

    def _result(self, payload: dict[str, Any], latency: float) -> ChatResult:
        choices = payload.get("choices") or [{}]
        message = choices[0].get("message") or {}
        text = message.get("content") or ""
        usage = payload.get("usage") or {}
        details = usage.get("completion_tokens_details") or {}
        if not text.strip():
            raise EmptyCompletion(
                f"{self.model} returned no text after spending "
                f"{usage.get('completion_tokens', 0)} completion tokens "
                f"(finish_reason {choices[0].get('finish_reason')!r}); raise max_tokens. "
                "Step 3.7 Flash bills hidden thinking as completion and reports "
                "reasoning_tokens as 0, so that field will not warn you."
            )
        if choices[0].get("finish_reason") == "length":
            raise EmptyCompletion(f"{self.model} returned a truncated completion; raise max_tokens")
        return ChatResult(
            text=text.strip(),
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
            reasoning_tokens=details.get("reasoning_tokens", 0),
            cost_usd=self._cost(usage),
            latency_s=latency,
            provider="stepfun",
            model=payload.get("model", self.model),
        )


class StepFunMediaClient:
    """StepFun models that answer with a file rather than a sentence."""

    def __init__(
        self,
        model: str,
        options: dict[str, Any] | None = None,
        api_key: str | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        key = _require_key(api_key)
        self.model = model
        self.options = dict(options or {})
        self.base_url = str(self.options.get("base_url") or API_URL).rstrip("/")
        self.endpoint = str(self.options.get("endpoint") or "").strip("/")
        if not self.endpoint:
            raise ModelRefused(
                f"the slot for {model!r} names no StepFun endpoint; add "
                "`endpoint: audio/speech` to its options"
            )
        self._headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        self._client = client or httpx.Client(timeout=float(self.options.get("timeout_s", 180)))

    def make(self, inputs: dict[str, Any]) -> MediaResult:
        """Send one job. Answers inline — there is no queue to poll here."""
        if self.endpoint.startswith("images/") or "/images/" in self.endpoint:
            raise ModelUnavailable("StepFun image models are disabled")
        started = time.monotonic()
        url = f"{self.base_url}/{self.endpoint}"
        try:
            response = self._client.post(
                url, headers=self._headers, json={"model": self.model, **inputs}
            )
        except httpx.RequestError as error:
            raise ModelUnavailable(f"stepfun unreachable: {error}") from error
        _raise_for_status(response)
        return self._read(response, time.monotonic() - started)

    def _read(self, response: httpx.Response, latency: float) -> MediaResult:
        """Speech comes back as the recording itself; anything else as JSON."""
        payload: dict[str, Any] = {}
        content = b""
        if response.headers.get("content-type", "").startswith("application/json"):
            try:
                payload = response.json()
            except ValueError as error:
                raise ModelRefused(
                    f"stepfun said JSON and sent {response.text[:120]!r}"
                ) from error
        else:
            content = response.content
            if not content:
                raise ModelRefused(f"{self.model} returned an empty file")
        return MediaResult(
            urls=urls_in(payload),
            payload=payload,
            content=content,
            # Zero under a subscription, for the reason StepFunClient._cost gives:
            # the profile's price_usd is a list price, and a plan has already paid.
            price_usd=0.0 if self.options.get("included_in_plan")
            else float(self.options.get("price_usd", 0.0)),
            latency_s=latency,
            provider="stepfun",
            model=self.model,
        )
