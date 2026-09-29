import base64
import io
import json
import threading

import httpx
import pytest
from PIL import Image

from deploy.trellis2.trellis_bridge import Server
from studio.core.errors import ModelRefused
from studio.providers.hybridmesh import HybridMeshClient
from studio.providers.media import MediaResult
from studio.core.slots import load_profile


class Recorder:
    def __init__(self, model):
        self.model, self.calls = model, []

    def make(self, inputs):
        self.calls.append(inputs)
        return MediaResult([], content=b"model", model=self.model)


def image_uri():
    output = io.BytesIO()
    Image.new("RGB", (128, 128), "white").save(output, format="PNG")
    return "data:image/png;base64," + base64.b64encode(output.getvalue()).decode()


def test_hybrid_routes_trellis_locally_and_pixal_only_when_selected():
    local, cloud = Recorder("trellis2"), Recorder("pixal")
    client = HybridMeshClient("trellis2", local=local, cloud=cloud)
    image = image_uri()
    assert client.make({"image": image}).model == "trellis2"
    assert client.make({"image": image, "model_choice": "pixal"}).model == "pixal"
    assert len(local.calls) == len(cloud.calls) == 1
    with pytest.raises(ModelRefused):
        client.make({"image": image, "model_choice": "unknown"})


def test_multi_model_profiles_make_their_3d_on_the_gpu_machine():
    """`stepfun` makes its 3D on the 4090 too. `api` used to
    buy it from hosted services instead; that deployment is archived."""
    for profile in ("cloud", "local"):
        config = load_profile(profile)["mesh.portrait"]
        assert config.provider == "hybridmesh"
        assert config.options["base_url"] == "http://127.0.0.1:7240"
    assert load_profile("stepfun")["mesh.portrait"].provider == "localmesh"


def test_bridge_is_private_single_job_and_returns_bounded_glb(tmp_path):
    started, release = threading.Event(), threading.Event()
    glb = b"glTF" + __import__("struct").pack("<II", 2, 20) + b"\0" * 8

    class Engine:
        def ready(self):
            return True

        def generate(self, image):
            assert image.startswith(b"\x89PNG")
            started.set()
            assert release.wait(3)
            return glb

    server = Server(0, Engine(), tmp_path / "gpu.lock")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_address[1]}"
    body = {"model": "trellis2", "image": image_uri()}
    statuses = []

    def first_job():
        with httpx.Client(timeout=5, trust_env=False) as client:
            response = client.post(url + "/v1/mesh", json=body)
            statuses.append((response.status_code, response.content))

    job = threading.Thread(target=first_job)
    try:
        with httpx.Client(trust_env=False) as client:
            assert client.get(url + "/v1/models").json()["data"][0]["id"] == "trellis2"
            assert client.post(url + "/v1/mesh", json=body, headers={"Origin": "https://example.test"}).status_code == 403
            job.start()
            assert started.wait(2)
            assert client.post(url + "/v1/mesh", json=body).status_code == 503
            assert client.get(url + "/v1/models").json()["busy"] is True
            release.set()
            job.join(3)
            assert statuses == [(200, glb)]
    finally:
        release.set()
        if job.ident is not None:
            job.join(3)
        server.shutdown()
        server.server_close()
