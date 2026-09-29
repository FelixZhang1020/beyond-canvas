"""Mesh boundary and classroom routing; model quality is measured separately."""
import json

import httpx
import pytest

from studio.making import mesh, sketch
from studio.core.errors import ModelRefused, ModelUnavailable
from studio.providers.localmesh import LocalMeshClient
from studio.providers.media import MediaResult, MediaSlot
from tests.making.test_sketch import classroom, run


def tetrahedron():
    return {"positions": [-1,0,-1, 1,0,-1, 0,0,1, 0,2,0],
            "normals": [0,1,0] * 4, "indices": [0,1,2, 0,3,1, 1,3,2, 2,3,0]}


def test_surface_boundary_uses_measured_extents_and_drops_model_prose():
    data = tetrahedron() | {"size": [99,99,99], "texture": "baked shadows", "name": "private inscription"}
    scene = mesh.scene(json.dumps({"mesh": data}).encode(), .67)
    assert scene["mesh"]["size"] == [2,2,2]
    assert scene["method"] == "single-image-mesh"
    assert "private" not in json.dumps(scene) and "texture" not in json.dumps(scene)


@pytest.mark.parametrize("mutate", [
    lambda m: m["positions"].__setitem__(0, float("nan")),
    lambda m: m["positions"].__setitem__(1, -1),
    lambda m: m["positions"].__setitem__(0, True),
    lambda m: m["normals"].__setitem__(1, 0),
    lambda m: m["indices"].__setitem__(0, 4),
    lambda m: m["indices"].__setitem__(0, True),
    lambda m: m["indices"].__setitem__(0, 1),
    lambda m: m.__setitem__("indices", m["indices"] * (mesh.MAX_FACES // 4 + 1)),
    lambda m: m.__setitem__("positions", [0,1,0] * (mesh.MAX_VERTICES + 1)),
])
def test_bad_surfaces_fail_before_browser_allocation(mutate):
    data = tetrahedron()
    mesh.validate(data)  # Positive control for each mutation.
    mutate(data)
    with pytest.raises(ValueError):
        mesh.validate(data)


@pytest.mark.parametrize("url", ["https://example.com", "http://192.168.1.2", "http://localhost@evil.test", "file:///tmp/x", "http://localhost/path"])
def test_local_mesh_cannot_upload_drawings_to_a_remote_endpoint(url):
    with pytest.raises(ValueError, match="loopback"):
        LocalMeshClient("test", {"base_url": url})


def test_local_client_maps_one_embedded_image_and_refuses_oversized_or_redirected_results(monkeypatch):
    seen = []
    def endpoint(req):
        seen.append(json.loads(req.content))
        return httpx.Response(200, json={"mesh": tetrahedron()})
    client = LocalMeshClient("test", client=httpx.Client(transport=httpx.MockTransport(endpoint)))
    result = client.make({"image": "data:image/png;base64,AA==", "unbounded_steps": 9999})
    assert seen == [{"model": "test", "image": "data:image/png;base64,AA=="}]
    assert not result.urls and result.content
    with pytest.raises(ModelRefused):
        client.make({"image": "https://example.test/drawing.png"})
    monkeypatch.setattr("studio.providers.localmesh.MAX_BYTES", 100)
    with pytest.raises(ModelRefused, match="byte budget"):
        client.make({"image": "data:image/png;base64,AA=="})
    for status, error in [(302, ModelRefused), (429, ModelUnavailable), (503, ModelUnavailable)]:
        client = LocalMeshClient("test", client=httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(status))))
        with pytest.raises(error):
            client.make({"image": "data:image/png;base64,AA=="})


class MeshClient:
    def __init__(self):
        self.calls = []

    def make(self, inputs):
        self.calls.append(inputs)
        return MediaResult(urls=[], content=json.dumps({"mesh": tetrahedron()}).encode())


FRUIT = [{"kind": "apple", "bbox": [170,316,545,865]},
         {"kind": "pear", "bbox": [527,52,820,765]}]


def test_fruit_study_reaches_image_model_without_template_parts_and_is_cached(tmp_path):
    room, sid, did, writer, screen = classroom(tmp_path, [json.dumps(FRUIT)])
    client = MeshClient()
    room.portrait = MediaSlot(client, "to_mesh", {}, {})
    try:
        first, second = run(room, sid, did), run(room, sid, did)
        output = lambda events: next(d["outputs"]["scene"] for event,d in events if event == "done")
        scene = output(first)
        assert scene == output(second)
        assert scene["method"] == "single-image-mesh" and scene["subject"] == "fruit"
        assert "objects" not in scene  # No sphere/lathe substitution.
        assert scene["source_aspect"] == 1.5
        assert len(client.calls) == len(writer.calls) == len(screen.calls) == 1
        assert client.calls[0]["subject"] == "fruit"
        assert client.calls[0]["image"].startswith("data:image/")
        assert room.ledger_lines(sid)[-1]["tokens"] == 0
    finally:
        room.close()


