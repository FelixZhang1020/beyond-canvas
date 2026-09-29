import importlib.util
from pathlib import Path

import httpx
import pytest

from studio.core.errors import ModelRefused, ModelUnavailable
from studio.providers import build_media_slot
from studio.providers.localvideo import LocalVideoClient
from studio.core.slots import load_profile

ROOT = Path(__file__).resolve().parents[2]
MEDIA_SERVER = ROOT / "deploy" / "gpu-media" / "extra" / "media_server.py"
WORKER = ROOT / "deploy" / "spark" / "wan_i2v_worker.py"


@pytest.mark.parametrize("url", ["https://127.0.0.1:7260", "http://example.test:7260", "http://u:p@127.0.0.1:7260"])
def test_worker_must_be_plain_loopback(url):
    with pytest.raises(ValueError, match="loopback"):
        LocalVideoClient("wan", {"base_url": url})


def test_a_new_start_is_passed_on_and_a_malformed_one_never_leaves():
    """A new try after a held-back clip asks the worker for another start."""
    sent = []

    def endpoint(request):
        sent.append(__import__("json").loads(request.content))
        return httpx.Response(200, content=b"movie", headers={"Content-Type": "video/mp4"})

    client = LocalVideoClient("wan", client=httpx.Client(transport=httpx.MockTransport(endpoint)))
    client.make({"image": "data:image/png;base64,eA==", "instruction": "move", "seed": 43})
    assert sent[-1]["seed"] == 43
    for bad in (True, -1, 2 ** 31, 4.5, "43"):
        with pytest.raises(ModelRefused):
            client.make({"image": "data:image/png;base64,eA==", "instruction": "move", "seed": bad})
    assert len(sent) == 1


def test_video_bytes_are_returned_without_a_remote_url():
    def endpoint(request):
        body = __import__("json").loads(request.content)
        assert request.url.path == "/v1/video"
        assert body == {"model": "wan", "image": "data:image/png;base64,eA==", "instruction": "move"}
        return httpx.Response(200, content=b"movie", headers={"Content-Type": "video/mp4"})

    client = LocalVideoClient("wan", client=httpx.Client(transport=httpx.MockTransport(endpoint)))
    result = client.make({"image": "data:image/png;base64,eA==", "instruction": "move"})
    assert result.content == b"movie"
    assert result.provider == "localvideo"


@pytest.mark.parametrize("status", [409, 429, 500, 503])
def test_busy_worker_is_unavailable(status):
    client = LocalVideoClient("wan", client=httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(status))))
    with pytest.raises(ModelUnavailable):
        client.make({"image": "data:image/png;base64,eA==", "instruction": "move"})


def test_non_video_success_is_refused():
    client = LocalVideoClient("wan", client=httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"oops": True}))))
    with pytest.raises(ModelRefused):
        client.make({"image": "data:image/png;base64,eA==", "instruction": "move"})


@pytest.mark.parametrize("asked,waited", [(1500, 1500), (5000, 1500), (600, 600)])
def test_a_clip_waits_as_long_as_asked_up_to_the_services_own_cap(monkeypatch, asked, waited):
    """A 5 s clip takes ~18 min on the Spark, and one queued behind a 3D
    job longer; the client may wait up to the video service's own 1500 s job deadline, never past it."""
    seen = {}

    def stream(client, base_url, path, body, timeout, cancelled=None):
        seen["timeout"] = timeout
        raise httpx.ConnectError("stop here")

    monkeypatch.setattr("studio.providers.localvideo.stream_job", stream)
    client = LocalVideoClient("wan", {"timeout_s": asked})
    with pytest.raises(ModelUnavailable):
        client.make({"image": "data:image/png;base64,eA==", "instruction": "move"})
    assert seen["timeout"] == waited


def test_stepfun_first_gives_a_clip_the_services_whole_deadline():
    """The studio waits exactly as long as the Spark's clip service lets a job run, no less and no more."""
    spec = importlib.util.spec_from_file_location("media_server", MEDIA_SERVER)
    media_server = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(media_server)
    assert load_profile("stepfun")["video.animation"].options["timeout_s"] == media_server.JOB_DEADLINE_S == 1500


def test_a_class_clip_is_five_seconds():
    """Operator, after the length trial: 81 pictures, ~5 s at 16 a second. The class sends no length,
    so the worker's own default is the class's length."""
    assert "count = request.get('frames', 81)" in WORKER.read_text()


def test_local_profile_routes_animation_to_the_4090_worker():
    config = load_profile("local")["video.animation"]
    slot = build_media_slot(config)
    assert config.provider == "localvideo"
    assert config.model == "wan2.2-ti2v-5b"
    assert slot.task == "to_video"
