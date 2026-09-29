from __future__ import annotations

import time
import ipaddress
from collections.abc import Sequence
from typing import Any
from urllib.parse import urlsplit

import httpx

from studio.server import textstream
from studio.core.errors import EmptyCompletion, ModelRefused, ModelUnavailable
from studio.providers import streaming
from studio.providers.base import ChatResult

DEFAULT_BASE_URL = "http://127.0.0.1:7100"
RETRYABLE = frozenset({408, 429, 500, 502, 503, 504})


def _raise_for_status(response: httpx.Response) -> None:
    if response.status_code in RETRYABLE:
        raise ModelUnavailable(f"llama-server {response.status_code}: {response.text[:200]}")
    if response.status_code >= 400:
        raise ModelRefused(f"llama-server {response.status_code}: {response.text[:200]}")


class LlamaCppClient:
    """A local llama-server over its OpenAI-compatible route.

    Serves the studio slot once a small Step model runs on the machine. Cost is
    always zero, which is the whole point of the local profile.
    """

    def __init__(
        self,
        model: str,
        options: dict[str, Any] | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self.model = model
        self.options = dict(options or {})
        self.base_url = str(self.options.get("base_url", DEFAULT_BASE_URL)).rstrip("/")
        host = urlsplit(self.base_url).hostname or ""
        try:
            loopback = ipaddress.ip_address(host).is_loopback
        except ValueError:
            loopback = host.lower() == "localhost"
        # HTTPX inherits proxy variables. A desktop proxy returned 502 for a
        # healthy local model; keep loopback inference on the same machine.
        timeout = float(self.options.get("timeout_s", 300.0))
        self._client = client or httpx.Client(timeout=timeout, trust_env=not loopback)

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
        # llama.cpp supports continuing a final assistant message. Geometry's
        # dedicated slot uses an empty completed think block; other callers keep
        # the model's normal template. Do not change the running server globally.
        prefill = self.options.get("assistant_prefill")
        if prefill:
            messages.append({"role": "assistant", "content": str(prefill)})
        asked = max_tokens or self.options.get("max_tokens", 1200)
        # A slot may name the most it can be asked for: Qwen's window holds the prompt, the picture and
        # the answer in 16384 tokens, and callers written for Step 3.7 Flash ask for 12000.
        if self.options.get("most_tokens"):
            asked = min(asked, int(self.options["most_tokens"]))
        body = {
            "model": self.model,
            "messages": messages,
            "max_tokens": asked,
            "temperature": self.options.get("temperature", 0.7),
        }
        # vLLM reads the chat template's switches here; Qwen3.6's first voice turns its thinking off.
        if self.options.get("chat_template_kwargs"):
            body["chat_template_kwargs"] = dict(self.options["chat_template_kwargs"])
        return body

    def _post(self, body: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}/v1/chat/completions"
        try:
            response = self._client.post(url, json=body)
        except httpx.RequestError as error:
            raise ModelUnavailable(
                f"llama-server at {self.base_url} did not answer: {error}"
            ) from error
        _raise_for_status(response)
        return response.json()

    def _stream(self, body: dict[str, Any], listener: textstream.Listener) -> dict[str, Any]:
        """The same call, streamed, so the page can show the words as they are written (studio/server/textstream.py).

        An assistant prefill is written back by the server as the start of the answer and cut off in
        _result, so the words shown skip it too.
        """
        url = f"{self.base_url}/v1/chat/completions"
        body = {**body, "stream": True, "stream_options": {"include_usage": True}}
        prefill = str(self.options.get("assistant_prefill") or "")
        def shown(text: str) -> None:
            listener(text[len(prefill):] if prefill and text.startswith(prefill) else text)
        try:
            with self._client.stream("POST", url, json=body) as response:
                if response.status_code >= 400:
                    response.read()
                _raise_for_status(response)
                return streaming.read(response.iter_lines(), shown, self.model)
        except httpx.RequestError as error:
            raise ModelUnavailable(
                f"llama-server at {self.base_url} did not answer: {error}"
            ) from error

    def _result(self, payload: dict[str, Any], latency: float) -> ChatResult:
        choices = payload.get("choices") or [{}]
        message = choices[0].get("message") or {}
        text = message.get("content") or ""
        prefill = self.options.get("assistant_prefill")
        if prefill and text.startswith(str(prefill)):
            text = text[len(str(prefill)):]
        if not text.strip():
            # A Step model spends its budget on hidden thinking before it writes
            # anything, and llama-server returns that thinking in its own field.
            # Saying so turns a blank answer into an instruction: ask for more
            # room. Measured on Step3-VL-10B, which used 200 tokens
            # of reasoning and wrote nothing, then answered well at 3000.
            thinking = len(message.get("reasoning_content") or "")
            if thinking:
                raise EmptyCompletion(
                    f"{self.model} spent its whole budget on {thinking} characters of "
                    "hidden reasoning and wrote no answer; raise max_tokens"
                )
            raise EmptyCompletion(f"{self.model} on llama-server returned no text")
        usage = payload.get("usage") or {}
        return ChatResult(
            text=text.strip(),
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
            reasoning_tokens=0,
            cost_usd=0.0,
            latency_s=latency,
            provider="llamacpp",
            model=payload.get("model", self.model),
        )