@pytest.mark.parametrize("repaired", [True, False])
def test_incomplete_json_gets_one_recheck_before_any_mesh_job(tmp_path, repaired):
    incomplete = '{"objects":' + json.dumps(FRUIT)
    room,sid,did,writer,_ = classroom(tmp_path,[incomplete,json.dumps(FRUIT) if repaired else incomplete])
    client = MeshClient()
    room.portrait = MediaSlot(client,"to_mesh",{},{})
    try:
        events = run(room,sid,did)
        assert len(writer.calls) == 2
        assert len(client.calls) == int(repaired)
        assert any("outputs" in d for _,d in events) is repaired
        if not repaired:
            assert any(d.get("reason_code") == "invalid_scene" for _,d in events)
        assert room.ledger_lines(sid)[-1]["tokens"] == 300
    finally:
        room.close()


@pytest.mark.parametrize("reply", [json.dumps(FRUIT), '{"subject":"head"}'])
def test_generation_refusal_has_no_template_fallback_or_retry(tmp_path, reply):
    room, sid, did, writer, _ = classroom(tmp_path, [reply])
    class Refused(MeshClient):
        def make(self, inputs):
            self.calls.append(inputs)
            raise ModelRefused("bad surface")
    client = Refused()
    room.portrait = MediaSlot(client, "to_mesh", {}, {})
    try:
        events = run(room, sid, did)
        assert any(d.get("reason_code") == "invalid_scene" for _,d in events)
        assert not any("outputs" in d for _,d in events)
        assert len(client.calls) == len(writer.calls) == 1
    finally:
        room.close()


@pytest.mark.parametrize("configured", [False, True])
def test_missing_or_busy_fruit_worker_has_its_own_message(tmp_path, configured):
    room, sid, did, writer, _ = classroom(tmp_path, [json.dumps(FRUIT)])
    class Busy(MeshClient):
        def make(self, inputs):
            self.calls.append(inputs)
            raise ModelUnavailable("busy")
    client = Busy()
    if configured:
        room.portrait = MediaSlot(client, "to_mesh", {}, {})
    try:
        events = run(room, sid, did)
        assert any(d.get("reason_code") == "fruit_mesh_unavailable" for _,d in events)
        assert not any("outputs" in d for _,d in events)
        assert len(writer.calls) == 1 and len(client.calls) == int(configured)
    finally:
        room.close()


@pytest.mark.parametrize("reply", [json.dumps(FRUIT), '{"subject":"head"}'])
def test_screening_refusal_prevents_any_mesh_inference(tmp_path, reply):
    room, sid, did, writer, screen = classroom(tmp_path, [reply])
    client = MeshClient()
    room.portrait = MediaSlot(client, "to_mesh", {}, {})
    screen.replies = ['{"verdict":"unsafe","reason":"unsafe","text_found":[]}'] * 2
    try:
        events = run(room, sid, did)
        assert any(d.get("reason_code") == "unsafe_image" for _,d in events)
        assert not client.calls and not writer.calls
    finally:
        room.close()


def test_fruit_routing_keeps_recognition_bounds_and_mixed_geometry_contract():
    assert sketch.parse_detections(json.dumps(FRUIT), 1.5, generative_fruit=True) == {"subject":"fruit"}
    for bad in ([{"kind":"banana", "bbox":[170,316,545,865]}], FRUIT*4,
                [{"kind":"apple", "bbox":[True,316,545,865]}],
                [{"kind":"apple", "bbox":[900,316,545,865]}]):
        with pytest.raises(ValueError):
            sketch.parse_detections(json.dumps(bad), 1.5, generative_fruit=True)
    from tests.making.test_still_life import DETECTIONS
    mixed = sketch.parse_detections(json.dumps(DETECTIONS), 1.5, generative_fruit=True)
    assert "subject" not in mixed and [o["kind"] for o in mixed["objects"]] == ["sphere","box","pear"]


def test_local_client_forwards_only_a_bounded_surface_subject():
    seen = []
    def endpoint(req):
        seen.append(json.loads(req.content))
        return httpx.Response(200, json={"mesh": tetrahedron()})
    client = LocalMeshClient("triposg", client=httpx.Client(transport=httpx.MockTransport(endpoint)))
    image = "data:image/png;base64,AA=="
    MediaSlot(client,"to_mesh",{},{}).to_mesh(image=image,subject="fruit")
    assert seen == [{"model":"triposg","image":image,"subject":"fruit"}]
    with pytest.raises(ModelRefused):
        client.make({"image":image,"subject":"unbounded"})
    assert len(seen) == 1


