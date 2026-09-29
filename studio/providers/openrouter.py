from __future__ import annotations

import os
import time
from collections.abc import Sequence
from typing import Any

import httpx

from studio.core.errors import EmptyCompletion, ModelRefused, ModelUnavailable
from studio.providers.base import ChatResult

API_URL = "https://openrouter.ai/api/v1/chat/completions"
RETRYABLE = frozenset({408, 409, 425, 429, 500, 502, 503, 504})
# OpenRouter shows this beside the traffic it attributes, so it names the project's public repository.
REFERER = "https://github.com/FelixZhang1020/beyond-canvas"


class OpenRouterClient:
    """Hosted Step models through OpenRouter's OpenAI-compatible endpoint."""

    def __init__(
        self,
        model: str,
        options: dict[str, Any] | None = None,
        api_key: str | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        key = api_key if api_key is not None else os.environ.get("OPENROUTER_API_KEY", "")
        if not key:
            raise ModelRefused("OPENROUTER_API_KEY is not set; copy .env.example to .env")
        self.model = model
        self.options = dict(options or {})
        self._headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "HTTP-Referer": REFERER,
            "X-Title": "spark-art-studio",
        }
        self._client = client or httpx.Client(timeout=180.0)

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
        payload = self._post(body)
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
        if effort := self.options.get("reasoning_effort"):
            body["reasoning"] = {"effort": effort}
        if order := self.options.get("provider_order"):
            body["provider"] = {"order": list(order), "allow_fallbacks": False}
        return body

    def _post(self, body: dict[str, Any]) -> dict[str, Any]:
        try:
            response = self._client.post(API_URL, headers=self._headers, json=body)
        except httpx.RequestError as error:
            raise ModelUnavailable(f"openrouter unreachable: {error}") from error
        if response.status_code in RETRYABLE:
            raise ModelUnavailable(f"openrouter {response.status_code}: {response.text[:200]}")
        if response.status_code >= 400:
            raise ModelRefused(f"openrouter {response.status_code}: {response.text[:200]}")
        return response.json()

    def _result(self, payload: dict[str, Any], latency: float) -> ChatResult:
        choices = payload.get("choices") or [{}]
        text = (choices[0].get("message") or {}).get("content") or ""
        usage = payload.get("usage") or {}
        details = usage.get("completion_tokens_details") or {}
        if not text.strip():
            raise EmptyCompletion(
                f"{self.model} returned no text after "
                f"{details.get('reasoning_tokens', 0)} reasoning tokens; "
                "raise max_tokens, Step 3.7 Flash needs at least 1000"
            )
        return ChatResult(
            text=text.strip(),
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
            reasoning_tokens=details.get("reasoning_tokens", 0),
            cost_usd=float(usage.get("cost", 0.0)),
            latency_s=latency,
            provider=payload.get("provider", "unknown"),
            model=payload.get("model", self.model),
        )
