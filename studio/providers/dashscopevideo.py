"""A short clip from Wan 3.0 on Alibaba's DashScope: the teacher's quick choice beside the Spark's own.

Operator, after timing both on the same drawing: the teacher chooses each time between a
5-second clip made on the Spark (Wan 2.2, about 18 minutes) and a clip made online (Wan 3.0, about 2
minutes), and is shown both times. The online clip was 10 s at first and 5 s soon after
(`duration_s` in the profile). The online choice sends the drawing to Alibaba, and the page
says so. Wan 3.0 has no download, so it is the one slot the Spark could not run itself; the operator
chose it knowing that (docs/measured/wan3-online.md).

DashScope answers a job id, is asked until the clip is ready, and hands back a link. The clip is then
made small and plain here: it arrives at about 1 MB a second with a sound track Wan 3.0 wrote and ran
10.03 s, and the studio's clip checks take one picture track of at most 10 s. Re-encoded without sound,
cut at 10 s, it is about 0.7 MB, which matters on the class's slow link.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from studio.core.errors import ModelCancelled, ModelRefused, ModelUnavailable
from studio.providers.gpu_job import cancelled_request
from studio.making.mesh import MAX_BYTES
from studio.providers.media import MediaResult

SUBMIT = "/api/v1/services/aigc/video-generation/video-synthesis"
MAX_DOWNLOAD_BYTES = 40 * 1024 * 1024   # the 720p 10 s clip was 17 MB before re-encoding
MAX_VIDEO_BYTES = 12 * 1024 * 1024       # what the studio keeps, as for the Spark's clip
POLL_S = 5


class DashScopeVideoClient:
    def __init__(self, model, options=None, client=None, sleep=time.sleep):
        self.model, self.options = model, dict(options or {})
        self.base_url = str(self.options.get("base_url", "https://dashscope.aliyuncs.com")).rstrip("/")
        if urlsplit(self.base_url).scheme != "https":
            raise ValueError("DashScope must be reached over HTTPS")
        self._client = client or httpx.Client(timeout=60, follow_redirects=False)
        self._sleep = sleep

    def make(self, inputs):
        image, instruction = inputs.get("image"), inputs.get("instruction")
        if not isinstance(image, str) or not image.startswith("data:image/") or len(image) > MAX_BYTES:
            raise ModelRefused("online video requires a bounded embedded image")
        if not isinstance(instruction, str) or not 1 <= len(instruction) <= 4000:
            raise ModelRefused("online video requires a bounded motion instruction")
        key = os.environ.get("DASHSCOPE_API_KEY", "").strip()
        if not key:
            raise ModelUnavailable("no DashScope key on this machine")
        parameters = {"resolution": self.options.get("resolution", "480P"), "ratio": "adaptive",
                      "duration": int(self.options.get("duration_s", 10)), "prompt_extend": False}
        seed = inputs.get("seed")
        if seed is not None:
            if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed < 2 ** 31:
                raise ModelRefused("online video requires a whole-number seed")
            parameters["seed"] = seed
        started = time.monotonic()
        deadline = started + max(1.0, float(self.options.get("timeout_s", 600)))
        # The teacher's Stop (set by classroom_requests.run_request). Until a code review caught it, a
        # stopped online clip kept polling to the end and held the class's clip slot, refusing the next one.
        stopped = cancelled_request.get() or (lambda: False)
        if stopped():
            raise ModelCancelled("the online clip was stopped")
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        body = {"model": self.model, "parameters": parameters,
                "input": {"prompt": instruction, "media": [{"type": "first_frame", "url": image}]}}
        try:
            made = self._client.post(self.base_url + SUBMIT, json=body,
                                     headers={**headers, "X-DashScope-Async": "enable"})
            if made.status_code in (429, 500, 502, 503, 504):
                raise ModelUnavailable("DashScope is busy or unavailable")
            task = made.json().get("output", {}).get("task_id") if made.status_code == 200 else None
            if not task:
                raise ModelRefused("DashScope refused the clip")
            while True:
                if time.monotonic() > deadline:
                    raise ModelUnavailable("the online clip did not finish in time")
                self._sleep(POLL_S)
                if stopped():   # checked after the wait, so a Stop pressed during it asks nothing more
                    raise ModelCancelled("the online clip was stopped")
                asked = self._client.get(f"{self.base_url}/api/v1/tasks/{task}", headers=headers)
                output = asked.json().get("output", {})
                status = output.get("task_status")
                if status == "SUCCEEDED":
                    break
                if status in ("FAILED", "CANCELED", "UNKNOWN"):
                    raise ModelRefused("DashScope did not make the clip")
            if stopped():
                raise ModelCancelled("the online clip was stopped")
            raw = self._fetch(output.get("video_url"))
        except (httpx.RequestError, ValueError) as error:
            raise ModelUnavailable("DashScope did not answer") from error
        return MediaResult(urls=[], content=plain(raw), latency_s=time.monotonic() - started,
                           provider="dashscopevideo", model=self.model)

    def _fetch(self, url):
        link = urlsplit(url or "")
        # Only Alibaba's own storage, and never with the key: a link is not a place to send credentials.
        host = link.hostname or ""
        if link.scheme != "https" or link.username or link.password or not host.endswith(".aliyuncs.com"):
            raise ModelRefused("unexpected online clip host")
        data = bytearray()
        with self._client.stream("GET", url) as response:   # no headers: the key stays with DashScope
            if response.status_code != 200:
                raise ModelUnavailable("the online clip could not be fetched")
            for chunk in response.iter_bytes(65536):
                if len(data) + len(chunk) > MAX_DOWNLOAD_BYTES:
                    raise ModelRefused("online clip exceeds the byte budget")
                data.extend(chunk)
        return bytes(data)


def plain(raw: bytes) -> bytes:
    """One picture track, no sound, at most 10 s, small: what the studio's clip checks accept."""
    if not shutil.which("ffmpeg"):
        raise ModelUnavailable("video tools are unavailable")
    with tempfile.TemporaryDirectory(prefix="studio-online-clip-") as folder:
        source, made = Path(folder) / "online.mp4", Path(folder) / "plain.mp4"
        source.write_bytes(raw)
        try:
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(source), "-t", "10", "-an",
                            "-c:v", "libx264", "-crf", "26", "-preset", "veryfast", "-pix_fmt", "yuv420p",
                            "-movflags", "+faststart", str(made)],
                           check=True, timeout=120, capture_output=True)
            data = made.read_bytes()
        except (OSError, subprocess.SubprocessError):
            raise ModelRefused("the online clip could not be re-encoded") from None
    if not data or len(data) > MAX_VIDEO_BYTES:
        raise ModelRefused("the online clip is empty or too large")
    return data