def test_head_routes_to_mesh_once_and_cached_relighting_spends_no_inference(tmp_path):
    room, sid, did, writer, screen = classroom(tmp_path, ['{"subject":"head"}'])
    client = MeshClient()
    room.portrait = MediaSlot(client, "to_mesh", {}, {})
    try:
        first, second = run(room, sid, did), run(room, sid, did)
        scene = lambda events: next(d["outputs"]["scene"] for event,d in events if event == "done")
        assert scene(first) == scene(second)
        assert scene(first)["method"] == "single-image-mesh"
        assert len(client.calls) == len(writer.calls) == len(screen.calls) == 1
    finally:
        room.close()


def test_blocked_drawing_never_reaches_head_model(tmp_path):
    room, sid, did, writer, screen = classroom(tmp_path, ['{"subject":"head"}'])
    client = MeshClient()
    room.portrait = MediaSlot(client, "to_mesh", {}, {})
    screen.replies = ['{"verdict":"unsafe","reason":"unsafe","text_found":[]}'] * 2
    try:
        events = run(room, sid, did)
        assert any(d.get("reason_code") == "unsafe_image" for _,d in events)
        assert not client.calls and not writer.calls
    finally:
        room.close()


def test_missing_head_worker_is_distinguished_from_unsupported_geometry(tmp_path):
    room, sid, did, writer, _ = classroom(tmp_path, ['{"subject":"head"}'])
    try:
        events = run(room, sid, did)
        assert any(d.get("reason_code") == "portrait_unavailable" for _,d in events)
        assert not any("outputs" in d for _,d in events)
        assert len(writer.calls) == 1
    finally:
        room.close()


def test_head_and_solids_are_not_silently_collapsed_into_one_bust():
    assert sketch.parse_detections('{"subject":"head"}', .67) == {"subject": "head"}
    with pytest.raises(sketch.UnsupportedSketch):
        sketch.parse_detections('{"subject":"head","objects":[{"kind":"sphere"}]}', .67)


def test_worker_accepts_bounded_images_rejects_photos_too_large_to_decode():
    import base64
    import io
    from PIL import Image
    from studio.portrait_runtime.server import decode_image
    def uri(size):
        output = io.BytesIO()
        Image.new("RGB", size).save(output, format="PNG")
        return "data:image/png;base64," + base64.b64encode(output.getvalue()).decode()
    assert decode_image(uri((300, 450))).size == (300, 450)
    for bad in ("https://example.test/head.png", "data:image/png;base64,!", uri((4096, 64)), uri((16, 16))):
        with pytest.raises(ValueError):
            decode_image(bad)


def test_worker_http_is_single_job_and_not_callable_from_a_web_origin():
    import base64
    import io
    import threading
    from PIL import Image
    from studio.portrait_runtime.server import Server
    started, release = threading.Event(), threading.Event()
    class Engine:
        def make(self, image, *, subject="head"):
            assert subject == "fruit"
            started.set()
            assert release.wait(3)
            return {"mesh": tetrahedron()}
    server = Server(0, Engine())
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    image = io.BytesIO()
    Image.new("RGB", (64, 64)).save(image, format="PNG")
    body = {"model": "triposg", "subject": "fruit", "image": "data:image/png;base64," + base64.b64encode(image.getvalue()).decode()}
    url = f"http://127.0.0.1:{server.server_address[1]}"
    results = []
    def first_job():
        with httpx.Client(trust_env=False, timeout=5) as client:
            results.append(client.post(url + "/v1/mesh", json=body).status_code)
    job = threading.Thread(target=first_job)
    try:
        with httpx.Client(trust_env=False) as client:
            assert client.get(url + "/v1/models").json()["data"][0]["id"] == "triposg"
            assert client.post(url + "/v1/mesh", json=body, headers={"Origin": "https://example.test"}).status_code == 403
            assert not started.is_set()
            assert client.post(url + "/v1/mesh", json={**body, "subject":"arbitrary"}).status_code == 422
            assert not started.is_set()
            job.start()
            assert started.wait(2)
            assert client.post(url + "/v1/mesh", json=body).status_code == 503
            assert client.get(url + "/v1/models").json()["busy"] is True
            release.set()
            job.join(3)
            assert results == [200]
    finally:
        release.set()
        if job.ident is not None:
            job.join(3)
        server.shutdown()
        server.server_close()
