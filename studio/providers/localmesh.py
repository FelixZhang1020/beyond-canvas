"""A bounded local-only media client; model weights live in a separate worker."""
from __future__ import annotations

import ipaddress
import time
from urllib.parse import urlsplit

from studio.providers.gpu_job import stream_job
import httpx

from studio.core.errors import ModelRefused, ModelUnavailable
from studio.making.mesh import MAX_BYTES
from studio.providers.media import MediaResult


class LocalMeshClient:
    def __init__(self, model, options=None, client=None):
        self.model, self.options = model, dict(options or {})
        self.base_url = str(self.options.get("base_url", "http://127.0.0.1:7240")).rstrip("/")
        url = urlsplit(self.base_url)
        try:
            local = ipaddress.ip_address(url.hostname or "").is_loopback
        except ValueError:
            local = url.hostname == "localhost"
        if not local or url.scheme != "http" or url.username or url.password or url.path or url.query or url.fragment:
            raise ValueError("mesh worker must use a loopback HTTP endpoint")
        self._client = client or httpx.Client(trust_env=False, follow_redirects=False)

    def make(self, inputs):
        image = inputs.get("image")
        if not isinstance(image, str) or not image.startswith("data:image/") or len(image) > MAX_BYTES:
            raise ModelRefused("mesh worker requires a bounded embedded image")
        body = {"model": self.model, "image": image}
        if inputs.get("subject") is not None:
            if inputs["subject"] not in ("head", "fruit"):
                raise ModelRefused("unsupported mesh subject")
            body["subject"] = inputs["subject"]
        start = time.monotonic()
        try:
            with stream_job(self._client, self.base_url, "/v1/mesh", body=body,
                                     timeout=min(900, max(1, float(self.options.get("timeout_s", 180))))) as response:
                if response.status_code in (408, 409, 429, 500, 502, 503, 504):
                    raise ModelUnavailable("local mesh worker is busy or unavailable")
                if response.status_code != 200:
                    raise ModelRefused("local mesh worker rejected this image")
                content = bytearray()
                for chunk in response.iter_bytes(65536):
                    if len(content) + len(chunk) > MAX_BYTES:
                        raise ModelRefused("mesh response exceeds the byte budget")
                    content.extend(chunk)
        except httpx.RequestError as error:
            raise ModelUnavailable("local mesh worker did not answer") from error
        return MediaResult(urls=[], content=bytes(content), latency_s=time.monotonic()-start,
                           provider="localmesh", model=self.model)
