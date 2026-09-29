"""Bounded image-to-video calls through a loopback-only GPU worker."""
from __future__ import annotations

import ipaddress
import time
from urllib.parse import urlsplit

from studio.providers.gpu_job import stream_job
import httpx

from studio.core.errors import ModelRefused, ModelUnavailable
from studio.making.mesh import MAX_BYTES
from studio.providers.media import MediaResult

MAX_VIDEO_BYTES = 12 * 1024 * 1024


class LocalVideoClient:
    def __init__(self, model, options=None, client=None):
        self.model, self.options = model, dict(options or {})
        self.base_url = str(self.options.get("base_url", "http://127.0.0.1:7260")).rstrip("/")
        url = urlsplit(self.base_url)
        try:
            local = ipaddress.ip_address(url.hostname or "").is_loopback
        except ValueError:
            local = url.hostname == "localhost"
        if not local or url.scheme != "http" or url.username or url.password or url.path or url.query or url.fragment:
            raise ValueError("video worker must use a loopback HTTP endpoint")
        self._client = client or httpx.Client(trust_env=False, follow_redirects=False)

    def make(self, inputs):
        image, instruction = inputs.get("image"), inputs.get("instruction")
        if not isinstance(image, str) or not image.startswith("data:image/") or len(image) > MAX_BYTES:
            raise ModelRefused("video worker requires a bounded embedded image")
        if not isinstance(instruction, str) or not 1 <= len(instruction) <= 4000:
            raise ModelRefused("video worker requires a bounded motion instruction")
        body = {"model": self.model, "image": image, "instruction": instruction}
        seed = inputs.get("seed")
        if seed is not None:
            # Sent only for a new try after a held-back clip; the first clip keeps the worker's own 42.
            if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed < 2 ** 31:
                raise ModelRefused("video worker requires a whole-number seed")
            body["seed"] = seed
        started = time.monotonic()
        try:
            with stream_job(
                self._client, self.base_url, "/v1/video",
                body=body,
                # Up to the video service's own job deadline (media_server.py, 1500 s): a 5 s clip on
                # the Spark takes ~18 min and can queue behind a 3D job. It was 900 at first, then 1200.
                timeout=min(1500, max(1, float(self.options.get("timeout_s", 600)))),
            ) as response:
                if response.status_code in (408, 409, 429, 500, 502, 503, 504):
                    raise ModelUnavailable("local video worker is busy or unavailable")
                if response.status_code != 200 or response.headers.get("content-type", "").split(";")[0] != "video/mp4":
                    raise ModelRefused("local video worker rejected this request")
                content = bytearray()
                for chunk in response.iter_bytes(65536):
                    if len(content) + len(chunk) > MAX_VIDEO_BYTES:
                        raise ModelRefused("video response exceeds the byte budget")
                    content.extend(chunk)
        except httpx.RequestError as error:
            raise ModelUnavailable("local video worker did not answer") from error
        if not content:
            raise ModelRefused("local video worker returned an empty clip")
        return MediaResult(urls=[], content=bytes(content), latency_s=time.monotonic()-started,
                           provider="localvideo", model=self.model)
