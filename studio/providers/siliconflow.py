"""Media through SiliconFlow, the route that takes Chinese payment.

Added because a Replicate credit purchase sat "in progress" and the
work stopped. That is a good reason to have a second route and a bad reason to
depend on one: a hackathon week cannot wait on an international card clearing.

NO PROFILE USES THIS PROVIDER any more, and this file is kept on purpose.
It carried the voice and the pictures for one day, and both moved the same day:
the voice to StepFun, which is also a Chinese platform and also takes that
payment but has an instruction field this API structurally cannot offer, and the
pictures to Replicate, for a model the box will actually load. Nothing here was
wrong — the sponsor simply turned out to sell what the product needed, which was
not knowable when this was written.

It stays wired and tested so a slot can be pointed back at it by editing a
profile, which is the whole reason the provider layer exists. If you need it
again: it served `FunAudioLLM/CosyVoice2-0.5B` and `Qwen/Qwen-Image-Edit`.

Two shapes, one client. The path is named in the slot options because it is a
vendor fact, and vendor facts live in the profile:

    endpoint: audio/speech          returns the audio FILE, as bytes
    endpoint: images/generations    returns JSON holding a URL

Contracts read from docs.siliconflow.com. Speech takes
`{model, input, voice, response_format, speed}` and answers with the recording
itself; images take `{model, prompt, image}` with the image as a base64 data
URI, and answer with `{"images": [{"url": ...}]}` valid for one hour.
"""

from __future__ import annotations

import os
import time
from typing import Any

import httpx

from studio.core.errors import ModelRefused, ModelUnavailable
from studio.providers.media import MediaResult, urls_in

# SiliconFlow runs TWO clouds and a key works on ONE of them. A .cn key gets
# {"code":30014,"message":"Token is invalid."} from the .com host, which reads
# as a bad key rather than as the wrong country — measured, and it
# cost a debugging round. The Chinese cloud is the default because this is a
# Chinese product; set base_url in the slot options for the international one.
API_URL = "https://api.siliconflow.cn/v1"
RETRYABLE = frozenset({408, 409, 425, 429, 500, 502, 503, 504})


class SiliconFlowClient:
    """One SiliconFlow model, answering either with a file or with a link."""

    def __init__(
        self,
        model: str,
        options: dict[str, Any] | None = None,
        api_key: str | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        key = api_key if api_key is not None else os.environ.get("SILICONFLOW_API_KEY", "")
        if not key:
            raise ModelRefused(
                "SILICONFLOW_API_KEY is not set; get one at "
                "https://cloud.siliconflow.cn/account/ak and put it in .env"
            )
        self.model = model
        self.options = dict(options or {})
        self.base_url = str(self.options.get("base_url") or API_URL).rstrip("/")
        self.endpoint = str(self.options.get("endpoint") or "").strip("/")
        if not self.endpoint:
            raise ModelRefused(
                f"the slot for {model!r} names no SiliconFlow endpoint; add "
                "`endpoint: audio/speech` or `endpoint: images/generations` to its options"
            )
        self._headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        self._client = client or httpx.Client(timeout=180.0)

    def make(self, inputs: dict[str, Any]) -> MediaResult:
        """Send one job. Answers inline — there is no queue to poll here."""
        started = time.monotonic()
        response = self._post({"model": self.model, **inputs})
        return self._read(response, time.monotonic() - started)

    def _post(self, body: dict[str, Any]) -> httpx.Response:
        url = f"{self.base_url}/{self.endpoint}"
        try:
            response = self._client.post(url, headers=self._headers, json=body)
        except httpx.RequestError as error:
            raise ModelUnavailable(f"siliconflow unreachable: {error}") from error
        if response.status_code in RETRYABLE:
            raise ModelUnavailable(f"siliconflow {response.status_code}: {response.text[:200]}")
        if response.status_code == 401:
            raise ModelRefused(
                f"SiliconFlow rejected SILICONFLOW_API_KEY at {self.base_url}. A key "
                "from cloud.siliconflow.cn works only on api.siliconflow.cn, and a "
                "siliconflow.com key only on api.siliconflow.com — check which cloud "
                "the key came from before assuming it is wrong."
            )
        if response.status_code == 402:
            raise ModelRefused(
                "SiliconFlow has no balance on this account, so the model never ran. "
                "Top up at https://cloud.siliconflow.cn/expensebill — the key itself "
                "is fine, or this would have been a 401."
            )
        if response.status_code >= 400:
            raise ModelRefused(f"siliconflow {response.status_code}: {response.text[:200]}")
        return response

    def _read(self, response: httpx.Response, latency: float) -> MediaResult:
        """Take the answer whichever way it came: a file, or a link to one.

        Speech comes back as the recording itself and image editing as JSON.
        Deciding on the content type rather than on the endpoint means a vendor
        that changes its mind about one model does not break the other.
        """
        payload: dict[str, Any] = {}
        content = b""
        if response.headers.get("content-type", "").startswith("application/json"):
            try:
                payload = response.json()
            except ValueError as error:
                raise ModelRefused(
                    f"siliconflow said JSON and sent {response.text[:120]!r}"
                ) from error
        else:
            content = response.content
            if not content:
                raise ModelRefused(f"{self.model} returned an empty file")
        return MediaResult(
            urls=urls_in(payload),
            payload=payload,
            content=content,
            price_usd=float(self.options.get("price_usd", 0.0)),
            latency_s=latency,
            provider="siliconflow",
            model=self.model,
        )
