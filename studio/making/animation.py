"""Bounded action videos: the one thing painting-to-animation makes.

The FLUX still pose it could make instead was retired (operator: Wan 2.2 makes
the real animation). Keyframe survives as the shape of one decoded frame, which is what the
output screening reads; old still pictures in the Portfolio are stored data and still show.

Keep vendor URLs and prediction payloads out of the classroom and its ledger.
Embedded media is persisted with the course after output screening.
"""

from __future__ import annotations

import base64
import io
import json
import subprocess
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from PIL import Image

from studio.core.errors import ModelError, ModelUnavailable
from studio.providers.media import MediaResult, MediaSlot

# The stronger wording (operator). The earlier one named "human hands" in a list and
# still got two hands holding brushes on the corgi; this one says nobody is painting and nothing enters
# the frame, and made no hands in six test clips (docs/measured/clip-hands-and-check.md).
VIDEO_PROMPT = ("This is a finished child's painting and it is complete: nobody is painting or drawing it. Animate only "
                "the painted figures inside it, with a fixed camera. The painting fills the whole frame for the whole "
                "clip and nothing enters it from outside: absolutely no human hands, fingers, arms, paintbrushes, "
                "pencils, crayons or people. Keep the original rough brushstrokes, colours, characters and composition; "
                "no new characters, no photorealism, no cartoon restyling. Action request: ")
# Names nothing that might not be in the painting (operator). It used to ask for "one foreground
# animal", and on a painting of a house by a canal, which has none, Wan put dark shapes reaching in
# from the bottom of the frame instead: shown in an overnight run, scored 2 of 5 by the likeness judge, and found by
# the clip check on all three tries the next morning (docs/measured/overnight-2d-to-3d.md).
VIDEO_DEFAULT_ACTION = "Whatever the child painted stirs a little where it stands, and nothing else changes."
MAX_DOWNLOAD = 12 * 1024 * 1024
MAX_PIXELS = 4_500_000
MAX_EDGE = 1280
# Each look at a made clip. On the Spark every ffprobe and ffmpeg is a fresh container (deploy/spark/bin): 0.28 s
# idle, past 15 and 20 s on a busy night, and a clip that fails its look is thrown away after minutes of making.
TOOL_SECONDS = 120


@dataclass(frozen=True)
class Keyframe:
    image: str
    width: int
    height: int

    def as_dict(self) -> dict:
        return {"kind": "keyframe", "image": self.image, "width": self.width, "height": self.height}


def download(result: MediaResult, *, client: httpx.Client | None = None) -> bytes:
    if result.content:
        if len(result.content) > MAX_DOWNLOAD:
            raise ValueError("generated image too large")
        return result.content
    if len(result.urls) != 1:
        raise ValueError("expected one generated image")
    url = urlsplit(result.urls[0])
    host = url.hostname or ""
    if (url.scheme != "https" or url.username or url.password or url.port not in (None, 443)
            or not (host == "replicate.delivery" or host.endswith(".replicate.delivery"))):
        raise ValueError("unexpected generated image host")
    # Never reuse the API client: its credentials must not reach a media host.
    owned = client is None
    client = client or httpx.Client(timeout=30, follow_redirects=False)
    try:
        with client.stream("GET", result.urls[0]) as response:
            if response.is_redirect:
                raise ValueError("unexpected image redirect")
            response.raise_for_status()
            data = bytearray()
            for chunk in response.iter_bytes(chunk_size=65536):
                data.extend(chunk)
                if len(data) > MAX_DOWNLOAD:
                    raise ValueError("generated image too large")
            return bytes(data)
    finally:
        if owned:
            client.close()


def normalize(data: bytes) -> Keyframe:
    with Image.open(io.BytesIO(data)) as opened:
        if opened.format not in ("PNG", "JPEG", "WEBP") or opened.width * opened.height > MAX_PIXELS:
            raise ValueError("unexpected generated image format or size")
        if getattr(opened, "n_frames", 1) != 1:
            raise ValueError("expected a still keyframe")
        image = opened.convert("RGB")
        image.thumbnail((MAX_EDGE, MAX_EDGE), Image.Resampling.LANCZOS)
        image.info.clear()
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
    return Keyframe("data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode(),
                    image.width, image.height)


def generate(image: str, child_said: str, editor: MediaSlot | None, seed: int | None = None,
             clip_maker: str | None = None) -> Video:
    if editor is None or editor.task != "to_video":
        raise ModelUnavailable("video.animation is unavailable")
    return generate_video(image, child_said, editor, seed, clip_maker)


@dataclass(frozen=True)
class Video:
    video_url: str
    screen_images: tuple[str, ...]

    @property
    def image(self):
        return self.screen_images[0]

    def as_dict(self):
        return {"kind": "video", "video_url": self.video_url}


def normalize_video(data: bytes) -> Video:
    """Bound the clip and decode five frames for output safety screening."""
    with tempfile.TemporaryDirectory(prefix="studio-video-") as folder:
        path = Path(folder) / "clip.mp4"
        path.write_bytes(data)
        try:
            info = json.loads(subprocess.check_output([
                "ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)
            ], timeout=TOOL_SECONDS, stderr=subprocess.DEVNULL))
            streams = info["streams"]
            duration = float(info["format"]["duration"])
            if (len(streams) != 1 or streams[0].get("codec_name") != "h264"
                    or not 0 < duration <= 10
                    or not 0 < streams[0].get("width", 0) * streams[0].get("height", 0) <= MAX_PIXELS):
                raise ValueError("invalid generated video limits")
            frames = []
            for i in range(5):
                raw = subprocess.check_output([
                    "ffmpeg", "-v", "error", "-ss", str(max(0, duration - .08) * i / 4),
                    "-i", str(path), "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"
                ], timeout=TOOL_SECONDS, stderr=subprocess.DEVNULL)
                frames.append(normalize(raw).image)
        except (OSError, subprocess.SubprocessError, KeyError, TypeError, json.JSONDecodeError):
            raise ValueError("generated video could not be verified") from None
    return Video("data:video/mp4;base64," + base64.b64encode(data).decode(), tuple(frames))


def generate_video(image: str, child_said: str, editor: MediaSlot, seed: int | None = None,
                   clip_maker: str | None = None) -> Video:
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise ModelUnavailable("video verification tools are unavailable")
    prompt = VIDEO_PROMPT + json.dumps(child_said[:600] or VIDEO_DEFAULT_ACTION, ensure_ascii=False)
    try:
        return normalize_video(download(editor.to_video(image=image, instruction=prompt, seed=seed, clip_maker=clip_maker)))
    except (ModelError, httpx.HTTPError):
        raise ModelUnavailable("video generation or download failed; no automatic resubmission") from None
